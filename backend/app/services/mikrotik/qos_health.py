"""Detección de colas QoS trabadas (ver services/mikrotik/qos.py).

Incidente real: después de reconstruir el árbol de colas completo dos veces
seguidas en pocos minutos (algo que la operación normal nunca hace — un
plan se monta UNA sola vez, dar de alta/baja un cliente es solo tocar un
address-list), una hoja del queue tree quedó en `rate=0` permanente sin
drenar su backlog (`queued-bytes` fijo, `dropped` creciendo) — sin nada mal
configurado. Solo un reinicio del equipo lo resolvió; no se confirmó la
causa raíz exacta dentro de RouterOS.

Esto NO previene el problema — lo detecta, para enterarse por una alerta
en vez de por un reclamo de un cliente. Una sola lectura con rate=0 puede
ser una casualidad de timing; quien llame debe confirmarlo en 2+ ciclos
seguidos antes de avisar de verdad (ver workers/poller.py).
"""

from __future__ import annotations

from typing import Any

from app.services.mikrotik import api_client

STUCK_QUEUED_BYTES_THRESHOLD = 1000


def find_stuck_queues(api: Any) -> list[str]:
    """Nombres de colas de ispmanager (prefijo `isp-`) con backlog sin
    drenar: algo encolado por encima del umbral pero velocidad de salida
    en cero ahora mismo."""
    stuck = []
    for row in api_client.get_queue_trees(api):
        name = row.get("name", "")
        if not name.startswith("isp-"):
            continue
        rate = int(row.get("rate", 0) or 0)
        queued = int(row.get("queued-bytes", 0) or 0)
        if rate == 0 and queued > STUCK_QUEUED_BYTES_THRESHOLD:
            stuck.append(name)
    return stuck
