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
   equipo no tiene IP). Requisitos ya cubiertos en este servidor:
   - El binario externo [`mactelnet`](https://github.com/haakonnessjoen/MAC-Telnet)
     instalado (`sudo apt-get install mactelnet-client`; ya está en los repos
     de Ubuntu/Debian).
   - Permisos de socket crudo sobre ese binario:
     `sudo setcap cap_net_raw+ep /usr/bin/mactelnet` (verificar con
     `getcap /usr/bin/mactelnet`).
   - El servidor debe estar en el **mismo segmento físico/VLAN** que el
     Mikrotik — no funciona a través de un router/firewall que no reenvíe
     ese tráfico de capa 2.

   En un servidor donde el binario no esté instalado o falle el permiso, el
   sistema lo reporta igual que un fallo de SSH (mensaje claro, sin tirar el
   proceso) — nunca es obligatorio para el resto de la app.

**Importante**: tanto el descubrimiento MNDP como MAC-Telnet requieren que
este servidor esté conectado a la misma red local (LAN/VLAN) que los equipos
Mikrotik. Si el backend corre en una red distinta (ej. una nube separada de
la red del ISP), ninguno de los dos mecanismos va a funcionar — solo quedará
la gestión por IP.

## Facturación

Una tarea diaria en background:
1. Genera facturas mensuales para clientes activos con plan asignado.
2. Marca como vencidas las facturas pendientes tras su `due_date`.
3. Suspende (en la base de datos y en el Mikrotik, deshabilitando el secreto
   PPPoE) a los clientes con facturas vencidas más allá del período de gracia
   (`OVERDUE_GRACE_DAYS` en `app/services/billing/invoicing.py`).

## Seguridad de credenciales

Las contraseñas de acceso a los Mikrotik y las contraseñas PPPoE de los
clientes se cifran en la base de datos con Fernet (`CREDENTIALS_ENCRYPTION_KEY`
en `.env`). Nunca se guardan en texto plano.
