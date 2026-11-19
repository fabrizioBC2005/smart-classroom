"""Control predictivo.

Un sistema por umbrales actúa cuando el valor YA se pasó — es decir,
cuando los alumnos ya estuvieron expuestos. Aquí calculamos la pendiente
sobre una ventana móvil y proyectamos cuándo se va a cruzar el umbral,
para ventilar ANTES.

Método: regresión lineal por mínimos cuadrados. Explicable y suficiente
para el volumen de datos de este proyecto. No hace falta deep learning:
un modelo sobredimensionado sin datos que lo justifiquen sería un punto
débil, no una fortaleza.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MIN_MUESTRAS = 4


@dataclass
class Tendencia:
    pendiente_ppm_min: float   # ppm por minuto
    r2: float                  # bondad del ajuste (0-1)
    eta_s: float | None        # segundos hasta cruzar el umbral (None = no cruza)
    valor_actual: float
    confiable: bool


def ajustar(ts_segundos: list[float], valores: list[float]) -> tuple[float, float, float]:
    """Devuelve (pendiente_por_segundo, intercepto, r2)."""
    x = np.asarray(ts_segundos, dtype=float)
    y = np.asarray(valores, dtype=float)

    if len(x) < 2:
        return 0.0, float(y[-1]) if len(y) else 0.0, 0.0

    # Normalizar PRIMERO. Con timestamps epoch (~1.7e9) cualquier comparacion
    # con tolerancia relativa considera iguales muestras separadas por minutos,
    # y la regresion devolveria pendiente cero en silencio.
    x0 = x - x[0]
    if float(np.ptp(x0)) < 1e-6:
        return 0.0, float(y[-1]), 0.0

    pendiente, intercepto = np.polyfit(x0, y, 1)

    y_pred = pendiente * x0 + intercepto
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 1.0

    return float(pendiente), float(intercepto), float(max(0.0, min(1.0, r2)))


def proyectar(
    ts_segundos: list[float],
    valores: list[float],
    umbral: float,
    r2_minimo: float = 0.55,
) -> Tendencia:
    """Proyecta cuántos segundos faltan para cruzar `umbral`."""
    if len(valores) < MIN_MUESTRAS:
        actual = valores[-1] if valores else 0.0
        return Tendencia(0.0, 0.0, None, actual, False)

    pendiente_s, _, r2 = ajustar(ts_segundos, valores)
    actual = float(valores[-1])
    confiable = r2 >= r2_minimo and pendiente_s > 0

    eta = None
    if confiable and actual < umbral:
        eta = (umbral - actual) / pendiente_s
        if eta < 0 or eta > 3600:      # más de una hora no aporta nada
            eta = None

    return Tendencia(
        pendiente_ppm_min=round(pendiente_s * 60.0, 2),
        r2=round(r2, 3),
        eta_s=round(eta, 1) if eta is not None else None,
        valor_actual=actual,
        confiable=confiable,
    )


def debe_ventilar(
    tendencia: Tendencia,
    umbral_alerta: float,
    anticipacion_s: int,
) -> tuple[bool, str]:
    """Decide si toca encender ventilación y devuelve el motivo auditable."""
    if tendencia.valor_actual >= umbral_alerta:
        return True, f"co2_sobre_umbral:{tendencia.valor_actual:.0f}ppm"

    if tendencia.eta_s is not None and tendencia.eta_s <= anticipacion_s:
        minutos = tendencia.eta_s / 60.0
        return True, (
            f"proyeccion_cruce_umbral:{minutos:.1f}min"
            f"|pendiente:{tendencia.pendiente_ppm_min:.1f}ppm_min"
            f"|r2:{tendencia.r2:.2f}"
        )

    return False, ""


def debe_apagar(valor_actual: float, umbral_alerta: float, histeresis: float = 120.0) -> bool:
    """Histéresis para no estar prendiendo y apagando el ventilador."""
    return valor_actual <= (umbral_alerta - histeresis)
