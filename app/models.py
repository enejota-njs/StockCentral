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


class Supplier(Base):
    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    telefone: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "nome = btrim(nome) AND char_length(nome) > 0", name="nome_valido"
        ),
        CheckConstraint("cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'", name="cnpj_formato"),
        CheckConstraint(
            "email = btrim(email) AND char_length(email) > 0", name="email_valido"
        ),
        Index("uq_fornecedores_email_ci", func.lower(email), unique=True),
    )
