"""Capa única de acceso a un Mikrotik: intenta API RouterOS y cae a SSH cuando aplica.

El resto del backend solo conoce esta interfaz, nunca los detalles de transporte.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
from app.schemas.mikrotik_device import (
    ActivePppSession,
    ConnectionTestResult,
    DeviceResourceStatus,
)
from app.schemas.wan_balancing import PublicBlockPin, WanCommandResult, WanLinkInput
from app.services.mikrotik import api_client, discovery, mactelnet_client, ssh_client

logger = logging.getLogger(__name__)


class DeviceService:
    def __init__(self, device: MikrotikDevice, password: str) -> None:
        self.device = device
        self.password = password

    def _api(self):
        return api_client.api_connection(
            host=self.device.host,
            username=self.device.username,
            password=self.password,
            port=self.device.api_port,
            use_tls=self.device.api_use_tls,
        )

    def _ssh(self):
        return ssh_client.ssh_connection(
            host=self.device.host,
            username=self.device.username,
            password=self.password,
            port=self.device.ssh_port,
        )

    def _test_connection_at_current_host(self) -> ConnectionTestResult:
        try:
            with self._api() as api:
                identity = api_client.get_identity(api)
                resource = api_client.get_system_resource(api)
                return ConnectionTestResult(
                    success=True,
                    method="api",
                    message="Conexión exitosa vía API RouterOS.",
                    identity=identity,
                    routeros_version=resource.get("version"),
                    uptime_seconds=_parse_routeros_uptime(resource.get("uptime")),
                )
        except api_client.RouterOsApiError as api_error:
            logger.warning("API RouterOS falló para %s, probando SSH: %s", self.device.host, api_error)
            try:
                with self._ssh() as client:
                    identity = ssh_client.get_identity(client)
                    return ConnectionTestResult(
                        success=True,
                        method="ssh",
                        message="La API falló, pero la conexión SSH fue exitosa.",
                        identity=identity,
                    )
            except ssh_client.RouterOsSshError as ssh_error:
                return ConnectionTestResult(
                    success=False,
                    method="none",
                    message=f"API falló ({api_error}); SSH también falló ({ssh_error}).",
                )

    def resolve_host_via_mac(self, db: Session) -> str | None:
        """Si el equipo tiene MAC registrada y MNDP la vio con otra IP, actualiza
        device.host en la base de datos. Devuelve la IP nueva si hubo cambio."""
        if not self.device.mac_address:
            return None
        seen = discovery.listener.get_by_mac(self.device.mac_address)
        if seen is None or seen.is_stale or seen.ip_address == self.device.host:
            return None

        logger.info(
            "Equipo %s: IP cambió de %s a %s (detectado por MAC %s).",
            self.device.name,
            self.device.host,
            seen.ip_address,
            self.device.mac_address,
        )
        self.device.host = seen.ip_address
        db.commit()
        return seen.ip_address

    def test_connection(self, db: Session | None = None) -> ConnectionTestResult:
        result = self._test_connection_at_current_host()
        if result.success or db is None or not self.device.mac_address:
            return result

        # La IP guardada falló por completo: intentamos redescubrir por MAC
        # antes de rendirnos (ver discovery.py).
        new_host = self.resolve_host_via_mac(db)
        if new_host:
            retry = self._test_connection_at_current_host()
            if retry.success:
                retry.resolved_via_mac = True
                retry.updated_host = new_host
                return retry
            result = retry

        # Último recurso: MAC-Telnet, solo funciona en la misma red L2 y con
        # el binario externo instalado (ver mactelnet_client.py).
        try:
            identity = mactelnet_client.get_identity(
                self.device.mac_address, self.device.username, self.password
            )
            return ConnectionTestResult(
                success=True,
                method="mactelnet",
                message="API y SSH fallaron; se alcanzó el equipo por MAC-Telnet (último recurso).",
                identity=identity,
                resolved_via_mac=True,
            )
        except mactelnet_client.MacTelnetError as mactelnet_error:
            return ConnectionTestResult(
                success=False,
                method="none",
                message=f"{result.message} MAC-Telnet también falló ({mactelnet_error}).",
            )

    def get_status(self) -> DeviceResourceStatus:
        with self._api() as api:
            resource = api_client.get_system_resource(api)
            sessions = api_client.get_active_ppp_sessions(api)
            return DeviceResourceStatus(
                cpu_load_percent=_safe_int(resource.get("cpu-load")),
                memory_used_bytes=_safe_int(resource.get("total-memory"), sub=_safe_int(resource.get("free-memory"))),
                memory_total_bytes=_safe_int(resource.get("total-memory")),
                uptime_seconds=_parse_routeros_uptime(resource.get("uptime")),
                active_ppp_sessions=len(sessions),
            )

    def get_interfaces_snapshot(self) -> list[dict]:
        with self._api() as api:
            interfaces = api_client.get_interfaces(api)
        return [
            {
                "name": iface.get("name"),
                "rx_bytes": _safe_int(iface.get("rx-byte")),
                "tx_bytes": _safe_int(iface.get("tx-byte")),
                "running": bool(iface.get("running")),
            }
            for iface in interfaces
        ]

    def list_interfaces(self) -> list[dict]:
        """Interfaces con sus campos crudos de RouterOS (.id, mac-address, mtu, etc.)."""
        with self._api() as api:
            return api_client.get_interfaces(api)

    def get_active_sessions(self) -> list[ActivePppSession]:
        with self._api() as api:
            sessions = api_client.get_active_ppp_sessions(api)
        return [
            ActivePppSession(
                name=row.get("name", ""),
                address=row.get("address"),
                uptime=row.get("uptime"),
                caller_id=row.get("caller-id"),
            )
            for row in sessions
        ]

    def ensure_suspension_bootstrap(self) -> None:
        """Idempotente: crea la regla de bloqueo de suspendidos si todavía
        no existe en el equipo. A diferencia del bootstrap de QoS (uno por
        plan, con preview/apply manual porque son ~30 objetos), acá es una
        sola regla — se crea sola la primera vez que hace falta."""
        from app.services.mikrotik import suspension

        with self._api() as api:
            if api_client.get_filter_rule_by_comment(api, suspension.FILTER_RULE_COMMENT):
                return
            for command in suspension.build_bootstrap_plan():
                list(api(command.path, **command.params))

    def suspend_client_ip(self, client_ip: str) -> None:
        from app.services.mikrotik import suspension

        self.ensure_suspension_bootstrap()
        with self._api() as api:
            api_client.add_address_list_entry(
                api, suspension.SUSPENDED_ADDRESS_LIST, client_ip, comment="ispmanager-suspend"
            )

    def reactivate_client_ip(self, client_ip: str) -> bool:
        from app.services.mikrotik import suspension

        with self._api() as api:
            return api_client.remove_address_list_entry(
                api, suspension.SUSPENDED_ADDRESS_LIST, client_ip
            )

    def list_ip_addresses(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_ip_addresses(api)

    def get_online_ip_set(self) -> set[str]:
        """IPs con entrada ARP 'complete' en el equipo ahora mismo -- sin
        PPPoE, esta es la señal de que el cliente está efectivamente
        conectado (su equipo está respondiendo en la red), no solo que
        tiene una IP asignada en la base. Usado por el poller para
        actualizar Client.is_online (ver workers/poller.py)."""
        with self._api() as api:
            entries = api_client.get_arp_entries(api)
        return {row["address"] for row in entries if row.get("complete") and row.get("address")}

    def add_ip_address(self, interface: str, address: str) -> None:
        with self._api() as api:
            api_client.add_ip_address(api, interface, address)

    def remove_ip_address(self, address_id: str) -> None:
        with self._api() as api:
            api_client.remove_ip_address(api, address_id)

    def list_bridges(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_bridges(api)

    def create_bridge(self, name: str) -> None:
        with self._api() as api:
            api_client.create_bridge(api, name)

    def remove_bridge(self, bridge_id: str) -> None:
        with self._api() as api:
            api_client.remove_bridge(api, bridge_id)

    def list_bridge_ports(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_bridge_ports(api)

    def add_bridge_port(self, bridge: str, interface: str) -> None:
        with self._api() as api:
            api_client.add_bridge_port(api, bridge, interface)

    def remove_bridge_port(self, port_id: str) -> None:
        with self._api() as api:
            api_client.remove_bridge_port(api, port_id)

    def setup_pppoe_server(
        self,
        interface: str,
        service_name: str,
        pool_start: str,
        pool_end: str,
        profile_name: str,
        local_address: str,
    ) -> None:
        with self._api() as api:
            api_client.setup_pppoe_server(
                api, interface, service_name, pool_start, pool_end, profile_name, local_address
            )

    def list_routes(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_routes(api)

    def list_mangle_rules(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_mangle_rules(api)

    def list_nat_rules(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_nat_rules(api)

    def list_dhcp_clients(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_dhcp_clients(api)

    def list_pppoe_clients(self) -> list[dict]:
        with self._api() as api:
            return api_client.get_pppoe_clients(api)

    def apply_wan_balancing_plan(
        self, plan: list[WanCommandResult], dry_run: bool
    ) -> list[WanCommandResult]:
        """Ejecuta (o simula) el plan generado por build_wan_balancing_plan."""
        return self.apply_command_plan(plan, dry_run)

    def apply_command_plan(
        self, plan: list[WanCommandResult], dry_run: bool
    ) -> list[WanCommandResult]:
        """Ejecuta (o simula) una lista de comandos RouterOS (path+params), en
        orden, deteniéndose en el primer error para no dejar una configuración
        a medias sin que quien llama se entere. Genérico: lo usan tanto el
        balanceo WAN como el QoS por cliente (ver services/mikrotik/qos.py)."""
        if dry_run:
            return [
                WanCommandResult(description=c.description, path=c.path, params=c.params, executed=False)
                for c in plan
            ]

        results: list[WanCommandResult] = []
        with self._api() as api:
            for command in plan:
                try:
                    list(api(command.path, **command.params))
                    results.append(
                        WanCommandResult(
                            description=command.description,
                            path=command.path,
                            params=command.params,
                            executed=True,
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        WanCommandResult(
                            description=command.description,
                            path=command.path,
                            params=command.params,
                            executed=False,
                            error=str(exc),
                        )
                    )
                    break
        return results

    def provision_client_qos_ip(self, plan: Plan, client_ip: str) -> None:
        """No crea nada nuevo: solo agrega la IP del cliente al address-list
        de su plan. El bootstrap del plan (build_plan_bootstrap_plan,
        aplicado aparte y una sola vez) es lo que hace que esa IP empiece a
        recibir shaping apenas entra a la lista."""
        from app.services.mikrotik import qos

        addr_list = qos.address_list_name(qos.plan_ref(plan))
        with self._api() as api:
            api_client.add_address_list_entry(api, addr_list, client_ip, comment="ispmanager-qos")

    def remove_client_qos_ip(self, plan: Plan, client_ip: str) -> bool:
        from app.services.mikrotik import qos

        addr_list = qos.address_list_name(qos.plan_ref(plan))
        with self._api() as api:
            return api_client.remove_address_list_entry(api, addr_list, client_ip)

    def remove_plan_qos(self, plan: Plan) -> None:
        """Desmonta toda la infraestructura QoS de un plan (mangle, queue
        tree, PCQ, entradas de address-list) — ej. antes de rearmarla con
        otros parámetros. Orden: mangle primero (no depende de nada más),
        después queue tree, y recién al final queue type — RouterOS no
        borra un /queue/type todavía referenciado por un nodo de queue
        tree."""
        from app.services.mikrotik import qos

        names = qos.plan_object_names(plan)
        comment_prefix = qos.mangle_comment_prefix(plan)
        with self._api() as api:
            for row in api_client.get_mangle_rules(api):
                if row.get("comment", "").startswith(comment_prefix):
                    list(api("/ip/firewall/mangle/remove", **{".id": row[".id"]}))
            for name in names["queue_trees"]:
                api_client.remove_queue_tree_by_name(api, name)
            for name in names["queue_types"]:
                api_client.remove_queue_type_by_name(api, name)
            addr_list = names["address_list"]
            for row in api_client.get_address_lists(api):
                if row.get("list") == addr_list:
                    list(api("/ip/firewall/address-list/remove", **{".id": row[".id"]}))

    def enable_traffic_flow(self, target_address: str, target_port: int) -> None:
        """Configura el equipo para exportar NetFlow v5 hacia el colector de
        ispmanager. Llamado automáticamente por el poller la primera vez que
        contacta un equipo (ver workers/poller.py) -- no requiere que el
        operador entre manualmente a Winbox."""
        with self._api() as api:
            api_client.enable_traffic_flow(api, target_address, target_port)

    def find_stuck_qos_queues(self) -> list[str]:
        """Ver services/mikrotik/qos_health.py -- detecta colas con
        backlog sin drenar (rate=0 sostenido). No confirma nada por sí
        solo: el llamador (poller) debe verlo en 2+ ciclos seguidos."""
        from app.services.mikrotik import qos_health

        with self._api() as api:
            return qos_health.find_stuck_queues(api)

    def reboot(self) -> None:
        try:
            with self._api() as api:
                api_client.reboot(api)
                return
        except api_client.RouterOsApiError:
            logger.warning("Reboot vía API falló para %s, probando SSH.", self.device.host)
        with self._ssh() as client:
            ssh_client.reboot(client)

    def reset_to_factory_defaults(self, no_defaults: bool = True) -> None:
        """ACCIÓN DESTRUCTIVA: borra toda la configuración del equipo y lo
        reinicia. Con no_defaults=True el equipo queda sin ninguna IP asignada
        (solo alcanzable por MAC vía MNDP/MAC-Telnet) hasta configurarlo desde cero."""
        logger.warning(
            "Ejecutando reset de configuración de fábrica en %s (%s) — no_defaults=%s",
            self.device.name,
            self.device.host,
            no_defaults,
        )
        try:
            with self._api() as api:
                api_client.reset_configuration(api, no_defaults=no_defaults)
                return
        except api_client.RouterOsApiError:
            logger.warning("Reset vía API falló para %s, probando SSH.", self.device.host)
        with self._ssh() as client:
            ssh_client.reset_configuration(client, no_defaults=no_defaults)


def _safe_int(value, sub: int | None = None) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if sub is not None:
        result = result - sub
    return result


def _parse_routeros_uptime(uptime: str | None) -> int | None:
    """Convierte '1w2d3h4m5s' (formato RouterOS) a segundos."""
    if not uptime:
        return None
    units = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    number = ""
    for char in uptime:
        if char.isdigit():
            number += char
        elif char in units and number:
            total += int(number) * units[char]
            number = ""
    return total or None


def build_wan_balancing_plan(
    lan_interface: str,
    wans: list[WanLinkInput],
    public_blocks: list[PublicBlockPin] | None = None,
) -> list[WanCommandResult]:
    """Construye (sin ejecutar nada) la lista ordenada de comandos RouterOS
    para balanceo+failover PCC entre 2+ WAN, con bloques de IP pública
    fijados de forma determinística a su propia WAN (Proxy ARP).

    Sintaxis verificada contra un CCR2004 real con RouterOS 7.24 (ver
    api_client.py): en RouterOS 7 el ruteo por marca requiere crear primero
    un objeto /routing/table, referenciado luego por nombre tanto desde
    mangle (new-routing-mark) como desde la ruta (routing-table). También
    se verificó que dhcp-client SÍ puede apuntar su ruta a tablas custom
    (parámetro "default-route-tables"), pero pppoe-client no tiene ese
    parámetro — para PPPoE el resto del plan agrega la ruta a mano usando
    el nombre de la interfaz PPPoE resultante como gateway.

    El orden importa y es funcionalmente crítico:
    -1. Proteger el tráfico de gestión del propio equipo (dst-address-type=local)
        en la interfaz LAN elegida — SIEMPRE primero, para que nunca quede
        capturado por las reglas PCC de más abajo (incidente real: si la
        interfaz LAN también se usa para administrar el equipo, sin esta
        regla la propia sesión de administración se enruta por una WAN sin
        camino de vuelta y el equipo se vuelve inalcanzable).
    0. Crear las tablas de ruteo (deben existir antes de referenciarlas).
    1. Aprovisionar la conexión real de cada WAN según su tipo (IP fija,
       cliente DHCP, o cliente PPPoE). Las WAN tipo DHCP quedan resueltas
       aquí mismo (RouterOS les agrega la ruta a la tabla marcada y a la
       principal automáticamente) y se saltan los pasos 4 y 5.
    2. Fijar cada bloque público a su WAN (antes de las reglas PCC, para que
       esas conexiones nunca entren al hash de balanceo).
    3. Reglas PCC de balanceo para el tráfico NATeado, por cada WAN.
    4. Ruta con routing-table por cada WAN static/pppoe (el "camino" real
       del tráfico marcado; las WAN dhcp no generan este paso).
    5. Rutas por defecto en la tabla principal (tráfico del propio router)
       para WAN static/pppoe, con distancia creciente para failover.
    6. NAT masquerade por WAN (solo aplica al tráfico NATeado).
    """
    public_blocks = public_blocks or []
    if len(wans) < 2:
        raise ValueError("Se necesitan al menos 2 WAN para balancear/hacer failover.")

    commands: list[WanCommandResult] = []
    routing_mark_for = {wan.interface: f"to-{wan.interface}" for wan in wans}

    # -1. Excluir SIEMPRE el tráfico de gestión del propio equipo antes de
    # cualquier otra regla. Sin esto, si la interfaz LAN elegida también se
    # usa para administrar el equipo (API/SSH/Winbox), esa sesión de
    # administración queda marcada y enrutada por una tabla de WAN — y si
    # esa WAN no tiene camino de vuelta, el equipo se vuelve inalcanzable.
    # Esto pasó de verdad en un incidente real; ver api_client.add_mangle_protect_local_traffic.
    commands.append(
        WanCommandResult(
            description=(
                f"Proteger tráfico de gestión del propio equipo en {lan_interface} "
                "(nunca se balancea/enruta por una WAN)"
            ),
            path="/ip/firewall/mangle/add",
            params={
                "chain": "prerouting",
                "action": "accept",
                "in-interface": lan_interface,
                "dst-address-type": "local",
            },
        )
    )

    # 0. Tablas de ruteo (deben existir antes de que dhcp-client/mangle/rutas las referencien).
    for wan in wans:
        mark = routing_mark_for[wan.interface]
        commands.append(
            WanCommandResult(
                description=f"Crear tabla de ruteo '{mark}'",
                path="/routing/table/add",
                params={"name": mark, "fib": ""},
            )
        )

    # 1. Aprovisionar la conexión real de cada WAN según su tipo. Para DHCP,
    # RouterOS mismo alimenta la tabla marcada Y la tabla principal en cuanto
    # obtiene el lease (default-route-tables), así que esa WAN se salta los
    # pasos 4 y 5 más abajo — dhcp-client ya los cubre.
    for wan in wans:
        mark = routing_mark_for[wan.interface]
        if wan.connection_type == "static":
            if wan.address:
                commands.append(
                    WanCommandResult(
                        description=f"Asignar IP {wan.address} a {wan.interface}",
                        path="/ip/address/add",
                        params={"address": wan.address, "interface": wan.interface},
                    )
                )
        elif wan.connection_type == "dhcp":
            commands.append(
                WanCommandResult(
                    description=(
                        f"Cliente DHCP en {wan.interface} "
                        f"(ruta por defecto automática a '{mark}' y a la tabla principal)"
                    ),
                    path="/ip/dhcp-client/add",
                    params={
                        "interface": wan.interface,
                        "add-default-route": "yes",
                        "default-route-tables": f"{mark},main",
                        "disabled": "no",
                    },
                )
            )
        elif wan.connection_type == "pppoe":
            params: dict[str, str] = {
                "interface": wan.interface,
                "name": wan.pppoe_client_name,
                "user": wan.pppoe_username or "",
                "password": wan.pppoe_password or "",
                "add-default-route": "no",
                "disabled": "no",
            }
            if wan.pppoe_service_name:
                params["service-name"] = wan.pppoe_service_name
            commands.append(
                WanCommandResult(
                    description=f"Cliente PPPoE '{wan.pppoe_client_name}' sobre {wan.interface}",
                    path="/interface/pppoe-client/add",
                    params=params,
                )
            )

    for block in public_blocks:
        mark = routing_mark_for.get(block.wan_interface)
        if mark is None:
            raise ValueError(
                f"El bloque {block.cidr} apunta a la WAN '{block.wan_interface}', "
                "que no está en la lista de WANs."
            )
        commands.append(
            WanCommandResult(
                description=f"Fijar {block.cidr} a la WAN {block.wan_interface}",
                path="/ip/firewall/mangle/add",
                params={
                    "chain": "prerouting",
                    "src-address": block.cidr,
                    "action": "mark-routing",
                    "new-routing-mark": mark,
                    "passthrough": "no",
                },
            )
        )

    total_wans = len(wans)
    for index, wan in enumerate(wans):
        connection_mark = f"{wan.interface}-conn"
        classifier = f"both-addresses:{total_wans}/{index}"
        commands.append(
            WanCommandResult(
                description=f"PCC: marcar {index + 1}/{total_wans} de las conexiones nuevas hacia {wan.interface}",
                path="/ip/firewall/mangle/add",
                params={
                    "chain": "prerouting",
                    "in-interface": lan_interface,
                    "connection-mark": "no-mark",
                    "per-connection-classifier": classifier,
                    "action": "mark-connection",
                    "new-connection-mark": connection_mark,
                    "passthrough": "yes",
                },
            )
        )
        commands.append(
            WanCommandResult(
                description=f"PCC: enrutar conexiones '{connection_mark}' por {wan.interface}",
                path="/ip/firewall/mangle/add",
                params={
                    "chain": "prerouting",
                    "connection-mark": connection_mark,
                    "action": "mark-routing",
                    "new-routing-mark": routing_mark_for[wan.interface],
                    "passthrough": "no",
                },
            )
        )

    # 4. Ruta de la tabla marcada por WAN. DHCP ya la crea sola (paso 1), así
    # que se salta aquí. Para PPPoE el "gateway" es el nombre de la interfaz
    # resultante (punto a punto, sin IP de gateway) y no aplica check-gateway=ping.
    for wan in wans:
        if wan.connection_type == "dhcp":
            continue
        gateway = wan.gateway if wan.connection_type == "static" else wan.pppoe_client_name
        params = {
            "gateway": gateway,
            "routing-table": routing_mark_for[wan.interface],
            "distance": "1",
        }
        if wan.connection_type == "static":
            params["check-gateway"] = "ping"
        commands.append(
            WanCommandResult(
                description=f"Ruta de la tabla '{routing_mark_for[wan.interface]}' vía {gateway}",
                path="/ip/route/add",
                params=params,
            )
        )

    # 5. Ruta por defecto de la tabla principal (tráfico del propio router),
    # con distancia creciente para failover. DHCP ya la crea sola (paso 1).
    for wan in wans:
        if wan.connection_type == "dhcp":
            continue
        gateway = wan.gateway if wan.connection_type == "static" else wan.pppoe_client_name
        params = {"gateway": gateway, "distance": str(wan.distance)}
        if wan.connection_type == "static":
            params["check-gateway"] = "ping"
        commands.append(
            WanCommandResult(
                description=f"Ruta por defecto (tabla principal) vía {gateway}, distancia {wan.distance}",
                path="/ip/route/add",
                params=params,
            )
        )

    for wan in wans:
        commands.append(
            WanCommandResult(
                description=f"NAT masquerade de salida por {wan.interface}",
                path="/ip/firewall/nat/add",
                params={"chain": "srcnat", "action": "masquerade", "out-interface": wan.interface},
            )
        )

    return commands
