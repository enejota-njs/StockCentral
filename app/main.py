import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine


logger = logging.getLogger(__name__)

app = FastAPI(title="StockCentral API")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/health/db",
    summary="Verificar a conexao com o banco",
    responses={
        503: {"description": "Banco de dados indisponivel"},
    },
)
def database_health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Falha ao verificar a conexao com o banco.")
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponivel.",
        ) from None

    return {"status": "ok", "database": "ok"}