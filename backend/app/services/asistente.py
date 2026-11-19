"""Asistente IA (Claude) de solo lectura.

Responde preguntas del personal del colegio sobre la calidad del aire usando
herramientas que consultan la base de datos. NO controla equipos: ninguna
herramienta publica en MQTT. El control sigue siendo el motor de reglas
(deterministico y auditable); la IA solo explica y resume.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic
from anthropic import beta_async_tool
from sqlalchemy import case, func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Actuacion, Aula, Evento, Lectura, Sede
from app.routers.aulas import estado_actual
from app.routers.reportes import reporte_cumplimiento, tasa_renovacion

log = logging.getLogger("asistente")

MODELO = "claude-opus-5-5"
MAX_HISTORIAL = 20  # mensajes de la conversacion que se reenvian

SISTEMA = """Eres el asistente de calidad ambiental de Smart Classroom, la plataforma IoT \
que monitorea las aulas de Innova Schools (Lima, Peru).

Hablas con docentes, coordinadores y directores, no con ingenieros: responde en espanol, \
claro y breve (unas pocas frases o una lista corta). Usa las herramientas para obtener datos \
reales antes de responder y nunca inventes cifras; si no hay datos, dilo.

Contexto del sistema:
- Umbral de CO2: {co2_alerta:.0f} ppm alerta (ASHRAE 62.1), {co2_critico:.0f} ppm critico.
- La ventilacion se enciende sola cuando el CO2 va a cruzar el umbral (control predictivo) \
o con temperatura >= {temp_alerta:.0f} C y gente en el aula. Las luces se encienden solas si hay \
gente y menos de {lux:.0f} lux, y se apagan tras un rato con el aula vacia.
- Cada actuacion tiene un motivo auditable (p.ej. "proyeccion_cruce_umbral:4.2min").
- ACH = renovaciones de aire por hora, medida por el decaimiento del CO2 con el aula vacia.
- El indice de habitabilidad (0-100) es un indicador de gestion, no una medida del \
rendimiento de los alumnos.

No puedes encender ni apagar equipos. Si te lo piden, explica que el sistema lo hace solo \
y que el control manual esta en la pagina de cada aula del dashboard."""


def _json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


async def _aula_por_codigo(db, codigo: str) -> Aula | None:
    return (
        await db.execute(select(Aula).where(Aula.codigo == codigo.strip()).limit(1))
    ).scalar_one_or_none()


# ------------------------------------------------------------- herramientas
@beta_async_tool
async def estado_actual_aulas() -> str:
    """Estado en vivo de todas las aulas: CO2, temperatura, ocupantes, indice,
    estado (ok/alerta/critico) y si la ventilacion esta encendida."""
    async with SessionLocal() as db:
        filas = await estado_actual(sede=None, db=db)
    return _json([f.model_dump() if hasattr(f, "model_dump") else f for f in filas])


@beta_async_tool
async def resumen_aula(codigo: str, horas: int = 24) -> str:
    """Resumen de la calidad del aire de un aula en un periodo: CO2 promedio y
    maximo, porcentaje de lecturas sobre el umbral, temperatura y cuantas veces
    actuo el sistema.

    Args:
        codigo: Codigo del aula, por ejemplo "303".
        horas: Cuantas horas hacia atras mirar (1 a 720).
    """
    horas = max(1, min(int(horas), 720))
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    async with SessionLocal() as db:
        aula = await _aula_por_codigo(db, codigo)
        if not aula:
            return _json({"error": f"No existe el aula {codigo}"})
        r = (await db.execute(
            select(
                func.count(Lectura.id),
                func.avg(Lectura.co2_ppm), func.max(Lectura.co2_ppm),
                func.sum(case((Lectura.co2_ppm >= settings.CO2_UMBRAL_ALERTA, 1), else_=0)),
                func.avg(Lectura.temp_c), func.max(Lectura.temp_c),
                func.avg(Lectura.indice),
            ).where(Lectura.aula_id == aula.id, Lectura.ts >= desde)
        )).one()
        acts = (await db.execute(
            select(Actuacion.actuador, Actuacion.accion, Actuacion.origen, func.count())
            .where(Actuacion.aula_id == aula.id, Actuacion.ts >= desde)
            .group_by(Actuacion.actuador, Actuacion.accion, Actuacion.origen)
        )).all()
    n = r[0] or 0
    return _json({
        "aula": codigo, "nivel": aula.nivel, "horas": horas, "lecturas": n,
        "co2_promedio": round(r[1], 0) if r[1] else None,
        "co2_maximo": round(r[2], 0) if r[2] else None,
        "pct_lecturas_sobre_umbral": round(100 * (r[3] or 0) / n, 1) if n else None,
        "temp_promedio": round(r[4], 1) if r[4] else None,
        "temp_maxima": round(r[5], 1) if r[5] else None,
        "indice_promedio": round(r[6], 1) if r[6] else None,
        "actuaciones": [
            {"actuador": a, "accion": ac, "origen": o, "veces": c} for a, ac, o, c in acts
        ],
    })


@beta_async_tool
async def eventos_recientes(codigo: str = "", limite: int = 20) -> str:
    """Alertas y eventos recientes (CO2 alto, temperatura, normalizaciones),
    de un aula o de todas.

    Args:
        codigo: Codigo del aula; vacio para todas las aulas.
        limite: Cuantos eventos devolver (maximo 100).
    """
    async with SessionLocal() as db:
        q = (select(Evento, Aula.codigo).join(Aula, Evento.aula_id == Aula.id)
             .order_by(Evento.ts.desc()).limit(max(1, min(int(limite), 100))))
        if codigo:
            q = q.where(Aula.codigo == codigo.strip())
        filas = (await db.execute(q)).all()
    return _json([
        {"aula": c, "ts": e.ts, "tipo": e.tipo, "severidad": e.severidad,
         "valor": e.valor, "mensaje": e.mensaje}
        for e, c in filas
    ])


@beta_async_tool
async def actuaciones_recientes(codigo: str = "", limite: int = 20) -> str:
    """Registro de lo que hizo el sistema (o una persona): encendidos y apagados
    de ventilacion e iluminacion con su motivo auditable.

    Args:
        codigo: Codigo del aula; vacio para todas las aulas.
        limite: Cuantas actuaciones devolver (maximo 100).
    """
    async with SessionLocal() as db:
        q = (select(Actuacion, Aula.codigo).join(Aula, Actuacion.aula_id == Aula.id)
             .order_by(Actuacion.ts.desc()).limit(max(1, min(int(limite), 100))))
        if codigo:
            q = q.where(Aula.codigo == codigo.strip())
        filas = (await db.execute(q)).all()
    return _json([
        {"aula": c, "ts": a.ts, "actuador": a.actuador, "accion": a.accion,
         "motivo": a.motivo, "origen": a.origen}
        for a, c in filas
    ])


@beta_async_tool
async def renovacion_aire(codigo: str, dias: int = 7) -> str:
    """Tasa de renovacion de aire real (ACH) de un aula, medida por la curva de
    caida del CO2 con el aula vacia, con diagnostico de ventilacion.

    Args:
        codigo: Codigo del aula, por ejemplo "303".
        dias: Dias de historial a analizar (1 a 60).
    """
    async with SessionLocal() as db:
        aula = await _aula_por_codigo(db, codigo)
        if not aula:
            return _json({"error": f"No existe el aula {codigo}"})
        res = await tasa_renovacion(aula_id=aula.id, dias=max(1, min(int(dias), 60)), db=db)
    return _json(res)


@beta_async_tool
async def reporte_cumplimiento_norma(dias: int = 7) -> str:
    """Reporte de cumplimiento de la Norma A.040 del RNE por aula: porcentaje del
    tiempo de ocupacion con CO2 bajo el umbral y si cumple.

    Args:
        dias: Periodo en dias (1 a 90).
    """
    async with SessionLocal() as db:
        rep = await reporte_cumplimiento(dias=max(1, min(int(dias), 90)), sede=None,
                                         umbral=None, db=db)
    return _json(rep.model_dump() if hasattr(rep, "model_dump") else rep)


HERRAMIENTAS = [
    estado_actual_aulas, resumen_aula, eventos_recientes,
    actuaciones_recientes, renovacion_aire, reporte_cumplimiento_norma,
]


# ---------------------------------------------------------------- consulta
class AsistenteNoConfigurado(Exception):
    pass


class AsistenteError(Exception):
    pass


_cliente: anthropic.AsyncAnthropic | None = None


def _cliente_api() -> anthropic.AsyncAnthropic:
    global _cliente
    if not settings.ANTHROPIC_API_KEY:
        raise AsistenteNoConfigurado(
            "Falta ANTHROPIC_API_KEY en el archivo .env del proyecto."
        )
    if _cliente is None:
        _cliente = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _cliente


async def preguntar(historial: list[dict]) -> str:
    """historial: [{"rol": "usuario"|"asistente", "texto": "..."}], el ultimo
    es la pregunta nueva. Solo texto: el contexto de herramientas de turnos
    anteriores no se reenvia (el asistente vuelve a consultar si lo necesita)."""
    mensajes = [
        {"role": "user" if m["rol"] == "usuario" else "assistant", "content": m["texto"]}
        for m in historial[-MAX_HISTORIAL:]
        if m.get("texto", "").strip()
    ]
    # la API exige empezar por el usuario
    while mensajes and mensajes[0]["role"] != "user":
        mensajes.pop(0)
    if not mensajes or mensajes[-1]["role"] != "user":
        raise AsistenteError("Falta la pregunta.")

    sistema = SISTEMA.format(
        co2_alerta=settings.CO2_UMBRAL_ALERTA, co2_critico=settings.CO2_UMBRAL_CRITICO,
        temp_alerta=settings.TEMP_UMBRAL_ALERTA, lux=settings.LUX_MINIMO,
    ) + f"\n\nFecha y hora actual (UTC): {datetime.now(timezone.utc):%Y-%m-%d %H:%M}."

    try:
        runner = _cliente_api().beta.messages.tool_runner(
            model=MODELO,
            max_tokens=16000,
            system=sistema,
            tools=HERRAMIENTAS,
            messages=mensajes,
            output_config={"effort": "low"},  # preguntas de consulta: rapido y barato
            max_iterations=8,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        final = await runner.until_done()
    except anthropic.AuthenticationError as exc:
        raise AsistenteNoConfigurado("La ANTHROPIC_API_KEY no es valida.") from exc
    except anthropic.RateLimitError as exc:
        raise AsistenteError("Demasiadas consultas seguidas; intenta en un momento.") from exc
    except anthropic.APIConnectionError as exc:
        raise AsistenteError("No hay conexion con el servicio de IA.") from exc
    except anthropic.APIStatusError as exc:
        log.exception("error de la API de Claude")
        raise AsistenteError(f"El servicio de IA respondio con error ({exc.status_code}).") from exc

    if final.stop_reason == "refusal":
        return "No puedo ayudar con esa consulta."
    texto = "".join(b.text for b in final.content if b.type == "text").strip()
    return texto or "No obtuve una respuesta. Intenta reformular la pregunta."
