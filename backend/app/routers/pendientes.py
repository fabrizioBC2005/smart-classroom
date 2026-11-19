"""Pendientes: lo que necesita a una persona."""
from __future__ import annotations

from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import PendienteResuelto
from app.services import pendientes as svc

router = APIRouter(prefix="/api/pendientes", tags=["pendientes"])


class ResolverIn(BaseModel):
    clave: str = Field(min_length=3, max_length=80)


@router.get("")
async def listar(db: AsyncSession = Depends(get_session)):
    redis = aioredis.from_url(settings.REDIS_URL)
    try:
        return await svc.calcular(db, redis)
    finally:
        await redis.aclose()


@router.post("/resolver")
async def resolver(r: ResolverIn, db: AsyncSession = Depends(get_session)):
    fila = await db.get(PendienteResuelto, r.clave)
    if fila:
        fila.ts = datetime.now(timezone.utc)
    else:
        db.add(PendienteResuelto(clave=r.clave))
    await db.commit()
    return {"ok": True, "clave": r.clave}
