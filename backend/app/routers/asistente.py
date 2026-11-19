"""Asistente IA en burbuja del dashboard."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import asistente as svc

router = APIRouter(prefix="/api/asistente", tags=["asistente"])


class MensajeIn(BaseModel):
    rol: Literal["usuario", "asistente"]
    texto: str = Field(max_length=4000)


class PreguntaIn(BaseModel):
    mensajes: list[MensajeIn] = Field(min_length=1, max_length=40)


@router.get("/estado")
async def estado():
    return {"configurado": bool(settings.ANTHROPIC_API_KEY), "modelo": svc.MODELO}


@router.post("")
async def preguntar(p: PreguntaIn):
    try:
        texto = await svc.preguntar([m.model_dump() for m in p.mensajes])
    except svc.AsistenteNoConfigurado as exc:
        raise HTTPException(503, str(exc)) from exc
    except svc.AsistenteError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"respuesta": texto}
