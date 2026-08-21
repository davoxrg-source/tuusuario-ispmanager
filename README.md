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
