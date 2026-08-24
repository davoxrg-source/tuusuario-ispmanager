import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_error
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol admin.")
    return user


def zone_scope_filter_ids(user: User) -> list[uuid.UUID] | None:
    """None = sin restricción (ADMIN, ve todo). Lista (puede ser vacía) =
    IDs de zona para filtrar una consulta de lista con
    .filter(Model.zone_id.in_(...)). Lista vacía es intencional: un
    TECHNICIAN/FINANCE sin zonas asignadas no ve nada, no ve todo -- seguro
    por defecto."""
    if user.role == UserRole.ADMIN:
        return None
    return [zone.id for zone in user.zones]


def ensure_zone_access(user: User, zone_id: uuid.UUID | None, not_found_detail: str) -> None:
    """Verifica acceso de `user` a un recurso con este zone_id; si no tiene,
    lanza 404 -- el mismo código que "no existe" (ver _get_client_or_404),
    a propósito: no distinguimos "no tienes acceso" de "no existe" para no
    filtrarle a un TECHNICIAN/FINANCE qué recursos hay fuera de su zona.
    zone_id=None (recurso sin zona asignada) tampoco es accesible para
    no-admins -- lo "sin asignar" solo lo ve un ADMIN."""
    if user.role == UserRole.ADMIN:
        return
    if zone_id is None or zone_id not in {z.id for z in user.zones}:
        raise HTTPException(status_code=404, detail=not_found_detail)
