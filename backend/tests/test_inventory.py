import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.inventory import (
    balance_by_technician,
    create_inventory_item,
    create_inventory_movement,
    create_supplier,
    delete_inventory_item,
    delete_supplier,
    list_inventory_items,
    list_suppliers,
    update_inventory_item,
)
from app.models.client import Client, ClientStatus
from app.models.inventory import InventoryItem, MovementReason
from app.models.user import User, UserRole
from app.schemas.inventory import InventoryItemCreate, InventoryItemUpdate, InventoryMovementCreate, SupplierCreate

def _make_user(db_session, name="Tecnico", role=UserRole.TECHNICIAN) -> User:
    # created_by_user_id/assigned_to_user_id son FK NOT NULL/NULL a
    # users.id -- necesita una fila real persistida, no un User(...)
    # transitorio (su .id queda en None hasta el INSERT).
    user = User(
        full_name=name, email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_client(db_session) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_item(db_session, quantity=0, **overrides) -> InventoryItem:
    item = InventoryItem(name="Router TP-Link", category="router", quantity=quantity)
    for field, value in overrides.items():
        setattr(item, field, value)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_supplier_and_item_crud(db_session):
    supplier = create_supplier(SupplierCreate(name="Ubiquiti Colombia", phone="3001234567"), db_session)
    assert supplier.name == "Ubiquiti Colombia"

    item = create_inventory_item(
        InventoryItemCreate(name="Antena PowerBeam", category="antena", supplier_id=supplier.id), db_session
    )
    assert item.quantity == 0
    assert item.supplier_id == supplier.id

    updated = update_inventory_item(item.id, InventoryItemUpdate(unit_cost=150.0), db_session)
    assert float(updated.unit_cost) == 150.0

    assert [s.id for s in list_suppliers(db_session)] == [supplier.id]
    assert [i.id for i in list_inventory_items(db_session)] == [item.id]


def test_delete_supplier_in_use_does_not_fail(db_session):
    supplier = create_supplier(SupplierCreate(name="Mikrotik LatAm"), db_session)
    item = create_inventory_item(
        InventoryItemCreate(name="Router hAP", supplier_id=supplier.id), db_session
    )

    delete_supplier(supplier.id, db_session)

    db_session.refresh(item)
    assert item.supplier_id is None  # SET NULL, no bloqueó el borrado


def test_delete_item_with_movements_returns_400(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=5)
    create_inventory_movement(
        InventoryMovementCreate(item_id=item.id, reason=MovementReason.PURCHASE, quantity_delta=5),
        db_session,
        admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        delete_inventory_item(item.id, db_session)
    assert exc_info.value.status_code == 400


def test_purchase_increases_quantity(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=0)

    movement = create_inventory_movement(
        InventoryMovementCreate(item_id=item.id, reason=MovementReason.PURCHASE, quantity_delta=10),
        db_session,
        admin,
    )

    assert movement.quantity_delta == 10
    db_session.refresh(item)
    assert item.quantity == 10


def test_purchase_rejects_negative_quantity(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session)

    with pytest.raises(HTTPException) as exc_info:
        create_inventory_movement(
            InventoryMovementCreate(item_id=item.id, reason=MovementReason.PURCHASE, quantity_delta=-3),
            db_session,
            admin,
        )
    assert exc_info.value.status_code == 400


def test_assignment_rejects_positive_quantity(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=5)
    tech = _make_user(db_session)

    with pytest.raises(HTTPException):
        create_inventory_movement(
            InventoryMovementCreate(
                item_id=item.id, reason=MovementReason.ASSIGNMENT, quantity_delta=3,
                assigned_to_user_id=tech.id,
            ),
            db_session,
            admin,
        )


def test_assignment_requires_technician(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=5)

    with pytest.raises(HTTPException) as exc_info:
        create_inventory_movement(
            InventoryMovementCreate(item_id=item.id, reason=MovementReason.ASSIGNMENT, quantity_delta=-2),
            db_session,
            admin,
        )
    assert exc_info.value.status_code == 400


def test_installation_requires_client(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=5)

    with pytest.raises(HTTPException) as exc_info:
        create_inventory_movement(
            InventoryMovementCreate(item_id=item.id, reason=MovementReason.INSTALLATION, quantity_delta=-1),
            db_session,
            admin,
        )
    assert exc_info.value.status_code == 400


def test_installation_decreases_quantity(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=5)
    client = _make_client(db_session)

    create_inventory_movement(
        InventoryMovementCreate(
            item_id=item.id, reason=MovementReason.INSTALLATION, quantity_delta=-1, client_id=client.id
        ),
        db_session,
        admin,
    )

    db_session.refresh(item)
    assert item.quantity == 4


def test_movement_rejects_insufficient_stock(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=2)
    tech = _make_user(db_session)

    with pytest.raises(HTTPException) as exc_info:
        create_inventory_movement(
            InventoryMovementCreate(
                item_id=item.id, reason=MovementReason.ASSIGNMENT, quantity_delta=-3,
                assigned_to_user_id=tech.id,
            ),
            db_session,
            admin,
        )
    assert exc_info.value.status_code == 400


def test_balance_by_technician_nets_assignment_and_return(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=10)
    tech = _make_user(db_session)

    create_inventory_movement(
        InventoryMovementCreate(
            item_id=item.id, reason=MovementReason.ASSIGNMENT, quantity_delta=-3,
            assigned_to_user_id=tech.id,
        ),
        db_session, admin,
    )
    create_inventory_movement(
        InventoryMovementCreate(
            item_id=item.id, reason=MovementReason.RETURN, quantity_delta=1,
            assigned_to_user_id=tech.id,
        ),
        db_session, admin,
    )

    balances = balance_by_technician(db_session)
    assert len(balances) == 1
    assert balances[0].user_id == tech.id
    assert balances[0].balance == 2


def test_balance_by_technician_excludes_fully_returned(db_session):
    admin = _make_user(db_session, "Admin", UserRole.ADMIN)
    item = _make_item(db_session, quantity=10)
    tech = _make_user(db_session)

    create_inventory_movement(
        InventoryMovementCreate(
            item_id=item.id, reason=MovementReason.ASSIGNMENT, quantity_delta=-2,
            assigned_to_user_id=tech.id,
        ),
        db_session, admin,
    )
    create_inventory_movement(
        InventoryMovementCreate(
            item_id=item.id, reason=MovementReason.RETURN, quantity_delta=2,
            assigned_to_user_id=tech.id,
        ),
        db_session, admin,
    )

    assert balance_by_technician(db_session) == []
