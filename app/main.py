import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.errors import database_error_handler
from app.routers.categories import router as categories_router
from app.routers.suppliers import router as suppliers_router


logger = logging.getLogger(__name__)

app = FastAPI(title="StockCentral API")
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.include_router(categories_router)
app.include_router(suppliers_router)


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
