from datetime import UTC, datetime
import json
import logging
from time import perf_counter

from fastapi import Request


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        content = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("method", "route", "status_code", "duration_ms", "error_type"):
            if hasattr(record, field):
                content[field] = getattr(record, field)
        return json.dumps(content, ensure_ascii=False)


def configure_logging() -> None:
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    # Recarregar a aplicacao nao deve multiplicar as linhas de log.
    if not any(handler.name == "stockcentral_json" for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.set_name("stockcentral_json")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)


async def log_request(request: Request, call_next):
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        # O template da rota evita registrar IDs, query strings, headers ou corpos.
        route = getattr(request.scope.get("route"), "path", "<sem_rota>")
        logging.getLogger("app.http").info("http_request", extra={
            "method": request.method,
            "route": route,
            "status_code": status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
        })
