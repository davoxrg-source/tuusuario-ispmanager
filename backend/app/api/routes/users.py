import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.models.zone import Zone
from app.schemas.user import UserCreate, UserRead, UserUpdate

# Listado de personal es más sensible que el de zonas -- admin-only también
# para leer, no solo para escribir.
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


def _set_zones(db: Session, user: User, zone_ids: list[uuid.UUID]) -> None:
    zones = db.query(Zone).filter(Zone.id.in_(zone_ids)).all()
    missing = set(zone_ids) - {z.id for z in zones}
    if missing:
        raise HTTPException(status_code=400, detail=f"Zona(s) no encontrada(s): {missing}")
    user.zones = zones


@router.get("", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return db.query(User).order_by(User.full_name).all()


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo.")

    data = payload.model_dump(exclude={"password", "zone_ids"})
    user = User(**data, hashed_password=hash_password(payload.password))
    db.add(user)
    db.flush()  # necesita user.id antes de asignar la relación muchos-a-muchos
    _set_zones(db, user, payload.zone_ids)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: uuid.UUID, payload: UserUpdate, db: Session = Depends(get_db)) -> User:
    user = _get_user_or_404(db, user_id)
    data = payload.model_dump(exclude_unset=True, exclude={"password", "zone_ids"})
    for field, value in data.items():
        setattr(user, field, value)
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    if payload.zone_ids is not None:
        _set_zones(db, user, payload.zone_ids)
    db.commit()
    db.refresh(user)
    return user
