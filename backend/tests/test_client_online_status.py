from unittest.mock import MagicMock

from app.models.client import Client
from app.workers.poller import _update_client_online_status


def test_marks_client_online_when_ip_has_arp_entry():
    device = MagicMock(id="device-1")
    service = MagicMock()
    service.get_online_ip_set.return_value = {"10.0.0.5"}

    db = MagicMock()
    online_client = Client(ip_address="10.0.0.5", is_online=False, last_seen_at=None)
    offline_client = Client(ip_address="10.0.0.9", is_online=True, last_seen_at=None)
    db.query.return_value.filter.return_value.all.return_value = [online_client, offline_client]

    _update_client_online_status(
        db, device, service, max_attempts=1, backoff_base_seconds=0, backoff_max_seconds=0
    )

    assert online_client.is_online is True
    assert online_client.last_seen_at is not None
    assert offline_client.is_online is False


def test_client_without_ip_is_never_online():
    device = MagicMock(id="device-1")
    service = MagicMock()
    service.get_online_ip_set.return_value = {"10.0.0.5"}

    db = MagicMock()
    no_ip_client = Client(ip_address=None, is_online=True)
    db.query.return_value.filter.return_value.all.return_value = [no_ip_client]

    _update_client_online_status(
        db, device, service, max_attempts=1, backoff_base_seconds=0, backoff_max_seconds=0
    )

    assert no_ip_client.is_online is False


def test_arp_read_failure_leaves_existing_status_untouched():
    device = MagicMock(id="device-1", name="R1")
    service = MagicMock()
    service.get_online_ip_set.side_effect = RuntimeError("timeout")

    db = MagicMock()
    client = Client(ip_address="10.0.0.5", is_online=True)
    db.query.return_value.filter.return_value.all.return_value = [client]

    _update_client_online_status(
        db, device, service, max_attempts=2, backoff_base_seconds=0, backoff_max_seconds=0
    )

    # Si falla la lectura ARP (ej. equipo inalcanzable), no se toca el
    # estado ya guardado -- ni a "conectado" ni a "desconectado".
    assert client.is_online is True
    # Se reintentó max_attempts veces antes de darse por vencido.
    assert service.get_online_ip_set.call_count == 2
