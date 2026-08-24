"""agrega el valor 'finance' al enum user_role

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-23

"""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE no puede correr en la misma transacción que
    # lo agrega -- este proyecto corre todas las migraciones pendientes de
    # un "alembic upgrade head" en una sola transacción (env.py no pasa
    # transaction_per_migration=True), así que se aísla con autocommit_block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'finance'")


def downgrade() -> None:
    # Postgres no tiene DROP VALUE para enums -- requeriría reconstruir el
    # tipo entero. No vale la pena para un downgrade rutinario, brecha
    # documentada a propósito.
    pass
