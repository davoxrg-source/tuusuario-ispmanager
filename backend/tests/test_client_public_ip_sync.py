from unittest.mock import MagicMock

from app.api.routes import clients as clients_module
from app.models.client import Client


def _patch_device_lookups(monkeypatch, service_mock, old_device_mock=None):
    monkeypatch.setattr(clients_module, "_device_service_for", lambda db, client: service_mock)
    monkeypatch.setattr(clients_module, "decrypt_secret", lambda secret: secret)
    monkeypatch.setattr(clients_module, "DeviceService", lambda device, password: service_mock)
    db = MagicMock()
    db.get.return_value = old_device_mock
    return db


def test_new_public_ip_gets_provisioned_no_removal_attempted(monkeypatch):
    service = MagicMock()
    db = _patch_device_lookups(monkeypatch, service)

    client = Client(
        public_ip_address="190.71.83.43",
        public_ip_provider_interface="eth10",
        public_ip_lan_interface="eth0",
        mikrotik_device_id="device-1",
    )

    clients_module._sync_client_public_ip(
        db, client, old_public_ip=None, old_provider_iface=None, old_lan_iface=None, old_device_id=None
    )

    service.provision_client_public_ip.assert_called_once_with("190.71.83.43", "eth10", "eth0")
    service.remove_client_public_ip.assert_not_called()


def test_changed_public_ip_removes_old_and_provisions_new(monkeypatch):
    service = MagicMock()
    old_device = MagicMock()
    db = _patch_device_lookups(monkeypatch, service, old_device_mock=old_device)

    client = Client(
        public_ip_address="190.71.83.44",  # cambió de .43 a .44
        public_ip_provider_interface="eth10",
        public_ip_lan_interface="eth0",
        mikrotik_device_id="device-1",
    )

    clients_module._sync_client_public_ip(
        db,
        client,
        old_public_ip="190.71.83.43",
        old_provider_iface="eth10",
        old_lan_iface="eth0",
        old_device_id="device-1",
    )

    service.remove_client_public_ip.assert_called_once_with("190.71.83.43")
    service.provision_client_public_ip.assert_called_once_with("190.71.83.44", "eth10", "eth0")


def test_clearing_public_ip_only_removes_does_not_reprovision(monkeypatch):
    service = MagicMock()
    old_device = MagicMock()
    db = _patch_device_lookups(monkeypatch, service, old_device_mock=old_device)

    client = Client(
        public_ip_address=None,
        public_ip_provider_interface=None,
        public_ip_lan_interface=None,
        mikrotik_device_id="device-1",
    )

    clients_module._sync_client_public_ip(
        db,
        client,
        old_public_ip="190.71.83.43",
        old_provider_iface="eth10",
        old_lan_iface="eth0",
        old_device_id="device-1",
    )

    service.remove_client_public_ip.assert_called_once_with("190.71.83.43")
    service.provision_client_public_ip.assert_not_called()


def test_unchanged_public_ip_reprovisions_without_removing(monkeypatch):
    """Mismo criterio que _sync_client_qos: si nada cambió, igual se
    reasegura la configuración actual (idempotente en el equipo), sin
    intentar retirar nada."""
    service = MagicMock()
    db = _patch_device_lookups(monkeypatch, service)

    client = Client(
        public_ip_address="190.71.83.43",
        public_ip_provider_interface="eth10",
        public_ip_lan_interface="eth0",
        mikrotik_device_id="device-1",
    )

    clients_module._sync_client_public_ip(
        db,
        client,
        old_public_ip="190.71.83.43",
        old_provider_iface="eth10",
        old_lan_iface="eth0",
        old_device_id="device-1",
    )

    service.provision_client_public_ip.assert_called_once_with("190.71.83.43", "eth10", "eth0")
    service.remove_client_public_ip.assert_not_called()
