"""Puente de tiempo real: el worker publica en Redis, la API lo reenvía
a cada navegador conectado por WebSocket.

Se separa así para que worker y API puedan escalar por separado.
"""
from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.config import settings

log = logging.getLogger("realtime")


class GestorConexiones:
    """Mantiene los WebSocket abiertos y hace fan-out de cada mensaje."""

    def __init__(self) -> None:
        self.activas: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def conectar(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.activas.add(ws)
        log.info("websocket conectado (total=%d)", len(self.activas))

    async def desconectar(self, ws: WebSocket) -> None:
        async with self._lock:
            self.activas.discard(ws)
        log.info("websocket desconectado (total=%d)", len(self.activas))

    async def difundir(self, mensaje: dict) -> None:
        if not self.activas:
            return
        data = json.dumps(mensaje, default=str)
        muertas = []
        for ws in list(self.activas):
            try:
                await ws.send_text(data)
            except Exception:
                muertas.append(ws)
        for ws in muertas:
            await self.desconectar(ws)


gestor = GestorConexiones()


async def publicar(canal: str, mensaje: dict) -> None:
    """Usado por el worker para empujar hacia los navegadores."""
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        await r.publish(canal, json.dumps(mensaje, default=str))
    finally:
        await r.aclose()


async def escuchar_redis() -> None:
    """Tarea de fondo de la API: Redis -> WebSocket."""
    while True:
        try:
            r = aioredis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            await pubsub.subscribe(settings.CANAL_TELEMETRIA, settings.CANAL_EVENTOS)
            log.info("suscrito a redis")
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    await gestor.difundir(json.loads(msg["data"]))
                except json.JSONDecodeError:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("redis caido (%s); reintento en 3s", exc)
            await asyncio.sleep(3)
