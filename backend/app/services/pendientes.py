"""Pendientes: lo que el sistema NO puede resolver solo y necesita a una persona.

La pantalla principal responde "¿como estan las aulas ahora?". Esta responde
"¿que tengo que hacer yo?". Lo que el sistema ya arreglo (ventilar, prender
luces) no es un pendiente: solo se cuenta en el resumen.

Cada pendiente tiene una clave estable (tipo:aula[:detalle]) para poder
marcarlo como resuelto; se oculta 24 h y vuelve si el problema sigue.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Actuacion, Aula, Evento, Lectura, PendienteResuelto, Sede

# en tiempo del aula (con el simulador acelerado pasa SIM_VELOCIDAD veces mas rapido)
MIN_VENTILANDO_SIN_EFECTO = 20      # el ventilador no alcanza
MIN_MANUAL_OLVIDADO = 60            # equipo olvidado en manual
SEG_SIN_SENAL = 120                 # reloj real: el ESP32 manda cada ~10 s
DIAS_CLIMA_REPETIDO = 3             # calor/humedad en al menos 3 dias de la semana
OCULTAR_RESUELTO = timedelta(hours=24)
CACHE_ACH_S = 600

PRIORIDAD = {"alta": 0, "media": 1, "baja": 2}

SENSORES = {
    "co2_ppm": "el sensor de aire (CO₂)",
    "temp_c": "el sensor de temperatura y humedad",
    "lux": "el sensor de luz",
    "ocupantes_conteo": "los sensores de la puerta",
}

NOMBRE_EQUIPO = {"ventilacion": "La ventilación", "iluminacion": "Las luces"}


def _min_aula(desde: datetime, ahora: datetime) -> float:
    return (ahora - desde).total_seconds() / 60.0 * settings.SIM_VELOCIDAD


def _texto_duracion(minutos: float) -> str:
    m = int(minutos)
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h} h" + (f" {r} min" if r else "")


async def _ach(redis, db: AsyncSession, aula_id: int) -> float | None:
    """ACH por decaimiento, cacheado: el calculo recorre 7 dias de lecturas."""
    from app.routers.reportes import tasa_renovacion

    clave = f"ach:{aula_id}"
    guardado = await redis.get(clave)
    if guardado is not None:
        v = json.loads(guardado)
        return v.get("ach")
    res = await tasa_renovacion(aula_id=aula_id, dias=7, db=db)
    await redis.setex(clave, CACHE_ACH_S, json.dumps({"ach": res.get("ach")}))
    return res.get("ach")


async def calcular(db: AsyncSession, redis) -> dict:
    ahora = datetime.now(timezone.utc)
    filas = (await db.execute(
        select(Aula, Sede).join(Sede, Aula.sede_id == Sede.id).order_by(Aula.codigo)
    )).all()

    vivos: dict[int, dict] = {}
    for aula, _ in filas:
        raw = await redis.get(f"aula:{aula.id}:ultimo")
        if raw:
            vivos[aula.id] = json.loads(raw)

    # ultima lectura de cada aula (para saber cuales miden y cuales se callaron)
    ultima_ts = dict((await db.execute(
        select(Lectura.aula_id, func.max(Lectura.ts))
        .where(Lectura.ts >= ahora - timedelta(days=7))
        .group_by(Lectura.aula_id)
    )).all())

    pendientes: list[dict] = []

    def agregar(tipo, prioridad, aula, sede, titulo, detalle, accion, desde=None, boton=None, extra=""):
        pendientes.append({
            "clave": f"{tipo}:{aula.id}" + (f":{extra}" if extra else ""),
            "tipo": tipo, "prioridad": prioridad,
            "aula_id": aula.id, "codigo": aula.codigo, "sede_slug": sede.slug,
            "titulo": titulo, "detalle": detalle, "accion": accion,
            "desde": desde.isoformat() if desde else None,
            "boton": boton,
        })

    # ---------- 1. sin señal (aula entera o un sensor) ----------
    for aula, sede in filas:
        ult = ultima_ts.get(aula.id)
        if ult is None:
            continue  # nunca midio esta semana: no tiene equipos, no es una falla
        if (ahora - ult).total_seconds() > SEG_SIN_SENAL:
            agregar(
                "sin_senal", "alta", aula, sede,
                f"El aula {aula.codigo} no envía datos",
                f"Su último dato llegó hace {_texto_duracion((ahora - ult).total_seconds() / 60)} "
                "(reloj real). Mientras tanto el sistema no puede vigilar ni ventilar esta aula.",
                "Revisar que el equipo esté enchufado y conectado al WiFi.",
                desde=ult,
            )
            continue
        # aula viva: ¿algun sensor dejo de medir? ultimas 10 lecturas vs. ultimas 24 h
        recientes = (await db.execute(
            select(Lectura).where(Lectura.aula_id == aula.id)
            .order_by(Lectura.ts.desc()).limit(10)
        )).scalars().all()
        if len(recientes) < 10:
            continue
        for campo, nombre in SENSORES.items():
            if any(getattr(r, campo) is not None for r in recientes):
                continue
            antes = (await db.execute(
                select(func.max(Lectura.ts)).where(
                    Lectura.aula_id == aula.id,
                    Lectura.ts >= ahora - timedelta(hours=24),
                    getattr(Lectura, campo).isnot(None),
                )
            )).scalar()
            if antes is not None:  # antes media y ahora no: se daño o se desconecto
                agregar(
                    "sin_senal", "alta", aula, sede,
                    f"Falla {nombre} del aula {aula.codigo}",
                    "Ese sensor dejó de enviar datos, aunque el resto del equipo sigue funcionando.",
                    "Revisar el cable o la conexión de ese sensor.",
                    desde=antes, extra=campo,
                )

    # ---------- 2. el ventilador no alcanza ----------
    for aula, sede in filas:
        v = vivos.get(aula.id)
        if not v or not v.get("ventilacion_on") or (v.get("co2_ppm") or 0) < settings.CO2_UMBRAL_ALERTA:
            continue
        ult_vent = (await db.execute(
            select(Actuacion).where(Actuacion.aula_id == aula.id, Actuacion.actuador == "ventilacion")
            .order_by(Actuacion.ts.desc()).limit(1)
        )).scalar_one_or_none()
        if not ult_vent or ult_vent.accion != "on":
            continue
        minutos = _min_aula(ult_vent.ts, ahora)
        if minutos >= MIN_VENTILANDO_SIN_EFECTO:
            agregar(
                "no_alcanza", "alta", aula, sede,
                f"El ventilador del aula {aula.codigo} no alcanza",
                f"Lleva {_texto_duracion(minutos)} encendido y el aire sigue cargado "
                f"({v['co2_ppm']:.0f} ppm). El sistema ya hizo lo que podía.",
                "Abrir puertas y ventanas, o hacer una pausa con el grupo fuera del aula.",
                desde=ult_vent.ts,
            )

    # ---------- 3. ventila mal (infraestructura) ----------
    achs: dict[int, float] = {}
    for aula, _ in filas:
        if aula.id in ultima_ts:
            a = await _ach(redis, db, aula.id)
            if a is not None:
                achs[aula.id] = a
    por_sede: dict[int, list[float]] = {}
    for aula, _ in filas:
        if aula.id in achs:
            por_sede.setdefault(aula.sede_id, []).append(achs[aula.id])
    for aula, sede in filas:
        ach = achs.get(aula.id)
        if ach is None:
            continue
        otros = por_sede.get(aula.sede_id, [])
        ref = median(otros) if len(otros) >= 3 else None
        if ach < 1.0:
            motivo = f"Su aire se renueva {ach:.1f} veces por hora; lo mínimo recomendable es 1."
        elif ref and ach < 0.5 * ref:
            motivo = (f"Su aire se renueva {ach:.1f} veces por hora, menos de la mitad que las "
                      f"demás aulas de la sede ({ref:.1f}).")
        else:
            continue
        agregar(
            "ventila_mal", "media", aula, sede,
            f"El aula {aula.codigo} ventila mal",
            motivo + " Se midió viendo qué tan rápido baja el CO₂ con el aula vacía.",
            "Revisar ventanas, rejillas y el extractor.",
        )

    # ---------- 4. equipo olvidado en manual ----------
    for aula, sede in filas:
        for actuador in ("ventilacion", "iluminacion"):
            if getattr(aula, f"modo_{actuador}") != "manual":
                continue
            desde = (await db.execute(
                select(func.max(Evento.ts)).where(
                    Evento.aula_id == aula.id, Evento.tipo == "modo_manual",
                    Evento.variable == actuador,
                )
            )).scalar()
            if desde is None or _min_aula(desde, ahora) >= MIN_MANUAL_OLVIDADO:
                durante = f" desde hace {_texto_duracion(_min_aula(desde, ahora))}" if desde else ""
                plural = actuador == "iluminacion"   # "las luces" / "la ventilacion"
                agregar(
                    "manual", "media", aula, sede,
                    f"{NOMBRE_EQUIPO[actuador]} del aula {aula.codigo} "
                    f"{'siguen' if plural else 'sigue'} en manual",
                    f"{'Están' if plural else 'Está'} en modo manual{durante}, así que el sistema "
                    f"no {'las' if plural else 'la'} enciende ni apaga aunque haga falta.",
                    "Si ya no hace falta, volver a automático.",
                    desde=desde, extra=actuador,
                    boton={"tipo": "volver_automatico", "actuador": actuador},
                )

    # ---------- 5. calor o humedad que se repite ----------
    dias = (await db.execute(
        select(Evento.aula_id, Evento.tipo, func.count(func.distinct(func.date(Evento.ts))))
        .where(Evento.tipo.in_(["temp_alerta", "hum_alerta"]),
               Evento.ts >= ahora - timedelta(days=7))
        .group_by(Evento.aula_id, Evento.tipo)
    )).all()
    por_id = {a.id: (a, s) for a, s in filas}
    for aula_id, tipo, n in dias:
        if n < DIAS_CLIMA_REPETIDO or aula_id not in por_id:
            continue
        aula, sede = por_id[aula_id]
        calor = tipo == "temp_alerta"
        agregar(
            "clima", "baja", aula, sede,
            f"El aula {aula.codigo} {'pasa calor' if calor else 'está muy húmeda'} seguido",
            f"Pasó {n} de los últimos 7 días "
            + (f"sobre {settings.TEMP_UMBRAL_ALERTA:.0f} °C." if calor
               else f"sobre {settings.HUM_UMBRAL_ALERTA:.0f} % de humedad."),
            "Considerar persianas, cortinas o aire acondicionado." if calor
            else "Revisar filtraciones y mejorar la ventilación natural.",
            extra=tipo,
        )

    # ---------- ocultar los marcados como resueltos (24 h) ----------
    resueltos = dict((await db.execute(
        select(PendienteResuelto.clave, PendienteResuelto.ts)
        .where(PendienteResuelto.ts >= ahora - OCULTAR_RESUELTO)
    )).all())
    visibles = [p for p in pendientes if p["clave"] not in resueltos]
    visibles.sort(key=lambda p: (PRIORIDAD[p["prioridad"]], p["codigo"]))

    # ---------- lo que el sistema resolvio solo ----------
    hace24 = ahora - timedelta(hours=24)
    acciones = (await db.execute(
        select(func.count()).select_from(Actuacion)
        .where(Actuacion.ts >= hace24, Actuacion.origen == "automatico")
    )).scalar() or 0
    alertas = (await db.execute(
        select(func.count()).select_from(Evento)
        .where(Evento.ts >= hace24, Evento.tipo.in_(["co2_alerta", "co2_critico"]))
    )).scalar() or 0

    return {
        "pendientes": visibles,
        "ocultos": len(pendientes) - len(visibles),
        "resumen": {"acciones_automaticas_24h": acciones, "alertas_24h": alertas},
    }
