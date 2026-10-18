"""Cria categorias com nomes unicos sem diferenciar maiusculas e minusculas."""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.CheckConstraint(
            "nome = btrim(nome) AND char_length(nome) > 0",
            name=op.f("ck_categorias_nome_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categorias")),
    )
    op.create_index(
        "uq_categorias_nome_ci", "categorias", [sa.text("lower(nome)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_categorias_nome_ci", table_name="categorias")
    op.drop_table("categorias")
