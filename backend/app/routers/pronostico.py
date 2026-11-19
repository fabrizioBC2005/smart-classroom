"""Pronostico del aire de un aula: que espera y cuanto viene acertando.

Todo en "modo prueba": el pronostico no maneja la ventilacion. Esta ruta
solo cuenta lo que dijo y lo compara con lo que realmente paso.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Lectura, Pronostico
from aprendizaje import que_mira

router = APIRouter(prefix="/api", tags=["pronostico"])

HORAS_A_REVISAR = 24
MAXIMO_A_REVISAR = 2000


def _informe() -> dict | None:
    try:
        return json.loads(que_mira.ARCHIVO_INFORME.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@router.get("/aulas/{aula_id}/pronostico")
async def pronostico_del_aula(aula_id: int, db: AsyncSession = Depends(get_session)):
    informe = _informe()

    # lo ultimo que dijo, desde la cache que llena el worker
    ahora = None
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        crudo = await r.get(f"aula:{aula_id}:ultimo")
        if crudo:
            snap = json.loads(crudo)
            if snap.get("pronostico"):
                ahora = {**snap["pronostico"], "co2_ahora": snap.get("co2_ppm"), "ts": snap.get("ts")}
    finally:
        await r.aclose()

    # revisar los pronosticos cuyo momento ya llego
    hoy = datetime.now(timezone.utc)
    pasados = (await db.execute(
        select(Pronostico)
        .where(
            Pronostico.aula_id == aula_id,
            Pronostico.ts_objetivo <= hoy,
            Pronostico.ts_objetivo >= hoy - timedelta(hours=HORAS_A_REVISAR),
        )
        .order_by(Pronostico.ts_objetivo.desc())
        .limit(MAXIMO_A_REVISAR)
    )).scalars().all()

    revision = None
    if pasados:
        adelante_s = que_mira.segundos_de_reloj(pasados[0].minutos_adelante, settings.SIM_VELOCIDAD)
        margen = que_mira.margen_de_busqueda(adelante_s)
        desde = min(p.ts_objetivo for p in pasados) - timedelta(seconds=margen)
        hasta = max(p.ts_objetivo for p in pasados) + timedelta(seconds=margen)
        lect = (await db.execute(
            select(Lectura.ts, Lectura.co2_ppm)
            .where(Lectura.aula_id == aula_id, Lectura.ts >= desde, Lectura.ts <= hasta,
                   Lectura.co2_ppm.is_not(None))
            .order_by(Lectura.ts)
        )).all()
        ts = np.array([l.ts.timestamp() for l in lect])
        co2 = np.array([l.co2_ppm for l in lect], dtype=float)
        real = que_mira.co2_en(ts, co2, np.array([p.ts_objetivo.timestamp() for p in pasados]), margen)

        acerto = acerto_linea = comparables = 0
        error = error_linea = 0.0
        for p, r_ in zip(pasados, real):
            if np.isnan(r_) or p.co2_linea_recta is None:
                continue
            comparables += 1
            zona_real = que_mira.como_esta_el_aire(r_)
            acerto += que_mira.como_esta_el_aire(p.co2_previsto) == zona_real
            acerto_linea += que_mira.como_esta_el_aire(p.co2_linea_recta) == zona_real
            error += abs(p.co2_previsto - r_)
            error_linea += abs(p.co2_linea_recta - r_)
        if comparables:
            revision = {
                "horas": HORAS_A_REVISAR,
                "revisados": comparables,
                "acerto": acerto,
                "acerto_linea_recta": acerto_linea,
                "error_promedio_ppm": round(error / comparables, 1),
                "error_promedio_linea_recta_ppm": round(error_linea / comparables, 1),
            }

    return {
        "aprendiendo": informe is None,
        "modo_prueba": True,
        "informe": informe,
        "ahora": ahora,
        "revision": revision,
    }
