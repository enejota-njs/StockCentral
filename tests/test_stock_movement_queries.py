from datetime import datetime

import pytest
from sqlalchemy import update

from app.models import StockMovement


@pytest.fixture
def history(client, stock_product, migrated_connection):
    connection, _ = migrated_connection
    supplier = client.post("/fornecedores", json={
        "nome": "Outro fornecedor", "cnpj": "11222333000181",
        "email": "outro@example.com", "telefone": "12345678",
    }).json()
    product = client.post("/produtos", json={
        "nome": "Lapis", "sku": "LAPIS-001", "preco_custo": "1.00",
        "preco_venda": "2.00", "estoque_minimo": 1,
        "categoria_id": stock_product["categoria_id"], "fornecedor_id": supplier["id"],
    }).json()
    rows = []
    for product_id, kind, quantity, date in [
        (stock_product["id"], "entrada", 10, "2026-10-17T12:00:00Z"),
        (product["id"], "entrada", 8, "2026-10-18T12:00:00Z"),
        (stock_product["id"], "saida", 3, "2026-10-19T12:00:00Z"),
        (stock_product["id"], "entrada", 2, "2026-10-19T12:00:00Z"),
    ]:
        response = client.post("/movimentacoes", json={
            "produto_id": product_id, "tipo": kind, "quantidade": quantity,
        })
        assert response.status_code == 201
        movement = response.json()
        # Datas controladas somente no schema de teste para conferir limites e empates.
        connection.execute(update(StockMovement).where(StockMovement.id == movement["id"]).values(
            data=datetime.fromisoformat(date),
        ))
        rows.append(client.get(f'/movimentacoes/{movement["id"]}').json())
    return rows


def test_empty_history_and_missing_id(client):
    assert client.get("/movimentacoes").json() == []
    response = client.get("/movimentacoes/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Movimentacao nao encontrada."}


def test_history_order_details_and_pagination(client, history):
    assert client.get("/movimentacoes").json() == history[::-1]
    assert client.get("/movimentacoes?offset=1&limit=2").json() == [history[2], history[1]]
    assert client.get("/movimentacoes?offset=10").json() == []
    for movement in history:
        response = client.get(f'/movimentacoes/{movement["id"]}')
        assert response.status_code == 200
        assert response.json() == movement


def test_combined_filters_are_applied_before_pagination(client, history):
    assert client.get("/movimentacoes", params={"tipo": "saida"}).json() == [history[2]]
    assert client.get("/movimentacoes", params={"produto_id": history[1]["produto_id"]}).json() == [history[1]]
    assert client.get("/movimentacoes", params={"fornecedor_id": history[1]["fornecedor_id"]}).json() == [history[1]]
    params = {
        "produto_id": history[0]["produto_id"], "fornecedor_id": history[0]["fornecedor_id"],
        "tipo": "entrada", "data_inicio": "2026-10-17T00:00:00Z",
        "data_fim": "2026-10-20T00:00:00Z", "offset": 1, "limit": 1,
    }
    assert client.get("/movimentacoes", params=params).json() == [history[0]]
    params["fornecedor_id"] = history[1]["fornecedor_id"]
    assert client.get("/movimentacoes", params=params).json() == []
    for field in ["produto_id", "fornecedor_id"]:
        assert client.get("/movimentacoes", params={field: 2147483647}).json() == []


def test_period_boundaries_and_equivalent_timezones(client, history):
    start = "2026-10-18T09:00:00-03:00"
    end = "2026-10-19T12:00:00Z"
    assert client.get("/movimentacoes", params={"data_inicio": start}).json() == history[:0:-1]
    assert client.get("/movimentacoes", params={"data_fim": start}).json() == history[1::-1]
    assert client.get("/movimentacoes", params={"data_inicio": start, "data_fim": end}).json() == history[:0:-1]
    assert client.get("/movimentacoes", params={
        "data_inicio": "2026-10-19T09:00:00-03:00", "data_fim": "2026-10-19T14:00:00+02:00",
    }).json() == history[3:1:-1]
    assert client.get("/movimentacoes", params={"data_inicio": "2026-10-19T12:00:00.000001Z"}).json() == []


@pytest.mark.parametrize("params", [
    {"offset": -1}, {"limit": 0}, {"limit": 101}, {"limit": "abc"},
    {"produto_id": 0}, {"fornecedor_id": -1}, {"produto_id": 2147483648},
    {"tipo": "ajuste"}, {"tipo": "ENTRADA"}, {"campo_desconhecido": 1},
    {"data_inicio": "invalido"}, {"data_fim": "2026-02-30T00:00:00Z"},
    {"data_inicio": "2026-10-19"}, {"data_fim": "2026-10-19T12:00:00"},
    {"data_inicio": "2026-10-20T00:00:00Z", "data_fim": "2026-10-19T00:00:00Z"},
])
def test_invalid_filters_return_validation_errors(client, params):
    response = client.get("/movimentacoes", params=params)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("value", ["0", "-1", "abc", "2147483648"])
def test_invalid_movement_ids(client, value):
    assert client.get(f"/movimentacoes/{value}").status_code == 422


def test_supplier_filter_preserves_history_after_product_edit(client, stock_product, history):
    old_supplier = stock_product["fornecedor_id"]
    new_supplier = history[1]["fornecedor_id"]
    payload = {key: stock_product[key] for key in (
        "nome", "sku", "preco_custo", "preco_venda", "estoque_minimo", "categoria_id", "fornecedor_id",
    )}
    payload["fornecedor_id"] = new_supplier
    assert client.put(f'/produtos/{stock_product["id"]}', json=payload).status_code == 200
    response = client.post("/movimentacoes", json={
        "produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 1,
    })
    assert response.status_code == 201
    assert response.json()["fornecedor_id"] == new_supplier
    assert client.get("/movimentacoes", params={"fornecedor_id": old_supplier}).json() == [history[3], history[2], history[0]]
    new_ids = {row["id"] for row in client.get("/movimentacoes", params={"fornecedor_id": new_supplier}).json()}
    assert new_ids == {history[1]["id"], response.json()["id"]}
    assert client.delete(f"/fornecedores/{old_supplier}").status_code == 409


def test_history_cannot_be_edited_or_deleted(client, stock_product, history):
    balance = client.get(f'/produtos/{stock_product["id"]}').json()["quantidade_em_estoque"]
    path = f'/movimentacoes/{history[0]["id"]}'
    for method in ["PUT", "PATCH", "DELETE"]:
        assert client.request(method, path, json={"quantidade": 999}).status_code == 405
    assert client.get(path).json() == history[0]
    assert client.get("/movimentacoes").json() == history[::-1]
    assert client.get(f'/produtos/{stock_product["id"]}').json()["quantidade_em_estoque"] == balance


def test_low_stock_filter_tracks_real_movements(client, stock_product):
    assert client.get("/produtos?estoque_baixo=true").json() == [stock_product]
    payload = {"produto_id": stock_product["id"], "tipo": "entrada", "quantidade": 6}
    assert client.post("/movimentacoes", json=payload).status_code == 201
    assert client.get("/produtos?estoque_baixo=true").json() == []
    assert client.post("/movimentacoes", json={**payload, "tipo": "saida", "quantidade": 1}).status_code == 201
    assert client.get("/produtos?estoque_baixo=true").json()[0]["quantidade_em_estoque"] == 5
