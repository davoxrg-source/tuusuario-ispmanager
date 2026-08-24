import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneUpdate

router = APIRouter(prefix="/zones", tags=["zones"], dependencies=[Depends(get_current_user)])


def _get_zone_or_404(db: Session, zone_id: uuid.UUID) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zona no encontrada.")
    return zone


@router.get("", response_model=list[ZoneRead])
def list_zones(db: Session = Depends(get_db)) -> list[Zone]:
    return db.query(Zone).order_by(Zone.name).all()


@router.post("", response_model=ZoneRead, status_code=201, dependencies=[Depends(require_admin)])
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)) -> Zone:
    zone = Zone(**payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.patch("/{zone_id}", response_model=ZoneRead, dependencies=[Depends(require_admin)])
def update_zone(zone_id: uuid.UUID, payload: ZoneUpdate, db: Session = Depends(get_db)) -> Zone:
    zone = _get_zone_or_404(db, zone_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/{zone_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    zone = _get_zone_or_404(db, zone_id)
    db.delete(zone)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Zona en uso, reasigná sus clientes/equipos antes de borrarla."
        )
