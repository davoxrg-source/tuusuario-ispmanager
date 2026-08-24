"""claves de API para integraciones externas

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        # Primeros caracteres de la clave en texto plano -- visible en la
        # lista para que el staff reconozca cuál es cuál sin poder
        # reconstruir la clave completa a partir de esto.
        sa.Column("key_prefix", sa.String(12), nullable=False),
        # SHA256 de la clave completa, no bcrypt -- acá hace falta un
        # lookup exacto y rápido, no una comparación lenta a propósito
        # como con una contraseña de login.
        sa.Column("hashed_key", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
