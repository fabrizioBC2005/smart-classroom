"""Endpoints de sedes, aulas y su estado actual."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Aula, Evento, Lectura, Sede
from app.schemas import AulaEstado, AulaOut, EventoOut, LecturaOut, SedeOut

router = APIRouter(prefix="/api", tags=["aulas"])

SEGUNDOS_OFFLINE = 60


@router.get("/sedes", response_model=list[SedeOut])
async def listar_sedes(db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(Sede).order_by(Sede.nombre))
    return res.scalars().all()


@router.get("/aulas", response_model=list[AulaOut])
async def listar_aulas(
    sede: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    q = select(Aula).join(Sede).order_by(Aula.codigo)
    if sede:
        q = q.where(Sede.slug == sede)
    res = await db.execute(q)
    return res.scalars().all()


@router.get("/estado", response_model=list[AulaEstado])
async def estado_actual(
    sede: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """Última lectura de cada aula. Es lo que alimenta el grid del dashboard."""
    q = select(Aula, Sede).join(Sede, Aula.sede_id == Sede.id).order_by(Aula.codigo)
    if sede:
        q = q.where(Sede.slug == sede)
    filas = (await db.execute(q)).all()

    redis = aioredis.from_url(settings.REDIS_URL)
    ahora = datetime.now(timezone.utc)
    salida: list[AulaEstado] = []

    try:
        for aula, sede_obj in filas:
            item = AulaEstado(
                aula_id=aula.id,
                codigo=aula.codigo,
                sede_slug=sede_obj.slug,
                nivel=aula.nivel,
                aforo_nominal=aula.aforo_nominal,
                instrumentada=aula.instrumentada,
            )

            # el worker cachea el último estado; evita un SELECT por aula
            cache = await redis.get(f"aula:{aula.id}:ultimo")
            if cache:
                d = json.loads(cache)
                item.ts = datetime.fromisoformat(d["ts"])
                item.co2_ppm = d.get("co2_ppm")
                item.temp_c = d.get("temp_c")
                item.hum_pct = d.get("hum_pct")
                item.lux = d.get("lux")
                item.iluminacion_on = d.get("iluminacion_on")
                item.ocupantes = d.get("ocupantes")
                item.indice = d.get("indice")
                item.estado = d.get("estado", "sin_datos")
                item.ventilacion_on = bool(d.get("ventilacion_on"))
            else:
                r = await db.execute(
                    select(Lectura)
                    .where(Lectura.aula_id == aula.id)
                    .order_by(Lectura.ts.desc())
                    .limit(1)
                )
                ult = r.scalar_one_or_none()
                if ult:
                    item.ts = ult.ts
                    item.co2_ppm = ult.co2_ppm
                    item.temp_c = ult.temp_c
                    item.hum_pct = ult.hum_pct
                    item.lux = ult.lux
                    item.ocupantes = ult.ocupantes_conteo or ult.ocupantes_estimado
                    item.indice = ult.indice
                    item.estado = ult.estado

            if item.ts:
                edad = (ahora - item.ts.astimezone(timezone.utc)).total_seconds()
                item.online = edad < SEGUNDOS_OFFLINE
                if not item.online:
                    item.estado = "sin_datos"

            salida.append(item)
    finally:
        await redis.aclose()

    return salida


@router.get("/aulas/{aula_id}", response_model=AulaOut)
async def detalle_aula(aula_id: int, db: AsyncSession = Depends(get_session)):
    aula = await db.get(Aula, aula_id)
    if not aula:
        raise HTTPException(404, "Aula no encontrada")
    return aula


@router.get("/aulas/{aula_id}/lecturas", response_model=list[LecturaOut])
async def serie_lecturas(
    aula_id: int,
    horas: int = Query(6, ge=1, le=168),
    limite: int = Query(1000, ge=1, le=5000),
    db: AsyncSession = Depends(get_session),
):
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    res = await db.execute(
        select(Lectura)
        .where(Lectura.aula_id == aula_id, Lectura.ts >= desde)
        .order_by(Lectura.ts.desc())
        .limit(limite)
    )
    return list(reversed(res.scalars().all()))


@router.get("/aulas/{aula_id}/eventos", response_model=list[EventoOut])
async def eventos_aula(
    aula_id: int,
    limite: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
):
    res = await db.execute(
        select(Evento)
        .where(Evento.aula_id == aula_id)
        .order_by(Evento.ts.desc())
        .limit(limite)
    )
    return res.scalars().all()
