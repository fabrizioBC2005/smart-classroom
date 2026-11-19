"""Integracion: simulador fisico + motor de reglas.

Demuestra la tesis del proyecto: el control predictivo reduce el tiempo
de exposicion sobre 1000 ppm frente a un control reactivo por umbral.

Este test es el resultado experimental que se presenta en la sustentacion.
"""
import random

from app.services import reglas

C_EXT = 420.0
G = 0.0052 / 1000.0 * 0.85      # m3/s por alumno de secundaria
VOL = 170.0
ACH_CERRADA, ACH_VENT = 0.6, 6.0
DT = 30.0                       # paso de simulacion, segundos
PASOS = 240                     # 2 horas simuladas
OCUPANTES = 32
UMBRAL = 1000.0


def _avanzar(co2: float, ventilando: bool, ocupantes: int) -> float:
    ach = ACH_VENT if ventilando else ACH_CERRADA
    gen = (ocupantes * G) / VOL * 1e6
    dil = (ach / 3600.0) * (co2 - C_EXT)
    return max(C_EXT, co2 + (gen - dil) * DT)


def _simular(predictivo: bool) -> dict:
    random.seed(11)
    co2 = 480.0
    ventilando = False
    st = reglas.EstadoAula(aula_id=1, volumen_m3=VOL, nivel="secundaria")
    kw = dict(co2_alerta=UMBRAL, co2_critico=1400, temp_alerta=26, hum_alerta=70,
              ventana_s=300, anticipacion_s=300 if predictivo else 0, ttl_s=600)

    minutos_sobre = 0.0
    pico = co2
    t = 1_700_000_000.0

    for _ in range(PASOS):
        d = reglas.evaluar(st, {"ts": t, "co2_ppm": co2, "temp_c": 23.0, "hum_pct": 55.0}, **kw)
        if d.comando:
            ventilando = d.comando["accion"] == "on"

        co2 = _avanzar(co2, ventilando, OCUPANTES)
        pico = max(pico, co2)
        if co2 >= UMBRAL:
            minutos_sobre += DT / 60.0
        t += DT

    return {"minutos_sobre": round(minutos_sobre, 1), "pico": round(pico)}


def test_predictivo_reduce_exposicion_frente_a_reactivo():
    reactivo = _simular(predictivo=False)
    predictivo = _simular(predictivo=True)

    print(f"\n  reactivo   -> {reactivo['minutos_sobre']:5.1f} min sobre {UMBRAL:.0f} ppm | pico {reactivo['pico']} ppm")
    print(f"  predictivo -> {predictivo['minutos_sobre']:5.1f} min sobre {UMBRAL:.0f} ppm | pico {predictivo['pico']} ppm")
    mejora = (1 - predictivo["minutos_sobre"] / reactivo["minutos_sobre"]) * 100
    print(f"  mejora     -> {mejora:.1f} %")

    assert predictivo["minutos_sobre"] < reactivo["minutos_sobre"]
    assert predictivo["pico"] < reactivo["pico"]


def test_el_sistema_estabiliza_el_aula():
    """Con ventilacion activa el CO2 no se dispara."""
    r = _simular(predictivo=True)
    assert r["pico"] < 1400, f"pico demasiado alto: {r['pico']}"
