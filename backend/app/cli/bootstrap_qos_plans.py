"""Aplica el bootstrap de QoS (ver services/mikrotik/qos.py) a todos los
planes que tienen al menos un cliente asignado en un equipo dado.

Sin esto, un cliente "aprovisionado" (agregado al address-list de su plan,
vía POST /clients/{id}/qos/provision o el botón "Aplicar QoS" del panel)
no tiene ningún límite real — el address-list por sí solo no hace nada; lo
que shapea de verdad son las reglas mangle + queue tree que este comando
crea, UNA VEZ POR PLAN. Sin este paso el cliente queda con banda libre, sin
ningún aviso de que algo falta (visto en producción: un cliente en un plan
de 1 Mbps midió 990 Mbps porque nadie había corrido esto todavía).

Uso:
    python -m app.cli.bootstrap_qos_plans <device_id> <lan_interface> <wan_interface>
    python -m app.cli.bootstrap_qos_plans <device_id> <lan_interface> <wan_interface> --apply

Sin --apply es dry-run: solo cuenta planes/comandos, no toca el equipo.
"""

from __future__ import annotations

import sys
import uuid

from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
from app.services.mikrotik import qos
from app.services.mikrotik.device_service import DeviceService


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv[1:]
    if len(args) != 3:
        print(__doc__)
        raise SystemExit(1)
    device_id, lan_interface, wan_interface = args

    db = SessionLocal()
    device = db.get(MikrotikDevice, uuid.UUID(device_id))
    if device is None:
        print(f"Equipo {device_id} no encontrado.")
        raise SystemExit(1)

    # No se filtra por Client.mikrotik_device_id: los clientes migrados desde
    # sequreisp_production no tienen equipo asignado todavía (a propósito,
    # no había forma segura de mapearlo automático — ver migrate_from_sequreisp.py).
    # Como hoy solo hay un equipo registrado, se bootstrapean acá los planes
    # de CUALQUIER cliente; cuando haya más de un equipo, este comando va a
    # necesitar ese filtro de vuelta.
    plan_ids_in_use = {row[0] for row in db.query(Client.plan_id).filter(Client.plan_id.isnot(None)).distinct()}
    plans = db.query(Plan).filter(Plan.id.in_(plan_ids_in_use)).order_by(Plan.name).all()
    print(f"=== Bootstrap QoS en {device.name} ({'APLICANDO' if apply else 'DRY-RUN'}) ===")
    print(f"Planes con al menos un cliente (cualquier equipo): {len(plans)}")

    if not apply:
        total_commands = 0
        for plan in plans:
            commands = qos.build_plan_bootstrap_plan(plan, lan_interface, wan_interface)
            total_commands += len(commands)
            print(f"  - {plan.name}: {len(commands)} comandos")
        print(f"\nTotal: {total_commands} comandos. Corré con --apply para aplicar de verdad.")
        return

    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)

    ok, failed = 0, []
    for plan in plans:
        commands = qos.build_plan_bootstrap_plan(plan, lan_interface, wan_interface)
        results = service.apply_command_plan(commands, dry_run=False)
        errors = [r for r in results if not r.executed]
        if errors:
            failed.append((plan.name, errors[0].error))
            print(f"  FALLO: {plan.name} -> {errors[0].error}")
        else:
            ok += 1
            print(f"  OK: {plan.name} ({len(results)} comandos)")

    print(f"\n{ok} planes aplicados OK, {len(failed)} fallaron.")
    if failed:
        print("Planes con error (revisar y reintentar):")
        for name, error in failed:
            print(f"  - {name}: {error}")


if __name__ == "__main__":
    main()
