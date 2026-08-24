import pytest
from fastapi import HTTPException

from app.api.routes.zones import create_zone, delete_zone, list_zones, update_zone
from app.models.client import Client, ClientStatus
from app.schemas.zone import ZoneCreate, ZoneUpdate


def test_create_zone_and_list_zones(db_session):
    create_zone(ZoneCreate(name="ZONA_DIA_1", description="Ruta lunes/miércoles"), db_session)
    create_zone(ZoneCreate(name="ZONA_DIA_15"), db_session)

    zones = list_zones(db_session)

    assert [z.name for z in zones] == ["ZONA_DIA_1", "ZONA_DIA_15"]


def test_update_zone(db_session):
    zone = create_zone(ZoneCreate(name="ZONA_DIA_1"), db_session)

    updated = update_zone(zone.id, ZoneUpdate(description="actualizada"), db_session)

    assert updated.description == "actualizada"
    assert updated.name == "ZONA_DIA_1"


def test_delete_zone_unused_succeeds(db_session):
    zone = create_zone(ZoneCreate(name="ZONA_DIA_1"), db_session)

    delete_zone(zone.id, db_session)

    assert list_zones(db_session) == []


def test_delete_zone_in_use_returns_400(db_session):
    zone = create_zone(ZoneCreate(name="ZONA_DIA_1"), db_session)
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, zone_id=zone.id)
    db_session.add(client)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        delete_zone(zone.id, db_session)

    assert exc_info.value.status_code == 400
    # la zona sigue existiendo -- el borrado no se aplicó a medias
    assert len(list_zones(db_session)) == 1
