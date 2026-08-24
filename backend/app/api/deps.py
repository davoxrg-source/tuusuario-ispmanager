import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.client import Client
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
portal_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/portal/auth/login")
api_key_scheme = HTTPBearer(auto_error=False)


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


def get_current_client(
    token: str = Depends(portal_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Client:
    """Paralelo a get_current_user pero para Client -- no comparte nada con
    el auth de staff, ni siquiera el token (tokenUrl distinto). No bloquea
    por ClientStatus: un cliente SUSPENDED tiene que poder entrar, ver que
    está suspendido, y reportar el pago para reactivarse -- solo se bloquea
    si nunca se activó el portal (hashed_password is None)."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None:
        raise credentials_error
    try:
        client_id = uuid.UUID(subject)
    except ValueError:
        raise credentials_error
    client = db.get(Client, client_id)
    if client is None or client.hashed_password is None:
        raise credentials_error
    return client


def get_current_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Paralelo a get_current_user/get_current_client pero para
    integraciones externas (ver app/api/routes/external_api.py) -- Bearer
    estático de larga duración, no un JWT. Se busca por hash exacto
    (SHA256, no bcrypt: acá hace falta un lookup rápido, no una
    comparación lenta a propósito como con una contraseña)."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="API key inválida o ausente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise credentials_error
    hashed = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    api_key = db.query(ApiKey).filter(ApiKey.hashed_key == hashed).first()
    if api_key is None or not api_key.is_active:
        raise credentials_error
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return api_key


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
