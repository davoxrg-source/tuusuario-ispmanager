"""plantillas de contrato + contratos con firma simple

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    contract_status = postgresql.ENUM(
        "draft", "signed", "void", name="contract_status", create_type=False
    )
    contract_status.create(bind, checkfirst=True)

    op.create_table(
        "contract_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # SET NULL, no cascada: un contrato firmado tiene valor legal/de
        # auditoría que debe sobrevivir aunque se borre el cliente después
        # -- mismo criterio que InventoryMovement.client_id (Fase 4b). El
        # texto ya tiene los datos del cliente congelados adentro.
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("rendered_body", sa.Text, nullable=False),
        sa.Column("status", contract_status, nullable=False, server_default="draft"),
        sa.Column("signer_name", sa.String(160), nullable=True),
        sa.Column("signer_identification", sa.String(60), nullable=True),
        sa.Column("signature_image", sa.Text, nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signer_ip", sa.String(45), nullable=True),
        sa.Column(
            "witnessed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )
    op.create_index("ix_contracts_client_id", "contracts", ["client_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_client_id", table_name="contracts")
    op.drop_table("contracts")
    op.drop_table("contract_templates")

    bind = op.get_bind()
    postgresql.ENUM(name="contract_status").drop(bind, checkfirst=True)
