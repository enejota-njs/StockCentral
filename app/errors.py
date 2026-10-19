import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError


logger = logging.getLogger(__name__)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "Erro ao acessar o banco: %s.", type(exc).__name__,
        extra={"error_type": type(exc).__name__},
    )
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=503, content={"detail": "Banco de dados indisponivel."}
        )
    return JSONResponse(
        status_code=500, content={"detail": "Erro interno ao acessar o banco de dados."}
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Erro inesperado na aplicacao.", extra={"error_type": type(exc).__name__})
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})
