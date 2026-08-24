import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.client import Client
from app.models.installation import Installation
from app.schemas.installation import (
    InstallationCreate,
    InstallationRead,
    InstallationUpdate,
    RouteDistanceRead,
    RouteDistanceRequest,
    RouteLeg,
)
from app.services.geo import haversine_km

router = APIRouter(prefix="/installations", tags=["installations"], dependencies=[Depends(get_current_user)])


def _get_installation_or_404(db: Session, installation_id: uuid.UUID) -> Installation:
    installation = db.get(Installation, installation_id)
    if installation is None:
        raise HTTPException(status_code=404, detail="Instalación no encontrada.")
    return installation


@router.get("", response_model=list[InstallationRead])
def list_installations(db: Session = Depends(get_db)) -> list[Installation]:
    return db.query(Installation).order_by(Installation.scheduled_date).all()


@router.post("", response_model=InstallationRead, status_code=201)
def create_installation(payload: InstallationCreate, db: Session = Depends(get_db)) -> Installation:
    installation = Installation(**payload.model_dump())
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation


# Registrada antes de "/{installation_id}" a propósito -- mismo motivo que
# /clients/bulk/*: son POST, así que no colisiona con el GET/PATCH/DELETE
# de un solo id (distinto método), pero se mantiene el mismo criterio de
# "rutas fijas antes que rutas con parámetro" del resto del proyecto.
@router.post("/route-distance", response_model=RouteDistanceRead)
def calculate_route_distance(payload: RouteDistanceRequest, db: Session = Depends(get_db)) -> RouteDistanceRead:
    installations = []
    for installation_id in payload.installation_ids:
        installation = db.get(Installation, installation_id)
        if installation is None:
            raise HTTPException(status_code=404, detail=f"Instalación no encontrada: {installation_id}")
        installations.append(installation)

    missing_coords = [
        str(i.id)
        for i in installations
        if i.client.latitude is None or i.client.longitude is None
    ]
    if missing_coords:
        raise HTTPException(
            status_code=400,
            detail=f"Estas instalaciones no tienen coordenadas cargadas en el cliente: {', '.join(missing_coords)}",
        )

    legs: list[RouteLeg] = []
    total_km = 0.0
    for a, b in zip(installations, installations[1:]):
        km = haversine_km(float(a.client.latitude), float(a.client.longitude), float(b.client.latitude), float(b.client.longitude))
        legs.append(RouteLeg(from_id=a.id, to_id=b.id, km=round(km, 2)))
        total_km += km

    return RouteDistanceRead(total_km=round(total_km, 2), legs=legs)


@router.get("/{installation_id}", response_model=InstallationRead)
def get_installation(installation_id: uuid.UUID, db: Session = Depends(get_db)) -> Installation:
    return _get_installation_or_404(db, installation_id)


@router.patch("/{installation_id}", response_model=InstallationRead)
def update_installation(
    installation_id: uuid.UUID, payload: InstallationUpdate, db: Session = Depends(get_db)
) -> Installation:
    installation = _get_installation_or_404(db, installation_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(installation, field, value)
    db.commit()
    db.refresh(installation)
    return installation


@router.delete("/{installation_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_installation(installation_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    installation = _get_installation_or_404(db, installation_id)
    db.delete(installation)
    db.commit()
