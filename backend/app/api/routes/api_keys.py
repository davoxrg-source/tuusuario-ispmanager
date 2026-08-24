import hashlib
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreateResult, ApiKeyRead

# Gestionar API keys es admin-only completo (incluso para listar) -- son
# credenciales que le dan acceso externo a datos de clientes/facturas,
# mismo criterio que la gestión de personal.
router = APIRouter(prefix="/api-keys", tags=["api-keys"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ApiKeyRead])
def list_api_keys(db: Session = Depends(get_db)) -> list[ApiKey]:
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.post("", response_model=ApiKeyCreateResult, status_code=201)
def create_api_key(
    payload: ApiKeyCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ApiKeyCreateResult:
    """La clave en texto plano viaja UNA sola vez, en esta respuesta -- solo
    se guarda su hash, no se puede volver a leer después."""
    plain_key = f"isp_live_{secrets.token_urlsafe(24)}"
    api_key = ApiKey(
        name=payload.name,
        key_prefix=plain_key[:12],
        hashed_key=hashlib.sha256(plain_key.encode()).hexdigest(),
        created_by_user_id=current_user.id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return ApiKeyCreateResult(key=plain_key, **ApiKeyRead.model_validate(api_key).model_dump())


@router.post("/{api_key_id}/revoke", response_model=ApiKeyRead)
def revoke_api_key(api_key_id: uuid.UUID, db: Session = Depends(get_db)) -> ApiKey:
    api_key = db.get(ApiKey, api_key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API key no encontrada.")
    api_key.is_active = False
    db.commit()
    db.refresh(api_key)
    return api_key
