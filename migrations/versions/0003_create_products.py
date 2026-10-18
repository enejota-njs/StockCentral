"""Cria produtos e protege categorias e fornecedores vinculados."""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "produtos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(150), nullable=False),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("preco_custo", sa.Numeric(12, 2), nullable=False),
        sa.Column("preco_venda", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantidade_em_estoque", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("estoque_minimo", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("data_cadastro", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("categoria_id", sa.Integer(), nullable=False),
        sa.Column("fornecedor_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_produtos")),
        sa.UniqueConstraint("sku", name=op.f("uq_produtos_sku")),
        sa.ForeignKeyConstraint(
            ["categoria_id"], ["categorias.id"], ondelete="RESTRICT",
            name=op.f("fk_produtos_categoria_id_categorias"),
        ),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"], ["fornecedores.id"], ondelete="RESTRICT",
            name=op.f("fk_produtos_fornecedor_id_fornecedores"),
        ),
        sa.CheckConstraint("nome = btrim(nome) AND char_length(nome) > 0", name=op.f("ck_produtos_nome_valido")),
        sa.CheckConstraint("sku ~ '^[A-Z0-9][A-Z0-9._-]{0,63}$'", name=op.f("ck_produtos_sku_formato")),
        sa.CheckConstraint("preco_custo BETWEEN 0 AND 9999999999.99", name=op.f("ck_produtos_preco_custo_valido")),
        sa.CheckConstraint("preco_venda BETWEEN 0 AND 9999999999.99", name=op.f("ck_produtos_preco_venda_valido")),
        sa.CheckConstraint("quantidade_em_estoque >= 0", name=op.f("ck_produtos_estoque_nao_negativo")),
        sa.CheckConstraint("estoque_minimo >= 0", name=op.f("ck_produtos_estoque_minimo_nao_negativo")),
    )
    op.create_index("ix_produtos_categoria_id", "produtos", ["categoria_id"])
    op.create_index("ix_produtos_fornecedor_id", "produtos", ["fornecedor_id"])


def downgrade() -> None:
    op.drop_index("ix_produtos_fornecedor_id", table_name="produtos")
    op.drop_index("ix_produtos_categoria_id", table_name="produtos")
    op.drop_table("produtos")
