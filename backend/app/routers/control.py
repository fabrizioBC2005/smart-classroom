"""Override manual de actuadores desde el dashboard."""
from __future__ import annotations

import json
import logging

import aiomqtt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Actuacion, Aula, Evento, Sede
from app.schemas import AulaOut, ComandoIn, ModoIn

router = APIRouter(prefix="/api", tags=["control"])
log = logging.getLogger("control")


NOMBRE = {"ventilacion": "La ventilación", "iluminacion": "Las luces"}


@router.put("/aulas/{aula_id}/modo", response_model=AulaOut)
async def cambiar_modo(
    aula_id: int,
    m: ModoIn,
    db: AsyncSession = Depends(get_session),
):
    """Automatico: el sistema maneja el equipo. Manual: solo las personas.

    Se guarda en la base (sobrevive reinicios) y se avisa al worker por MQTT
    para que aplique el cambio en la siguiente lectura.
    """
    fila = (
        await db.execute(
            select(Aula, Sede).join(Sede, Aula.sede_id == Sede.id).where(Aula.id == aula_id)
        )
    ).first()
    if not fila:
        raise HTTPException(404, "Aula no encontrada")
    aula, sede = fila

    columna = f"modo_{m.actuador}"
    if getattr(aula, columna) != m.modo:
        setattr(aula, columna, m.modo)
        db.add(Evento(
            aula_id=aula.id, tipo=f"modo_{m.modo}", severidad="info", variable=m.actuador,
            mensaje=f"{NOMBRE[m.actuador]} pasó a modo {m.modo}",
        ))
        await db.commit()
        await db.refresh(aula)

    try:
        async with aiomqtt.Client(
            hostname=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USER or None,
            password=settings.MQTT_PASSWORD or None,
        ) as cliente:
            await cliente.publish(
                settings.topic_modo(sede.slug, aula.codigo),
                json.dumps({"actuador": m.actuador, "modo": m.modo}),
                qos=1,
            )
    except Exception as exc:
        # ya quedo guardado: el worker lo lee de la base al reiniciar
        log.error("no se pudo avisar el cambio de modo al worker: %s", exc)
        raise HTTPException(503, f"Modo guardado, pero el broker MQTT no responde: {exc}") from exc

    return aula


@router.post("/aulas/{aula_id}/comando")
async def enviar_comando(
    aula_id: int,
    cmd: ComandoIn,
    db: AsyncSession = Depends(get_session),
):
    fila = (
        await db.execute(
            select(Aula, Sede).join(Sede, Aula.sede_id == Sede.id).where(Aula.id == aula_id)
        )
    ).first()
    if not fila:
        raise HTTPException(404, "Aula no encontrada")
    aula, sede = fila

    payload = {
        "actuador": cmd.actuador,
        "accion": cmd.accion,
        "motivo": cmd.motivo,
        "ttl_s": settings.VENTILACION_TTL_S if cmd.accion == "on" else 0,
        # el worker escucha este campo: pausa la automatizacion de este
        # actuador durante OVERRIDE_MANUAL_S para no deshacer lo que hizo la persona
        "origen": "manual",
    }

    try:
        async with aiomqtt.Client(
            hostname=settings.MQTT_HOST,
            port=settings.MQTT_PORT,
            username=settings.MQTT_USER or None,
            password=settings.MQTT_PASSWORD or None,
        ) as cliente:
            await cliente.publish(
                settings.topic_comando(sede.slug, aula.codigo),
                json.dumps(payload),
                qos=1,
            )
    except Exception as exc:
        log.error("no se pudo publicar el comando: %s", exc)
        raise HTTPException(503, f"Broker MQTT no disponible: {exc}") from exc

    db.add(
        Actuacion(
            aula_id=aula.id,
            actuador=cmd.actuador,
            accion=cmd.accion,
            motivo=cmd.motivo,
            origen="manual",
        )
    )
    await db.commit()
    return {"ok": True, "publicado_en": settings.topic_comando(sede.slug, aula.codigo), **payload}
