import uuid

from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

# Tabla de asociación pura (sin columnas propias) -- se declara como Table,
# no como modelo mapeado, porque no hay ningún dato adicional por fila que
# lo justifique.
user_zones = Table(
    "user_zones",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", UUID(as_uuid=True), ForeignKey("zones.id", ondelete="CASCADE"), primary_key=True),
)


class Zone(Base, TimestampMixin):
    """Agrupación de clientes/equipos para acceso por rol (ver
    app/api/deps.py: zone_scope_filter_ids/ensure_zone_access). Distinta de
    MikrotikDevice.site (etiqueta de texto libre, ej. dirección física) --
    no se fusionan."""

    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship(secondary=user_zones, back_populates="zones")  # noqa: F821
    # passive_deletes=True: sin esto, SQLAlchemy pone zone_id=NULL en los
    # hijos antes de borrar la zona (comportamiento por defecto de la
    # relación), lo que evitaría el IntegrityError que DELETE /zones/{id}
    # necesita para fallar fuerte en vez de desasignar en silencio -- con
    # esto, la restricción real de la FK en la base de datos es la que decide.
    clients: Mapped[list["Client"]] = relationship(back_populates="zone", passive_deletes=True)  # noqa: F821
    devices: Mapped[list["MikrotikDevice"]] = relationship(  # noqa: F821
        back_populates="zone", passive_deletes=True
    )
