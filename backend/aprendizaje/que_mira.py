"""Lo que el pronostico mira para adivinar el CO2 de dentro de 10 minutos.

Este archivo lo usan los dos lados: el entrenamiento (con el historial) y el
worker (en vivo). Que sea el MISMO codigo es a proposito: si el pronostico
aprende con una cuenta y en vivo se hace otra distinta, se equivoca sin
que nadie se de cuenta.

Sobre el tiempo: todos los "minutos" de aqui son minutos del aula. Con el
hardware real coinciden con el reloj. Con el simulador acelerado
(SIM_VELOCIDAD=5) un minuto del aula pasa en 12 segundos de reloj, por eso
todo se convierte con segundos_de_reloj().
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

# cuanto hacia adelante adivina
MINUTOS_ADELANTE = 10.0

# donde queda guardado lo aprendido (la carpeta esta montada en api y worker)
CARPETA_GUARDADO = Path(__file__).resolve().parent / "guardado"
ARCHIVO_APRENDIDO = CARPETA_GUARDADO / "pronostico_co2.joblib"
ARCHIVO_INFORME = CARPETA_GUARDADO / "informe.json"

DATOS_QUE_MIRA = [
    "co2_ahora",
    "subida_ultimos_5_min",
    "subida_ultimos_15_min",
    "personas_en_el_aula",
    "ventilacion_encendida",
    "temperatura",
    "humedad",
    "ruido",
    "tamano_del_aula_m3",
]

# La hora y el dia solo sirven con datos reales: el simulador repite su
# propio horario escolar sin relacion con la hora del reloj, y el pronostico
# aprenderia una costumbre que no existe.
DATOS_DE_HORARIO = ["hora_del_dia", "dia_de_la_semana"]

# Peru no cambia de hora en el ano: basta con un desfase fijo
HORA_PERU = timezone(timedelta(hours=-5))


def segundos_de_reloj(minutos_del_aula: float, velocidad: float) -> float:
    return minutos_del_aula * 60.0 / max(velocidad, 1e-6)


def margen_de_busqueda(segundos: float) -> float:
    """Que tan lejos puede estar una lectura del momento buscado y seguir valiendo."""
    return max(20.0, 0.2 * segundos)


def co2_en(ts: np.ndarray, co2: np.ndarray, momentos: np.ndarray, margen_s: float) -> np.ndarray:
    """CO2 de la lectura mas cercana a cada momento. NaN si no hay ninguna cerca.

    `ts` tiene que venir ordenado de menor a mayor.
    """
    momentos = np.asarray(momentos, dtype=float)
    if len(ts) == 0:
        return np.full(momentos.shape, np.nan)
    pos = np.searchsorted(ts, momentos)
    antes = np.clip(pos - 1, 0, len(ts) - 1)
    despues = np.clip(pos, 0, len(ts) - 1)
    usar_despues = np.abs(ts[despues] - momentos) < np.abs(ts[antes] - momentos)
    cual = np.where(usar_despues, despues, antes)
    distancia = np.abs(ts[cual] - momentos)
    return np.where(distancia <= margen_s, co2[cual], np.nan)


def columnas(con_horario: bool) -> list[str]:
    return DATOS_QUE_MIRA + (DATOS_DE_HORARIO if con_horario else [])


def armar_tabla(
    *,
    ts_historial: np.ndarray,
    co2_historial: np.ndarray,
    momentos: np.ndarray,
    co2_ahora: np.ndarray,
    personas: np.ndarray,
    ventilacion: np.ndarray,
    temperatura: np.ndarray,
    humedad: np.ndarray,
    ruido: np.ndarray,
    tamano_aula: float,
    velocidad: float,
    con_horario: bool,
) -> np.ndarray:
    """Una fila por momento, una columna por cada dato de `columnas()`.

    Los datos que faltan quedan como NaN: el pronostico sabe arreglarse
    sin ellos (por ejemplo, un aula sin sensor de ruido).
    """
    momentos = np.asarray(momentos, dtype=float)
    hace_5 = segundos_de_reloj(5, velocidad)
    hace_15 = segundos_de_reloj(15, velocidad)
    co2_hace_5 = co2_en(ts_historial, co2_historial, momentos - hace_5, margen_de_busqueda(hace_5))
    co2_hace_15 = co2_en(ts_historial, co2_historial, momentos - hace_15, margen_de_busqueda(hace_15))

    co2_ahora = np.asarray(co2_ahora, dtype=float)
    filas = [
        co2_ahora,
        co2_ahora - co2_hace_5,
        co2_ahora - co2_hace_15,
        np.asarray(personas, dtype=float),
        np.asarray(ventilacion, dtype=float),
        np.asarray(temperatura, dtype=float),
        np.asarray(humedad, dtype=float),
        np.asarray(ruido, dtype=float),
        np.full(momentos.shape, float(tamano_aula)),
    ]
    if con_horario:
        fechas = [datetime.fromtimestamp(t, tz=HORA_PERU) for t in momentos]
        filas.append(np.array([f.hour + f.minute / 60.0 for f in fechas]))
        filas.append(np.array([float(f.weekday()) for f in fechas]))
    return np.column_stack(filas)


def linea_recta(co2_ahora: np.ndarray, subida_5_min: np.ndarray) -> np.ndarray:
    """Lo que diria el metodo actual: seguir la misma subida de los ultimos minutos."""
    return limitar(co2_ahora + subida_5_min / 5.0 * MINUTOS_ADELANTE)


def limitar(co2: np.ndarray) -> np.ndarray:
    """El CO2 de un aula no baja del aire de afuera ni pasa de lo que miden los sensores."""
    return np.clip(co2, 400.0, 5000.0)


def como_esta_el_aire(co2: float) -> str:
    """Las mismas zonas que el dashboard (web/src/lib/formato.ts, ZONAS_AIRE)."""
    if co2 < 800:
        return "limpio"
    if co2 < 1000:
        return "bien"
    if co2 < 1400:
        return "cargado"
    return "muy_cargado"
