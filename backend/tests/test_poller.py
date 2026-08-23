import logging

from app.models.mikrotik_device import MikrotikDevice
from app.workers import poller


def _fake_device() -> MikrotikDevice:
    return MikrotikDevice(
        name="Router Lab",
        host="10.0.0.1",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        encrypted_password="unused-in-test",
    )


class FakeService:
    def __init__(self, stuck_sequence):
        self._sequence = iter(stuck_sequence)

    def find_stuck_qos_queues(self):
        return next(self._sequence)


def test_check_qos_health_does_not_warn_on_first_sighting(caplog):
    poller._previously_stuck.clear()
    device = _fake_device()
    service = FakeService([["isp-abc-down-bulk"]])

    with caplog.at_level(logging.WARNING):
        poller._check_qos_health(device, service)

    assert "trabada" not in caplog.text


def test_check_qos_health_warns_only_when_stuck_two_cycles_in_a_row(caplog):
    # Reproduce el incidente real: una lectura sola puede ser casualidad de
    # timing -- solo avisa si la MISMA cola sigue trabada al ciclo siguiente.
    poller._previously_stuck.clear()
    device = _fake_device()
    service = FakeService([["isp-abc-down-bulk"], ["isp-abc-down-bulk"]])

    with caplog.at_level(logging.WARNING):
        poller._check_qos_health(device, service)  # 1er ciclo: no avisa
        assert "trabada" not in caplog.text
        poller._check_qos_health(device, service)  # 2do ciclo: mismo nombre -> avisa

    assert "isp-abc-down-bulk" in caplog.text
    assert "trabada" in caplog.text


def test_check_qos_health_does_not_warn_if_it_recovers_between_cycles(caplog):
    poller._previously_stuck.clear()
    device = _fake_device()
    service = FakeService([["isp-abc-down-bulk"], []])  # drenó antes del 2do chequeo

    with caplog.at_level(logging.WARNING):
        poller._check_qos_health(device, service)
        poller._check_qos_health(device, service)

    assert "trabada" not in caplog.text
