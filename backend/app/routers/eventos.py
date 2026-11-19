"""Alertas: listado, reconocimiento y resolución."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Actuacion, Evento
from app.schemas import ActuacionOut, EventoOut

router = APIRouter(prefix="/api", tags=["eventos"])


@router.get("/eventos", response_model=list[EventoOut])
async def listar_eventos(
    severidad: str | None = None,
    solo_abiertos: bool = False,
    limite: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
):
    q = select(Evento).order_by(Evento.ts.desc()).limit(limite)
    if severidad:
        q = q.where(Evento.severidad == severidad)
    if solo_abiertos:
        q = q.where(Evento.reconocido.is_(False))
    res = await db.execute(q)
    return res.scalars().all()


@router.post("/eventos/{evento_id}/reconocer", response_model=EventoOut)
async def reconocer(evento_id: int, db: AsyncSession = Depends(get_session)):
    ev = await db.get(Evento, evento_id)
    if not ev:
        raise HTTPException(404, "Evento no encontrado")
    ev.reconocido = True
    ev.resuelto_ts = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ev)
    return ev


@router.get("/actuaciones", response_model=list[ActuacionOut])
async def listar_actuaciones(
    aula_id: int | None = None,
    limite: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
):
    """Registro auditable de cada decisión del sistema."""
    q = select(Actuacion).order_by(Actuacion.ts.desc()).limit(limite)
    if aula_id:
        q = q.where(Actuacion.aula_id == aula_id)
    res = await db.execute(q)
    return res.scalars().all()
