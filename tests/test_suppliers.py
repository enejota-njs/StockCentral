import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.validators import validate_cnpj


# O CNPJ alfanumerico vem do exemplo do manual de DV da Receita Federal.
SUPPLIER = {
    "nome": "Fornecedor de exemplo",
    "cnpj": "12ABC34501DE35",
    "email": "contato@example.com",
    "telefone": "(75) 99999-1234",
}
SECOND_SUPPLIER = {
    **SUPPLIER, "nome": "Outro fornecedor", "cnpj": "11222333000181",
    "email": "outro@example.com",
}


def test_supplier_lifecycle_and_normalization(client):
    assert client.get("/fornecedores").json() == []
    response = client.post("/fornecedores", json={
        **SUPPLIER, "nome": "  Fornecedor de exemplo  ", "cnpj": " 12.abc.345/01de-35 ",
        "email": " CONTATO@EXAMPLE.COM ", "telefone": " (75) 99999-1234 ",
    })
    assert response.status_code == 201
    supplier = response.json()
    assert supplier == {"id": supplier["id"], **SUPPLIER}
    path = f'/fornecedores/{supplier["id"]}'
    assert client.get(path).json() == supplier
    assert client.get("/fornecedores").json() == [supplier]
    changed = {**SECOND_SUPPLIER, "telefone": "+55 (75) 3333-1234"}
    response = client.put(path, json=changed)
    assert response.status_code == 200
    assert response.json() == {"id": supplier["id"], **changed}
    # Reenviar os mesmos dados nao e uma duplicata de outro fornecedor.
    assert client.put(path, json=changed).status_code == 200
    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404
    assert client.get("/fornecedores").json() == []


@pytest.mark.parametrize("field, duplicate, message", [
    ("cnpj", "12.abc.345/01de-35", "Ja existe um fornecedor com esse CNPJ."),
    ("email", " CONTATO@EXAMPLE.COM ", "Ja existe um fornecedor com esse email."),
])
def test_duplicates_and_transaction_recovery(client, field, duplicate, message):
    assert client.post("/fornecedores", json=SUPPLIER).status_code == 201
    response = client.post("/fornecedores", json={**SECOND_SUPPLIER, field: duplicate})
    assert response.status_code == 409
    assert response.json() == {"detail": message}
    assert client.post("/fornecedores", json=SECOND_SUPPLIER).status_code == 201
    assert len(client.get("/fornecedores").json()) == 2


@pytest.mark.parametrize("field", ["cnpj", "email"])
def test_conflicting_update_preserves_all_fields(client, field):
    client.post("/fornecedores", json=SUPPLIER)
    second = client.post("/fornecedores", json=SECOND_SUPPLIER).json()
    path = f'/fornecedores/{second["id"]}'
    response = client.put(path, json={
        **SECOND_SUPPLIER, field: SUPPLIER[field], "nome": "Nao deve persistir",
        "telefone": "12345678",
    })
    assert response.status_code == 409
    assert client.get(path).json() == second


@pytest.mark.parametrize("changes", [
    {"nome": " \t\n"}, {"nome": "a" * 151}, {"nome": None},
    {"cnpj": "00000000000000"}, {"cnpj": "11111111111111"},
    {"cnpj": "12ABC34501DE34"}, {"cnpj": "11222333000182"},
    {"cnpj": "12ABC34501DE3A"}, {"cnpj": "12-ABC-345-01DE35"},
    {"cnpj": "12ABC34501DE35extra"}, {"cnpj": 11222333000181},
    {"cnpj": "１２ABC34501DE35"}, {"cnpj": None},
    {"email": "invalido"}, {"email": "a@@example.com"}, {"email": None},
    {"telefone": ""}, {"telefone": "1234567"}, {"telefone": "1" * 16},
    {"telefone": "ligue 75999991234"}, {"telefone": 75999991234},
    {"telefone": "+55+75999991234"}, {"id": 9},
])
def test_invalid_supplier_has_no_side_effects(client, changes):
    assert client.post("/fornecedores", json={**SUPPLIER, **changes}).status_code == 422
    assert client.get("/fornecedores").json() == []


@pytest.mark.parametrize("field", ["nome", "cnpj", "email", "telefone"])
def test_all_supplier_fields_are_required(client, field):
    payload = {key: value for key, value in SUPPLIER.items() if key != field}
    assert client.post("/fornecedores", json=payload).status_code == 422


def test_invalid_update_preserves_supplier(client):
    supplier = client.post("/fornecedores", json=SUPPLIER).json()
    path = f'/fornecedores/{supplier["id"]}'
    assert client.put(path, json={"nome": "Incompleto"}).status_code == 422
    assert client.put(path, json={**SUPPLIER, "cnpj": "00000000000000"}).status_code == 422
    assert client.get(path).json() == supplier


def test_missing_supplier_and_invalid_ids(client):
    assert client.get("/fornecedores/999").status_code == 404
    assert client.put("/fornecedores/999", json=SUPPLIER).status_code == 404
    assert client.delete("/fornecedores/999").status_code == 404
    for supplier_id in ["0", "-1", "abc", "2147483648"]:
        assert client.get(f"/fornecedores/{supplier_id}").status_code == 422


def test_supplier_pagination(client):
    first = client.post("/fornecedores", json=SUPPLIER).json()
    second = client.post("/fornecedores", json=SECOND_SUPPLIER).json()
    assert client.get("/fornecedores").json() == [first, second]
    assert client.get("/fornecedores?offset=1&limit=1").json() == [second]
    assert client.get("/fornecedores?offset=10").json() == []
    for query in ["limit=0", "limit=101", "offset=-1"]:
        assert client.get(f"/fornecedores?{query}").status_code == 422


@pytest.mark.parametrize("field, value, constraint", [
    ("cnpj", SUPPLIER["cnpj"], "uq_fornecedores_cnpj"),
    ("email", "CONTATO@EXAMPLE.COM", "uq_fornecedores_email_ci"),
])
def test_database_rejects_duplicates(migrated_connection, field, value, constraint):
    connection, _ = migrated_connection
    insert = text("""
        INSERT INTO fornecedores (nome, cnpj, email, telefone)
        VALUES (:nome, :cnpj, :email, :telefone)
    """)
    connection.execute(insert, SUPPLIER)
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            connection.execute(insert, {**SECOND_SUPPLIER, field: value})
    assert error.value.orig.diag.constraint_name == constraint
    assert connection.scalar(text("SELECT count(*) FROM fornecedores")) == 1


def test_supplier_migration_preserves_categories(migrated_connection):
    connection, config = migrated_connection
    connection.execute(text("INSERT INTO categorias (nome) VALUES ('Existente')"))
    command.downgrade(config, "0001")
    assert "fornecedores" not in inspect(connection).get_table_names()
    assert connection.scalar(text("SELECT nome FROM categorias")) == "Existente"
    command.upgrade(config, "head")
    assert "fornecedores" in inspect(connection).get_table_names()
    assert connection.scalar(text("SELECT nome FROM categorias")) == "Existente"


@pytest.mark.parametrize("value, expected", [
    ("12.ABC.345/01DE-35", "12ABC34501DE35"),
    ("11.222.333/0001-81", "11222333000181"),
    ("04.252.011/0001-10", "04252011000110"),
    ("00.000.000/0001-91", "00000000000191"),
])
def test_cnpj_known_check_digits(value, expected):
    assert validate_cnpj(value) == expected
