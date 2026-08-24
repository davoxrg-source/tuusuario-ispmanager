import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from app.api.routes import (
    api_keys,
    auth,
    billing,
    billing_settings,
    clients,
    contracts,
    devices,
    external_api,
    installations,
    interfaces,
    inventory,
    monitoring,
    notifications,
    plans,
    portal,
    portal_auth,
    tickets,
    traffic,
    users,
    webhooks,
    zones,
)
from app.core.config import get_settings
from app.services.mikrotik.discovery import listener as mndp_listener
from app.services.netflow.collector import start_collector
from app.workers.poller import (
    poll_client_online_status_forever,
    poll_devices_forever,
    run_daily_billing_forever,
    run_payment_reminders_forever,
    run_traffic_maintenance_forever,
)

logging.basicConfig(level=logging.INFO)

background_tasks: list[asyncio.Task] = []
netflow_transport: asyncio.DatagramTransport | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global netflow_transport
    mndp_listener.start()
    # El colector NetFlow es una mejora, no un requisito para operar: si el
    # puerto UDP está ocupado o falla por cualquier otra razón, el resto del
    # backend (facturación, polling, API) debe arrancar igual.
    try:
        netflow_transport, netflow_protocol = await start_collector(settings.netflow_collector_port)
        if netflow_protocol.maintenance_task:
            background_tasks.append(netflow_protocol.maintenance_task)
    except OSError as exc:
        logging.getLogger(__name__).error(
            "No se pudo iniciar el colector NetFlow en UDP %d (%s) -- "
            "uso de tráfico por cliente quedará deshabilitado, el resto del backend sigue.",
            settings.netflow_collector_port,
            exc,
        )
    background_tasks.append(asyncio.create_task(poll_devices_forever()))
    background_tasks.append(asyncio.create_task(poll_client_online_status_forever()))
    background_tasks.append(asyncio.create_task(run_daily_billing_forever()))
    background_tasks.append(asyncio.create_task(run_traffic_maintenance_forever()))
    background_tasks.append(asyncio.create_task(run_payment_reminders_forever()))
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        mndp_listener.stop()
        if netflow_transport:
            netflow_transport.close()


settings = get_settings()

app = FastAPI(title="ISP Manager", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)
app.include_router(plans.router, prefix=api_prefix)
app.include_router(clients.router, prefix=api_prefix)
app.include_router(monitoring.router, prefix=api_prefix)
app.include_router(billing.router, prefix=api_prefix)
app.include_router(billing_settings.router, prefix=api_prefix)
app.include_router(interfaces.router, prefix=api_prefix)
app.include_router(traffic.router, prefix=api_prefix)
app.include_router(tickets.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(users.directory_router, prefix=api_prefix)
app.include_router(zones.router, prefix=api_prefix)
app.include_router(inventory.router, prefix=api_prefix)
app.include_router(installations.router, prefix=api_prefix)
app.include_router(contracts.router, prefix=api_prefix)
app.include_router(portal_auth.router, prefix=api_prefix)
app.include_router(portal.router, prefix=api_prefix)
app.include_router(notifications.router, prefix=api_prefix)
app.include_router(webhooks.router, prefix=api_prefix)
app.include_router(api_keys.router, prefix=api_prefix)
app.include_router(external_api.router, prefix=api_prefix)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


class SpaStaticFiles(StaticFiles):
    """StaticFiles que cae a index.html en cualquier 404, para que refrescar
    una ruta de React Router (ej. /devices) no devuelva un 404 crudo: el
    ruteo real lo resuelve el navegador una vez que carga la SPA.

    Nunca aplica este fallback a rutas /api/*: una ruta de API inexistente
    debe seguir devolviendo un 404 real, no el HTML de la SPA."""

    async def get_response(self, path: str, scope: Scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            request_path = scope.get("path", "")
            if exc.status_code == 404 and not request_path.startswith("/api/"):
                return await super().get_response("index.html", scope)
            raise


# Sirve los dos builds de React (staff en /, portal de clientes en /portal)
# para tener un único servicio/puerto -- el mount de /portal se registra
# ANTES que el de "/" a propósito: Starlette evalúa los mounts en orden de
# registro, y "/" como catch-all capturaría cualquier ruta si fuera primero.
portal_dist = Path(__file__).resolve().parent.parent.parent / "frontend-portal" / "dist"
if portal_dist.exists():
    # El patrón de Mount("/portal", ...) de Starlette solo matchea rutas que
    # empiecen con "/portal/" -- "/portal" pelado (sin barra) no matchea y
    # cae al mount catch-all de "/" de abajo, sirviendo el bundle de staff
    # por error. Redirect explícito para ese caso puntual.
    @app.get("/portal", include_in_schema=False)
    def _portal_root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/portal/")

    app.mount("/portal", SpaStaticFiles(directory=portal_dist, html=True), name="portal")

frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", SpaStaticFiles(directory=frontend_dist, html=True), name="frontend")
