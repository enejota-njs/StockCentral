"""Cria a estrutura do historico de movimentacoes de estoque."""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movimentacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(7), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.Column("data", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("produto_id", sa.Integer(), nullable=False),
        sa.Column("fornecedor_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movimentacoes")),
        sa.ForeignKeyConstraint(
            ["produto_id"], ["produtos.id"], ondelete="RESTRICT",
            name=op.f("fk_movimentacoes_produto_id_produtos"),
        ),
        sa.ForeignKeyConstraint(
            ["fornecedor_id"], ["fornecedores.id"], ondelete="RESTRICT",
            name=op.f("fk_movimentacoes_fornecedor_id_fornecedores"),
        ),
        sa.CheckConstraint(
            "tipo IN ('entrada', 'saida')", name=op.f("ck_movimentacoes_tipo_valido"),
        ),
        sa.CheckConstraint(
            "quantidade > 0", name=op.f("ck_movimentacoes_quantidade_positiva"),
        ),
    )
    op.create_index("ix_movimentacoes_data", "movimentacoes", ["data"])
    op.create_index("ix_movimentacoes_produto_id", "movimentacoes", ["produto_id"])
    op.create_index("ix_movimentacoes_fornecedor_id", "movimentacoes", ["fornecedor_id"])


def downgrade() -> None:
    op.drop_index("ix_movimentacoes_fornecedor_id", table_name="movimentacoes")
    op.drop_index("ix_movimentacoes_produto_id", table_name="movimentacoes")
    op.drop_index("ix_movimentacoes_data", table_name="movimentacoes")
    op.drop_table("movimentacoes")
