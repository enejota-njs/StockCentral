import pytest
from alembic import command
from sqlalchemy import insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from app.models import Category, Product, StockMovement, Supplier


@pytest.fixture
def movement_payload(migrated_connection):
    connection, _ = migrated_connection
    category_id = connection.scalar(insert(Category).values(nome="Papelaria").returning(Category.id))
    supplier_id = connection.scalar(insert(Supplier).values(
        nome="Fornecedor", cnpj="12ABC34501DE35", email="contato@example.com", telefone="12345678",
    ).returning(Supplier.id))
    product_id = connection.scalar(insert(Product).values(
        nome="Caneta", sku="CANETA-001", preco_custo="2.50", preco_venda="4.90",
        categoria_id=category_id, fornecedor_id=supplier_id,
    ).returning(Product.id))
    return {"tipo": "entrada", "quantidade": 5, "produto_id": product_id, "fornecedor_id": supplier_id}


@pytest.mark.parametrize("kind", ["entrada", "saida"])
def test_movement_fields_and_generated_date(migrated_connection, movement_payload, kind):
    connection, _ = migrated_connection
    payload = {**movement_payload, "tipo": kind}
    movement = connection.execute(insert(StockMovement).values(**payload).returning(
        StockMovement.__table__,
    )).mappings().one()
    assert movement["id"] > 0
    assert movement["data"].utcoffset() is not None
    assert all(movement[field] == value for field, value in payload.items())


@pytest.mark.parametrize("changes, constraint", [
    ({"tipo": "ajuste"}, "ck_movimentacoes_tipo_valido"),
    ({"quantidade": 0}, "ck_movimentacoes_quantidade_positiva"),
    ({"quantidade": -1}, "ck_movimentacoes_quantidade_positiva"),
    ({"produto_id": 2147483647}, "fk_movimentacoes_produto_id_produtos"),
    ({"fornecedor_id": 2147483647}, "fk_movimentacoes_fornecedor_id_fornecedores"),
])
def test_database_rejects_invalid_movements(migrated_connection, movement_payload, changes, constraint):
    connection, _ = migrated_connection
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            connection.execute(insert(StockMovement).values(**{**movement_payload, **changes}))
    assert error.value.orig.diag.constraint_name == constraint
    assert connection.execute(select(StockMovement.id)).all() == []


def test_product_with_history_cannot_be_deleted(client, migrated_connection, movement_payload):
    connection, _ = migrated_connection
    connection.execute(insert(StockMovement).values(**movement_payload))
    path = f'/produtos/{movement_payload["produto_id"]}'
    assert client.delete(path).status_code == 409
    assert client.get(path).status_code == 200
    assert len(connection.execute(select(StockMovement.id)).all()) == 1


def test_history_keeps_original_supplier(client, migrated_connection, movement_payload):
    connection, _ = migrated_connection
    connection.execute(insert(StockMovement).values(**movement_payload))
    new_supplier_id = connection.scalar(insert(Supplier).values(
        nome="Outro", cnpj="11222333000181", email="outro@example.com", telefone="12345678",
    ).returning(Supplier.id))
    connection.execute(update(Product).where(Product.id == movement_payload["produto_id"]).values(
        fornecedor_id=new_supplier_id,
    ))
    assert connection.scalar(select(StockMovement.fornecedor_id)) == movement_payload["fornecedor_id"]
    # O vinculo historico protege o fornecedor antigo mesmo sem produtos atuais.
    path = f'/fornecedores/{movement_payload["fornecedor_id"]}'
    assert client.delete(path).status_code == 409
    assert client.get(path).status_code == 200


def test_movement_migration_preserves_existing_records(migrated_connection, movement_payload):
    connection, config = migrated_connection
    before = connection.execute(select(Product.__table__)).mappings().all()
    command.downgrade(config, "0003")
    assert "movimentacoes" not in inspect(connection).get_table_names()
    assert connection.execute(select(Product.__table__)).mappings().all() == before
    command.upgrade(config, "head")
    assert connection.execute(select(Product.__table__)).mappings().all() == before
    assert connection.scalar(select(Supplier.id)) == movement_payload["fornecedor_id"]
    assert connection.scalar(select(Category.id)) == before[0]["categoria_id"]
    connection.execute(insert(StockMovement).values(**movement_payload))
    assert len(connection.execute(select(StockMovement.id)).all()) == 1
