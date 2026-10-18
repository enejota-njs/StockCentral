import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app.database import get_session
from app.main import app


def test_category_lifecycle(client):
    assert client.get("/categorias").json() == []
    response = client.post("/categorias", json={"nome": "  Eletrônicos  "})
    assert response.status_code == 201
    category = response.json()
    assert category["nome"] == "Eletrônicos"
    path = f'/categorias/{category["id"]}'
    assert client.get(path).json() == category
    assert client.get("/categorias").json() == [category]
    response = client.put(path, json={"nome": "Utilidades"})
    assert response.status_code == 200
    assert response.json()["nome"] == "Utilidades"
    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404


def test_duplicate_name_and_transaction_recovery(client):
    client.post("/categorias", json={"nome": "Eletrônicos"})
    response = client.post("/categorias", json={"nome": " eletrônicos "})
    assert response.status_code == 409
    assert response.json() == {"detail": "Ja existe uma categoria com esse nome."}
    assert client.post("/categorias", json={"nome": "Papelaria"}).status_code == 201
    assert len(client.get("/categorias").json()) == 2


def test_conflicting_update_preserves_original_name(client):
    client.post("/categorias", json={"nome": "Papelaria"})
    second = client.post("/categorias", json={"nome": "Brinquedos"}).json()
    path = f'/categorias/{second["id"]}'
    assert client.put(path, json={"nome": "PAPELARIA"}).status_code == 409
    assert client.get(path).json()["nome"] == "Brinquedos"
    assert client.put(path, json={"nome": "BRINQUEDOS"}).status_code == 200


@pytest.mark.parametrize("payload", [
    {}, {"nome": ""}, {"nome": " \t\n"}, {"nome": "a" * 101},
    {"nome": None}, {"nome": 123}, {"nome": "Valido", "id": 10},
])
def test_invalid_creation_has_no_side_effects(client, payload):
    assert client.post("/categorias", json=payload).status_code == 422
    assert client.get("/categorias").json() == []


def test_invalid_update_preserves_existing_data(client):
    category = client.post("/categorias", json={"nome": "Papelaria"}).json()
    path = f'/categorias/{category["id"]}'
    assert client.put(path, json={"nome": " "}).status_code == 422
    assert client.get(path).json() == category


def test_category_accepts_maximum_name_length(client):
    response = client.post("/categorias", json={"nome": "a" * 100})
    assert response.status_code == 201
    assert response.json()["nome"] == "a" * 100


def test_missing_resources_and_invalid_ids(client):
    assert client.get("/categorias/999").status_code == 404
    assert client.put("/categorias/999", json={"nome": "Valido"}).status_code == 404
    assert client.delete("/categorias/999").status_code == 404
    assert client.get("/categorias/0").status_code == 422


def test_pagination_and_limits(client):
    categories = [client.post("/categorias", json={"nome": name}).json()
                  for name in ["A", "B", "C"]]
    assert client.get("/categorias?offset=1&limit=1").json() == [categories[1]]
    assert client.get("/categorias?offset=10").json() == []
    for query in ["limit=0", "limit=101", "offset=-1"]:
        assert client.get(f"/categorias?{query}").status_code == 422


@pytest.mark.parametrize("error_type, status_code", [
    (OperationalError, 503), (ProgrammingError, 500),
])
def test_database_errors_hide_internal_details(client, error_type, status_code):
    def unavailable_session():
        raise error_type("private SQL", {}, Exception("private server details"))
        yield

    app.dependency_overrides[get_session] = unavailable_session
    response = client.get("/categorias")
    assert response.status_code == status_code
    assert "private" not in response.text
    assert set(response.json()) == {"detail"}


def test_migration_can_be_reversed_and_reapplied(migrated_connection):
    connection, config = migrated_connection
    assert "categorias" in inspect(connection).get_table_names()
    command.downgrade(config, "base")
    assert "categorias" not in inspect(connection).get_table_names()
    command.upgrade(config, "head")
    assert "categorias" in inspect(connection).get_table_names()


def test_database_itself_rejects_case_insensitive_duplicates(migrated_connection):
    connection, _ = migrated_connection
    insert = text("INSERT INTO categorias (nome) VALUES (:nome)")
    connection.execute(insert, {"nome": "Papelaria"})
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert, {"nome": "PAPELARIA"})
    assert connection.scalar(text("SELECT count(*) FROM categorias")) == 1
