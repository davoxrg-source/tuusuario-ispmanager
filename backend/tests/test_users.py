import pytest
from fastapi import HTTPException

from app.api.deps import zone_scope_filter_ids
from app.api.routes.users import create_user, list_staff_directory, update_user
from app.api.routes.zones import create_zone
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.zone import ZoneCreate


def test_create_user_with_zones(db_session):
    zone_a = create_zone(ZoneCreate(name="ZONA_A"), db_session)
    zone_b = create_zone(ZoneCreate(name="ZONA_B"), db_session)

    user = create_user(
        UserCreate(
            full_name="Tecnico Uno",
            email="tecnico1@compusoft-isp.com",
            password="segura123",
            role=UserRole.TECHNICIAN,
            zone_ids=[zone_a.id, zone_b.id],
        ),
        db_session,
    )

    assert {z.name for z in user.zones} == {"ZONA_A", "ZONA_B"}
    assert user.role == UserRole.TECHNICIAN


def test_create_user_duplicate_email_rejected(db_session):
    payload = UserCreate(full_name="Uno", email="dup@compusoft-isp.com", password="segura123")
    create_user(payload, db_session)

    with pytest.raises(HTTPException) as exc_info:
        create_user(payload, db_session)

    assert exc_info.value.status_code == 400


def test_update_user_replaces_zone_assignment(db_session):
    zone_a = create_zone(ZoneCreate(name="ZONA_A"), db_session)
    zone_b = create_zone(ZoneCreate(name="ZONA_B"), db_session)
    user = create_user(
        UserCreate(
            full_name="Tecnico", email="t@compusoft-isp.com", password="segura123",
            zone_ids=[zone_a.id, zone_b.id],
        ),
        db_session,
    )

    updated = update_user(user.id, UserUpdate(zone_ids=[zone_b.id]), db_session)

    assert {z.name for z in updated.zones} == {"ZONA_B"}


def test_update_user_deactivate_sets_is_active_false(db_session):
    user = create_user(
        UserCreate(full_name="Tecnico", email="t2@compusoft-isp.com", password="segura123"), db_session
    )

    updated = update_user(user.id, UserUpdate(is_active=False), db_session)

    assert updated.is_active is False


def test_seed_admin_still_creates_working_admin_after_schema_changes(db_session):
    # Replica la lógica de app/cli/seed_admin.py contra db_session -- ese
    # script no se toca en esta fase, esto confirma que sigue funcionando.
    admin = User(
        email="admin2@compusoft-isp.com",
        full_name="Admin",
        hashed_password=hash_password("segura123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    assert admin.role == UserRole.ADMIN
    assert admin.zones == []
    # Sin zonas asignadas y aun así sin restricción -- confirma el bypass de ADMIN.
    assert zone_scope_filter_ids(admin) is None


def test_staff_directory_returns_only_id_and_name_for_active_users(db_session):
    active = create_user(
        UserCreate(full_name="Tecnico Activo", email="activo@compusoft-isp.com", password="segura123"),
        db_session,
    )
    inactive = create_user(
        UserCreate(full_name="Tecnico Inactivo", email="inactivo@compusoft-isp.com", password="segura123"),
        db_session,
    )
    update_user(inactive.id, UserUpdate(is_active=False), db_session)

    directory = list_staff_directory(db_session)

    # list_staff_directory devuelve filas ORM crudas -- el filtrado a solo
    # id+full_name lo hace response_model (StaffNameRead) en la capa HTTP,
    # no algo observable llamando la función directo, como el resto de los
    # tests de este archivo.
    assert [d.full_name for d in directory] == ["Tecnico Activo"]
    assert directory[0].id == active.id
