# ISP Manager

Aplicación web para administrar un ISP: clientes, planes, facturación e
inventario de equipos MikroTik, con monitoreo en vivo y control remoto
(activar/suspender clientes, reiniciar equipos) vía **API RouterOS + SSH**.
Todo el estado se guarda en **PostgreSQL** en el mismo servidor Linux.

- Backend: FastAPI (Python) + SQLAlchemy + Alembic.
- Frontend: React + Vite + TypeScript + Tailwind, servido por el propio backend.
- Despliegue: systemd nativo, sin Docker.

## Estructura

```
backend/    API FastAPI, modelos, integración Mikrotik, worker de polling
frontend/   Panel web React
deploy/     systemd, script de instalación, init de PostgreSQL
```

## Instalación en el servidor (primera vez)

Requiere `sudo` para instalar paquetes de sistema y habilitar el servicio.

```bash
bash deploy/scripts/install.sh
```

Esto instala Python venv, PostgreSQL, Node.js; crea la base de datos; instala
dependencias; corre las migraciones; compila el frontend; e instala/arranca
el servicio `ispmanager-backend` con systemd.

Luego crea el primer usuario admin:

```bash
cd backend && source .venv/bin/activate
python -m app.cli.seed_admin admin@tuisp.com "Nombre Completo" "contraseña-segura"
```

El panel queda disponible en `http://<IP-del-servidor>:8000`.

## Desarrollo local

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ajusta DATABASE_URL, SECRET_KEY, CREDENTIALS_ENCRYPTION_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend (apunta a `http://localhost:8000` vía proxy de Vite):

```bash
cd frontend
npm install
npm run dev
```

Tests del backend (no requieren un Mikrotik real; el cliente RouterOS se mockea):

```bash
cd backend && source .venv/bin/activate
pytest
```

## Integración con MikroTik

Cada equipo se conecta primero por **API RouterOS** (puerto 8728/8729). Si
falla, ciertas operaciones (identidad, reinicio) intentan **SSH** como
respaldo. Ver `backend/app/services/mikrotik/device_service.py` para la
interfaz única que usa el resto del backend.

Un worker en background (dentro del mismo proceso de uvicorn) sondea cada
`DEVICE_POLL_INTERVAL_SECONDS` los equipos registrados y guarda snapshots de
CPU/memoria/uptime/sesiones PPP activas en `device_metrics` para los gráficos
de monitoreo.

### Gestión por MAC (equipo con IP inestable/perdida)

Si un equipo tiene su `mac_address` registrada, el sistema puede seguir
encontrándolo aunque su IP cambie o deje de responder:

1. **Descubrimiento MNDP** (`backend/app/services/mikrotik/discovery.py`):
   un listener en background escucha los anuncios que cada Mikrotik transmite
   por broadcast/multicast UDP al puerto 5678 (Neighbor Discovery, activado
   por defecto en RouterOS). El endpoint `GET /api/devices/discovered`
   muestra lo que ve ahora mismo — identidad, MAC, IP — para registrar un
   equipo con un clic desde el panel ("Detectados en la red" en la página de
   Equipos) en vez de escribir la IP a mano. Validado contra tráfico real
   (varios Mikrotik RouterOS 7.19–7.24 en la red de este servidor).
2. **Auto-reparación de IP**: si la IP guardada de un equipo deja de
   responder (tanto por API como por SSH) y el equipo tiene MAC registrada,
   el sistema busca esa MAC en la caché de MNDP; si la encuentra con otra IP,
   reintenta la conexión ahí y, si funciona, actualiza `host` en la base de
   datos automáticamente. Esto ocurre tanto al pulsar "Probar conexión" como
   en cada ciclo del poller de monitoreo.
3. **MAC-Telnet como último recurso**: si ni la IP guardada ni el
   descubrimiento MNDP funcionan, se intenta alcanzar el equipo directamente
   por su MAC vía MAC-Telnet (el mismo mecanismo que usa Winbox cuando un
   equipo no tiene IP).

   **No uses el paquete `mactelnet-client` de Ubuntu/Debian** — es la versión
   0.4.4 (~2011) y no soporta la autenticación EC-SRP que RouterOS exige
   desde 6.43 en adelante; truena con segfault en cualquier conexión real
   contra un equipo moderno. Hay que compilar la versión oficial:

   ```bash
   sudo apt-get install -y autoconf automake libtool pkg-config gettext build-essential git
   git clone https://github.com/haakonnessjoen/MAC-Telnet.git /tmp/mactelnet-src
   cd /tmp/mactelnet-src
   # Este Ubuntu no trae 'autopoint' (parte normal de gettext en otras distros);
   # sin internacionalización no lo necesitamos, así que se deshabilita:
   sed -i 's/^AM_GNU_GETTEXT(\[external\])/dnl disabled/' configure.ac
   sed -i 's/^AM_GNU_GETTEXT_VERSION(\[0.19\])/dnl disabled/' configure.ac
   sed -i 's#po/Makefile.in##' configure.ac
   sed -i '/^SUBDIRS = src doc config po/s/ po//' Makefile.am
   sed -i '/^LDFLAGS += -lintl/d' src/Makefile.am
   autoreconf -fi
   ./configure --without-mactelnetd
   make
   cp src/mactelnet /home/ispapp/ispmanager/backend/bin/mactelnet
   sudo setcap cap_net_raw+ep /home/ispapp/ispmanager/backend/bin/mactelnet
   ```

   `app/services/mikrotik/mactelnet_client.py` usa automáticamente
   `backend/bin/mactelnet` si existe (y solo cae al binario del PATH del
   sistema si no). El binario no se versiona en git (`backend/bin/` está en
   `.gitignore`) — hay que compilarlo una vez por servidor.

   El servidor debe estar en el **mismo segmento físico/VLAN** que el
   Mikrotik — no funciona a través de un router/firewall que no reenvíe
   tráfico de capa 2. En un servidor donde el binario no esté disponible o
   falle el permiso, el sistema lo reporta igual que un fallo de SSH
   (mensaje claro, sin tirar el proceso) — nunca es obligatorio para el
   resto de la app.

   Dos bugs más, ya resueltos en `mactelnet_client.py` (encontrados
   depurando con gdb y capturas de buffer crudo, no son teóricos):
   - El binario lee `TERM` del entorno y hace `strlen(NULL)` si no está
     definida (los procesos de systemd no la traen) — se fija explícitamente.
   - La consola de RouterOS pregunta la posición del cursor (`ESC [ 6n`) y
     redibuja el prompt con colores ANSI en cada línea; un simple
     `pexpect.expect()` sobre el prompt cae en falsos positivos contra esos
     redibujados — se responde la consulta y se drena/limpia el buffer
     completo en vez de confiar en un único match.

   `mactelnet_client.set_initial_password()` completa además el cambio de
   contraseña obligatorio que RouterOS 7 exige en el primer login tras un
   reset de fábrica (el mismo diálogo "Change Password Now" de Winbox, pero
   por consola) — ver más abajo, "Recuperar un equipo reseteado a fábrica".

**Importante**: tanto el descubrimiento MNDP como MAC-Telnet requieren que
este servidor esté conectado a la misma red local (LAN/VLAN) que los equipos
Mikrotik. Si el backend corre en una red distinta (ej. una nube separada de
la red del ISP), ninguno de los dos mecanismos va a funcionar — solo quedará
la gestión por IP.

### Recuperar un equipo reseteado a fábrica

Después de `/system reset-configuration no-defaults=yes` (el botón
"Restablecer a fábrica" del panel, o hecho a mano), el equipo queda:

1. **Sin ninguna IP asignada** — solo alcanzable por MAC (MNDP lo sigue
   detectando, anunciándose con IP de origen `0.0.0.0`).
2. **Con la contraseña del usuario `admin` en blanco**, pero RouterOS 7
   exige cambiarla en el primer login antes de aceptar cualquier comando —
   ni la API ni SSH funcionan hasta que esto se complete (es el mismo
   diálogo "Change Password Now" que muestra Winbox).

Flujo real usado para recuperar un equipo en este estado, sin acceso físico
ni Winbox, completamente por MAC-Telnet:

```python
from app.services.mikrotik.mactelnet_client import set_initial_password, get_identity

MAC = "18:FD:74:E6:E9:52"
set_initial_password(MAC, "admin", old_password="", new_password="una-contraseña-fuerte")
# a partir de aquí ya acepta comandos normales:
get_identity(MAC, "admin", "una-contraseña-fuerte")  # -> "CCR2004"
```

Después, para dejarlo operativo hay que reconfigurar desde cero (no queda
nada tras el reset): IP de gestión, y al menos una WAN con salida real a
internet, por ejemplo:

```python
from app.services.mikrotik.mactelnet_client import run_command

run_command(MAC, "admin", PWD, "/ip address add address=10.100.8.1/21 interface=sfp-sfpplus1")
run_command(MAC, "admin", PWD, "/ip dhcp-client add interface=ether2 add-default-route=yes disabled=no")
run_command(MAC, "admin", PWD, "/ip firewall nat add chain=srcnat action=masquerade out-interface=ether2")
```

En cuanto la IP de gestión responde, el sistema de auto-reparación por MAC
(ver arriba) actualiza solo el registro del equipo en la base de datos con
la IP nueva — no hace falta editarlo a mano en el panel.

**Nota:** hoy este flujo se ejecuta a mano (como en el ejemplo de arriba),
no hay un botón en el panel para "cambiar contraseña inicial" todavía — es
la pieza que falta si se quiere hacer completamente desde la UI.

### Balanceo y failover multi-WAN

Configurable desde el detalle de cada equipo: balanceo PCC entre 2+ WAN para
tráfico NATeado, con bloques de IP pública (Proxy ARP) fijados de forma
determinística a su propia WAN — no se balancean, porque un bloque público
solo es alcanzable por la WAN de su proveedor específico. Cada WAN puede ser
IP fija, DHCP, o cliente PPPoE.

**Siempre revisa la vista previa antes de aplicar.** Un error en estas reglas
puede tumbar la salida a internet de todo el equipo, no solo una interfaz —
esto pasó de verdad una vez: si la interfaz LAN elegida es la misma por la
que se administra el equipo, las reglas de balanceo capturaban también la
propia sesión de administración, enrutándola por una WAN sin camino de
vuelta y dejando el equipo inalcanzable por IP (recuperado por MAC-Telnet).
Por eso `build_wan_balancing_plan` siempre antepone una regla que excluye el
tráfico destinado al propio equipo (`dst-address-type=local`) antes de
cualquier otra cosa — pero sigue siendo buena práctica no mezclar la
interfaz de gestión con la interfaz de clientes cuando sea posible.

## QoS (shaping por plan)

Reemplaza el shaping legacy de wisprosvr01/SequreISP (HFSC en Linux, un
árbol de objetos por cliente — la causa de sus crashes recurrentes de
kernel) con shaping nativo de RouterOS: 3 niveles de prioridad por paquete
sin DPI (paquete chico = tiempo real, puertos configurados = prioridad,
resto = bulk), piso garantizado + techo de ráfaga por plan. Diseño completo
y el porqué de cada decisión en `services/mikrotik/qos.py` — verificado
contra un CCR2004 real, con varios bugs encontrados solo al medir tráfico
real (no evidentes revisando la configuración).

Se aplica **una vez por plan** (`/devices/{id}/qos-plans/{plan_id}/apply`,
o `app/cli/bootstrap_qos_plans.py` para todos los planes en uso de una),
no por cliente — dar de alta/baja un cliente es agregarlo/sacarlo de un
address-list, no crea ningún objeto nuevo.

**Colas trabadas**: hay un incidente real sin causa raíz confirmada donde
reconstruir el árbol de colas muy seguido (algo que la operación normal no
hace) dejó una cola en `rate=0` permanente hasta reiniciar el equipo — ver
el docstring de `qos.py` para el detalle completo. `qos_health.py`
detecta el síntoma (colas con backlog sin drenar) desde el poller de
fondo y avisa por log si persiste 2 ciclos seguidos.

## Facturación

Una tarea diaria en background:
1. Genera facturas mensuales para clientes activos con plan asignado.
2. Marca como vencidas las facturas pendientes tras su `due_date`.
3. Suspende (en la base de datos y en el Mikrotik, agregando su IP al
   address-list de bloqueo — ver `services/mikrotik/suspension.py`) a los
   clientes con facturas vencidas más allá del período de gracia
   (`OVERDUE_GRACE_DAYS` en `app/services/billing/invoicing.py`).

## Backups

`deploy/scripts/backup-db.sh` hace un `pg_dump` comprimido de la base todos
los días, con retención de 15 días (configurable con
`ISPMANAGER_BACKUP_RETENTION_DAYS`). Lee la conexión directo de
`backend/.env`, no hace falta pasarle credenciales.

En una instalación con `install.sh`, queda programado solo vía
`ispmanager-backup.timer` (systemd, 3am todos los días — ver
`systemctl list-timers ispmanager-backup.timer`). Los backups quedan en
`backups/` en la raíz del proyecto por defecto (`ISPMANAGER_BACKUP_DIR` para
cambiarlo) — **nunca se versionan** (`.gitignore`), tienen PII real de
clientes.

## Seguridad de credenciales

Las contraseñas de acceso a los Mikrotik se cifran en la base de datos con
Fernet (`CREDENTIALS_ENCRYPTION_KEY` en `.env`). Nunca se guardan en texto
plano. Este despliegue no usa PPPoE por cliente (clientes por IP estática) —
ver `services/mikrotik/suspension.py` para cómo se corta el servicio sin eso.
