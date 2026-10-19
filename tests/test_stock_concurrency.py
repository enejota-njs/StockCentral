from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.database import database_url, engine, get_session
from app.main import app
from app.models import Product


@pytest.fixture
def concurrent_api():
    # Conexoes distintas precisam enxergar dados confirmados, sem a transacao
    # externa usada nos outros testes. Todo o teste fica neste schema descartavel.
    schema = f"test_concurrency_{uuid4().hex}"
    scoped_engine = create_engine(database_url, connect_args={
        "connect_timeout": 5,
        "application_name": schema,
        "options": f"-c search_path={schema} -c statement_timeout=15000",
    })
    previous_overrides = app.dependency_overrides.copy()
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

        def independent_session():
            with Session(scoped_engine) as session:
                yield session

        app.dependency_overrides[get_session] = independent_session
        with TestClient(app) as client:
            yield client, scoped_engine, schema
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        scoped_engine.dispose()
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True, if_exists=True))


def wait_for_two_blocked_requests(application_name):
    deadline = monotonic() + 8
    # AUTOCOMMIT renova a visao de pg_stat_activity a cada consulta.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as observer:
        while monotonic() < deadline:
            blocked = observer.scalar(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE application_name = :name AND wait_event_type = 'Lock'
            """), {"name": application_name})
            if blocked == 2:
                return
            sleep(0.02)
    pytest.fail("As duas requisicoes nao chegaram ao bloqueio dentro do prazo.")


@pytest.mark.parametrize("initial, operations, statuses, final_balance", [
    (1, [("saida", 1), ("saida", 1)], [201, 409], 0),
    (0, [("entrada", 2), ("entrada", 3)], [201, 201], 5),
    (10, [("entrada", 3), ("saida", 4)], [201, 201], 9),
])
def test_simultaneous_movements(concurrent_api, initial, operations, statuses, final_balance):
    client, scoped_engine, schema = concurrent_api
    category = client.post("/categorias", json={"nome": "Papelaria"}).json()
    supplier = client.post("/fornecedores", json={
        "nome": "Fornecedor", "cnpj": "12ABC34501DE35",
        "email": "contato@example.com", "telefone": "12345678",
    }).json()
    product_response = client.post("/produtos", json={
        "nome": "Caneta", "sku": "CANETA-001", "preco_custo": "2.50",
        "preco_venda": "4.90", "estoque_minimo": 5,
        "categoria_id": category["id"], "fornecedor_id": supplier["id"],
    })
    assert product_response.status_code == 201
    product_id = product_response.json()["id"]
    if initial:
        assert client.post("/movimentacoes", json={
            "produto_id": product_id, "tipo": "entrada", "quantidade": initial,
        }).status_code == 201

    with ThreadPoolExecutor(max_workers=2) as pool:
        with scoped_engine.begin() as blocker:
            blocker.execute(select(Product.id).where(Product.id == product_id).with_for_update())
            futures = [pool.submit(client.post, "/movimentacoes", json={
                "produto_id": product_id, "tipo": kind, "quantidade": quantity,
            }) for kind, quantity in operations]
            # Confirma a sobreposicao real antes de soltar o produto para as duas operacoes.
            wait_for_two_blocked_requests(schema)
        responses = [future.result(timeout=20) for future in futures]

    assert sorted(response.status_code for response in responses) == statuses
    assert client.get(f"/produtos/{product_id}").json()["quantidade_em_estoque"] == final_balance
    history = client.get("/movimentacoes", params={"produto_id": product_id}).json()
    assert len(history) == statuses.count(201) + bool(initial)
    calculated_balance = sum(row["quantidade"] if row["tipo"] == "entrada" else -row["quantidade"] for row in history)
    assert calculated_balance == final_balance
