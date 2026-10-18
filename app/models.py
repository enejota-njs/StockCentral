from sqlalchemy import CheckConstraint, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Category(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "nome = btrim(nome) AND char_length(nome) > 0",
            name="nome_valido",
        ),
        # A restricao no banco tambem impede duplicatas em requisicoes simultaneas.
        Index("uq_categorias_nome_ci", func.lower(nome), unique=True),
    )
