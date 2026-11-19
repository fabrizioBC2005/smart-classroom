"""Estimación de ocupación sin tratar datos personales.

Dos vías independientes:

  Vía A — conteo directo con sensores de distancia en la puerta.
          La secuencia de activación da la dirección (entra / sale).

  Vía B — inferencia por balance de masa de CO2:

              dC/dt = (N * G) / V  -  (Q / V) * (C - C_ext)

          C     concentración interior (ppm)
          N     número de ocupantes
          G     generación de CO2 por persona (m3/s)
          V     volumen del ambiente (m3)
          Q     caudal de ventilación (m3/s)
          C_ext concentración exterior (ppm)

Ninguna de las dos captura información que permita identificar a una
persona. Eso no es un accidente del diseño: es un requisito derivado de
la Ley 29733, y es lo que hace viable el sistema en un colegio.

El resultado experimental del proyecto es el error de la Vía B medido
contra la Vía A.
"""
from __future__ import annotations

from dataclasses import dataclass

# Generación de CO2 por persona sentada, actividad ligera.
# Adulto ~0.0052 L/s. Un escolar genera menos; ajustar por nivel.
G_ADULTO_M3_S = 0.0052 / 1000.0          # m3/s
FACTOR_NIVEL = {
    "inicial": 0.45,
    "primaria": 0.65,
    "secundaria": 0.85,
    "adulto": 1.0,
}

C_EXTERIOR_PPM = 420.0                   # aire exterior típico urbano
ACH_INFILTRACION = 0.6                   # renovaciones/hora con puertas y ventanas cerradas


@dataclass
class EstimacionAforo:
    ocupantes: float
    confiable: bool
    metodo: str
    detalle: str = ""


def generacion_por_persona(nivel: str = "secundaria") -> float:
    """m3/s de CO2 que genera un ocupante de ese nivel educativo."""
    return G_ADULTO_M3_S * FACTOR_NIVEL.get(nivel, 0.85)


def estimar_por_co2(
    pendiente_ppm_min: float,
    co2_actual_ppm: float,
    volumen_m3: float,
    nivel: str = "secundaria",
    ach: float = ACH_INFILTRACION,
    c_ext_ppm: float = C_EXTERIOR_PPM,
) -> EstimacionAforo:
    """Despeja N del balance de masa.

    Partiendo de:   dC/dt = (N*G)/V - (Q/V)*(C - C_ext)
    se obtiene:     N = ( dC/dt + (Q/V)*(C - C_ext) ) * V / G
    """
    if volumen_m3 <= 0:
        return EstimacionAforo(0.0, False, "co2", "volumen invalido")

    # ppm/min -> fracción/s
    dcdt = (pendiente_ppm_min / 60.0) / 1e6
    q_sobre_v = ach / 3600.0                       # 1/s
    delta_c = (co2_actual_ppm - c_ext_ppm) / 1e6

    g = generacion_por_persona(nivel)
    n = (dcdt + q_sobre_v * delta_c) * volumen_m3 / g
    n = max(0.0, n)

    # La estimación solo es creíble mientras el CO2 está subiendo con el
    # aula cerrada. Con la puerta abierta el término Q deja de ser constante.
    confiable = pendiente_ppm_min > 1.0 and co2_actual_ppm > c_ext_ppm + 80

    return EstimacionAforo(
        ocupantes=round(n, 1),
        confiable=confiable,
        metodo="co2",
        detalle=f"pendiente={pendiente_ppm_min:.2f}ppm/min ach={ach}",
    )


def error_relativo(estimado: float, real: int) -> float | None:
    """Métrica que se reporta como resultado experimental del proyecto."""
    if real <= 0:
        return None
    return round(abs(estimado - real) / real * 100.0, 1)


def tasa_renovacion_desde_decaimiento(
    co2_inicial: float,
    co2_final: float,
    minutos: float,
    c_ext_ppm: float = C_EXTERIOR_PPM,
) -> float | None:
    """Firma de decaimiento: ACH real del ambiente con el aula vacía.

    Es el diagnóstico de infraestructura del proyecto: un aula que decae
    demasiado lento tiene ventilación deficiente y se puede detectar sin
    inspección física.

        C(t) = C_ext + (C0 - C_ext) * e^(-ACH * t)
    """
    import math

    if minutos <= 0:
        return None
    num = co2_final - c_ext_ppm
    den = co2_inicial - c_ext_ppm
    if num <= 0 or den <= 0 or num >= den:
        return None

    horas = minutos / 60.0
    ach = -math.log(num / den) / horas
    return round(ach, 2)
