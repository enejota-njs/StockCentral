import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine
from app.errors import database_error_handler, unexpected_error_handler
from app.observability import configure_logging, log_request
from app.routers.categories import router as categories_router
from app.routers.suppliers import router as suppliers_router
from app.routers.products import router as products_router
from app.routers.stock_movements import router as stock_movements_router


logger = logging.getLogger(__name__)
configure_logging()

app = FastAPI(title="StockCentral API")
app.add_exception_handler(SQLAlchemyError, database_error_handler)
app.add_exception_handler(Exception, unexpected_error_handler)
app.middleware("http")(log_request)
app.include_router(categories_router)
app.include_router(suppliers_router)
app.include_router(products_router)
app.include_router(stock_movements_router)


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
    except SQLAlchemyError as exc:
        logger.error(
            "Falha ao verificar a conexao com o banco.",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=503,
            detail="Banco de dados indisponivel.",
        ) from None

    return {"status": "ok", "database": "ok"}
