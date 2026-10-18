"""Cria fornecedores com CNPJ e email unicos."""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fornecedores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("telefone", sa.String(length=30), nullable=False),
        sa.CheckConstraint(
            "nome = btrim(nome) AND char_length(nome) > 0",
            name=op.f("ck_fornecedores_nome_valido"),
        ),
        sa.CheckConstraint(
            "cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'",
            name=op.f("ck_fornecedores_cnpj_formato"),
        ),
        sa.CheckConstraint(
            "email = btrim(email) AND char_length(email) > 0",
            name=op.f("ck_fornecedores_email_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fornecedores")),
        sa.UniqueConstraint("cnpj", name=op.f("uq_fornecedores_cnpj")),
    )
    op.create_index(
        "uq_fornecedores_email_ci", "fornecedores", [sa.text("lower(email)")], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_fornecedores_email_ci", table_name="fornecedores")
    op.drop_table("fornecedores")
