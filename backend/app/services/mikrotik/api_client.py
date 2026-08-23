"""Wrapper delgado sobre librouteros (API binaria RouterOS, puertos 8728/8729)."""

from __future__ import annotations

import ssl
from contextlib import contextmanager
from typing import Any, Iterator

from librouteros import connect
from librouteros.exceptions import TrapError, FatalError, ConnectionClosed


class RouterOsApiError(Exception):
    pass


@contextmanager
def api_connection(
    host: str,
    username: str,
    password: str,
    port: int = 8728,
    use_tls: bool = False,
    timeout: float = 8.0,
) -> Iterator[Any]:
    """Abre una conexión API RouterOS y la cierra al salir del bloque `with`."""
    kwargs: dict[str, Any] = {
        "host": host,
        "username": username,
        "password": password,
        "port": port,
        "timeout": timeout,
    }
    if use_tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_wrapper"] = ctx.wrap_socket

    try:
        api = connect(**kwargs)
    except (TrapError, FatalError, ConnectionClosed, OSError) as exc:
        raise RouterOsApiError(str(exc)) from exc

    try:
        yield api
    except (TrapError, FatalError, ConnectionClosed) as exc:
        raise RouterOsApiError(str(exc)) from exc
    finally:
        try:
            api.close()
        except Exception:
            pass


def get_identity(api: Any) -> str:
    rows = list(api("/system/identity/print"))
    return rows[0]["name"] if rows else ""


def get_system_resource(api: Any) -> dict[str, Any]:
    rows = list(api("/system/resource/print"))
    return rows[0] if rows else {}


def get_interfaces(api: Any) -> list[dict[str, Any]]:
    return list(api("/interface/print"))


def get_active_ppp_sessions(api: Any) -> list[dict[str, Any]]:
    return list(api("/ppp/active/print"))


def list_ppp_secrets(api: Any) -> list[dict[str, Any]]:
    return list(api("/ppp/secret/print"))


def find_ppp_secret_id(api: Any, pppoe_username: str) -> str | None:
    for row in list_ppp_secrets(api):
        if row.get("name") == pppoe_username:
            return row.get(".id")
    return None


def create_ppp_secret(
    api: Any,
    name: str,
    password: str,
    profile: str | None = None,
    service: str = "pppoe",
) -> None:
    kwargs: dict[str, Any] = {"name": name, "password": password, "service": service}
    if profile:
        kwargs["profile"] = profile
    list(api("/ppp/secret/add", **kwargs))


def set_ppp_secret_enabled(api: Any, pppoe_username: str, enabled: bool) -> bool:
    secret_id = find_ppp_secret_id(api, pppoe_username)
    if secret_id is None:
        return False
    list(api("/ppp/secret/set", **{".id": secret_id, "disabled": "no" if enabled else "yes"}))
    return True


def remove_ppp_secret(api: Any, pppoe_username: str) -> bool:
    secret_id = find_ppp_secret_id(api, pppoe_username)
    if secret_id is None:
        return False
    list(api("/ppp/secret/remove", **{".id": secret_id}))
    return True


def reboot(api: Any) -> None:
    list(api("/system/reboot"))


def get_ip_addresses(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/address/print"))


def get_arp_entries(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/arp/print"))


def add_ip_address(api: Any, interface: str, address: str) -> None:
    list(api("/ip/address/add", address=address, interface=interface))


def remove_ip_address(api: Any, address_id: str) -> None:
    list(api("/ip/address/remove", **{".id": address_id}))


def get_bridges(api: Any) -> list[dict[str, Any]]:
    return list(api("/interface/bridge/print"))


def create_bridge(api: Any, name: str) -> None:
    list(api("/interface/bridge/add", name=name))


def remove_bridge(api: Any, bridge_id: str) -> None:
    list(api("/interface/bridge/remove", **{".id": bridge_id}))


def get_bridge_ports(api: Any) -> list[dict[str, Any]]:
    return list(api("/interface/bridge/port/print"))


def add_bridge_port(api: Any, bridge: str, interface: str) -> None:
    list(api("/interface/bridge/port/add", bridge=bridge, interface=interface))


def remove_bridge_port(api: Any, port_id: str) -> None:
    list(api("/interface/bridge/port/remove", **{".id": port_id}))


def setup_pppoe_server(
    api: Any,
    interface: str,
    service_name: str,
    pool_start: str,
    pool_end: str,
    profile_name: str,
    local_address: str,
) -> None:
    """Alta básica de un servidor PPPoE: pool de IPs + perfil PPP + instancia
    del servidor, en ese orden (cada uno depende del anterior)."""
    pool_name = f"{profile_name}-pool"
    list(api("/ip/pool/add", name=pool_name, ranges=f"{pool_start}-{pool_end}"))
    list(
        api(
            "/ppp/profile/add",
            name=profile_name,
            **{"local-address": local_address, "remote-address": pool_name},
        )
    )
    list(
        api(
            "/interface/pppoe-server/server/add",
            interface=interface,
            **{"service-name": service_name, "default-profile": profile_name, "disabled": "no"},
        )
    )


# --- Balanceo/failover multi-WAN (PCC + routing-table de RouterOS 7.x) ---
# Sintaxis verificada contra un CCR2004 real (RouterOS 7.24) creando y
# borrando de inmediato una tabla/ruta/regla de prueba antes de escribir
# este módulo. En RouterOS 7 el antiguo "routing-mark" de las rutas pasó a
# llamarse "routing-table" y ahora es un objeto que hay que crear primero
# con /routing/table/add; el parámetro del lado de mangle (mark-routing)
# sigue llamándose "new-routing-mark" sin cambios.


def get_routing_tables(api: Any) -> list[dict[str, Any]]:
    return list(api("/routing/table/print"))


def enable_traffic_flow(api: Any, target_address: str, target_port: int) -> None:
    """Habilita el export NetFlow v5 del equipo hacia el colector de
    ispmanager (ver services/netflow/collector.py). Idempotente: si ya
    existe un target con esa IP:puerto no agrega uno duplicado.

    Sintaxis verificada contra un CCR2004 real (RouterOS 7.24): el parámetro
    se llama "dst-address", no "address" (falla con "unknown parameter
    address"); y el target por defecto queda en NetFlow v9 si no se fija
    "version" explícitamente -- el colector solo entiende v5 (formato fijo,
    mucho más simple de parsear que el v9 basado en templates), así que acá
    se fuerza version=5 siempre."""
    list(api("/ip/traffic-flow/set", enabled="yes"))
    for row in api("/ip/traffic-flow/target/print"):
        if row.get("dst-address") == target_address and str(row.get("port")) == str(target_port):
            return
    list(
        api(
            "/ip/traffic-flow/target/add",
            **{"dst-address": target_address, "port": str(target_port), "version": "5"},
        )
    )


def create_routing_table(api: Any, name: str) -> None:
    list(api("/routing/table/add", name=name, fib=""))


def remove_routing_table(api: Any, table_id: str) -> None:
    list(api("/routing/table/remove", **{".id": table_id}))


def get_mangle_rules(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/firewall/mangle/print"))


def add_mangle_protect_local_traffic(api: Any, in_interface: str) -> None:
    """Excluye del balanceo PCC el tráfico destinado al propio equipo
    (gestión: API/SSH/Winbox/Webfig), sin importar por cuál IP se le
    administre. Sin esta regla, si la interfaz LAN elegida es la misma por
    la que se gestiona el equipo, la propia sesión de administración queda
    marcada y enrutada por una tabla de WAN — y si esa WAN no tiene camino
    de vuelta, el equipo se vuelve inalcanzable (visto en un incidente real:
    ver device_service.build_wan_balancing_plan)."""
    list(
        api(
            "/ip/firewall/mangle/add",
            chain="prerouting",
            action="accept",
            **{"in-interface": in_interface, "dst-address-type": "local"},
        )
    )


def add_mangle_mark_connection_pcc(
    api: Any, in_interface: str, classifier: str, connection_mark: str
) -> None:
    list(
        api(
            "/ip/firewall/mangle/add",
            chain="prerouting",
            **{
                "in-interface": in_interface,
                "connection-mark": "no-mark",
                "per-connection-classifier": classifier,
                "action": "mark-connection",
                "new-connection-mark": connection_mark,
                "passthrough": "yes",
            },
        )
    )


def add_mangle_mark_routing_from_connection(
    api: Any, connection_mark: str, routing_mark: str
) -> None:
    list(
        api(
            "/ip/firewall/mangle/add",
            chain="prerouting",
            **{
                "connection-mark": connection_mark,
                "action": "mark-routing",
                "new-routing-mark": routing_mark,
                "passthrough": "no",
            },
        )
    )


def add_mangle_mark_routing_by_source(api: Any, src_address: str, routing_mark: str) -> None:
    """Fija de forma determinística un bloque de IP pública a una WAN
    específica (para clientes con IP pública por Proxy ARP) — se agrega
    ANTES de las reglas PCC para que esas conexiones nunca entren al hash."""
    list(
        api(
            "/ip/firewall/mangle/add",
            chain="prerouting",
            **{
                "src-address": src_address,
                "action": "mark-routing",
                "new-routing-mark": routing_mark,
                "passthrough": "no",
            },
        )
    )


def remove_mangle_rule(api: Any, rule_id: str) -> None:
    list(api("/ip/firewall/mangle/remove", **{".id": rule_id}))


def get_routes(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/route/print"))


def add_route(
    api: Any,
    gateway: str,
    routing_table: str | None = None,
    distance: int = 1,
    check_gateway: str = "ping",
) -> None:
    kwargs: dict[str, Any] = {
        "gateway": gateway,
        "distance": str(distance),
        "check-gateway": check_gateway,
    }
    if routing_table:
        kwargs["routing-table"] = routing_table
    list(api("/ip/route/add", **kwargs))


def remove_route(api: Any, route_id: str) -> None:
    list(api("/ip/route/remove", **{".id": route_id}))


def get_nat_rules(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/firewall/nat/print"))


def add_nat_masquerade(api: Any, out_interface: str) -> None:
    list(
        api(
            "/ip/firewall/nat/add",
            chain="srcnat",
            action="masquerade",
            **{"out-interface": out_interface},
        )
    )


def remove_nat_rule(api: Any, nat_id: str) -> None:
    list(api("/ip/firewall/nat/remove", **{".id": nat_id}))


# --- Aprovisionamiento de conexión WAN (DHCP / PPPoE) ---
# Verificado contra un CCR2004 real (RouterOS 7.24): dhcp-client acepta
# apuntar su ruta por defecto a tablas custom vía "default-route-tables"
# (no "routing-table"); pppoe-client NO tiene ese parámetro — para PPPoE
# el resto del plan agrega la ruta a mano usando el nombre de la interfaz
# PPPoE resultante como gateway (es un enlace punto a punto, sin IP de
# gateway). Ver device_service.build_wan_balancing_plan.


def get_dhcp_clients(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/dhcp-client/print"))


def add_dhcp_client(api: Any, interface: str, routing_tables: list[str]) -> None:
    list(
        api(
            "/ip/dhcp-client/add",
            interface=interface,
            **{
                "add-default-route": "yes",
                "default-route-tables": ",".join(routing_tables),
                "disabled": "no",
            },
        )
    )


def get_pppoe_clients(api: Any) -> list[dict[str, Any]]:
    return list(api("/interface/pppoe-client/print"))


def add_pppoe_client(
    api: Any,
    interface: str,
    client_name: str,
    username: str,
    password: str,
    service_name: str | None = None,
) -> None:
    kwargs: dict[str, Any] = {
        "interface": interface,
        "name": client_name,
        "user": username,
        "password": password,
        "add-default-route": "no",
        "disabled": "no",
    }
    if service_name:
        kwargs["service-name"] = service_name
    list(api("/interface/pppoe-client/add", **kwargs))


# --- QoS: marcado de tráfico por nivel (mangle), pools de clientes por plan
# (address-list) y colas compartidas por plan con PCQ ---
# Ver app/services/mikrotik/qos.py para el diseño completo. Reemplaza el
# shaping legacy de wisprosvr01/SequreISP (HFSC en Linux, un árbol de
# objetos por cliente — la causa real de los crashes de kernel que motivaron
# este reemplazo).
#
# IMPORTANTE — verificado contra un CCR2004 real (RouterOS 7.24, ver
# tests/test_qos.py y la verificación registrada en la conversación de
# diseño): `/queue/tree` NO acepta `dst-address`/`src-address` como
# parámetro ("unknown parameter dst-address") — a diferencia de lo que un
# primer diseño asumió por analogía con Linux tc. El filtrado por cliente
# tiene que resolverse en el mangle (address-list) + PCQ (pcq-classifier),
# nunca en el queue tree directamente. Por eso el diseño es por PLAN, no por
# cliente: address-list + reglas mangle + PCQ + queue tree se crean UNA VEZ
# POR PLAN (no por cliente); dar de alta/baja un cliente es agregarlo o
# sacarlo del address-list de su plan — una sola llamada API, sin crear
# ningún objeto nuevo.


def get_address_lists(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/firewall/address-list/print"))


def find_address_list_entry_id(api: Any, list_name: str, address: str) -> str | None:
    for row in get_address_lists(api):
        if row.get("list") == list_name and row.get("address") == address:
            return row.get(".id")
    return None


def add_address_list_entry(api: Any, list_name: str, address: str, comment: str | None = None) -> None:
    """Idempotente: si la IP ya está en esta lista (ej. el cliente ya estaba
    aprovisionado, o se hizo doble clic en el panel), no hace nada — RouterOS
    rechaza un /add duplicado con "failure: already have such entry" y sin
    este chequeo esa acción, pensada para poder repetirse sin drama, fallaba."""
    if find_address_list_entry_id(api, list_name, address) is not None:
        return
    params: dict[str, str] = {"list": list_name, "address": address}
    if comment:
        params["comment"] = comment
    list(api("/ip/firewall/address-list/add", **params))


def remove_address_list_entry(api: Any, list_name: str, address: str) -> bool:
    entry_id = find_address_list_entry_id(api, list_name, address)
    if entry_id is None:
        return False
    list(api("/ip/firewall/address-list/remove", **{".id": entry_id}))
    return True


def get_queue_types(api: Any) -> list[dict[str, Any]]:
    return list(api("/queue/type/print"))


def find_queue_type_id_by_name(api: Any, name: str) -> str | None:
    for row in get_queue_types(api):
        if row.get("name") == name:
            return row.get(".id")
    return None


def add_pcq_queue_type(
    api: Any, name: str, rate_kbps: int, classifier: str, pcq_limit: int = 50
) -> None:
    """`classifier` es 'dst-address' (descarga: separa por IP destino, la del
    cliente) o 'src-address' (subida: separa por IP origen). `rate_kbps` es
    el techo POR CLIENTE dentro de este pool — normalmente el ceil del plan."""
    list(
        api(
            "/queue/type/add",
            name=name,
            kind="pcq",
            **{
                "pcq-rate": f"{rate_kbps}k",
                "pcq-classifier": classifier,
                "pcq-limit": str(pcq_limit),
            },
        )
    )


def remove_queue_type_by_name(api: Any, name: str) -> bool:
    type_id = find_queue_type_id_by_name(api, name)
    if type_id is None:
        return False
    list(api("/queue/type/remove", **{".id": type_id}))
    return True


def get_mangle_rule_by_comment(api: Any, comment: str) -> dict[str, Any] | None:
    for row in get_mangle_rules(api):
        if row.get("comment") == comment:
            return row
    return None


def add_mangle_mark_connection(
    api: Any,
    chain: str,
    new_connection_mark: str,
    comment: str,
    match: dict[str, str] | None = None,
    connection_mark: str = "no-mark",
) -> None:
    """Marca la CONEXIÓN (no cada paquete) la primera vez que matchea — el
    resto de los paquetes de esa conexión se reconocen después por
    connection-mark sin volver a evaluar el criterio (packet-size, puerto,
    etc.), que es lo caro. `match` son condiciones adicionales del chain
    (protocol, port, packet-size, etc.), tal cual las espera la API."""
    params: dict[str, str] = {
        "chain": chain,
        "connection-mark": connection_mark,
        "action": "mark-connection",
        "new-connection-mark": new_connection_mark,
        "passthrough": "yes",
        "comment": comment,
    }
    params.update(match or {})
    list(api("/ip/firewall/mangle/add", **params))


def add_mangle_mark_packet_from_connection(
    api: Any, chain: str, connection_mark: str, new_packet_mark: str, comment: str
) -> None:
    list(
        api(
            "/ip/firewall/mangle/add",
            chain=chain,
            **{
                "connection-mark": connection_mark,
                "action": "mark-packet",
                "new-packet-mark": new_packet_mark,
                "passthrough": "no",
                "comment": comment,
            },
        )
    )


def get_queue_trees(api: Any) -> list[dict[str, Any]]:
    return list(api("/queue/tree/print"))


def find_queue_tree_id_by_name(api: Any, name: str) -> str | None:
    for row in get_queue_trees(api):
        if row.get("name") == name:
            return row.get(".id")
    return None


def add_queue_tree(
    api: Any,
    name: str,
    parent: str,
    max_limit_kbps: int,
    packet_mark: str | None = None,
    queue_type: str | None = None,
    limit_at_kbps: int | None = None,
    priority: int = 8,
) -> None:
    """`parent` es una interfaz real (nodo raíz) o el nombre de otro queue
    tree (nodo hijo) — nunca una IP: `/queue/tree` no tiene forma de filtrar
    por dirección directamente (verificado contra un CCR2004 real, RouterOS
    7.24: rechaza dst-address/src-address con "unknown parameter"). El
    filtrado por cliente va en `queue_type` (un /queue/type kind=pcq con
    pcq-classifier=dst-address o src-address, ver add_pcq_queue_type) y/o en
    `packet_mark` (puesto en mangle vía address-list, ver qos.py)."""
    params: dict[str, str] = {
        "name": name,
        "parent": parent,
        "max-limit": f"{max_limit_kbps}k",
        "priority": str(priority),
    }
    if limit_at_kbps is not None:
        params["limit-at"] = f"{limit_at_kbps}k"
    if packet_mark:
        params["packet-mark"] = packet_mark
    if queue_type:
        params["queue"] = queue_type
    list(api("/queue/tree/add", **params))


def remove_queue_tree(api: Any, queue_tree_id: str) -> None:
    list(api("/queue/tree/remove", **{".id": queue_tree_id}))


def remove_queue_tree_by_name(api: Any, name: str) -> bool:
    tree_id = find_queue_tree_id_by_name(api, name)
    if tree_id is None:
        return False
    remove_queue_tree(api, tree_id)
    return True


# --- Corte por mora (address-list + regla de firewall) ---
# Ver app/services/mikrotik/suspension.py para el diseño. Verificado contra
# un CCR2004 real (RouterOS 7.24): /ip/firewall/filter acepta
# src-address-list igual que mangle.


def get_filter_rules(api: Any) -> list[dict[str, Any]]:
    return list(api("/ip/firewall/filter/print"))


def get_filter_rule_by_comment(api: Any, comment: str) -> dict[str, Any] | None:
    for row in get_filter_rules(api):
        if row.get("comment") == comment:
            return row
    return None


def reset_configuration(api: Any, no_defaults: bool = True) -> None:
    """Borra TODA la configuración del equipo y lo reinicia. Con no_defaults=True
    (equivalente a 'no-defaults=yes' en RouterOS) el equipo queda sin bridge, sin
    DHCP client y SIN NINGUNA IP asignada — solo queda alcanzable por MAC
    (MNDP/MAC-Telnet) hasta que se le configure una interfaz manualmente."""
    list(
        api(
            "/system/reset-configuration",
            **{"no-defaults": "yes" if no_defaults else "no", "skip-backup": "yes"},
        )
    )
