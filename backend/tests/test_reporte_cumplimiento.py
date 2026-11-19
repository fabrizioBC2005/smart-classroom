"""Tests del reporte de cumplimiento normativo (Norma A.040).

Cubren los dos defectos conceptuales que tenia el reporte: un aula sin
sensores no puede aparecer como "Cumple" (no se puede evidenciar lo que no
se mide), y los minutos sobre umbral no pueden exceder el tiempo que las
lecturas realmente cubrieron.
"""
from datetime import datetime, timedelta, timezone

from app.routers.reportes import (
    MAX_MIN_POR_MUESTRA,
    _fila_desde_agregados,
    _fila_sin_datos,
    _intervalo_estimado_min,
)


# --------------------------------------------------------------- estado
def test_aula_sin_muestras_da_estado_sin_datos():
    """Un aula sin instrumentar no cumple ni incumple: es indeterminada."""
    fila = _fila_sin_datos(aula_id=1, codigo="A-101")
    assert fila.estado == "sin_datos"
    assert fila.muestras == 0
    assert fila.minutos_registrados == 0.0
    assert fila.co2_promedio is None


def test_aula_con_pocas_muestras_sobre_umbral_da_no_cumple():
    ts_min = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ts_max = ts_min + timedelta(minutes=20)
    fila = _fila_desde_agregados(
        aula_id=2, codigo="A-102", total=20, sobre=15,
        prom=1100.0, maximo=1300.0, indice_prom=40.0,
        ts_min=ts_min, ts_max=ts_max,
    )
    assert fila.estado == "no_cumple"


def test_aula_bajo_tolerancia_da_cumple():
    ts_min = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ts_max = ts_min + timedelta(minutes=20)
    fila = _fila_desde_agregados(
        aula_id=3, codigo="A-103", total=20, sobre=1,
        prom=600.0, maximo=900.0, indice_prom=85.0,
        ts_min=ts_min, ts_max=ts_max,
    )
    assert fila.estado == "cumple"


# ------------------------------------------------------- minutos reales
def test_intervalo_se_calcula_sobre_el_span_real_no_la_ventana_pedida():
    """21 muestras que en realidad llegaron en 10 minutos (sistema recien
    encendido), aunque se pidio una ventana de 7 dias: el intervalo debe
    salir del span real (10 min / 20), no de 7 dias / 21 muestras."""
    ts_min = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ts_max = ts_min + timedelta(minutes=10)
    intervalo = _intervalo_estimado_min(ts_min, ts_max, muestras=21)
    assert abs(intervalo - (10.0 / 20.0)) < 1e-6


def test_hueco_largo_sin_lecturas_no_infla_minutos_sobre_umbral():
    """Un fin de semana sin clases (hueco de 2 dias) entre dos lecturas no
    debe traducirse en minutos "sobre umbral" que nadie midio."""
    ts_min = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ts_max = ts_min + timedelta(days=2)
    fila = _fila_desde_agregados(
        aula_id=4, codigo="A-104", total=2, sobre=2,
        prom=1200.0, maximo=1200.0, indice_prom=30.0,
        ts_min=ts_min, ts_max=ts_max,
    )
    # el intervalo esta acotado a MAX_MIN_POR_MUESTRA por muestra
    assert fila.minutos_sobre_umbral <= 2 * MAX_MIN_POR_MUESTRA
    # pero minutos_registrados si refleja el span real cubierto (2 dias)
    assert fila.minutos_registrados == (2 * 24 * 60)


def test_minutos_sobre_umbral_no_excede_minutos_registrados():
    """Propiedad general: nunca se puede reportar mas tiempo sobre el
    umbral que tiempo total efectivamente registrado."""
    ts_min = datetime(2026, 9, 1, tzinfo=timezone.utc)
    ts_max = ts_min + timedelta(hours=3)
    fila = _fila_desde_agregados(
        aula_id=5, codigo="A-105", total=21, sobre=21,
        prom=1500.0, maximo=1600.0, indice_prom=20.0,
        ts_min=ts_min, ts_max=ts_max,
    )
    assert fila.minutos_sobre_umbral <= fila.minutos_registrados


def test_una_sola_muestra_no_produce_intervalo():
    ts = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert _intervalo_estimado_min(ts, ts, muestras=1) == 0.0
