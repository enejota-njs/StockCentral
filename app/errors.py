import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError


logger = logging.getLogger(__name__)


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error(
        "Erro de banco na rota %s: %s", request.url.path, type(exc).__name__
    )
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=503, content={"detail": "Banco de dados indisponivel."}
        )
    return JSONResponse(
        status_code=500, content={"detail": "Erro interno ao acessar o banco de dados."}
    )
