#!/bin/bash
# Agrega/quita IPs secundarias consecutivas en una interfaz, y además fuerza
# (solo para esas IPs, vía policy routing) que su tráfico salga por el
# CCR2004 -- usado por la prueba de carga de QoS que simula N clientes
# sintéticos contra el plan C_10MB (scratchpad/qos_load_test/simulate_clients.py).
#
# Gotcha real encontrado en vivo: el CCR2004 (10.100.8.1) todavía NO es el
# gateway activo de este segmento -- la ruta por defecto real de este
# servidor sigue siendo otro equipo (10.100.10.1). Sin esto, el tráfico de
# la prueba nunca tocaba el router que se quiere medir. Se resuelve con una
# tabla de ruteo aparte (100) + una regla "from 10.100.12.0/22 table 100" --
# no toca la ruta por defecto real del servidor, solo desvía el tráfico que
# sale específicamente desde el bloque de IPs sintéticas de esta prueba.
#
# Existe como script propio (en vez de dar sudo directo sobre `ip`) para que
# el permiso otorgado en sudoers quede acotado a esta acción puntual, con la
# interfaz y el rango de IP validados acá adentro, no confiado a sudoers.
#
# Uso: loadtest-secondary-ips.sh add|del <primera_ip> <cantidad> <interfaz>
set -euo pipefail

ROUTER_LAN_IP="10.100.8.1"
POLICY_TABLE="100"
POLICY_CIDR="10.100.12.0/22"

ACTION="${1:?accion requerida (add|del)}"
FIRST_IP="${2:?primera IP requerida}"
COUNT="${3:?cantidad requerida}"
IFACE="${4:?interfaz requerida}"

if [[ "$ACTION" != "add" && "$ACTION" != "del" ]]; then
  echo "accion invalida: $ACTION" >&2
  exit 1
fi
if [[ "$IFACE" != "ens192" ]]; then
  echo "interfaz no permitida: $IFACE" >&2
  exit 1
fi
if [[ ! "$FIRST_IP" =~ ^10\.100\.1[2-5]\.[0-9]+$ ]]; then
  echo "rango de IP no permitido (solo 10.100.12-15.x, el bloque libre de clientes reales): $FIRST_IP" >&2
  exit 1
fi
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [[ "$COUNT" -gt 1000 ]]; then
  echo "cantidad invalida (max 1000): $COUNT" >&2
  exit 1
fi

python3 - "$ACTION" "$FIRST_IP" "$COUNT" "$IFACE" <<'PYEOF'
import ipaddress
import subprocess
import sys

action, first_ip, count, iface = sys.argv[1:5]
ip0 = ipaddress.IPv4Address(first_ip)
n = int(count)
lines = [f"addr {action} {ip0 + i}/21 dev {iface}" for i in range(n)]
subprocess.run(["ip", "-batch", "-"], input="\n".join(lines) + "\n", text=True, check=False)
PYEOF

SINK_IP="10.100.8.10"

if [[ "$ACTION" == "add" ]]; then
  ip route replace default via "$ROUTER_LAN_IP" dev "$IFACE" table "$POLICY_TABLE"
  ip rule add from "$POLICY_CIDR" table "$POLICY_TABLE" priority 100 2>/dev/null || true
  # Sin esto, la RESPUESTA del servidor local (sink, misma /21) volvería
  # directo por ARP al cliente sintético en vez de cruzar el router de
  # vuelta -- solo se forzaría el tramo de ida, no la vuelta.
  ip rule add from "$SINK_IP" to "$POLICY_CIDR" table "$POLICY_TABLE" priority 101 2>/dev/null || true
  # Gotcha real encontrado en vivo: el router tiene send-redirects=yes, y al
  # reenviar un hairpin (mismo subnet de origen y destino) manda un ICMP
  # Redirect de vuelta a este servidor -- el kernel lo obedece y cachea una
  # ruta directa al destino, saltándose esta tabla de política después de
  # los primeros paquetes (confirmado: `ip route get` mostraba `via <destino>`
  # con la flag <redirected> en vez de pasar por el router). Ignorar
  # redirects entrantes en esta interfaz es la única forma de que el tráfico
  # de la prueba siga cruzando el router de verdad durante toda la conexión.
  sysctl -q -w net.ipv4.conf."$IFACE".accept_redirects=0
  sysctl -q -w net.ipv4.conf.all.accept_redirects=0
  ip route flush cache
else
  ip rule del from "$POLICY_CIDR" table "$POLICY_TABLE" priority 100 2>/dev/null || true
  ip rule del from "$SINK_IP" to "$POLICY_CIDR" table "$POLICY_TABLE" priority 101 2>/dev/null || true
  ip route flush table "$POLICY_TABLE" 2>/dev/null || true
  sysctl -q -w net.ipv4.conf."$IFACE".accept_redirects=1
  sysctl -q -w net.ipv4.conf.all.accept_redirects=1
  ip route flush cache
fi
