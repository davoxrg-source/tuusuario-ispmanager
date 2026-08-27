"""Diseño y generación de reglas QoS (shaping por cliente) para RouterOS.

Reemplaza el shaping legacy de wisprosvr01/SequreISP: mismo comportamiento
observado ahí — 3 niveles de prioridad por paquete sin DPI (paquetes chicos
= interactivo, puertos configurados = prioridad, resto = bulk), piso
garantizado + techo de ráfaga por cliente — pero sin la causa real de sus
crashes de kernel: un árbol de miles de objetos, uno por cliente,
reconstruido entero en cada boot.

VERIFICADO CONTRA UN CCR2004 REAL (RouterOS 7.24) antes de escribir esta
versión. La primera versión de este módulo asumía, por analogía con Linux
tc, que `/queue/tree` podía filtrar por `dst-address`/`src-address` — ES
FALSO: RouterOS lo rechaza ("unknown parameter dst-address"). El filtrado
por cliente en RouterOS se resuelve distinto:

- **PCQ** (`/queue/type` kind=pcq, pcq-classifier=dst-address o
  src-address): separa automáticamente el tráfico que llega a una cola por
  IP, sin que el queue tree necesite saber nada de direcciones.
- **address-list**: en mangle, `dst-address-list=`/`src-address-list=`
  scopea las reglas de marcado a los clientes de un plan.

Eso cambia el diseño de raíz: en vez de "clasificación global del equipo +
queue tree por cliente" (lo que se armó originalmente y no es válido), es
**"todo se crea una sola vez POR PLAN, no por cliente"**:

- `build_plan_bootstrap_plan()`: address-list del plan + 2 PCQ (descarga/
  subida) + reglas mangle scopeadas a ese address-list + 6 nodos de queue
  tree (rt/prio/bulk × descarga/subida). Se aplica UNA VEZ por plan por
  equipo, sin importar cuántos clientes tenga ese plan.
- Alta/baja de cliente = agregarlo/sacarlo del address-list de su plan.
  Una sola llamada API, no crea ningún objeto nuevo (ver
  DeviceService.provision_client_qos / remove_client_qos).

Contrapartida real de este diseño frente al legacy (documentada, no
escondida): el piso garantizado (`limit-at`) es un piso a nivel del POOL de
clientes de ese plan/nivel, no un piso individual blindado por cliente como
hacía HFSC. PCQ reparte lo disponible de forma justa entre los clientes
activos del pool, capado por cliente en el ceil del plan — en la práctica
un resultado muy similar salvo que TODOS los clientes de un plan estén
saturando el mismo nivel exactamente al mismo tiempo.

Dos bugs más, encontrados con un cliente real bajo un test de velocidad
real (no teóricos):

1. El nivel "tiempo real" clasifica por PAQUETE (`mark-packet`), no por
   conexión. Una versión anterior usaba `mark-connection` (marca una vez,
   en el primer paquete, y esa marca queda para toda la conexión) — pero
   el primer paquete de CUALQUIER conexión TCP es el handshake, siempre
   chico, así que toda conexión nueva heredaba "tiempo real" para
   siempre, aunque después transportara datos grandes (medido: 58MB de
   una descarga real coladas ahí, contra 25KB de tráfico genuinamente
   chico). El legacy nunca tuvo este problema porque marca cada paquete
   por separado (`-j MARK`, no `-j CONNMARK`).
2. El techo del nivel "tiempo real" es el PISO del plan (9%), no su ceil
   — igual que el legacy, cuya clase rt nunca tuvo `ul`. Si tuviera
   acceso al ceil completo, cualquier tráfico mal clasificado ahí (aunque
   el bug de arriba esté resuelto, algo va a colarse alguna vez) podría
   saturar la cola de mayor prioridad consigo misma y arrastrar el
   tráfico real-time genuino con ella.

También se probó (y se descartó) escalar `pcq-limit` proporcional a la
velocidad del plan para evitar bufferbloat en planes lentos — bajarlo lo
suficiente para importar en un plan de 1 Mbit resultó en ~99% de pérdida
de paquetes navegando de verdad (ver DEFAULT_PCQ_LIMIT). Como este ISP no
ofrece planes por debajo de 10 Mbit, queda fijo en el default de RouterOS.

INCIDENTE SIN CAUSA RAÍZ CONFIRMADA — reconstruir el árbol de colas
completo de los ~55 planes DOS VECES SEGUIDAS en pocos minutos (mientras se
diagnosticaban los bugs de arriba) dejó una hoja del queue tree en
`rate=0` permanente: nada mal configurado, el backlog (`queued-bytes`)
simplemente dejó de drenar y `dropped` seguía creciendo indefinidamente.
Ni el tamaño de pcq-limit ni la cantidad de colas hermanas (se probó
aislando a solo 6 de 282 activas) lo explicaron. Un reinicio del equipo lo
resolvió del todo. No se confirmó el mecanismo interno de RouterOS. La
operación normal de este sistema NUNCA reconstruye el árbol completo
así de seguido — un plan se monta una sola vez; dar de alta/baja un
cliente es solo tocar un address-list — así que se sospecha que el
problema fue ese volumen inusual de reconfiguración rápida, no algo que
vaya a aparecer en uso normal. `services/mikrotik/qos_health.py` detecta
el síntoma (colas con backlog sin drenar) para enterarse por una alerta
en vez de por un reclamo, ya que no se pudo prevenir la causa de fondo.
"""

from __future__ import annotations

import unicodedata

from app.models.plan import Plan
from app.schemas.wan_balancing import WanCommandResult  # tipo genérico: descripción+path+params


def _ascii_safe(text: str) -> str:
    """librouteros (el cliente de la API RouterOS que usa este proyecto)
    manda los parámetros como ASCII puro — cualquier tilde/ñ en CUALQUIER
    valor (no solo comentarios: el nombre de un plan escrito por el usuario
    puede tener acentos) hace que la llamada entera falle con
    UnicodeEncodeError. Verificado contra un CCR2004 real (RouterOS 7.24):
    "tráfico" rompe, "trafico" no. Se usa solo para lo que se manda a la
    API (comment, etc.) — la `description` que ve el usuario en el preview
    se arma aparte y puede llevar tildes sin problema."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")

TIER_REALTIME = "rt"
TIER_PRIORITY = "prio"
TIER_BULK = "bulk"
TIERS = (TIER_REALTIME, TIER_PRIORITY, TIER_BULK)

QOS_COMMENT_PREFIX = "ispmanager-qos"

# Puertos de streaming/juegos habituales — mismo rol que default_tcp_prio_ports
# en el sistema legacy. Se pueden pisar por parámetro.
DEFAULT_PRIORITY_TCP_PORTS = [8100, 8200, 32400]
DEFAULT_PRIORITY_UDP_PORTS = [8100, 8200, 32400]


def plan_ref(plan: Plan) -> str:
    """Identificador corto y estable para nombrar objetos RouterOS de este
    plan (los nombres de /queue/type, /queue/tree, address-list tienen
    límite de longitud)."""
    return str(plan.id).replace("-", "")[:12]


def address_list_name(ref: str) -> str:
    return f"isp-plan-{ref}"


def pcq_type_name(ref: str, direction: str) -> str:
    return f"isp-pcq-{ref}-{direction}"


def mark_name(ref: str, tier: str) -> str:
    """El packet-mark de este plan+nivel (ver build_plan_bootstrap_plan)."""
    return f"isp-{ref}-{tier}"


# Tamaño del buffer de PCQ (paquetes) -- el default de RouterOS. Se probó
# escalarlo proporcional a la velocidad del plan para evitar bufferbloat en
# planes muy lentos (50 paquetes son ~600ms de cola extra a 1 Mbit, medido
# en vivo: 382ms-1.8s de latencia bajo carga) -- pero bajarlo demasiado
# (12-37 paquetes) causó ~99% de pérdida de paquetes navegando de verdad
# (ráfagas de varias conexiones simultáneas al cargar una página, nada
# parecido al flujo parejo de un test de velocidad; medido: 3539 paquetes
# descartados contra 44 entregados). Dado que este ISP no maneja planes
# por debajo de 10 Mbit para ningún cliente (a esa velocidad 50 paquetes
# son ~40ms, insignificante), no vale la pena la complejidad de escalarlo
# -- si en algún momento se ofrece un plan bien lento, ahí sí conviene
# retomar un cálculo proporcional (ver historial de este archivo en git).
DEFAULT_PCQ_LIMIT = 50


def kbps_for_plan(plan: Plan) -> tuple[int, int, int, int]:
    """(ceil_down, ceil_up, floor_down, floor_up) en kbit/s para un plan."""
    ceil_down = plan.download_speed_mbps * 1000
    ceil_up = plan.upload_speed_mbps * 1000
    floor_down = (ceil_down * plan.guaranteed_floor_percent) // 100
    floor_up = (ceil_up * plan.guaranteed_floor_percent) // 100
    return ceil_down, ceil_up, floor_down, floor_up


DEFAULT_POOL_CAPACITY_KBPS = 1_000_000  # 1 Gbit -- techo agregado del pool, no del cliente (ver bug documentado abajo)


def build_plan_bootstrap_plan(
    plan: Plan,
    lan_interface: str,
    wan_interface: str,
    priority_tcp_ports: list[int] | None = None,
    priority_udp_ports: list[int] | None = None,
    realtime_tcp_max_size: int = 128,
    realtime_udp_max_size: int = 200,
    lan_pool_capacity_kbps: int = DEFAULT_POOL_CAPACITY_KBPS,
    wan_pool_capacity_kbps: int = DEFAULT_POOL_CAPACITY_KBPS,
) -> list[WanCommandResult]:
    """Todo lo que un plan necesita para poder dar shaping, armado una sola
    vez. Después de esto, un cliente nuevo en este plan solo necesita
    entrar al address-list (ver DeviceService.provision_client_qos)."""
    if priority_tcp_ports is None:
        priority_tcp_ports = DEFAULT_PRIORITY_TCP_PORTS
    if priority_udp_ports is None:
        priority_udp_ports = DEFAULT_PRIORITY_UDP_PORTS

    ref = plan_ref(plan)
    addr_list = address_list_name(ref)
    ceil_down, ceil_up, floor_down, floor_up = kbps_for_plan(plan)
    pcq_down, pcq_up = pcq_type_name(ref, "down"), pcq_type_name(ref, "up")
    commands: list[WanCommandResult] = []

    # --- 1) PCQ por dirección: separa automáticamente por IP de cliente
    # dentro del pool de este plan, capado al ceil del plan por cliente.
    commands.append(
        WanCommandResult(
            description=f"Cola PCQ de descarga del plan {plan.name}",
            path="/queue/type/add",
            params={
                "name": pcq_down, "kind": "pcq",
                "pcq-rate": f"{ceil_down}k", "pcq-classifier": "dst-address",
                "pcq-limit": str(DEFAULT_PCQ_LIMIT),
            },
        )
    )
    commands.append(
        WanCommandResult(
            description=f"Cola PCQ de subida del plan {plan.name}",
            path="/queue/type/add",
            params={
                "name": pcq_up, "kind": "pcq",
                "pcq-rate": f"{ceil_up}k", "pcq-classifier": "src-address",
                "pcq-limit": str(DEFAULT_PCQ_LIMIT),
            },
        )
    )

    # --- 2) Mangle: marca cada PAQUETE (no la conexión) de clientes de ESTE
    # plan (scopeado por address-list) en 3 niveles, con el mismo criterio
    # del sistema legacy (paquete chico = interactivo, sin DPI).
    #
    # Importante — bug real, visto en producción: la primera versión de
    # este módulo usaba mark-connection (marca UNA VEZ, en el primer
    # paquete de la conexión, y esa marca queda para toda la conexión). El
    # primer paquete de CUALQUIER conexión TCP es el handshake (SYN), que
    # siempre es chico — así que toda conexión nueva se marcaba "tiempo
    # real" por su arranque, y los datos grandes que venían después en esa
    # misma conexión heredaban esa marca para siempre (medido: 58MB de una
    # descarga real coladas en la cola de tiempo real de un plan de 1Mbit,
    # contra apenas 25KB de tráfico genuinamente chico). El legacy nunca
    # tuvo este problema porque marca cada paquete (`-j MARK`, no
    # `-j CONNMARK`) de forma independiente. Acá se replica eso: mark-packet
    # directo, sin pasar por connection-mark — cada paquete se reclasifica
    # solo, sin memoria de los anteriores de su misma conexión.
    def mark_packet(comment: str, tier: str, match: dict[str, str]) -> None:
        mark = mark_name(ref, tier)
        for list_field in ("dst-address-list", "src-address-list"):
            params: dict[str, str] = {
                "chain": "forward",
                "packet-mark": "no-mark",
                list_field: addr_list,
                "action": "mark-packet",
                "new-packet-mark": mark,
                "passthrough": "no",
                "comment": _ascii_safe(f"{QOS_COMMENT_PREFIX} {plan.name}: {comment}"),
            }
            params.update(match)
            commands.append(
                WanCommandResult(description=comment, path="/ip/firewall/mangle/add", params=params)
            )

    mark_packet(
        "tiempo real: TCP chico (ACKs/control)", TIER_REALTIME,
        {"protocol": "tcp", "packet-size": f"0-{realtime_tcp_max_size}"},
    )
    mark_packet(
        "tiempo real: UDP chico (DNS/voz/juegos)", TIER_REALTIME,
        {"protocol": "udp", "packet-size": f"0-{realtime_udp_max_size}"},
    )
    mark_packet("tiempo real: ICMP", TIER_REALTIME, {"protocol": "icmp"})
    mark_packet("tiempo real: SSH", TIER_REALTIME, {"protocol": "tcp", "port": "22"})
    mark_packet("tiempo real: DNS", TIER_REALTIME, {"protocol": "tcp", "port": "53"})
    mark_packet("tiempo real: DNS", TIER_REALTIME, {"protocol": "udp", "port": "53"})
    mark_packet("tiempo real: RDP", TIER_REALTIME, {"protocol": "tcp", "port": "3389"})
    mark_packet(
        "tiempo real: SIP (equivalente a helper=sip del legacy)", TIER_REALTIME,
        {"protocol": "tcp", "port": "5060-5061"},
    )
    mark_packet(
        "tiempo real: SIP (equivalente a helper=sip del legacy)", TIER_REALTIME,
        {"protocol": "udp", "port": "5060-5061"},
    )
    mark_packet("prioridad: IGMP", TIER_PRIORITY, {"protocol": "igmp"})
    if priority_tcp_ports:
        mark_packet(
            "prioridad: puertos TCP configurados", TIER_PRIORITY,
            {"protocol": "tcp", "port": ",".join(str(p) for p in priority_tcp_ports)},
        )
    if priority_udp_ports:
        mark_packet(
            "prioridad: puertos UDP configurados", TIER_PRIORITY,
            {"protocol": "udp", "port": ",".join(str(p) for p in priority_udp_ports)},
        )
    mark_packet("bulk: resto del tráfico", TIER_BULK, {})

    # --- 3) Queue tree: 3 niveles × 2 direcciones, cada uno filtrado por su
    # propio packet-mark (único por plan+nivel — no hace falta address en el
    # queue tree porque el PCQ ya separa por cliente adentro de cada nodo).
    # rt y prio tienen limit-at (piso garantizado); bulk no — igual que en
    # el legacy, donde el nivel bulk no tenía un piso plano, solo la curva
    # decoupled de ráfaga corta + prioridad más baja.
    #
    # El techo de rt es el PISO (floor_kbps), no el ceil del plan -- bug
    # real, visto en producción: con max-limit=ceil (igual que prio/bulk),
    # tráfico que cae en rt por la heurística de paquete chico (fast.com
    # abre muchas conexiones con segmentos chicos) llegó a acaparar >600kbit
    # de un plan de 1Mbit, saturando la cola de mayor prioridad consigo
    # misma y arrastrando con ella los pings reales. El legacy (HFSC) nunca
    # tuvo este problema porque su nivel rt tampoco tenía `ul`: quedaba
    # fijo en el piso (rt=ls=9%, sin upper limit) — tráfico real-time
    # genuino (voz, DNS, ping) nunca necesita más que eso, y así ninguna
    # mala clasificación puede inundar la cola de más prioridad.
    #
    # SEGUNDO bug real, encontrado recién con una prueba de carga de 1000
    # clientes sintéticos: prio/bulk usaban max-limit=ceil_kbps (el techo
    # POR CLIENTE) en el nodo de queue tree, que es COMPARTIDO por TODOS los
    # clientes del plan (PCQ separa adentro de ese mismo nodo). Resultado:
    # el pool ENTERO de un plan quedaba limitado a la velocidad de UN SOLO
    # cliente, sin importar cuántos estuvieran activos -- confirmado en vivo
    # contra un CCR2004 real: con 1000 clientes de un plan de 10Mbit, el
    # nodo bulk nunca superó 10Mbit agregados (contra los ~1000×10Mbit que
    # debería poder repartir PCQ), con `dropped` creciendo sin parar. El
    # límite por cliente ya lo impone el PCQ (`pcq-rate=ceil`, ver arriba)
    # -- el max-limit de ESTE nodo tiene que ser la capacidad del POOL
    # (cuánto puede cursar el plan entero en conjunto), no la de un cliente.
    def add_leaf(direction: str, tier: str, parent_interface: str, pool_capacity_kbps: int, floor_kbps: int, queue_type: str, priority: int) -> None:
        mark = mark_name(ref, tier)
        max_limit_kbps = floor_kbps if tier == TIER_REALTIME else pool_capacity_kbps
        params: dict[str, str] = {
            "name": f"isp-{ref}-{direction}-{tier}",
            "parent": parent_interface,
            "queue": queue_type,
            "packet-mark": mark,
            "max-limit": f"{max_limit_kbps}k",
            "priority": str(priority),
        }
        if tier != TIER_BULK:
            params["limit-at"] = f"{floor_kbps}k"
        commands.append(
            WanCommandResult(
                description=f"Cola {direction} nivel {tier} del plan {plan.name}",
                path="/queue/tree/add",
                params=params,
            )
        )

    priority_by_tier = {TIER_REALTIME: 1, TIER_PRIORITY: 4, TIER_BULK: 8}
    for tier in TIERS:
        add_leaf("down", tier, lan_interface, lan_pool_capacity_kbps, floor_down, pcq_down, priority_by_tier[tier])
    for tier in TIERS:
        add_leaf("up", tier, wan_interface, wan_pool_capacity_kbps, floor_up, pcq_up, priority_by_tier[tier])

    return commands


def mangle_comment_prefix(plan: Plan) -> str:
    """Prefijo común a TODAS las reglas mangle que crea build_plan_bootstrap_plan
    para este plan — sirve para encontrarlas y borrarlas todas sin guardar
    sus .id en ningún lado (a diferencia de queue tree/type, una regla
    mangle no tiene nombre propio)."""
    return _ascii_safe(f"{QOS_COMMENT_PREFIX} {plan.name}:")


def plan_object_names(plan: Plan) -> dict[str, list[str]]:
    """Nombres de todos los objetos RouterOS de un plan, agrupados por tipo
    y en orden seguro de borrado (queue tree antes que queue type — RouterOS
    no borra un /queue/type todavía referenciado por un queue tree)."""
    ref = plan_ref(plan)
    queue_trees = [f"isp-{ref}-{direction}-{tier}" for direction in ("down", "up") for tier in TIERS]
    queue_types = [pcq_type_name(ref, "down"), pcq_type_name(ref, "up")]
    return {"queue_trees": queue_trees, "queue_types": queue_types, "address_list": address_list_name(ref)}
