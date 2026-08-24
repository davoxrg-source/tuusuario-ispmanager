"""almacén: proveedores, artículos, log de movimientos

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    movement_reason = postgresql.ENUM(
        "purchase", "assignment", "installation", "return", "adjustment", "loss",
        name="movement_reason", create_type=False,
    )
    movement_reason.create(bind, checkfirst=True)

    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("phone", sa.String(60), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(60), nullable=False, server_default="otro"),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        # SET NULL, no falla fuerte: un proveedor puede dejar de operar sin
        # que eso deba bloquear el borrado (a diferencia de Zona).
        sa.Column(
            "supplier_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )

    op.create_table(
        "inventory_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Sin ondelete: borrar un artículo con movimientos debe fallar
        # fuerte (el log de auditoría no puede desaparecer con él).
        sa.Column(
            "item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inventory_items.id"), nullable=False
        ),
        sa.Column("reason", movement_reason, nullable=False),
        sa.Column("quantity_delta", sa.Integer, nullable=False),
        sa.Column(
            "assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        # SET NULL: DELETE /clients/{id} es un borrado real -- el
        # movimiento ("se instaló X en esta casa") debe seguir existiendo.
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_inventory_movements_item_id", "inventory_movements", ["item_id"])
    op.create_index(
        "ix_inventory_movements_assigned_to_user_id", "inventory_movements", ["assigned_to_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_assigned_to_user_id", table_name="inventory_movements")
    op.drop_index("ix_inventory_movements_item_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_table("inventory_items")
    op.drop_table("suppliers")

    bind = op.get_bind()
    postgresql.ENUM(name="movement_reason").drop(bind, checkfirst=True)
