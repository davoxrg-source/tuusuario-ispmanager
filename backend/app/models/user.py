import enum
import uuid

from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum
from app.models.zone import user_zones


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TECHNICIAN = "technician"
    FINANCE = "finance"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), default=UserRole.TECHNICIAN)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Zonas asignadas -- sin efecto si role=ADMIN (acceso total siempre, ver
    # app/api/deps.py: zone_scope_filter_ids/ensure_zone_access).
    zones: Mapped[list["Zone"]] = relationship(secondary=user_zones, back_populates="users")  # noqa: F821
