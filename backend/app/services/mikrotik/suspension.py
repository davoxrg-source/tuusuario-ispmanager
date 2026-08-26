"""Corte de servicio por mora vía address-list + regla de firewall.

Reemplaza el mecanismo original de "deshabilitar el secreto PPPoE": este
despliegue no usa PPPoE (clientes por IP estática — confirmado migrando los
770 contratos reales desde sequreisp_production, todos con pppoe_active
NULL), así que ese mecanismo nunca cortaba nada en la práctica.

Mismo patrón que el QoS por plan (ver qos.py): reglas de firewall por
equipo, creadas una sola vez (idempotente — DeviceService.ensure_suspension_bootstrap
las crea solas si hace falta, no requiere un paso manual aparte como el
bootstrap de QoS). Suspender/reactivar un cliente es agregarlo o sacarlo de
esa lista — una sola llamada API, verificado contra un CCR2004 real
(RouterOS 7.24).

Además del drop silencioso, el bootstrap agrega una redirección DNAT del
tráfico HTTP (puerto 80) de los suspendidos hacia un servidor de aviso
dedicado (ver app/cli/suspension_notice_server.py) -- HTTPS no se puede
interceptar de forma confiable sin un certificado falso, así que ese
tráfico sigue cayendo en el drop silencioso de siempre.

Gotchas reales, encontrados al probar en vivo contra el CCR2004 (2, no 1):

1. El drop bloqueaba TODO el tráfico del suspendido, incluido DNS -- sin
   poder resolver el nombre del sitio, el navegador nunca llega a intentar
   la conexión HTTP que dispara el aviso. Se agrega una regla ANTES del
   drop (place-before) que deja pasar DNS (UDP 53) de los suspendidos.

2. Con DNS ya permitido, el DNAT del aviso sí reescribía el destino del
   paquete HTTP -- pero el drop sigue evaluándose DESPUÉS del DNAT (orden
   real de RouterOS: prerouting/dstnat primero, forward filter después), y
   el drop matchea por IP de ORIGEN, no de destino -- así que el paquete ya
   redirigido caía en el mismo drop igual, confirmado con los contadores
   (el DNAT sí incrementaba, pero el aviso nunca llegaba a cargar). Se
   agrega una segunda regla ANTES del drop que acepta explícitamente el
   tráfico ya redirigido hacia el servidor de aviso (dst-address/dst-port
   del servidor, después del DNAT).

3. Con DNS y el accept ya andando, la conexión TCP igual se quedaba en
   syn-sent para siempre (confirmado con /ip/firewall/connection/print: el
   conntrack mostraba reply-src-address=<server del aviso> correctamente,
   pero seen-reply=False). Causa: el servidor del aviso y el cliente
   suspendido están en la MISMA red L2 (el mismo /21 plano) -- la respuesta
   del servidor sale directo por ARP hacia el cliente, sin volver a pasar
   por el router para deshacer el DNAT, así que el cliente recibe una
   respuesta que no coincide con la conexión que abrió (esperaba una
   respuesta del sitio original, no del servidor del aviso) y la descarta
   (hairpin NAT clásico). Se agrega una regla de srcnat/masquerade
   específica para el tráfico ya redirigido al aviso, para que la
   respuesta tenga que volver a pasar por el router y se deshaga el NAT
   correctamente en el camino de vuelta.

El resto del tráfico de un suspendido (todo lo que no sea DNS o el propio
aviso) sigue cortado exactamente igual que antes.
"""

from __future__ import annotations

from app.schemas.wan_balancing import WanCommandResult

SUSPENDED_ADDRESS_LIST = "isp-suspended-clients"
FILTER_RULE_COMMENT = "ispmanager: bloquea clientes suspendidos por mora"
NOTICE_RULE_COMMENT = "ispmanager: aviso de suspension"  # sin tilde -- librouteros solo manda ASCII
DNS_ACCEPT_RULE_COMMENT = "ispmanager: permite DNS a suspendidos para ver el aviso"
NOTICE_ACCEPT_RULE_COMMENT = "ispmanager: permite el trafico redirigido al aviso"
NOTICE_SRCNAT_RULE_COMMENT = "ispmanager: hairpin NAT para el aviso de suspension"


def build_drop_rule() -> WanCommandResult:
    return WanCommandResult(
        description="Bloquear tráfico de clientes suspendidos",
        path="/ip/firewall/filter/add",
        params={
            "chain": "forward",
            "src-address-list": SUSPENDED_ADDRESS_LIST,
            "action": "drop",
            "comment": FILTER_RULE_COMMENT,
        },
    )


def build_dns_accept_rule(place_before_id: str | None = None) -> WanCommandResult:
    params = {
        "chain": "forward",
        "src-address-list": SUSPENDED_ADDRESS_LIST,
        "protocol": "udp",
        "dst-port": "53",
        "action": "accept",
        "comment": DNS_ACCEPT_RULE_COMMENT,
    }
    if place_before_id:
        params["place-before"] = place_before_id
    return WanCommandResult(
        description="Permitir DNS a clientes suspendidos (para que vean el aviso)",
        path="/ip/firewall/filter/add",
        params=params,
    )


def build_notice_accept_rule(
    notice_server_ip: str, notice_server_port: int = 8095, place_before_id: str | None = None
) -> WanCommandResult:
    """Acepta el tráfico ya redirigido por el DNAT del aviso -- necesaria
    porque el drop evalúa por IP de ORIGEN (el suspendido), no de destino,
    así que sin esta regla el paquete ya reescrito cae en el mismo drop."""
    params = {
        "chain": "forward",
        "src-address-list": SUSPENDED_ADDRESS_LIST,
        "dst-address": notice_server_ip,
        "dst-port": str(notice_server_port),
        "protocol": "tcp",
        "action": "accept",
        "comment": NOTICE_ACCEPT_RULE_COMMENT,
    }
    if place_before_id:
        params["place-before"] = place_before_id
    return WanCommandResult(
        description="Permitir tráfico redirigido hacia el aviso de suspensión",
        path="/ip/firewall/filter/add",
        params=params,
    )


def build_notice_rule(notice_server_ip: str, notice_server_port: int = 8095) -> WanCommandResult:
    return WanCommandResult(
        description="Redirigir HTTP de suspendidos al aviso de suspensión",
        path="/ip/firewall/nat/add",
        params={
            "chain": "dstnat",
            "src-address-list": SUSPENDED_ADDRESS_LIST,
            "protocol": "tcp",
            "dst-port": "80",
            "action": "dst-nat",
            "to-addresses": notice_server_ip,
            "to-ports": str(notice_server_port),
            "comment": NOTICE_RULE_COMMENT,
        },
    )


def build_notice_srcnat_rule(notice_server_ip: str, notice_server_port: int = 8095) -> WanCommandResult:
    """Hairpin NAT: enmascara también el ORIGEN del tráfico ya redirigido
    al aviso, para que la respuesta del servidor tenga que volver a pasar
    por el router (y ahí se deshaga el DNAT correctamente) en vez de irse
    directo por ARP al cliente -- ver gotcha 3 arriba. Distinto out-interface
    que el masquerade general (que solo matchea out-interface=ether2), así
    que no hace falta ningún orden particular entre las dos reglas."""
    return WanCommandResult(
        description="Hairpin NAT para el tráfico redirigido al aviso de suspensión",
        path="/ip/firewall/nat/add",
        params={
            "chain": "srcnat",
            "src-address-list": SUSPENDED_ADDRESS_LIST,
            "dst-address": notice_server_ip,
            "dst-port": str(notice_server_port),
            "protocol": "tcp",
            "action": "masquerade",
            "comment": NOTICE_SRCNAT_RULE_COMMENT,
        },
    )


def build_bootstrap_plan(notice_server_ip: str, notice_server_port: int = 8095) -> list[WanCommandResult]:
    """Orden correcto para un equipo sin ninguna de las 5 reglas todavía --
    las 2 reglas de accept antes que el drop, sin necesitar place-before
    (el orden natural de agregado ya las deja bien ordenadas)."""
    return [
        build_dns_accept_rule(),
        build_notice_accept_rule(notice_server_ip, notice_server_port),
        build_drop_rule(),
        build_notice_rule(notice_server_ip, notice_server_port),
        build_notice_srcnat_rule(notice_server_ip, notice_server_port),
    ]
