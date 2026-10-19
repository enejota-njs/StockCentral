from datetime import datetime
from io import StringIO
import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.database import get_session
from app.main import app
from app.observability import JsonFormatter, configure_logging


@pytest.fixture
def captured_logs():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("app")
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        handler.close()


def log_records(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_requests_produce_structured_logs_without_input_data(captured_logs):
    secret = "nao_deve_aparecer_nos_logs"
    with TestClient(app) as client:
        assert client.get("/health", params={"senha": secret}, headers={"Authorization": secret}).status_code == 200
        assert client.post("/movimentacoes", json={"campo_secreto": secret}).status_code == 422
        assert client.get(f"/{secret}").status_code == 404
    records = log_records(captured_logs)
    assert [row["status_code"] for row in records] == [200, 422, 404]
    assert [row["route"] for row in records] == ["/health", "/movimentacoes", "<sem_rota>"]
    assert [row["method"] for row in records] == ["GET", "POST", "GET"]
    for row in records:
        assert row["message"] == "http_request"
        assert row["level"] == "INFO"
        assert row["duration_ms"] >= 0
        assert datetime.fromisoformat(row["timestamp"]).utcoffset() is not None
    assert secret not in captured_logs.getvalue()


@pytest.mark.parametrize("error_type, status_code", [(OperationalError, 503), (ProgrammingError, 500)])
def test_database_errors_are_logged_without_sql_or_credentials(monkeypatch, captured_logs, error_type, status_code):
    secret = "senha_e_sql_privados"

    def broken_session():
        raise error_type(secret, {"password": secret}, Exception(secret))
        yield

    monkeypatch.setitem(app.dependency_overrides, get_session, broken_session)
    with TestClient(app) as client:
        response = client.get("/movimentacoes/123")
    assert response.status_code == status_code
    records = log_records(captured_logs)
    error = next(row for row in records if row["level"] == "ERROR")
    assert error["error_type"] == error_type.__name__
    access = next(row for row in records if row["message"] == "http_request")
    assert access["route"] == "/movimentacoes/{movement_id}"
    assert access["status_code"] == status_code
    assert secret not in captured_logs.getvalue()
    assert secret not in response.text


def test_unexpected_errors_return_json_without_internal_details(monkeypatch, captured_logs):
    secret = "detalhe_interno_privado"

    def broken_session():
        raise RuntimeError(secret)
        yield

    monkeypatch.setitem(app.dependency_overrides, get_session, broken_session)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/movimentacoes")
    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno do servidor."}
    records = log_records(captured_logs)
    assert any(row.get("error_type") == "RuntimeError" for row in records)
    assert any(row.get("status_code") == 500 for row in records)
    assert secret not in captured_logs.getvalue()


def test_logging_configuration_does_not_duplicate_handlers():
    configure_logging()
    configure_logging()
    handlers = [handler for handler in logging.getLogger("app").handlers if handler.name == "stockcentral_json"]
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JsonFormatter)
