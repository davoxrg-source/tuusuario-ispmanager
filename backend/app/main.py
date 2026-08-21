import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, billing, clients, devices, monitoring, plans
from app.core.config import get_settings
from app.workers.poller import poll_devices_forever, run_daily_billing_forever

logging.basicConfig(level=logging.INFO)

background_tasks: list[asyncio.Task] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks.append(asyncio.create_task(poll_devices_forever()))
    background_tasks.append(asyncio.create_task(run_daily_billing_forever()))
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)


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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Sirve el build de React (frontend/dist) para tener un único servicio/puerto.
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
