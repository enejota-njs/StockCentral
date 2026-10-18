from alembic import context

from app.database import Base, database_url, engine
from app import models  # noqa: F401 -- registra as tabelas no metadata do Alembic


target_metadata = Base.metadata


def migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    # Permite testar as migracoes dentro de uma transacao externa reversivel.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        migrate(connection)
    else:
        with engine.connect() as connection:
            migrate(connection)
