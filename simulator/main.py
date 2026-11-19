"""Simulador de aulas.

Reemplaza al hardware mientras no existan los sensores. Publica en los
mismos topics MQTT y con el mismo payload que el ESP32, asi que el resto
del sistema no distingue si los datos vienen de aqui o de un aula real.

Modela el fenomeno de verdad, no numeros aleatorios:

    dC/dt = (N * G) / V  -  (Q / V) * (C - C_ext)

Con horario escolar: el aula se llena, el CO2 sube; en el recreo se
vacia y se ventila, y la curva decae. Eso produce exactamente el patron
en dientes de sierra que se ve en un aula real y que hace creible la demo.

Ademas escucha los comandos del backend: cuando el sistema decide
ventilar, el simulador SUBE el caudal de aire y la curva se dobla. El
lazo cerrado queda visible en el dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

import aiomqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("simulador")

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
BASE = os.getenv("MQTT_BASE_TOPIC", "smartclassroom")

SEDE = os.getenv("SIM_SEDE", "lima-norte")
AULAS = [a.strip() for a in os.getenv("SIM_AULAS", "302,303,304,305,401,402,403,404").split(",") if a.strip()]
INTERVALO_S = float(os.getenv("SIM_INTERVALO_S", "5"))
# de aqui saca aforo, volumen y nivel de cada aula, para simular las mismas
# aulas que muestra el dashboard (antes se inventaban al azar y salian cosas
# como 31 personas en un aula de aforo 28)
API_URL = os.getenv("SIM_API_URL", "http://api:8000")
# 60 = un minuto simulado por segundo real. Asi una jornada completa se
# ve en minutos y la demo no depende de esperar horas.
VELOCIDAD = float(os.getenv("SIM_VELOCIDAD", "60"))

C_EXT = 420.0
G_PERSONA = 0.0052 / 1000.0          # m3/s, adulto sentado
FACTOR_NIVEL = {"inicial": 0.45, "primaria": 0.65, "secundaria": 0.85}

ACH_CERRADA = 0.6      # puerta y ventanas cerradas
ACH_VENTILADA = 6.0    # ventilador encendido / ventanas abiertas
ACH_RECREO = 9.0       # aula vacia con puerta abierta


@dataclass
class AulaSim:
    codigo: str
    volumen: float
    aforo: int
    nivel: str
    co2: float = 480.0
    temp: float = 21.5
    hum: float = 58.0
    ventilacion_on: bool = False
    ventilacion_hasta: float = 0.0
    # cada aula arranca con una "calidad de ventilacion" distinta:
    # asi el ranking de aulas del dashboard tiene sentido
    factor_fuga: float = 1.0
    ocupantes: int = 0
    iluminacion_on: bool = False
    # cuanta luz natural entra (ventanas, orientacion). Algunas aulas son
    # oscuras y necesitan luz artificial casi todo el dia.
    factor_luz: float = field(default_factory=lambda: random.uniform(0.4, 1.2))
    minuto: float = 0.0
    _sesgo: float = field(default_factory=lambda: random.uniform(-0.15, 0.15))


def leer_aulas_api() -> dict[str, dict]:
    """codigo -> {aforo_nominal, volumen_m3, nivel} desde la API."""
    with urllib.request.urlopen(f"{API_URL}/api/aulas?sede={SEDE}", timeout=5) as r:
        return {a["codigo"]: a for a in json.load(r)}


async def datos_de_la_base(intentos: int = 30) -> dict[str, dict]:
    """Espera a que la API este arriba (arranca junto con el simulador).
    Si nunca responde, devuelve {} y se usan valores por defecto."""
    for i in range(intentos):
        try:
            datos = await asyncio.to_thread(leer_aulas_api)
            log.info("aforo y volumen de %d aulas leidos de la base", len(datos))
            return datos
        except Exception as exc:
            if i == 0:
                log.info("esperando a la API en %s (%s)", API_URL, exc)
            await asyncio.sleep(2)
    log.warning("la API no respondio: aforo y volumen por defecto")
    return {}


def construir_aulas(base: dict[str, dict]) -> dict[str, AulaSim]:
    aulas: dict[str, AulaSim] = {}
    for i, cod in enumerate(AULAS):
        nivel = "secundaria" if cod.startswith("3") else ("primaria" if cod.startswith("4") else "secundaria")
        if cod == "404":
            nivel = "inicial"
        d = base.get(cod)
        if d is None and base:
            log.warning("el aula %s no esta en la base (corre el seed): valores por defecto", cod)
        aulas[cod] = AulaSim(
            codigo=cod,
            volumen=float(d["volumen_m3"]) if d else 170.0,
            aforo=int(d["aforo_nominal"]) if d else 32,
            nivel=d["nivel"] if d else nivel,
            # el aula 303 ventila mal a proposito: es la que el reporte
            # de renovacion debe detectar
            factor_fuga=0.45 if cod == "303" else random.uniform(0.85, 1.25),
        )
    return aulas


def minuto_escolar(t_sim: float) -> float:
    """Minutos transcurridos desde las 07:30 dentro de una jornada de 7h."""
    return (t_sim / 60.0) % (7 * 60)


def ocupacion_objetivo(aula: AulaSim, minuto: float) -> int:
    """Horario: bloques de clase de 90 min con recreos de 20 min."""
    ciclo = minuto % 110
    if ciclo > 90:                       # recreo
        return 0
    if minuto < 10:                      # llegando
        return int(aula.aforo * minuto / 10)
    if minuto > 6 * 60 + 40:             # salida
        return 0
    # pequenas ausencias
    return max(0, aula.aforo - random.randint(0, 3))


async def publicar_estado(cliente: aiomqtt.Client, aula: AulaSim) -> None:
    payload = {
        "device_id": f"sim-{aula.codigo}",
        "ts": datetime.now(timezone.utc).timestamp(),
        "co2_ppm": round(aula.co2, 1),
        "temp_c": round(aula.temp, 2),
        "hum_pct": round(aula.hum, 1),
        "lux": round(lux_medido(aula), 0),
        "db_spl": round(38 + aula.ocupantes * 0.55 + random.uniform(-3, 3), 1),
        "ocupantes": aula.ocupantes,
        "fw": "sim-1.0.0",
    }
    await cliente.publish(f"{BASE}/{SEDE}/{aula.codigo}/telemetria", json.dumps(payload), qos=0)


LUX_ARTIFICIAL = 420.0   # lo que aportan las luminarias en el pupitre


def lux_medido(aula: AulaSim) -> float:
    """Luz natural que sube hacia el mediodia y baja en la tarde, mas la
    artificial si las luces estan prendidas."""
    natural = 60 + 420 * aula.factor_luz * math.sin(math.pi * min(aula.minuto, 420) / 420)
    total = natural + (LUX_ARTIFICIAL if aula.iluminacion_on else 0.0)
    return max(0.0, total + random.uniform(-25, 25))


def avanzar(aula: AulaSim, dt_sim_s: float, ahora: float) -> None:
    """Un paso de la ecuacion de balance de masa."""
    if aula.ventilacion_on and ahora > aula.ventilacion_hasta:
        aula.ventilacion_on = False

    if aula.ocupantes == 0:
        ach = ACH_RECREO * aula.factor_fuga
    elif aula.ventilacion_on:
        ach = ACH_VENTILADA * aula.factor_fuga
    else:
        ach = ACH_CERRADA * aula.factor_fuga

    g = G_PERSONA * FACTOR_NIVEL.get(aula.nivel, 0.85)
    generacion = (aula.ocupantes * g) / aula.volumen * 1e6      # ppm/s
    dilucion = (ach / 3600.0) * (aula.co2 - C_EXT)              # ppm/s

    aula.co2 += (generacion - dilucion) * dt_sim_s
    aula.co2 = max(C_EXT - 5, min(5000.0, aula.co2 + random.uniform(-1.5, 1.5)))

    # la temperatura sigue a la ocupacion con inercia
    objetivo_t = 20.5 + aula.ocupantes * 0.14 + aula._sesgo
    if aula.ventilacion_on:
        objetivo_t -= 1.8
    aula.temp += (objetivo_t - aula.temp) * min(1.0, dt_sim_s / 900.0)
    aula.temp += random.uniform(-0.03, 0.03)

    objetivo_h = 54 + aula.ocupantes * 0.32
    if aula.ventilacion_on:
        objetivo_h -= 4
    aula.hum += (objetivo_h - aula.hum) * min(1.0, dt_sim_s / 1200.0)
    aula.hum = max(25.0, min(92.0, aula.hum + random.uniform(-0.15, 0.15)))


async def escuchar_comandos(cliente: aiomqtt.Client, aulas: dict[str, AulaSim]) -> None:
    """Cierra el lazo: cuando el backend ordena ventilar, la curva se dobla."""
    await cliente.subscribe(f"{BASE}/{SEDE}/+/comando", qos=1)
    async for msg in cliente.messages:
        partes = str(msg.topic).split("/")
        if len(partes) < 4:
            continue
        codigo = partes[2]
        aula = aulas.get(codigo)
        if not aula:
            continue
        try:
            cmd = json.loads(msg.payload.decode())
        except Exception:
            continue
        if cmd.get("actuador") == "iluminacion":
            aula.iluminacion_on = cmd.get("accion") == "on"
            log.info("aula %s -> luces %s (%s)", codigo,
                     "ON" if aula.iluminacion_on else "off", cmd.get("motivo", ""))
            continue
        if cmd.get("actuador") != "ventilacion":
            continue

        if cmd.get("accion") == "on":
            aula.ventilacion_on = True
            aula.ventilacion_hasta = asyncio.get_event_loop().time() + float(cmd.get("ttl_s", 600)) / VELOCIDAD
            log.info("aula %s -> VENTILACION ON (%s)", codigo, cmd.get("motivo", ""))
        else:
            aula.ventilacion_on = False
            log.info("aula %s -> ventilacion off", codigo)


async def bucle_telemetria(cliente: aiomqtt.Client, aulas: dict[str, AulaSim]) -> None:
    t_sim = 0.0
    dt_sim = INTERVALO_S * VELOCIDAD
    log.info(
        "simulando %d aulas de %s | %.0fs reales = %.0f min simulados",
        len(aulas), SEDE, INTERVALO_S, dt_sim / 60,
    )
    while True:
        minuto = minuto_escolar(t_sim)
        ahora = asyncio.get_event_loop().time()
        for aula in aulas.values():
            aula.minuto = minuto
            objetivo = ocupacion_objetivo(aula, minuto)
            # transicion suave para que la entrada y salida no sea un escalon
            if aula.ocupantes < objetivo:
                aula.ocupantes = min(objetivo, aula.ocupantes + max(1, aula.aforo // 4))
            elif aula.ocupantes > objetivo:
                aula.ocupantes = max(objetivo, aula.ocupantes - max(1, aula.aforo // 3))

            avanzar(aula, dt_sim, ahora)
            await publicar_estado(cliente, aula)

        t_sim += dt_sim
        await asyncio.sleep(INTERVALO_S)


async def main() -> None:
    aulas = construir_aulas(await datos_de_la_base())
    while True:
        try:
            async with aiomqtt.Client(
                hostname=MQTT_HOST, port=MQTT_PORT,
                username=MQTT_USER or None, password=MQTT_PASSWORD or None,
                identifier="sc-simulador",
            ) as cliente:
                log.info("conectado a mqtt://%s:%s", MQTT_HOST, MQTT_PORT)
                await asyncio.gather(
                    bucle_telemetria(cliente, aulas),
                    escuchar_comandos(cliente, aulas),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("mqtt caido (%s); reintento en 5s", exc)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("simulador detenido")
