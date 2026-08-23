from app.services.mikrotik import qos_health

# Incidente real: una hoja del queue tree quedó en rate=0 permanente con
# backlog sin drenar, sin nada mal configurado -- solo un reinicio del
# equipo lo resolvió. Esto detecta el síntoma (no lo previene).


class FakeApi:
    def __init__(self, rows):
        self.rows = rows

    def __call__(self, cmd, **kwargs):
        assert cmd == "/queue/tree/print"
        return iter(self.rows)


def test_find_stuck_queues_flags_zero_rate_with_backlog():
    api = FakeApi([
        {"name": "isp-abc-down-bulk", "rate": "0", "queued-bytes": "64509"},
        {"name": "isp-abc-down-rt", "rate": "4328", "queued-bytes": "0"},
    ])
    assert qos_health.find_stuck_queues(api) == ["isp-abc-down-bulk"]


def test_find_stuck_queues_ignores_idle_queue_with_no_backlog():
    # rate=0 solo, sin nada encolado -- no hay tráfico, no está trabada.
    api = FakeApi([{"name": "isp-abc-up-prio", "rate": "0", "queued-bytes": "0"}])
    assert qos_health.find_stuck_queues(api) == []


def test_find_stuck_queues_ignores_tiny_transient_backlog():
    api = FakeApi([{"name": "isp-abc-down-bulk", "rate": "0", "queued-bytes": "10"}])
    assert qos_health.find_stuck_queues(api) == []


def test_find_stuck_queues_ignores_non_ispmanager_queues():
    api = FakeApi([{"name": "default-queue", "rate": "0", "queued-bytes": "999999"}])
    assert qos_health.find_stuck_queues(api) == []


def test_find_stuck_queues_ignores_queue_actively_draining():
    # Backlog alto pero rate>0 -- está fluyendo, no trabada.
    api = FakeApi([{"name": "isp-abc-up-bulk", "rate": "2934032", "queued-bytes": "39366"}])
    assert qos_health.find_stuck_queues(api) == []
