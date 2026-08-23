"""Corte de servicio por mora vía address-list + regla de firewall.

Reemplaza el mecanismo original de "deshabilitar el secreto PPPoE": este
despliegue no usa PPPoE (clientes por IP estática — confirmado migrando los
770 contratos reales desde sequreisp_production, todos con pppoe_active
NULL), así que ese mecanismo nunca cortaba nada en la práctica.

Mismo patrón que el QoS por plan (ver qos.py): UNA regla de firewall por
equipo, creada una sola vez (idempotente — DeviceService.ensure_suspension_bootstrap
la crea sola si hace falta, no requiere un paso manual aparte como el
bootstrap de QoS). Suspender/reactivar un cliente es agregarlo o sacarlo de
esa lista — una sola llamada API, verificado contra un CCR2004 real
(RouterOS 7.24).
"""

from __future__ import annotations

from app.schemas.wan_balancing import WanCommandResult

SUSPENDED_ADDRESS_LIST = "isp-suspended-clients"
FILTER_RULE_COMMENT = "ispmanager: bloquea clientes suspendidos por mora"


def build_bootstrap_plan() -> list[WanCommandResult]:
    return [
        WanCommandResult(
            description="Bloquear tráfico de clientes suspendidos",
            path="/ip/firewall/filter/add",
            params={
                "chain": "forward",
                "src-address-list": SUSPENDED_ADDRESS_LIST,
                "action": "drop",
                "comment": FILTER_RULE_COMMENT,
            },
        )
    ]
