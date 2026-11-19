"""Índice de Habitabilidad (0-100).

Traduce las variables ambientales a un solo número interpretable.
No es una medición de desempeño cognitivo: es un INDICADOR DE GESTIÓN
ponderado por la evidencia disponible. La literatura sobre CO2 y cognición
no es unánime (Allen et al. 2016 vs. el estudio danés del mismo año), por
eso el CO2 pesa más pero no define el índice por sí solo.

Cada subíndice vale 1.0 en condición óptima y 0.0 en condición inaceptable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

# Pesos. Suman 1.0. Justificados en el documento (seccion 1.12).
PESOS = {
    "co2": 0.45,
    "temp": 0.25,
    "hum": 0.15,
    "ruido": 0.10,
    "lux": 0.05,
}

# Rangos de referencia
CO2_OPTIMO, CO2_INACEPTABLE = 600.0, 1600.0      # ppm
TEMP_MIN_OK, TEMP_MAX_OK = 20.0, 25.0            # °C confort en aula
TEMP_MIN_ABS, TEMP_MAX_ABS = 16.0, 31.0
HUM_MIN_OK, HUM_MAX_OK = 40.0, 60.0              # %
HUM_MIN_ABS, HUM_MAX_ABS = 20.0, 85.0
RUIDO_OK, RUIDO_INACEPTABLE = 40.0, 75.0         # dB(A)
LUX_OK, LUX_MIN_ABS = 300.0, 50.0                # lux (referencia EM.010)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _sub_descendente(valor: float, optimo: float, inaceptable: float) -> float:
    """1.0 en `optimo`, 0.0 en `inaceptable`. Lineal entre ambos."""
    if inaceptable == optimo:
        return 1.0
    return _clamp(1.0 - (valor - optimo) / (inaceptable - optimo))


def _sub_banda(valor: float, min_ok: float, max_ok: float,
               min_abs: float, max_abs: float) -> float:
    """1.0 dentro de la banda cómoda, decae hacia los límites absolutos."""
    if min_ok <= valor <= max_ok:
        return 1.0
    if valor < min_ok:
        return _clamp((valor - min_abs) / (min_ok - min_abs))
    return _clamp((max_abs - valor) / (max_abs - max_ok))


@dataclass
class ResultadoIndice:
    valor: float                 # 0-100
    estado: str                  # ok | alerta | critico
    subindices: dict[str, float] # detalle por variable (0-1)

    def dict(self) -> dict:
        return asdict(self)


def calcular(
    co2_ppm: float | None = None,
    temp_c: float | None = None,
    hum_pct: float | None = None,
    db_spl: float | None = None,
    lux: float | None = None,
    co2_alerta: float = 1000.0,
    co2_critico: float = 1400.0,
) -> ResultadoIndice:
    """Calcula el índice con las variables disponibles.

    Si falta una variable, su peso se redistribuye entre las presentes.
    Así el índice sigue siendo comparable aunque un sensor no esté montado.
    """
    subs: dict[str, float] = {}

    if co2_ppm is not None:
        subs["co2"] = _sub_descendente(co2_ppm, CO2_OPTIMO, CO2_INACEPTABLE)
    if temp_c is not None:
        subs["temp"] = _sub_banda(temp_c, TEMP_MIN_OK, TEMP_MAX_OK, TEMP_MIN_ABS, TEMP_MAX_ABS)
    if hum_pct is not None:
        subs["hum"] = _sub_banda(hum_pct, HUM_MIN_OK, HUM_MAX_OK, HUM_MIN_ABS, HUM_MAX_ABS)
    if db_spl is not None:
        subs["ruido"] = _sub_descendente(db_spl, RUIDO_OK, RUIDO_INACEPTABLE)
    if lux is not None:
        # por debajo de LUX_OK penaliza; por encima no premia ni castiga
        subs["lux"] = _clamp((lux - LUX_MIN_ABS) / (LUX_OK - LUX_MIN_ABS))

    if not subs:
        return ResultadoIndice(valor=0.0, estado="ok", subindices={})

    peso_total = sum(PESOS[k] for k in subs)
    valor = sum(subs[k] * PESOS[k] for k in subs) / peso_total * 100.0

    # El estado lo marca el CO2 contra el umbral normativo, no el índice.
    # Un índice alto no debe ocultar un CO2 fuera de rango.
    estado = "ok"
    if co2_ppm is not None:
        if co2_ppm >= co2_critico:
            estado = "critico"
        elif co2_ppm >= co2_alerta:
            estado = "alerta"
    if estado == "ok" and valor < 50:
        estado = "alerta"
    if valor < 35:
        estado = "critico"

    return ResultadoIndice(
        valor=round(valor, 1),
        estado=estado,
        subindices={k: round(v, 3) for k, v in subs.items()},
    )
