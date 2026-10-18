from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
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


class Product(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    preco_custo: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantidade_em_estoque: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    estoque_minimo: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    data_cadastro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    categoria_id: Mapped[int] = mapped_column(
        ForeignKey("categorias.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    fornecedor_id: Mapped[int] = mapped_column(
        ForeignKey("fornecedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint("nome = btrim(nome) AND char_length(nome) > 0", name="nome_valido"),
        CheckConstraint("sku ~ '^[A-Z0-9][A-Z0-9._-]{0,63}$'", name="sku_formato"),
        CheckConstraint("preco_custo BETWEEN 0 AND 9999999999.99", name="preco_custo_valido"),
        CheckConstraint("preco_venda BETWEEN 0 AND 9999999999.99", name="preco_venda_valido"),
        CheckConstraint("quantidade_em_estoque >= 0", name="estoque_nao_negativo"),
        CheckConstraint("estoque_minimo >= 0", name="estoque_minimo_nao_negativo"),
    )
