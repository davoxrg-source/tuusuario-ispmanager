import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.inventory import InventoryItem, InventoryMovement, MovementReason, Supplier
from app.models.user import User
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMovementCreate,
    InventoryMovementRead,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
    TechnicianBalanceRead,
)

router = APIRouter(tags=["inventory"], dependencies=[Depends(get_current_user)])

# Los movimientos que "salen" de un técnico (o vuelven de uno) -- ver
# balance-by-technician y las validaciones de POST /inventory-movements.
_POSITIVE_REASONS = {MovementReason.PURCHASE, MovementReason.RETURN}
_NEGATIVE_REASONS = {MovementReason.ASSIGNMENT, MovementReason.INSTALLATION, MovementReason.LOSS}


def _get_supplier_or_404(db: Session, supplier_id: uuid.UUID) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    return supplier


def _get_item_or_404(db: Session, item_id: uuid.UUID) -> InventoryItem:
    item = db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado.")
    return item


@router.get("/suppliers", response_model=list[SupplierRead])
def list_suppliers(db: Session = Depends(get_db)) -> list[Supplier]:
    return db.query(Supplier).order_by(Supplier.name).all()


@router.post("/suppliers", response_model=SupplierRead, status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)) -> Supplier:
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID, payload: SupplierUpdate, db: Session = Depends(get_db)
) -> Supplier:
    supplier = _get_supplier_or_404(db, supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_supplier(supplier_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Los artículos de este proveedor no se borran -- quedan con
    supplier_id=None (ver ondelete=SET NULL en la migración). Un proveedor
    que deja de operar es algo común; bloquear el borrado sería más
    disruptivo que simplemente desvincular sus artículos."""
    supplier = _get_supplier_or_404(db, supplier_id)
    db.delete(supplier)
    db.commit()


@router.get("/inventory-items", response_model=list[InventoryItemRead])
def list_inventory_items(db: Session = Depends(get_db)) -> list[InventoryItem]:
    return db.query(InventoryItem).order_by(InventoryItem.name).all()


@router.post("/inventory-items", response_model=InventoryItemRead, status_code=201)
def create_inventory_item(payload: InventoryItemCreate, db: Session = Depends(get_db)) -> InventoryItem:
    item = InventoryItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/inventory-items/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: uuid.UUID, payload: InventoryItemUpdate, db: Session = Depends(get_db)
) -> InventoryItem:
    item = _get_item_or_404(db, item_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/inventory-items/{item_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_inventory_item(item_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    item = _get_item_or_404(db, item_id)
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Artículo con movimientos registrados, no se puede borrar."
        )


@router.get("/inventory-items/{item_id}/movements", response_model=list[InventoryMovementRead])
def list_item_movements(item_id: uuid.UUID, db: Session = Depends(get_db)) -> list[InventoryMovement]:
    _get_item_or_404(db, item_id)
    return (
        db.query(InventoryMovement)
        .filter(InventoryMovement.item_id == item_id)
        .order_by(InventoryMovement.created_at.desc())
        .all()
    )


@router.post("/inventory-movements", response_model=InventoryMovementRead, status_code=201)
def create_inventory_movement(
    payload: InventoryMovementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InventoryMovement:
    item = _get_item_or_404(db, payload.item_id)

    if payload.quantity_delta == 0:
        raise HTTPException(status_code=400, detail="La cantidad no puede ser cero.")
    if payload.reason in _POSITIVE_REASONS and payload.quantity_delta < 0:
        raise HTTPException(
            status_code=400, detail=f"'{payload.reason.value}' debe tener una cantidad positiva."
        )
    if payload.reason in _NEGATIVE_REASONS and payload.quantity_delta > 0:
        raise HTTPException(
            status_code=400, detail=f"'{payload.reason.value}' debe tener una cantidad negativa."
        )
    if payload.reason == MovementReason.ASSIGNMENT and payload.assigned_to_user_id is None:
        raise HTTPException(status_code=400, detail="Asignar material requiere indicar el técnico.")
    if payload.reason == MovementReason.INSTALLATION and payload.client_id is None:
        raise HTTPException(status_code=400, detail="Instalar material requiere indicar el cliente.")

    new_quantity = item.quantity + payload.quantity_delta
    if new_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente: quedan {item.quantity}, se pidió mover {payload.quantity_delta}.",
        )

    item.quantity = new_quantity
    movement = InventoryMovement(**payload.model_dump(), created_by_user_id=current_user.id)
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return movement


@router.get("/inventory/balance-by-technician", response_model=list[TechnicianBalanceRead])
def balance_by_technician(db: Session = Depends(get_db)) -> list[TechnicianBalanceRead]:
    rows = (
        db.query(
            InventoryMovement.assigned_to_user_id,
            User.full_name,
            InventoryMovement.item_id,
            InventoryItem.name,
            func.sum(InventoryMovement.quantity_delta).label("balance"),
        )
        .join(User, User.id == InventoryMovement.assigned_to_user_id)
        .join(InventoryItem, InventoryItem.id == InventoryMovement.item_id)
        .filter(
            InventoryMovement.reason.in_([MovementReason.ASSIGNMENT, MovementReason.RETURN]),
            InventoryMovement.assigned_to_user_id.isnot(None),
        )
        .group_by(InventoryMovement.assigned_to_user_id, User.full_name, InventoryMovement.item_id, InventoryItem.name)
        .having(func.sum(InventoryMovement.quantity_delta) != 0)
        .all()
    )
    return [
        TechnicianBalanceRead(
            user_id=row.assigned_to_user_id,
            user_name=row.full_name,
            item_id=row.item_id,
            item_name=row.name,
            # ASSIGNMENT resta stock (negativo) y RETURN suma (positivo) --
            # lo que el técnico tiene en mano es lo contrario de esa suma.
            balance=-row.balance,
        )
        for row in rows
    ]
