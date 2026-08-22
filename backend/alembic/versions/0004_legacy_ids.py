"""add legacy_plan_id / legacy_contract_id for sequreisp migration

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("legacy_plan_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_plans_legacy_plan_id", "plans", ["legacy_plan_id"])

    op.add_column("clients", sa.Column("legacy_contract_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_clients_legacy_contract_id", "clients", ["legacy_contract_id"])


def downgrade() -> None:
    op.drop_constraint("uq_clients_legacy_contract_id", "clients", type_="unique")
    op.drop_column("clients", "legacy_contract_id")

    op.drop_constraint("uq_plans_legacy_plan_id", "plans", type_="unique")
    op.drop_column("plans", "legacy_plan_id")
