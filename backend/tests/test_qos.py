import uuid
from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
from app.services.mikrotik import qos
from app.services.mikrotik.device_service import DeviceService

# NOTA: el diseño de este módulo cambió después de verificarlo contra un
# CCR2004 real (RouterOS 7.24). Una primera versión asumía, por analogía con
# Linux tc, que /queue/tree podía filtrar por dst-address/src-address —
# RouterOS lo rechaza ("unknown parameter dst-address"). Por eso acá no hay
# ningún test que use esos parámetros: el filtrado por cliente se resuelve
# con PCQ (pcq-classifier) + address-list, nunca en el queue tree.


def _fake_device() -> MikrotikDevice:
    return MikrotikDevice(
        name="Router Lab",
        host="10.0.0.1",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        encrypted_password="unused-in-test",
    )


def _fake_plan(**overrides) -> Plan:
    defaults = dict(
        id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        name="30MB",
        download_speed_mbps=30,
        upload_speed_mbps=10,
        price=100,
        guaranteed_floor_percent=9,
    )
    defaults.update(overrides)
    return Plan(**defaults)


def test_kbps_for_plan_applies_guaranteed_floor_percent():
    plan = _fake_plan()
    ceil_down, ceil_up, floor_down, floor_up = qos.kbps_for_plan(plan)
    assert (ceil_down, ceil_up) == (30000, 10000)
    # 9% exacto, igual que el piso observado en el sistema legacy reemplazado.
    assert (floor_down, floor_up) == (2700, 900)


def test_build_plan_bootstrap_pcq_limit_is_fixed_at_routeros_default():
    # Se probó (y se descartó) escalar pcq-limit proporcional a la
    # velocidad del plan para evitar bufferbloat en planes lentos -- bajarlo
    # lo suficiente para que importe en un plan de 1 Mbit causó ~99% de
    # pérdida de paquetes navegando de verdad (ráfagas de varias conexiones
    # a la vez, no el flujo parejo de un test de velocidad). Como este ISP
    # no ofrece planes por debajo de 10 Mbit, donde el default de RouterOS
    # ya es insignificante (~40ms), queda fijo -- no escala con la
    # velocidad del plan.
    slow_plan = _fake_plan(download_speed_mbps=10, upload_speed_mbps=10)
    fast_plan = _fake_plan(download_speed_mbps=300, upload_speed_mbps=300)

    slow_commands = qos.build_plan_bootstrap_plan(slow_plan, "bridge-lan", "ether1-wan")
    fast_commands = qos.build_plan_bootstrap_plan(fast_plan, "bridge-lan", "ether1-wan")

    for commands in (slow_commands, fast_commands):
        pcq_commands = [c for c in commands if c.path == "/queue/type/add"]
        assert len(pcq_commands) == 2
        for c in pcq_commands:
            assert c.params["pcq-limit"] == str(qos.DEFAULT_PCQ_LIMIT) == "50"


def test_build_plan_bootstrap_creates_pcq_before_queue_tree_and_never_uses_address_on_tree():
    plan = _fake_plan()
    commands = qos.build_plan_bootstrap_plan(
        plan, lan_interface="bridge-lan", wan_interface="ether1-wan"
    )

    # Los PCQ (uno por dirección) tienen que existir ANTES de que cualquier
    # queue tree los referencie por nombre.
    pcq_names = {c.params["name"] for c in commands if c.path == "/queue/type/add"}
    assert pcq_names == {qos.pcq_type_name(qos.plan_ref(plan), "down"), qos.pcq_type_name(qos.plan_ref(plan), "up")}
    first_pcq_index = next(i for i, c in enumerate(commands) if c.path == "/queue/type/add")
    first_tree_index = next(i for i, c in enumerate(commands) if c.path == "/queue/tree/add")
    assert first_pcq_index < first_tree_index

    # Verificado contra hardware real: /queue/tree NUNCA debe llevar
    # dst-address/src-address (RouterOS 7.24 lo rechaza).
    tree_commands = [c for c in commands if c.path == "/queue/tree/add"]
    assert tree_commands, "debe haber nodos de queue tree"
    for c in tree_commands:
        assert "dst-address" not in c.params
        assert "src-address" not in c.params
        assert "queue" in c.params  # referencia al PCQ del plan, es lo que separa por cliente


def test_build_plan_bootstrap_queue_tree_has_three_tiers_per_direction_with_floor_on_rt_and_prio_only():
    plan = _fake_plan(download_speed_mbps=20, upload_speed_mbps=20)
    commands = qos.build_plan_bootstrap_plan(plan, lan_interface="bridge-lan", wan_interface="ether1-wan")
    tree = {c.params["name"]: c.params for c in commands if c.path == "/queue/tree/add"}

    ref = qos.plan_ref(plan)
    down_names = {f"isp-{ref}-down-{t}" for t in qos.TIERS}
    up_names = {f"isp-{ref}-up-{t}" for t in qos.TIERS}
    assert down_names <= tree.keys()
    assert up_names <= tree.keys()

    rt = tree[f"isp-{ref}-down-rt"]
    prio = tree[f"isp-{ref}-down-prio"]
    bulk = tree[f"isp-{ref}-down-bulk"]

    # rt y prio tienen piso garantizado; bulk no (igual que el legacy, donde
    # el nivel bulk no tenía una ls plana, solo la curva decoupled + menor prioridad).
    assert rt["limit-at"] == "1800k"  # 9% de 20000
    assert prio["limit-at"] == "1800k"
    assert "limit-at" not in bulk

    # Techo: rt usa el piso (floor), igual que el legacy (rt=ls=9%, sin
    # `ul`) -- si rt pudiera llegar al ceil, tráfico mal clasificado ahí
    # (paquetes chicos de un test de velocidad, por ejemplo) puede saturar
    # la cola de mayor prioridad consigo misma y arrastrar el tráfico
    # real-time genuino (bug real, visto en producción).
    #
    # prio/bulk usan la capacidad del POOL (parámetro aparte,
    # lan_pool_capacity_kbps/wan_pool_capacity_kbps), NO el ceil del plan --
    # segundo bug real, encontrado con una prueba de carga de 1000 clientes
    # sintéticos: este nodo es COMPARTIDO por todos los clientes del plan
    # (PCQ separa adentro), así que usar el ceil por cliente acá capaba el
    # pool ENTERO a la velocidad de uno solo, sin importar cuántos clientes
    # estuvieran activos (confirmado en vivo: 1000 clientes de 10Mbit nunca
    # superaron 10Mbit agregados, con paquetes descartados creciendo sin
    # parar). El límite por cliente ya lo impone el PCQ (pcq-rate=ceil).
    assert rt["max-limit"] == "1800k"
    assert prio["max-limit"] == bulk["max-limit"] == str(qos.DEFAULT_POOL_CAPACITY_KBPS) + "k"

    # Prioridad: tiempo real > prioridad > bulk (1 = más alta en RouterOS).
    assert int(rt["priority"]) < int(prio["priority"]) < int(bulk["priority"])

    # Cada nodo cuelga directo de la interfaz (no hay padre intermedio por
    # cliente — eso es justo lo que evita la explosión de objetos del legacy).
    assert rt["parent"] == prio["parent"] == bulk["parent"] == "bridge-lan"

    # Cada nodo filtra por su propio packet-mark único (plan+nivel).
    assert rt["packet-mark"] == qos.mark_name(ref, qos.TIER_REALTIME)
    assert prio["packet-mark"] == qos.mark_name(ref, qos.TIER_PRIORITY)
    assert bulk["packet-mark"] == qos.mark_name(ref, qos.TIER_BULK)


def test_build_plan_bootstrap_pool_capacity_is_independent_of_per_client_ceil():
    """El bug real (ver comentario arriba): antes de este fix, el max-limit
    de prio/bulk usaba el ceil del plan -- un plan de 10Mbit y uno de
    300Mbit terminaban con el MISMO nodo compartido limitado a la
    velocidad de un solo cliente. Acá se confirma que ahora es al revés:
    la capacidad del pool es un parámetro aparte, constante entre planes
    de distinta velocidad, y distinta del pcq-rate (que sí sigue siendo
    por-cliente, ligado al ceil del plan)."""
    slow_plan = _fake_plan(download_speed_mbps=10, upload_speed_mbps=10)
    fast_plan = _fake_plan(download_speed_mbps=300, upload_speed_mbps=300)

    for plan in (slow_plan, fast_plan):
        commands = qos.build_plan_bootstrap_plan(
            plan, lan_interface="bridge-lan", wan_interface="ether1-wan",
            lan_pool_capacity_kbps=500_000, wan_pool_capacity_kbps=200_000,
        )
        ref = qos.plan_ref(plan)
        tree = {c.params["name"]: c.params for c in commands if c.path == "/queue/tree/add"}
        pcq = {c.params["name"]: c.params for c in commands if c.path == "/queue/type/add"}

        # Pool: mismo valor sin importar la velocidad del plan (parámetro aparte).
        assert tree[f"isp-{ref}-down-bulk"]["max-limit"] == "500000k"
        assert tree[f"isp-{ref}-down-prio"]["max-limit"] == "500000k"
        assert tree[f"isp-{ref}-up-bulk"]["max-limit"] == "200000k"
        assert tree[f"isp-{ref}-up-prio"]["max-limit"] == "200000k"

        # Por-cliente: el pcq-rate sigue siendo el ceil del plan, distinto entre planes.
        ceil_down, ceil_up, _, _ = qos.kbps_for_plan(plan)
        assert pcq[qos.pcq_type_name(ref, "down")]["pcq-rate"] == f"{ceil_down}k"
        assert pcq[qos.pcq_type_name(ref, "up")]["pcq-rate"] == f"{ceil_up}k"


def test_build_plan_bootstrap_mangle_marks_every_packet_not_the_connection():
    # Reproduce el bug real: con mark-connection, el primer paquete de una
    # conexión (el handshake, siempre chico) decidía la marca para TODA la
    # conexión -- 58MB de una descarga real terminaron en la cola de tiempo
    # real de un plan de 1Mbit por esto. Cada paquete se tiene que
    # reclasificar solo, sin memoria de los anteriores de su conexión.
    plan = _fake_plan()
    commands = qos.build_plan_bootstrap_plan(plan, lan_interface="bridge-lan", wan_interface="ether1-wan")
    addr_list = qos.address_list_name(qos.plan_ref(plan))

    assert not any(c.params.get("action") == "mark-connection" for c in commands)
    assert not any("connection-mark" in c.params for c in commands)

    mark_rules = [c for c in commands if c.params.get("action") == "mark-packet"]
    assert mark_rules, "debe haber reglas de marcado"
    for c in mark_rules:
        assert c.params.get("packet-mark") == "no-mark"  # re-evalúa cada paquete, sin memoria
        # Cada regla scopea al address-list del plan por un lado u otro
        # (no sabemos de qué lado sale el paquete respecto del cliente).
        assert c.params.get("dst-address-list") == addr_list or c.params.get("src-address-list") == addr_list

    marks = {c.params["new-packet-mark"] for c in mark_rules}
    ref = qos.plan_ref(plan)
    assert marks == {qos.mark_name(ref, t) for t in qos.TIERS}


def test_build_plan_bootstrap_skips_empty_priority_port_lists():
    plan = _fake_plan()
    commands = qos.build_plan_bootstrap_plan(
        plan, lan_interface="bridge-lan", wan_interface="ether1-wan",
        priority_tcp_ports=[], priority_udp_ports=[],
    )
    port_rules = [c for c in commands if "port" in c.params and c.description.startswith("prioridad: puertos")]
    assert port_rules == []


def test_build_plan_bootstrap_includes_configured_priority_ports():
    plan = _fake_plan()
    commands = qos.build_plan_bootstrap_plan(
        plan, lan_interface="bridge-lan", wan_interface="ether1-wan",
        priority_tcp_ports=[32400], priority_udp_ports=[],
    )
    tcp_rule = next(
        c for c in commands
        if c.params.get("protocol") == "tcp" and c.description.startswith("prioridad: puertos")
    )
    assert tcp_rule.params["port"] == "32400"


def test_plan_object_names_orders_queue_trees_before_queue_types():
    plan = _fake_plan()
    names = qos.plan_object_names(plan)
    ref = qos.plan_ref(plan)
    assert set(names["queue_trees"]) == {f"isp-{ref}-{d}-{t}" for d in ("down", "up") for t in qos.TIERS}
    assert set(names["queue_types"]) == {qos.pcq_type_name(ref, "down"), qos.pcq_type_name(ref, "up")}
    assert names["address_list"] == qos.address_list_name(ref)


def test_provision_client_qos_ip_only_touches_address_list(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            calls.append((cmd, kwargs))
            if cmd == "/ip/firewall/address-list/print":
                return iter([])  # lista vacía: el cliente todavía no está
            return iter([])

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    plan = _fake_plan()
    service = DeviceService(_fake_device(), password="unused")
    service.provision_client_qos_ip(plan, "10.0.0.5")

    # Aprovisionar un cliente es: revisar si ya está (para ser idempotente,
    # ver el test de abajo) y, si no, UNA sola llamada de alta -- no crea
    # ningún objeto nuevo, solo lo agrega al address-list de su plan.
    assert calls == [
        ("/ip/firewall/address-list/print", {}),
        (
            "/ip/firewall/address-list/add",
            {"list": qos.address_list_name(qos.plan_ref(plan)), "address": "10.0.0.5", "comment": "ispmanager-qos"},
        ),
    ]


def test_provision_client_qos_ip_is_idempotent_if_already_in_list(monkeypatch):
    """Reproduce el bug real visto contra el CCR2004: aplicar QoS dos veces
    (o a un cliente que ya estaba provisionado) tiraba "failure: already
    have such entry" de RouterOS con un 500 opaco en el panel. Provisionar
    debe poder repetirse sin error."""
    plan = _fake_plan()
    addr_list = qos.address_list_name(qos.plan_ref(plan))
    add_calls: list[dict] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/address-list/print":
                return iter([{".id": "*1", "list": addr_list, "address": "10.0.0.5"}])
            if cmd == "/ip/firewall/address-list/add":
                add_calls.append(kwargs)
                raise AssertionError("no debería intentar agregar una entrada que ya existe")
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.provision_client_qos_ip(plan, "10.0.0.5")  # no debe lanzar

    assert add_calls == []


def test_ascii_safe_transliterates_accents():
    # Verificado contra un CCR2004 real: librouteros manda ASCII puro, un
    # UnicodeEncodeError con "tráfico" tumbaba la regla entera. plan.name
    # también pasa por acá porque lo escribe el usuario y puede tener tildes.
    assert qos._ascii_safe("tráfico") == "trafico"
    assert qos._ascii_safe("Plan Básico Ñandú") == "Plan Basico Nandu"
    assert qos._ascii_safe("sin acentos") == "sin acentos"


def test_build_plan_bootstrap_mangle_comments_are_pure_ascii_even_with_accented_plan_name():
    plan = _fake_plan(name="Plan Básico 20MB Ñandú")
    commands = qos.build_plan_bootstrap_plan(plan, lan_interface="bridge-lan", wan_interface="ether1-wan")
    comments = [c.params["comment"] for c in commands if "comment" in c.params]
    assert comments, "debe haber reglas con comentario"
    for comment in comments:
        comment.encode("ascii")  # no debe tirar UnicodeEncodeError


def test_remove_plan_qos_deletes_mangle_before_queue_trees_before_queue_types(monkeypatch):
    order: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/mangle/print":
                prefix = qos.mangle_comment_prefix(plan)
                return iter(
                    [{".id": "*m0", "comment": f"{prefix} tiempo real: SSH"}, {".id": "*m1", "comment": "otra regla, no es del plan"}]
                )
            if cmd == "/queue/tree/print":
                return iter([{".id": f"*t{i}", "name": n} for i, n in enumerate(qos.plan_object_names(plan)["queue_trees"])])
            if cmd == "/queue/type/print":
                return iter([{".id": f"*y{i}", "name": n} for i, n in enumerate(qos.plan_object_names(plan)["queue_types"])])
            if cmd == "/ip/firewall/address-list/print":
                return iter([{".id": "*a0", "list": qos.plan_object_names(plan)["address_list"], "address": "10.0.0.5"}])
            if cmd in ("/queue/tree/remove", "/ip/firewall/address-list/remove", "/ip/firewall/mangle/remove"):
                order.append((cmd, kwargs[".id"]))
                return iter([])
            if cmd == "/queue/type/remove":
                order.append((cmd, kwargs[".id"]))
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    plan = _fake_plan()
    service = DeviceService(_fake_device(), password="unused")
    service.remove_plan_qos(plan)

    cmds = [c for c, _ in order]
    assert cmds.index("/ip/firewall/mangle/remove") < cmds.index("/queue/tree/remove") < cmds.index("/queue/type/remove")

    # Solo se borró la regla mangle que es de este plan, no la ajena.
    mangle_removed_ids = [i for c, i in order if c == "/ip/firewall/mangle/remove"]
    assert mangle_removed_ids == ["*m0"]
