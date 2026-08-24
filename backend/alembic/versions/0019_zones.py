"""zonas + asignación usuario-zona + zone_id en clients/mikrotik_devices

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    # Tabla de asociación pura -- ondelete=CASCADE en ambas FK porque no hay
    # motivo para dejar filas huérfanas en user_zones.
    op.create_table(
        "user_zones",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # zone_id nullable y SIN ondelete=CASCADE en estas dos: borrar una zona
    # en uso debe fallar fuerte (ver DELETE /zones/{id}), no desasignar en
    # silencio a los clientes/equipos que la tenían.
    op.add_column(
        "clients", sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=True)
    )
    op.create_index("ix_clients_zone_id", "clients", ["zone_id"])

    op.add_column(
        "mikrotik_devices",
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=True),
    )
    op.create_index("ix_mikrotik_devices_zone_id", "mikrotik_devices", ["zone_id"])


def downgrade() -> None:
    op.drop_index("ix_mikrotik_devices_zone_id", table_name="mikrotik_devices")
    op.drop_column("mikrotik_devices", "zone_id")
    op.drop_index("ix_clients_zone_id", table_name="clients")
    op.drop_column("clients", "zone_id")
    op.drop_table("user_zones")
    op.drop_table("zones")
