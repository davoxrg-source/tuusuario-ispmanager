"""fichas hotspot prepago

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

hotspot_voucher_status = postgresql.ENUM(
    "unused", "sold", "void", name="hotspot_voucher_status", create_type=False
)


def upgrade() -> None:
    hotspot_voucher_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "hotspot_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("duration_hours", sa.Integer, nullable=True),
        sa.Column("data_limit_mb", sa.Integer, nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    op.create_table(
        "hotspot_vouchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Sin ondelete: borrar un perfil con fichas generadas debe fallar
        # fuerte (ver delete_hotspot_profile), mismo criterio que
        # InventoryItem/movements.
        sa.Column(
            "profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hotspot_profiles.id"), nullable=False
        ),
        sa.Column("code", sa.String(8), nullable=False, unique=True),
        # Congelado del precio del perfil al momento de generar la ficha --
        # una ficha ya impresa no puede cambiar de precio retroactivamente.
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            hotspot_voucher_status,
            nullable=False,
            server_default="unused",
        ),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sold_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_hotspot_vouchers_profile_id", "hotspot_vouchers", ["profile_id"])
    op.create_index("ix_hotspot_vouchers_batch_id", "hotspot_vouchers", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_hotspot_vouchers_batch_id", table_name="hotspot_vouchers")
    op.drop_index("ix_hotspot_vouchers_profile_id", table_name="hotspot_vouchers")
    op.drop_table("hotspot_vouchers")
    op.drop_table("hotspot_profiles")
    hotspot_voucher_status.drop(op.get_bind(), checkfirst=True)
