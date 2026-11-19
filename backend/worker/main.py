"""Worker de ingesta.

Es el corazón del sistema:

    MQTT  ->  valida  ->  motor de reglas  ->  PostgreSQL
                                  |
                                  +--> MQTT (comando al actuador)
                                  +--> Redis (empuja al dashboard)

Corre como proceso aparte de la API para que se puedan escalar por
separado y para que un reinicio del dashboard no interrumpa la ingesta.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiomqtt
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import SessionLocal, crear_tablas
from app.models import Actuacion, Aula, Dispositivo, Evento, Lectura, Pronostico, Sede
from app.services import reglas
from aprendizaje import que_mira
from aprendizaje.pronosticador import Pronosticador

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

# ventanas móviles en memoria, una por aula
ESTADOS: dict[int, reglas.EstadoAula] = {}
# cache slug/codigo -> (aula_id, volumen, nivel)
CACHE_AULAS: dict[tuple[str, str], tuple[int, float, str]] = {}
# modo guardado en la base de cada aula, para el EstadoAula que se cree
MODOS_INICIALES: dict[int, dict[str, str]] = {}

# pronostico del aire en modo prueba (ver aprendizaje/pronosticador.py)
PRONOSTICO = Pronosticador(velocidad=settings.SIM_VELOCIDAD)
# para no anotar un pronostico por lectura: uno cada tanto por aula alcanza
ANOTAR_PRONOSTICO_CADA_S = 30.0
ULTIMO_PRONOSTICO_ANOTADO: dict[int, float] = {}


# --------------------------------------------------------------- utilidades
def parsear_topic(topic: str) -> tuple[str, str] | None:
    """smartclassroom/{sede}/{aula}/telemetria -> (sede, aula)"""
    partes = topic.split("/")
    if len(partes) < 4 or partes[0] != settings.MQTT_BASE_TOPIC:
        return None
    return partes[1], partes[2]


async def resolver_aula(db: AsyncSession, sede_slug: str, codigo: str):
    clave = (sede_slug, codigo)
    if clave in CACHE_AULAS:
        return CACHE_AULAS[clave]

    fila = (
        await db.execute(
            select(Aula)
            .join(Sede, Aula.sede_id == Sede.id)
            .where(Sede.slug == sede_slug, Aula.codigo == codigo)
        )
    ).scalar_one_or_none()

    if not fila:
        log.warning("telemetria de un aula desconocida: %s/%s (corre el seed)", sede_slug, codigo)
        return None

    CACHE_AULAS[clave] = (fila.id, fila.volumen_m3, fila.nivel)
    MODOS_INICIALES[fila.id] = {
        "ventilacion": fila.modo_ventilacion or "automatico",
        "iluminacion": fila.modo_iluminacion or "automatico",
    }
    return CACHE_AULAS[clave]


def estado_de(aula_id: int, volumen: float, nivel: str) -> reglas.EstadoAula:
    st = ESTADOS.get(aula_id)
    if st is None:
        st = reglas.EstadoAula(aula_id=aula_id, volumen_m3=volumen, nivel=nivel)
        st.modo.update(MODOS_INICIALES.get(aula_id, {}))
        ESTADOS[aula_id] = st
    return st


def num(d: dict, clave: str) -> float | None:
    v = d.get(clave)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # descarta lecturas imposibles (sensor desconectado suele dar 0 o -999)
    if clave == "co2_ppm" and not (300 <= f <= 12000):
        return None
    if clave == "temp_c" and not (-10 <= f <= 60):
        return None
    if clave == "hum_pct" and not (0 <= f <= 100):
        return None
    return f


# ------------------------------------------------------------- procesamiento
async def procesar(
    db: AsyncSession,
    redis: aioredis.Redis,
    mqtt: aiomqtt.Client,
    sede_slug: str,
    codigo: str,
    payload: dict,
) -> None:
    info = await resolver_aula(db, sede_slug, codigo)
    if not info:
        return
    aula_id, volumen, nivel = info

    ts_epoch = payload.get("ts") or datetime.now(timezone.utc).timestamp()
    lectura = {
        "ts": float(ts_epoch),
        "co2_ppm": num(payload, "co2_ppm"),
        "temp_c": num(payload, "temp_c"),
        "hum_pct": num(payload, "hum_pct"),
        "lux": num(payload, "lux"),
        "db_spl": num(payload, "db_spl"),
    }
    ocupantes = payload.get("ocupantes")
    try:
        lectura["ocupantes"] = int(ocupantes) if ocupantes is not None else None
    except (TypeError, ValueError):
        lectura["ocupantes"] = None

    st = estado_de(aula_id, volumen, nivel)
    decision = reglas.evaluar(
        st, lectura,
        co2_alerta=settings.CO2_UMBRAL_ALERTA,
        co2_critico=settings.CO2_UMBRAL_CRITICO,
        temp_alerta=settings.TEMP_UMBRAL_ALERTA,
        hum_alerta=settings.HUM_UMBRAL_ALERTA,
        ventana_s=settings.PREDICCION_VENTANA_S,
        anticipacion_s=settings.PREDICCION_ANTICIPACION_S,
        ttl_s=settings.VENTILACION_TTL_S,
        factor_aceleracion=settings.SIM_VELOCIDAD,
        lux_minimo=settings.LUX_MINIMO,
        luz_apagar_vacia_s=settings.LUZ_APAGAR_VACIA_S,
        temp_histeresis=settings.TEMP_HISTERESIS,
    )

    ts_dt = datetime.fromtimestamp(lectura["ts"], tz=timezone.utc)

    # ---- pronostico (modo prueba: no decide nada) ----
    co2_previsto = PRONOSTICO.anotar_y_prever(
        aula_id=aula_id, ts=lectura["ts"], co2=lectura["co2_ppm"],
        personas=float(ocupantes) if ocupantes is not None else decision.ocupantes_estimado,
        ventilacion=st.ventilacion_on, temperatura=lectura["temp_c"],
        humedad=lectura["hum_pct"], ruido=lectura["db_spl"], tamano_aula=volumen,
    )
    pronostico = None
    if co2_previsto is not None and lectura["co2_ppm"] is not None:
        # lo que diria el metodo de hoy: seguir la misma subida (ya en minutos del aula)
        co2_linea = None
        if decision.pendiente_ppm_min is not None:
            co2_linea = float(min(5000.0, max(400.0,
                lectura["co2_ppm"] + decision.pendiente_ppm_min * que_mira.MINUTOS_ADELANTE)))
        pronostico = {
            "minutos_adelante": que_mira.MINUTOS_ADELANTE,
            "co2_previsto": round(co2_previsto, 1),
            "co2_linea_recta": round(co2_linea, 1) if co2_linea is not None else None,
        }
        if lectura["ts"] - ULTIMO_PRONOSTICO_ANOTADO.get(aula_id, 0.0) >= ANOTAR_PRONOSTICO_CADA_S:
            ULTIMO_PRONOSTICO_ANOTADO[aula_id] = lectura["ts"]
            adelante_s = que_mira.segundos_de_reloj(que_mira.MINUTOS_ADELANTE, settings.SIM_VELOCIDAD)
            db.add(Pronostico(
                aula_id=aula_id, ts=ts_dt,
                ts_objetivo=datetime.fromtimestamp(lectura["ts"] + adelante_s, tz=timezone.utc),
                minutos_adelante=que_mira.MINUTOS_ADELANTE,
                co2_ahora=lectura["co2_ppm"], co2_previsto=co2_previsto,
                co2_linea_recta=co2_linea,
            ))

    # ---- persistir lectura ----
    db.add(
        Lectura(
            aula_id=aula_id,
            ts=ts_dt,
            co2_ppm=lectura["co2_ppm"],
            temp_c=lectura["temp_c"],
            hum_pct=lectura["hum_pct"],
            lux=lectura["lux"],
            db_spl=lectura["db_spl"],
            ocupantes_conteo=int(ocupantes) if ocupantes is not None else None,
            ocupantes_estimado=decision.ocupantes_estimado,
            indice=decision.indice,
            estado=decision.estado,
            ventilacion_on=st.ventilacion_on,
        )
    )

    # ---- eventos ----
    for e in decision.eventos:
        db.add(
            Evento(
                aula_id=aula_id, ts=ts_dt, tipo=e["tipo"], severidad=e["severidad"],
                variable=e.get("variable", ""), valor=e.get("valor"),
                indice=e.get("indice"), mensaje=e.get("mensaje", ""),
            )
        )

    # ---- actuación ----
    for act in decision.actuaciones:
        db.add(Actuacion(aula_id=aula_id, ts=ts_dt, **act))

    # ---- marcar dispositivo vivo ----
    device_id = payload.get("device_id")
    if device_id:
        disp = (
            await db.execute(select(Dispositivo).where(Dispositivo.device_id == device_id))
        ).scalar_one_or_none()
        if disp:
            disp.ultimo_visto = ts_dt
            if payload.get("fw"):
                disp.firmware = str(payload["fw"])

    await db.commit()

    # ---- publicar comandos a los actuadores ----
    topic = settings.topic_comando(sede_slug, codigo)
    for cmd in decision.comandos:
        await mqtt.publish(topic, json.dumps(cmd), qos=1)
        log.info("aula %s/%s -> %s %s (%s)",
                 sede_slug, codigo, cmd["actuador"], cmd["accion"], cmd["motivo"])

    # ---- empujar al dashboard ----
    snapshot = {
        "tipo": "telemetria",
        "aula_id": aula_id,
        "sede_slug": sede_slug,
        "codigo": codigo,
        "ts": ts_dt.isoformat(),
        "co2_ppm": lectura["co2_ppm"],
        "temp_c": lectura["temp_c"],
        "hum_pct": lectura["hum_pct"],
        "lux": lectura["lux"],
        "db_spl": lectura["db_spl"],
        "ocupantes": ocupantes if ocupantes is not None else decision.ocupantes_estimado,
        "ocupantes_estimado": decision.ocupantes_estimado,
        "indice": decision.indice,
        "estado": decision.estado,
        "subindices": decision.subindices,
        "pendiente_ppm_min": decision.pendiente_ppm_min,
        "eta_s": decision.eta_s,
        "ventilacion_on": st.ventilacion_on,
        "iluminacion_on": st.iluminacion_on,
        # actuadores en pausa por una orden manual (la automatizacion no los toca)
        "override_manual": [a for a in ("ventilacion", "iluminacion")
                            if st.en_override(a, lectura["ts"])],
        "modos": dict(st.modo),
        "pronostico": pronostico,
    }
    await redis.publish(settings.CANAL_TELEMETRIA, json.dumps(snapshot))
    # cache para que /api/estado no haga un SELECT por aula
    await redis.setex(f"aula:{aula_id}:ultimo", 120, json.dumps(snapshot))

    for e in decision.eventos:
        await redis.publish(
            settings.CANAL_EVENTOS,
            json.dumps({"tipo": "evento", "aula_id": aula_id, "codigo": codigo,
                        "ts": ts_dt.isoformat(), **e}),
        )


async def registrar_override(sede_slug: str, codigo: str, payload: dict) -> None:
    """Una persona mando una orden desde el dashboard: la automatizacion de
    ese actuador se pausa para no deshacerla en la siguiente lectura.

    Solo cuentan las ordenes con origen "manual": las que publica el propio
    worker (origen "automatico") tambien vuelven por este topic y se ignoran.
    """
    if payload.get("origen") != "manual":
        return
    actuador, accion = payload.get("actuador"), payload.get("accion")
    if actuador not in ("ventilacion", "iluminacion") or accion not in ("on", "off"):
        return
    async with SessionLocal() as db:
        info = await resolver_aula(db, sede_slug, codigo)
    if not info:
        return
    aula_id, volumen, nivel = info
    duracion_real_s = settings.OVERRIDE_MANUAL_S / max(settings.SIM_VELOCIDAD, 1e-6)
    estado_de(aula_id, volumen, nivel).aplicar_manual(
        actuador, accion, datetime.now(timezone.utc).timestamp(), duracion_real_s
    )
    log.info("aula %s/%s: override manual %s %s, automatizacion en pausa %.0fs",
             sede_slug, codigo, actuador, accion, duracion_real_s)


async def registrar_modo(sede_slug: str, codigo: str, payload: dict) -> None:
    """Cambio de modo automatico/manual desde el dashboard."""
    actuador, modo = payload.get("actuador"), payload.get("modo")
    if actuador not in ("ventilacion", "iluminacion") or modo not in ("automatico", "manual"):
        return
    async with SessionLocal() as db:
        info = await resolver_aula(db, sede_slug, codigo)
    if not info:
        return
    aula_id, volumen, nivel = info
    MODOS_INICIALES.setdefault(aula_id, {})[actuador] = modo
    estado_de(aula_id, volumen, nivel).cambiar_modo(actuador, modo)
    log.info("aula %s/%s: %s en modo %s", sede_slug, codigo, actuador, modo)


# --------------------------------------------------------------------- loop
async def correr() -> None:
    await crear_tablas()
    redis = aioredis.from_url(settings.REDIS_URL)
    log.info("worker iniciado, conectando a mqtt://%s:%s", settings.MQTT_HOST, settings.MQTT_PORT)

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.MQTT_HOST,
                port=settings.MQTT_PORT,
                username=settings.MQTT_USER or None,
                password=settings.MQTT_PASSWORD or None,
                identifier="sc-worker",
            ) as mqtt:
                await mqtt.subscribe(settings.topic_telemetria, qos=1)
                await mqtt.subscribe(settings.topic_comandos, qos=1)
                await mqtt.subscribe(settings.topic_modos, qos=1)
                log.info("suscrito a %s y %s", settings.topic_telemetria, settings.topic_comandos)

                async for mensaje in mqtt.messages:
                    topic = str(mensaje.topic)
                    partes = parsear_topic(topic)
                    if not partes:
                        continue
                    sede_slug, codigo = partes

                    try:
                        payload = json.loads(mensaje.payload.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        log.warning("payload invalido en %s", topic)
                        continue

                    if topic.endswith("/modo"):
                        try:
                            await registrar_modo(sede_slug, codigo, payload)
                        except Exception:
                            log.exception("error registrando modo %s", topic)
                        continue

                    if topic.endswith("/comando"):
                        try:
                            await registrar_override(sede_slug, codigo, payload)
                        except Exception:
                            log.exception("error registrando override %s", topic)
                        continue

                    try:
                        async with SessionLocal() as db:
                            await procesar(db, redis, mqtt, sede_slug, codigo, payload)
                    except Exception:
                        log.exception("error procesando %s", topic)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("conexion mqtt perdida (%s); reintento en 5s", exc)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(correr())
    except KeyboardInterrupt:
        log.info("worker detenido")
