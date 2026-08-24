import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.hotspot import HotspotProfile, HotspotVoucher, HotspotVoucherStatus
from app.models.user import User
from app.schemas.hotspot import (
    HotspotProfileCreate,
    HotspotProfileRead,
    HotspotProfileUpdate,
    HotspotVoucherBatchCreate,
    HotspotVoucherRead,
)
from app.services.hotspot.vouchers import create_voucher_batch

router = APIRouter(tags=["hotspot"], dependencies=[Depends(get_current_user)])

MAX_BATCH_QUANTITY = 500


def _get_profile_or_404(db: Session, profile_id: uuid.UUID) -> HotspotProfile:
    profile = db.get(HotspotProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado.")
    return profile


def _get_voucher_or_404(db: Session, voucher_id: uuid.UUID) -> HotspotVoucher:
    voucher = db.get(HotspotVoucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Ficha no encontrada.")
    return voucher


def _validate_profile_limits(duration_hours: int | None, data_limit_mb: int | None) -> None:
    if duration_hours is None and data_limit_mb is None:
        raise HTTPException(
            status_code=400, detail="El perfil necesita al menos duración o límite de datos."
        )


@router.get("/hotspot-profiles", response_model=list[HotspotProfileRead])
def list_hotspot_profiles(db: Session = Depends(get_db)) -> list[HotspotProfile]:
    return db.query(HotspotProfile).order_by(HotspotProfile.name).all()


@router.post(
    "/hotspot-profiles",
    response_model=HotspotProfileRead,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_hotspot_profile(payload: HotspotProfileCreate, db: Session = Depends(get_db)) -> HotspotProfile:
    _validate_profile_limits(payload.duration_hours, payload.data_limit_mb)
    profile = HotspotProfile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.patch(
    "/hotspot-profiles/{profile_id}",
    response_model=HotspotProfileRead,
    dependencies=[Depends(require_admin)],
)
def update_hotspot_profile(
    profile_id: uuid.UUID, payload: HotspotProfileUpdate, db: Session = Depends(get_db)
) -> HotspotProfile:
    profile = _get_profile_or_404(db, profile_id)
    updates = payload.model_dump(exclude_unset=True)
    duration_hours = updates.get("duration_hours", profile.duration_hours)
    data_limit_mb = updates.get("data_limit_mb", profile.data_limit_mb)
    _validate_profile_limits(duration_hours, data_limit_mb)
    for field, value in updates.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/hotspot-profiles/{profile_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_hotspot_profile(profile_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    profile = _get_profile_or_404(db, profile_id)
    db.delete(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Perfil con fichas generadas, no se puede borrar."
        )


@router.get("/hotspot-vouchers", response_model=list[HotspotVoucherRead])
def list_hotspot_vouchers(
    profile_id: uuid.UUID | None = None,
    status_filter: HotspotVoucherStatus | None = None,
    batch_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[HotspotVoucher]:
    query = db.query(HotspotVoucher)
    if profile_id is not None:
        query = query.filter(HotspotVoucher.profile_id == profile_id)
    if status_filter is not None:
        query = query.filter(HotspotVoucher.status == status_filter)
    if batch_id is not None:
        query = query.filter(HotspotVoucher.batch_id == batch_id)
    return query.order_by(HotspotVoucher.created_at.desc()).all()


@router.post("/hotspot-vouchers/batch", response_model=list[HotspotVoucherRead], status_code=201)
def generate_voucher_batch(payload: HotspotVoucherBatchCreate, db: Session = Depends(get_db)) -> list[HotspotVoucher]:
    if not (1 <= payload.quantity <= MAX_BATCH_QUANTITY):
        raise HTTPException(
            status_code=400, detail=f"La cantidad debe estar entre 1 y {MAX_BATCH_QUANTITY}."
        )
    profile = _get_profile_or_404(db, payload.profile_id)
    return create_voucher_batch(db, profile, payload.quantity)


@router.post("/hotspot-vouchers/{voucher_id}/sell", response_model=HotspotVoucherRead)
def sell_voucher(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HotspotVoucher:
    voucher = _get_voucher_or_404(db, voucher_id)
    if voucher.status != HotspotVoucherStatus.UNUSED:
        raise HTTPException(status_code=400, detail="Solo se puede vender una ficha sin usar.")
    voucher.status = HotspotVoucherStatus.SOLD
    voucher.sold_at = datetime.now(timezone.utc)
    voucher.sold_by_user_id = current_user.id
    db.commit()
    db.refresh(voucher)
    return voucher


@router.post(
    "/hotspot-vouchers/{voucher_id}/void",
    response_model=HotspotVoucherRead,
    dependencies=[Depends(require_admin)],
)
def void_voucher(voucher_id: uuid.UUID, db: Session = Depends(get_db)) -> HotspotVoucher:
    voucher = _get_voucher_or_404(db, voucher_id)
    if voucher.status == HotspotVoucherStatus.VOID:
        raise HTTPException(status_code=400, detail="Esta ficha ya está anulada.")
    voucher.status = HotspotVoucherStatus.VOID
    voucher.voided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(voucher)
    return voucher
