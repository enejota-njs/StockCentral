from datetime import datetime
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def product_payload(client):
    category = client.post("/categorias", json={"nome": "Papelaria"}).json()
    supplier = client.post("/fornecedores", json={
        "nome": "Fornecedor", "cnpj": "12ABC34501DE35",
        "email": "contato@example.com", "telefone": "75999991234",
    }).json()
    return {
        "nome": "Caneta azul", "sku": "CANETA-001", "preco_custo": "2.50",
        "preco_venda": "4.90", "estoque_minimo": 5,
        "categoria_id": category["id"], "fornecedor_id": supplier["id"],
    }


def test_product_lifecycle(client, product_payload):
    assert client.get("/produtos").json() == []
    response = client.post("/produtos", json={
        **product_payload, "nome": "  Caneta azul  ", "sku": " caneta-001 ",
    })
    assert response.status_code == 201
    product = response.json()
    assert product == {
        **product_payload, "id": product["id"], "quantidade_em_estoque": 0,
        "data_cadastro": product["data_cadastro"],
    }
    assert datetime.fromisoformat(product["data_cadastro"]).utcoffset() is not None
    path = f'/produtos/{product["id"]}'
    assert client.get(path).json() == product
    assert client.get("/produtos").json() == [product]
    changed = {**product_payload, "nome": "Caneta preta", "sku": "CANETA-002",
               "preco_custo": "0.10", "preco_venda": "0.30", "estoque_minimo": 10}
    response = client.put(path, json=changed)
    assert response.status_code == 200
    assert response.json() == {**product, **changed}
    assert client.put(path, json=changed).status_code == 200
    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404
    assert client.get("/produtos").json() == []


def test_duplicate_sku_and_rejected_edit_are_atomic(client, product_payload):
    first = client.post("/produtos", json=product_payload).json()
    response = client.post("/produtos", json={**product_payload, "sku": " caneta-001 "})
    assert response.status_code == 409
    assert response.json() == {"detail": "Ja existe um produto com esse SKU."}
    second_payload = {**product_payload, "sku": "OUTRO"}
    second = client.post("/produtos", json=second_payload).json()
    path = f'/produtos/{second["id"]}'
    response = client.put(path, json={
        **second_payload, "sku": first["sku"], "nome": "Nao persistir", "preco_venda": "99.00",
    })
    assert response.status_code == 409
    assert client.get(path).json() == second
    assert client.put(path, json=second_payload).status_code == 200


@pytest.mark.parametrize("field, message", [
    ("categoria_id", "Categoria informada nao existe."),
    ("fornecedor_id", "Fornecedor informado nao existe."),
])
def test_missing_reference_rejects_create_and_update(client, product_payload, field, message):
    invalid = {**product_payload, field: 2147483647}
    response = client.post("/produtos", json=invalid)
    assert response.status_code == 422
    assert response.json() == {"detail": message}
    assert client.get("/produtos").json() == []
    product = client.post("/produtos", json=product_payload).json()
    path = f'/produtos/{product["id"]}'
    assert client.put(path, json={**invalid, "nome": "Nao persistir"}).status_code == 422
    assert client.get(path).json() == product


@pytest.mark.parametrize("changes", [
    {"nome": " \t\n"}, {"nome": "x" * 151}, {"nome": None},
    {"sku": ""}, {"sku": "x" * 65}, {"sku": "COM ESPACO"}, {"sku": "ÁBC"},
    {"sku": "-ABC"}, {"sku": 123}, {"estoque_minimo": -1},
    {"estoque_minimo": 1.5}, {"estoque_minimo": True}, {"estoque_minimo": 2147483648},
    {"categoria_id": 0}, {"categoria_id": True}, {"categoria_id": 1.5},
    {"fornecedor_id": -1}, {"fornecedor_id": 2147483648},
    {"quantidade_em_estoque": 10}, {"quantidade_em_estoque": 0},
    {"data_cadastro": "2026-01-01T00:00:00Z"}, {"id": 1},
])
def test_invalid_product_has_no_side_effects(client, product_payload, changes):
    assert client.post("/produtos", json={**product_payload, **changes}).status_code == 422
    assert client.get("/produtos").json() == []


@pytest.mark.parametrize("field", ["preco_custo", "preco_venda"])
@pytest.mark.parametrize("value", ["-0.01", "1.001", "10000000000.00", "NaN", "Infinity", None, True])
def test_invalid_prices(client, product_payload, field, value):
    assert client.post("/produtos", json={**product_payload, field: value}).status_code == 422
    assert client.get("/produtos").json() == []


@pytest.mark.parametrize("cost, sale", [("0.00", "0.00"), ("9999999999.99", "0.01")])
def test_price_boundaries_and_sale_below_cost(client, product_payload, cost, sale):
    response = client.post("/produtos", json={**product_payload, "preco_custo": cost, "preco_venda": sale})
    assert response.status_code == 201
    assert response.json()["preco_custo"] == cost
    assert response.json()["preco_venda"] == sale


def test_readonly_fields_and_invalid_put_preserve_existing_stock(client, product_payload, migrated_connection):
    product = client.post("/produtos", json=product_payload).json()
    connection, _ = migrated_connection
    # Simula um saldo existente; movimentacoes serao implementadas na proxima etapa.
    connection.execute(text("UPDATE produtos SET quantidade_em_estoque = 7 WHERE id = :id"), {"id": product["id"]})
    path = f'/produtos/{product["id"]}'
    product = client.get(path).json()
    for changes in [{"quantidade_em_estoque": 8}, {"id": 999},
                    {"data_cadastro": "2026-01-01T00:00:00Z"}, {"preco_custo": "-1"}]:
        assert client.put(path, json={**product_payload, **changes}).status_code == 422
        assert client.get(path).json() == product
    assert client.put(path, json={"nome": "Incompleto"}).status_code == 422
    response = client.put(path, json={**product_payload, "nome": "Nome novo"})
    assert response.status_code == 200
    assert response.json() == {**product, "nome": "Nome novo"}


@pytest.mark.parametrize("route, field", [("categorias", "categoria_id"), ("fornecedores", "fornecedor_id")])
def test_linked_parents_cannot_be_deleted(client, product_payload, route, field):
    product = client.post("/produtos", json=product_payload).json()
    path = f'/{route}/{product_payload[field]}'
    original = client.get(path).json()
    assert client.delete(path).status_code == 409
    assert client.get(path).json() == original
    assert client.get(f'/produtos/{product["id"]}').json() == product
    assert client.delete(f'/produtos/{product["id"]}').status_code == 204
    assert client.delete(path).status_code == 204


def test_reassign_product_releases_old_parents(client, product_payload):
    product = client.post("/produtos", json=product_payload).json()
    category = client.post("/categorias", json={"nome": "Outra"}).json()
    supplier = client.post("/fornecedores", json={
        "nome": "Outro", "cnpj": "11222333000181", "email": "outro@example.com", "telefone": "12345678",
    }).json()
    changed = {**product_payload, "categoria_id": category["id"], "fornecedor_id": supplier["id"]}
    assert client.put(f'/produtos/{product["id"]}', json=changed).status_code == 200
    assert client.delete(f'/categorias/{product_payload["categoria_id"]}').status_code == 204
    assert client.delete(f'/fornecedores/{product_payload["fornecedor_id"]}').status_code == 204
    assert client.delete(f'/categorias/{category["id"]}').status_code == 409
    assert client.delete(f'/fornecedores/{supplier["id"]}').status_code == 409


def test_filters_and_pagination(client, product_payload, migrated_connection):
    first = client.post("/produtos", json=product_payload).json()
    category = client.post("/categorias", json={"nome": "Outra"}).json()
    supplier = client.post("/fornecedores", json={
        "nome": "Outro", "cnpj": "11222333000181", "email": "outro@example.com", "telefone": "12345678",
    }).json()
    second = client.post("/produtos", json={**product_payload, "sku": "P2", "categoria_id": category["id"]}).json()
    third = client.post("/produtos", json={**product_payload, "sku": "P3", "fornecedor_id": supplier["id"]}).json()
    connection, _ = migrated_connection
    connection.execute(text("UPDATE produtos SET quantidade_em_estoque = 5 WHERE id = :id"), {"id": second["id"]})
    connection.execute(text("UPDATE produtos SET quantidade_em_estoque = 6 WHERE id = :id"), {"id": third["id"]})
    second["quantidade_em_estoque"] = 5
    third["quantidade_em_estoque"] = 6
    assert client.get("/produtos").json() == [first, second, third]
    assert client.get("/produtos?estoque_baixo=true").json() == [first, second]
    assert client.get("/produtos?estoque_baixo=false").json() == [third]
    assert client.get(f'/produtos?categoria_id={category["id"]}').json() == [second]
    assert client.get(f'/produtos?fornecedor_id={supplier["id"]}').json() == [third]
    query = f'/produtos?categoria_id={product_payload["categoria_id"]}&fornecedor_id={product_payload["fornecedor_id"]}&estoque_baixo=true'
    assert client.get(query).json() == [first]
    assert client.get("/produtos?estoque_baixo=true&offset=1&limit=1").json() == [second]
    assert client.get("/produtos?offset=99").json() == []
    assert client.get("/produtos?categoria_id=2147483647").json() == []
    for query in ["limit=0", "limit=101", "offset=-1", "categoria_id=0", "fornecedor_id=-1", "estoque_baixo=talvez"]:
        assert client.get(f"/produtos?{query}").status_code == 422


def test_missing_product_and_invalid_ids(client, product_payload):
    assert client.get("/produtos/999").status_code == 404
    assert client.put("/produtos/999", json=product_payload).status_code == 404
    assert client.delete("/produtos/999").status_code == 404
    for value in ["0", "-1", "abc", "2147483648"]:
        assert client.get(f"/produtos/{value}").status_code == 422


@pytest.mark.parametrize("column, value, constraint", [
    ("quantidade_em_estoque", -1, "ck_produtos_estoque_nao_negativo"),
    ("estoque_minimo", -1, "ck_produtos_estoque_minimo_nao_negativo"),
    ("preco_custo", Decimal("-0.01"), "ck_produtos_preco_custo_valido"),
    ("preco_venda", Decimal("NaN"), "ck_produtos_preco_venda_valido"),
    ("categoria_id", 2147483647, "fk_produtos_categoria_id_categorias"),
    ("fornecedor_id", 2147483647, "fk_produtos_fornecedor_id_fornecedores"),
])
def test_database_constraints(client, product_payload, migrated_connection, column, value, constraint):
    product = client.post("/produtos", json=product_payload).json()
    connection, _ = migrated_connection
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            # A coluna vem da lista fixa do teste; os valores usam parametros SQL.
            connection.execute(text(f"UPDATE produtos SET {column} = :value WHERE id = :id"),
                               {"value": value, "id": product["id"]})
    assert error.value.orig.diag.constraint_name == constraint
    assert client.get(f'/produtos/{product["id"]}').json() == product


def test_database_guarantees_unique_sku(client, product_payload, migrated_connection):
    first = client.post("/produtos", json=product_payload).json()
    second = client.post("/produtos", json={**product_payload, "sku": "OUTRO"}).json()
    connection, _ = migrated_connection
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            connection.execute(text("UPDATE produtos SET sku = :sku WHERE id = :id"),
                               {"sku": first["sku"], "id": second["id"]})
    assert error.value.orig.diag.constraint_name == "uq_produtos_sku"


def test_product_migration_preserves_existing_parents(client, product_payload, migrated_connection):
    connection, config = migrated_connection
    command.downgrade(config, "0002")
    assert "produtos" not in inspect(connection).get_table_names()
    assert connection.scalar(text("SELECT count(*) FROM categorias")) == 1
    assert connection.scalar(text("SELECT count(*) FROM fornecedores")) == 1
    command.upgrade(config, "head")
    assert "produtos" in inspect(connection).get_table_names()
    assert client.post("/produtos", json=product_payload).status_code == 201
