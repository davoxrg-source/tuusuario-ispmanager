"""cuentas/formas de pago (reconciliación) + FK opcional en payments

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-23

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "payment_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("kind", sa.String(30), nullable=False, server_default="other"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )
    op.add_column(
        "payments",
        sa.Column(
            "payment_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_accounts.id"),
            nullable=True,
        ),
    )

    # Backfill: una cuenta por cada valor distinto de payments.method que ya
    # exista, para no perder el dato histórico al pasar a la nueva FK.
    distinct_methods = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT DISTINCT method FROM payments WHERE method IS NOT NULL")
        )
    ]
    for method in distinct_methods:
        account_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO payment_accounts (id, name, kind) VALUES (:id, :name, 'other')"
            ),
            {"id": account_id, "name": method},
        )
        bind.execute(
            sa.text(
                "UPDATE payments SET payment_account_id = :account_id WHERE method = :method"
            ),
            {"account_id": account_id, "method": method},
        )


def downgrade() -> None:
    op.drop_column("payments", "payment_account_id")
    op.drop_table("payment_accounts")
