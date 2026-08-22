import pytest
from pydantic import ValidationError

from app.schemas.mikrotik_device import MikrotikDeviceCreate, MikrotikDeviceRead


def _base_payload(**overrides):
    payload = dict(
        name="Router",
        host="10.0.0.1",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        password="",
    )
    payload.update(overrides)
    return payload


def test_create_rejects_0_0_0_0_as_host():
    with pytest.raises(ValidationError):
        MikrotikDeviceCreate(**_base_payload(host="0.0.0.0"))


def test_create_accepts_real_host():
    device = MikrotikDeviceCreate(**_base_payload(host="10.0.0.1"))
    assert device.host == "10.0.0.1"


def test_read_does_not_reject_a_pre_existing_invalid_host():
    """Un registro que ya quedó guardado con un host inválido (antes de esta
    validación, o por otra vía) debe poder seguir leyéndose sin romper la API."""
    device = MikrotikDeviceRead(
        id="00000000-0000-0000-0000-000000000000",
        name="CCR2004",
        host="0.0.0.0",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        status="offline",
    )
    assert device.host == "0.0.0.0"
