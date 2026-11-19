"""API de Smart Classroom — REST + WebSocket."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.db import crear_tablas
from app.realtime import escuchar_redis, gestor
from app.routers import asistente, aulas, control, eventos, pendientes, pronostico, reportes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await crear_tablas()
    tarea = asyncio.create_task(escuchar_redis())
    log.info("API lista")
    yield
    tarea.cancel()


app = FastAPI(
    title="Smart Classroom API",
    description=(
        "Plataforma IoT de monitoreo ambiental y de ocupacion para aulas. "
        "Mide, analiza, decide y actua antes de que se cruce el umbral critico."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # en produccion: dominio del dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aulas.router)
app.include_router(eventos.router)
app.include_router(control.router)
app.include_router(reportes.router)
app.include_router(pronostico.router)
app.include_router(asistente.router)
app.include_router(pendientes.router)


@app.get("/salud", tags=["sistema"])
async def salud():
    return {"ok": True, "servicio": "smart-classroom-api", "version": "1.0.0"}


@app.websocket("/ws")
async def websocket(ws: WebSocket):
    """Empuja cada telemetria y cada evento al dashboard en vivo."""
    await gestor.conectar(ws)
    try:
        while True:
            await ws.receive_text()      # mantiene viva la conexion
    except WebSocketDisconnect:
        await gestor.desconectar(ws)
    except Exception:
        await gestor.desconectar(ws)
