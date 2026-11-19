"""Tests de la renovacion de la ventilacion y del pronostico del aire."""
import numpy as np

from app.services import reglas
from aprendizaje import que_mira

KW = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
          ventana_s=300, anticipacion_s=60, ttl_s=600)


def _leer(st, t, co2, factor=1.0):
    return reglas.evaluar(st, {"ts": t, "co2_ppm": co2, "temp_c": 22.0, "hum_pct": 50.0},
                          factor_aceleracion=factor, **KW)


def test_la_orden_de_ventilar_se_renueva_antes_de_que_el_aparato_se_apague():
    """El ventilador se apaga solo a los ttl_s. Si el aire sigue cargado, el
    sistema tiene que repetir la orden; antes la mandaba una sola vez y el
    panel decia "Ventilando" con el aparato apagado."""
    st = reglas.EstadoAula(aula_id=1)
    t = 1_700_000_000.0
    primera = _leer(st, t, 1200)
    assert primera.comando and primera.comando["accion"] == "on"

    ordenes = []
    for i in range(1, 121):                      # 20 minutos, una lectura cada 10 s
        d = _leer(st, t + i * 10, 1150)
        if d.comando:
            ordenes.append((i * 10, d.comando))
    assert ordenes, "nunca renovo la orden"
    primera_renovacion = ordenes[0][0]
    assert primera_renovacion < 600, "la renovo despues de que el aparato ya se apago"
    assert all(c["accion"] == "on" for _, c in ordenes)
    # renovar no es una actuacion nueva: no ensucia el historial
    assert all(_leer(st, t + 2000 + k, 1150).actuacion is None for k in range(3))


def test_la_renovacion_respeta_el_simulador_acelerado():
    """Con SIM_VELOCIDAD=5 el temporizador dura 600/5 = 120 s de reloj."""
    st = reglas.EstadoAula(aula_id=1)
    t = 1_700_000_000.0
    _leer(st, t, 1200, factor=5)
    renovo_en = next(i * 5 for i in range(1, 60) if _leer(st, t + i * 5, 1150, factor=5).comando)
    assert renovo_en < 120


def test_no_renueva_si_el_aire_ya_se_normalizo():
    st = reglas.EstadoAula(aula_id=1)
    t = 1_700_000_000.0
    _leer(st, t, 1200)
    d = _leer(st, t + 700, 700)                 # bajo de 880: se apaga
    assert d.comando and d.comando["accion"] == "off"
    assert _leer(st, t + 710, 700).comando is None


def test_co2_en_busca_la_lectura_mas_cercana_y_respeta_el_margen():
    ts = np.array([0.0, 10.0, 20.0, 30.0])
    co2 = np.array([500.0, 510.0, 520.0, 530.0])
    r = que_mira.co2_en(ts, co2, np.array([11.0, 19.0, 100.0]), margen_s=5)
    assert r[0] == 510 and r[1] == 520 and np.isnan(r[2])


def test_la_tabla_mide_la_subida_de_los_ultimos_minutos():
    # CO2 que sube 10 ppm por minuto, una lectura por minuto, hardware real
    ts = np.arange(0, 30 * 60, 60.0)
    co2 = 600 + np.arange(len(ts)) * 10.0
    tabla = que_mira.armar_tabla(
        ts_historial=ts, co2_historial=co2, momentos=ts[-1:], co2_ahora=co2[-1:],
        personas=np.array([30.0]), ventilacion=np.array([0.0]),
        temperatura=np.array([23.0]), humedad=np.array([55.0]), ruido=np.array([np.nan]),
        tamano_aula=170, velocidad=1.0, con_horario=False,
    )
    fila = dict(zip(que_mira.columnas(False), tabla[0]))
    assert fila["subida_ultimos_5_min"] == 50
    assert fila["subida_ultimos_15_min"] == 150
    assert np.isnan(fila["ruido"])


def test_las_zonas_coinciden_con_el_dashboard():
    assert que_mira.como_esta_el_aire(799) == "limpio"
    assert que_mira.como_esta_el_aire(999) == "bien"
    assert que_mira.como_esta_el_aire(1000) == "cargado"
    assert que_mira.como_esta_el_aire(1400) == "muy_cargado"
