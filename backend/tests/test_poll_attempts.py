from unittest.mock import MagicMock

import pytest

from app.models.mikrotik_device import DeviceStatus
from app.models.poll_attempt import PollAttempt, PollAttemptStatus, PollJobType
from app.workers.poller import _poll_device_once, _run_daily_billing, _run_traffic_maintenance


def _poll_attempts_added(db: MagicMock) -> list[PollAttempt]:
    return [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], PollAttempt)]


def _make_device():
    return MagicMock(id="device-1", name="R1", host="10.0.0.1", encrypted_password="enc")


def test_poll_device_once_success_records_one_attempt(monkeypatch):
    device = _make_device()
    db = MagicMock()

    fake_status = MagicMock(
        cpu_load_percent=10, memory_used_bytes=1, memory_total_bytes=2,
        uptime_seconds=3, active_ppp_sessions=0,
    )
    service = MagicMock()
    service.get_status.return_value = fake_status
    service.get_interfaces_snapshot.return_value = []
    service.find_stuck_qos_queues.return_value = []

    monkeypatch.setattr("app.workers.poller.decrypt_secret", lambda secret: "pw")
    monkeypatch.setattr("app.workers.poller.DeviceService", lambda dev, pw: service)

    _poll_device_once(db, device)

    attempts = _poll_attempts_added(db)
    assert len(attempts) == 1
    assert attempts[0].device_id == "device-1"
    assert attempts[0].job_type == PollJobType.DEVICE_POLL
    assert attempts[0].status == PollAttemptStatus.SUCCESS
    assert attempts[0].attempt_number == 1
    assert device.status == DeviceStatus.ONLINE


def test_poll_device_once_failure_retries_and_records_every_attempt(monkeypatch):
    device = _make_device()
    db = MagicMock()

    service = MagicMock()
    service.get_status.side_effect = RuntimeError("no responde")
    service.resolve_host_via_mac.return_value = None  # no hay MAC para redescubrir

    monkeypatch.setattr("app.workers.poller.decrypt_secret", lambda secret: "pw")
    monkeypatch.setattr("app.workers.poller.DeviceService", lambda dev, pw: service)
    monkeypatch.setattr("app.workers.retry.time.sleep", lambda s: None)

    _poll_device_once(db, device)

    attempts = _poll_attempts_added(db)
    # Default settings: poller_retry_max_attempts = 3
    assert len(attempts) == 3
    assert [a.attempt_number for a in attempts] == [1, 2, 3]
    assert all(a.status == PollAttemptStatus.FAILURE for a in attempts)
    assert all(a.device_id == "device-1" for a in attempts)
    assert device.status == DeviceStatus.OFFLINE


def test_run_daily_billing_success_records_one_attempt(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.workers.poller.SessionLocal", lambda: db)
    monkeypatch.setattr("app.workers.poller.get_billing_settings", lambda db: MagicMock())
    monkeypatch.setattr(
        "app.workers.poller.invoicing.generate_monthly_invoices", lambda db, settings, today: []
    )
    monkeypatch.setattr("app.workers.poller.invoicing.mark_overdue_invoices", lambda db, today: [])
    monkeypatch.setattr(
        "app.workers.poller.invoicing.suspend_clients_with_overdue_invoices",
        lambda db, settings, today: [],
    )
    monkeypatch.setattr("app.workers.poller.invoicing.apply_late_fees", lambda db, now, settings: [])

    _run_daily_billing()

    attempts = _poll_attempts_added(db)
    assert len(attempts) == 1
    assert attempts[0].device_id is None
    assert attempts[0].job_type == PollJobType.DAILY_BILLING
    assert attempts[0].status == PollAttemptStatus.SUCCESS


def test_run_daily_billing_failure_records_one_attempt_and_raises(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.workers.poller.SessionLocal", lambda: db)
    monkeypatch.setattr("app.workers.poller.get_billing_settings", lambda db: MagicMock())

    def _raise(db, settings, today):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.workers.poller.invoicing.generate_monthly_invoices", _raise)

    with pytest.raises(RuntimeError, match="boom"):
        _run_daily_billing()

    attempts = _poll_attempts_added(db)
    assert len(attempts) == 1
    assert attempts[0].device_id is None
    assert attempts[0].job_type == PollJobType.DAILY_BILLING
    assert attempts[0].status == PollAttemptStatus.FAILURE


def test_run_traffic_maintenance_success_records_one_attempt(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.workers.poller.SessionLocal", lambda: db)
    monkeypatch.setattr("app.workers.poller.purge_old_buckets", lambda db, older_than_days: 0)

    _run_traffic_maintenance()

    attempts = _poll_attempts_added(db)
    assert len(attempts) == 1
    assert attempts[0].device_id is None
    assert attempts[0].job_type == PollJobType.TRAFFIC_MAINTENANCE
    assert attempts[0].status == PollAttemptStatus.SUCCESS


def test_run_traffic_maintenance_failure_records_one_attempt_and_raises(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.workers.poller.SessionLocal", lambda: db)

    def _raise(db, older_than_days):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.workers.poller.purge_old_buckets", _raise)

    with pytest.raises(RuntimeError, match="boom"):
        _run_traffic_maintenance()

    attempts = _poll_attempts_added(db)
    assert len(attempts) == 1
    assert attempts[0].device_id is None
    assert attempts[0].job_type == PollJobType.TRAFFIC_MAINTENANCE
    assert attempts[0].status == PollAttemptStatus.FAILURE
