from datetime import datetime

import pytest
from sqlalchemy import select, text

from app.models import StockMovement


@pytest.fixture
def stock_product(client):
    category = client.post("/categorias", json={"nome": "Papelaria"}).json()
    supplier = client.post("/fornecedores", json={
        "nome": "Fornecedor", "cnpj": "12ABC34501DE35",
        "email": "contato@example.com", "telefone": "12345678",
    }).json()
    response = client.post("/produtos", json={
        "nome": "Caneta", "sku": "CANETA-001", "preco_custo": "2.50",
        "preco_venda": "4.90", "estoque_minimo": 5,
        "categoria_id": category["id"], "fornecedor_id": supplier["id"],
    })
    assert response.status_code == 201
    return response.json()


def test_entries_and_exits_update_balance_and_history(client, stock_product, migrated_connection):
    connection, _ = migrated_connection
    payload = {"produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 8}
    response = client.post("/movimentacoes", json=payload)
    assert response.status_code == 201
    movement = response.json()
    assert movement == {
        **payload, "id": movement["id"], "data": movement["data"],
        "fornecedor_id": stock_product["fornecedor_id"],
    }
    assert datetime.fromisoformat(movement["data"]).utcoffset() is not None
    path = f'/produtos/{stock_product["id"]}'
    assert client.get(path).json()["quantidade_em_estoque"] == 8
    for quantity, expected_balance in [(3, 5), (5, 0)]:
        response = client.post("/movimentacoes", json={**payload, "tipo": "saida", "quantidade": quantity})
        assert response.status_code == 201
        assert client.get(path).json()["quantidade_em_estoque"] == expected_balance
    rows = connection.execute(select(StockMovement.tipo, StockMovement.quantidade).order_by(StockMovement.id)).all()
    assert rows == [("entrada", 8), ("saida", 3), ("saida", 5)]
    assert client.delete(path).status_code == 409


def test_insufficient_stock_has_no_side_effects(client, stock_product, migrated_connection):
    connection, _ = migrated_connection
    payload = {"produto_id": stock_product["id"], "tipo": "saida", "quantidade": 1}
    response = client.post("/movimentacoes", json=payload)
    assert response.status_code == 409
    assert response.json() == {"detail": "Estoque insuficiente para essa saida."}
    assert connection.execute(select(StockMovement.id)).all() == []
    assert client.get(f'/produtos/{stock_product["id"]}').json() == stock_product
    assert client.post("/movimentacoes", json={**payload, "tipo": "entrada"}).status_code == 201


def test_stock_limit_is_checked_before_writing(client, stock_product, migrated_connection):
    connection, _ = migrated_connection
    payload = {"produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 2147483647}
    assert client.post("/movimentacoes", json=payload).status_code == 201
    response = client.post("/movimentacoes", json={**payload, "quantidade": 1})
    assert response.status_code == 409
    assert response.json() == {"detail": "Limite de quantidade em estoque excedido."}
    assert client.get(f'/produtos/{stock_product["id"]}').json()["quantidade_em_estoque"] == 2147483647
    assert len(connection.execute(select(StockMovement.id)).all()) == 1


@pytest.mark.parametrize("changes", [
    {"quantidade": 0}, {"quantidade": -1}, {"quantidade": 1.5},
    {"quantidade": True}, {"quantidade": "5"}, {"quantidade": 2147483648},
    {"tipo": "ajuste"}, {"produto_id": 0}, {"produto_id": True},
    {"fornecedor_id": 1}, {"data": "2026-01-01T00:00:00Z"}, {"id": 10},
])
def test_invalid_movement_is_rejected(client, stock_product, migrated_connection, changes):
    connection, _ = migrated_connection
    payload = {"produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 5}
    assert client.post("/movimentacoes", json={**payload, **changes}).status_code == 422
    assert connection.execute(select(StockMovement.id)).all() == []
    assert client.get(f'/produtos/{stock_product["id"]}').json() == stock_product


def test_missing_product_and_required_fields(client, migrated_connection):
    connection, _ = migrated_connection
    assert client.post("/movimentacoes", json={}).status_code == 422
    response = client.post("/movimentacoes", json={"produto_id": 2147483647, "tipo": "entrada", "quantidade": 1})
    assert response.status_code == 404
    assert response.json() == {"detail": "Produto nao encontrado."}
    assert connection.execute(select(StockMovement.id)).all() == []


def test_history_failure_rolls_back_balance(client, stock_product, migrated_connection, caplog):
    connection, _ = migrated_connection
    # Falha real no INSERT, depois de executar o UPDATE do saldo, no schema isolado.
    connection.execute(text("""
        CREATE FUNCTION reject_test_movement() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (SELECT quantidade_em_estoque FROM produtos WHERE id = NEW.produto_id) <> 5 THEN
                RAISE EXCEPTION 'saldo ainda nao atualizado';
            END IF;
            RAISE EXCEPTION 'falha de teste no historico' USING ERRCODE = '23514';
        END;
        $$
    """))
    connection.execute(text("""
        CREATE TRIGGER reject_test_movement BEFORE INSERT ON movimentacoes
        FOR EACH ROW EXECUTE FUNCTION reject_test_movement()
    """))
    payload = {"produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 5}
    response = client.post("/movimentacoes", json=payload)
    assert response.status_code == 500
    # Somente o ramo que observou saldo 5 gera IntegrityError (SQLSTATE 23514).
    assert "IntegrityError" in caplog.text
    assert response.json() == {"detail": "Erro interno ao acessar o banco de dados."}
    assert client.get(f'/produtos/{stock_product["id"]}').json() == stock_product
    assert connection.execute(select(StockMovement.id)).all() == []
    connection.execute(text("DROP TRIGGER reject_test_movement ON movimentacoes"))
    assert client.post("/movimentacoes", json=payload).status_code == 201
