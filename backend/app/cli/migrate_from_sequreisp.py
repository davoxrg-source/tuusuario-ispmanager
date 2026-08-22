"""Migra clientes/contratos/planes desde el sistema legacy (sequreisp_production,
MySQL en wisprosvr01) hacia esta base de ispmanager.

Alcance deliberado: solo datos OPERATIVOS — planes y clientes (cada contrato
legacy pasa a ser un Client acá, con su plan e IP). NO migra facturas ni
pagos históricos — queda para una segunda etapa una vez validado esto.

Uso:
    python -m app.cli.migrate_from_sequreisp              # dry-run: arma todo, no guarda nada
    python -m app.cli.migrate_from_sequreisp --apply       # escribe de verdad

Requiere el host SSH "wispro" (ver ~/.ssh/config) alcanzable, con acceso de
lectura a la base MySQL `sequreisp_production` en ese servidor (mismo
mecanismo ya usado para administrarlo: `ssh wispro mysql ...`). El SQL se
manda por stdin (no como argumento de shell) para no depender de escapado de
comillas, y cada fila se arma como una sola columna separada por el byte
0x1F (unit separator) para blindarse contra tabs/saltos de línea dentro de
los datos (nombres, direcciones).

Idempotente: cada plan/cliente importado queda vinculado a su id legacy
(Plan.legacy_plan_id / Client.legacy_contract_id) — correr el script de
nuevo ACTUALIZA los registros ya importados en vez de duplicarlos.

Cada contrato legacy se convierte en UN Client de ispmanager, porque el
modelo de datos de ispmanager asocia un plan y una IP por cliente, no por
contrato (a diferencia del legacy, que separaba `clients` de `contracts`).
Los ~9 clientes legacy con más de un contrato activo quedan como más de un
Client acá, uno por servicio — es la representación correcta dado el modelo
actual, no un error de este script.

No imprime PII (nombres, emails, teléfonos, direcciones) — solo conteos e
ids, para que sea seguro correrlo con la salida a la vista de cualquiera.
"""

from __future__ import annotations

import subprocess
import sys
import uuid

from app.db.session import SessionLocal
from app.models.client import Client, ClientStatus
from app.models.plan import Plan

SSH_HOST = "wispro"
FIELD_SEP = "\x1f"


class MigrationError(Exception):
    pass


def _ssh_query(query: str) -> list[list[str]]:
    """Corre `query` contra sequreisp_production en SSH_HOST vía stdin y
    devuelve las filas ya separadas por columna. Cada columna del SELECT
    debe venir armada con CONCAT_WS(0x1f, ...) para que la fila entera sea
    una sola columna de salida — así una fila == una línea, siempre."""
    try:
        result = subprocess.run(
            ["ssh", SSH_HOST, "mysql -N sequreisp_production"],
            input=query.encode("utf-8"),
            capture_output=True,
            timeout=60,
        )
    except FileNotFoundError as exc:
        raise MigrationError("No se encontró el comando 'ssh' en este sistema.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MigrationError(f"Timeout consultando {SSH_HOST} (60s).") from exc
    if result.returncode != 0:
        raise MigrationError(f"Fallo la consulta en {SSH_HOST}: {result.stderr.decode(errors='replace')}")
    lines = result.stdout.decode("utf-8", errors="replace").splitlines()
    return [line.split(FIELD_SEP) for line in lines if line]


def _clean(value: str) -> str | None:
    value = value.strip()
    if not value or value == "NULL":
        return None
    return value


def _kbit_to_mbps(raw: str) -> int:
    kbit = int(raw)
    return max(1, round(kbit / 1024))


def migrate_plans(db) -> dict[int, uuid.UUID]:
    rows = _ssh_query(
        "SELECT CONCAT_WS(0x1f, id, name, ceil_down, ceil_up, price_cents, price_currency) "
        "FROM plans ORDER BY id;"
    )
    print(f"Planes encontrados en sequreisp_production: {len(rows)}")

    plan_id_map: dict[int, uuid.UUID] = {}
    created = updated = 0
    for legacy_id, name, ceil_down, ceil_up, price_cents, price_currency in rows:
        legacy_id_int = int(legacy_id)
        plan = db.query(Plan).filter(Plan.legacy_plan_id == legacy_id_int).first()
        if plan is None:
            plan = Plan(legacy_plan_id=legacy_id_int)
            db.add(plan)
            created += 1
        else:
            updated += 1

        plan.name = name
        plan.download_speed_mbps = _kbit_to_mbps(ceil_down)
        plan.upload_speed_mbps = _kbit_to_mbps(ceil_up)
        plan.price = int(price_cents) / 100
        plan.currency = price_currency or "USD"
        # guaranteed_floor_percent NO se pisa: si ya existe, puede que se
        # haya ajustado a mano en ispmanager; si es nuevo, se queda con el
        # default del modelo (9%, el mismo piso que tenía el legacy).

        db.flush()  # asigna plan.id aunque todavía no se haga commit
        plan_id_map[legacy_id_int] = plan.id

    print(f"  -> {created} nuevos, {updated} actualizados.")
    return plan_id_map


def migrate_clients(db, plan_id_map: dict[int, uuid.UUID]) -> None:
    rows = _ssh_query(
        "SELECT CONCAT_WS(0x1f, "
        "  c.id, c.plan_id, c.ip, c.state, "
        "  REPLACE(cl.name, '\\n', ' '), "
        "  REPLACE(COALESCE(cl.email,''), '\\n', ' '), "
        "  REPLACE(COALESCE(cl.phone,''), '\\n', ' '), "
        "  REPLACE(COALESCE(cl.phone_mobile,''), '\\n', ' '), "
        "  REPLACE(COALESCE(cl.address,''), '\\n', ' '), "
        "  REPLACE(COALESCE(cl.national_identification_number,''), '\\n', ' '), "
        "  REPLACE(COALESCE(cl.taxpayer_identification_number,''), '\\n', ' ') "
        ") FROM contracts c JOIN clients cl ON cl.id = c.client_id ORDER BY c.id;"
    )
    print(f"Contratos encontrados en sequreisp_production: {len(rows)}")

    created = updated = skipped_no_plan = 0
    for (
        contract_id, legacy_plan_id, ip, state,
        name, email, phone, phone_mobile, address,
        national_id, taxpayer_id,
    ) in rows:
        contract_id_int = int(contract_id)
        plan_uuid = plan_id_map.get(int(legacy_plan_id))
        if plan_uuid is None:
            # No debería pasar (se verificó que no hay contratos sin plan_id
            # antes de escribir este script), pero no se asume — se salta y
            # se avisa en vez de fallar toda la migración por un caso raro.
            print(f"  AVISO: contrato legacy #{contract_id_int} referencia un plan_id "
                  f"que no se pudo migrar ({legacy_plan_id}) — se salta.")
            skipped_no_plan += 1
            continue

        client = db.query(Client).filter(Client.legacy_contract_id == contract_id_int).first()
        if client is None:
            client = Client(legacy_contract_id=contract_id_int)
            db.add(client)
            created += 1
        else:
            updated += 1

        client.full_name = name
        client.email = _clean(email)
        client.phone = _clean(phone) or _clean(phone_mobile)
        client.address = _clean(address)
        client.identification = _clean(national_id) or _clean(taxpayer_id)
        client.plan_id = plan_uuid
        client.ip_address = _clean(ip)
        client.status = ClientStatus.ACTIVE if state == "enabled" else ClientStatus.SUSPENDED

        try:
            db.flush()  # falla acá, con el contrato identificado, no en un commit de 770 filas
        except Exception as exc:  # noqa: BLE001
            raise MigrationError(
                f"Contrato legacy #{contract_id_int}: {exc}"
            ) from exc
        # mikrotik_device_id y pppoe_* quedan sin tocar deliberadamente: no
        # hay forma segura de mapear automáticamente a un equipo real
        # registrado en ispmanager, y este despliegue de sequreisp no usa
        # PPPoE (pppoe_active es NULL en los 770 contratos). Se asignan a
        # mano desde el panel.

    print(f"  -> {created} nuevos, {updated} actualizados"
          + (f", {skipped_no_plan} saltados por plan faltante" if skipped_no_plan else "") + ".")


def main() -> None:
    apply = "--apply" in sys.argv[1:]
    print(f"=== Migración sequreisp_production -> ispmanager ({'APLICANDO' if apply else 'DRY-RUN'}) ===")

    db = SessionLocal()
    try:
        plan_id_map = migrate_plans(db)
        migrate_clients(db, plan_id_map)

        if apply:
            db.commit()
            print("\nGuardado.")
        else:
            db.rollback()
            print("\nDRY-RUN: no se guardó nada. Corré con --apply para aplicar de verdad.")
    except MigrationError as exc:
        db.rollback()
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
