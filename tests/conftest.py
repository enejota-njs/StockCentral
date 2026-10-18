from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app.database import engine, get_session
from app.main import app


@pytest.fixture
def migrated_connection():
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = f"test_{uuid4().hex}"
        try:
            connection.execute(CreateSchema(schema))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            yield connection, config
        finally:
            # O rollback remove inclusive o schema; nenhum dado de teste persiste.
            transaction.rollback()


@pytest.fixture
def client(migrated_connection):
    connection, _ = migrated_connection

    def test_session():
        # Os commits da API encerram apenas savepoints, preservando o rollback externo.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
