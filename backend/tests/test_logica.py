"""Tests de la lógica que sostiene el proyecto.

Estos tests son los que puedes mostrar si te preguntan cómo validaron
el índice, el control predictivo y el estimador de aforo.
"""
import math

from app.services import aforo, indice, prediccion


# --------------------------------------------------------------- índice
def test_indice_aula_optima_es_alto():
    r = indice.calcular(co2_ppm=520, temp_c=22, hum_pct=50, db_spl=42, lux=400)
    assert r.valor > 90
    assert r.estado == "ok"


def test_indice_cae_cuando_sube_co2():
    bueno = indice.calcular(co2_ppm=500, temp_c=22, hum_pct=50)
    malo = indice.calcular(co2_ppm=1500, temp_c=22, hum_pct=50)
    assert malo.valor < bueno.valor
    assert malo.estado == "critico"


def test_estado_lo_marca_el_co2_aunque_el_indice_sea_alto():
    """Un índice cómodo no debe ocultar un CO2 sobre el umbral normativo."""
    r = indice.calcular(co2_ppm=1050, temp_c=21, hum_pct=48, db_spl=38, lux=420)
    assert r.estado == "alerta"


def test_pesos_se_redistribuyen_si_falta_un_sensor():
    """Sin micrófono ni LDR el índice debe seguir siendo comparable."""
    completo = indice.calcular(co2_ppm=700, temp_c=23, hum_pct=55, db_spl=45, lux=350)
    parcial = indice.calcular(co2_ppm=700, temp_c=23, hum_pct=55)
    assert abs(completo.valor - parcial.valor) < 12
    assert "ruido" not in parcial.subindices


def test_pesos_suman_uno():
    assert abs(sum(indice.PESOS.values()) - 1.0) < 1e-9


# ----------------------------------------------------------- predicción
def test_regresion_detecta_pendiente_conocida():
    ts = [0, 60, 120, 180, 240, 300]
    vals = [500 + 20 * (t / 60) for t in ts]        # 20 ppm/min exactos
    t = prediccion.proyectar(ts, vals, umbral=1000)
    assert abs(t.pendiente_ppm_min - 20.0) < 0.1
    assert t.r2 > 0.99


def test_eta_hasta_el_umbral():
    ts = [0, 60, 120, 180]
    vals = [800, 820, 840, 860]                     # 20 ppm/min, faltan 140 ppm
    t = prediccion.proyectar(ts, vals, umbral=1000)
    assert t.eta_s is not None
    assert abs(t.eta_s - 420) < 30                  # ~7 minutos


def test_ventila_por_anticipacion_no_por_umbral():
    ts = [0, 60, 120, 180]
    vals = [820, 850, 880, 910]                     # aun por debajo de 1000
    t = prediccion.proyectar(ts, vals, umbral=1000)
    ventilar, motivo = prediccion.debe_ventilar(t, 1000, anticipacion_s=300)
    assert ventilar is True
    assert motivo.startswith("proyeccion_cruce_umbral")


def test_no_ventila_si_esta_estable():
    ts = [0, 60, 120, 180, 240]
    vals = [610, 608, 612, 609, 611]                # plano
    t = prediccion.proyectar(ts, vals, umbral=1000)
    ventilar, _ = prediccion.debe_ventilar(t, 1000, anticipacion_s=300)
    assert ventilar is False


def test_histeresis_evita_ciclado():
    assert prediccion.debe_apagar(860, 1000) is True
    assert prediccion.debe_apagar(950, 1000) is False


def test_pocas_muestras_no_es_confiable():
    t = prediccion.proyectar([0, 60], [500, 900], umbral=1000)
    assert t.confiable is False


# ---------------------------------------------------------------- aforo
def test_estimador_recupera_el_aforo_real():
    """Simulamos un aula cerrada con 30 alumnos y verificamos que el
    balance de masa devuelva algo cercano a 30."""
    volumen = 170.0
    nivel = "secundaria"
    n_real = 30
    g = aforo.generacion_por_persona(nivel)
    ach = 0.6
    co2 = 900.0

    # pendiente teórica que produciría ese aforo
    dcdt = (n_real * g) / volumen - (ach / 3600.0) * ((co2 - aforo.C_EXTERIOR_PPM) / 1e6)
    pendiente_ppm_min = dcdt * 1e6 * 60.0

    est = aforo.estimar_por_co2(pendiente_ppm_min, co2, volumen, nivel, ach)
    assert est.confiable is True
    assert abs(est.ocupantes - n_real) < 1.0


def test_error_relativo():
    assert aforo.error_relativo(33.0, 30) == 10.0
    assert aforo.error_relativo(30.0, 0) is None


def test_no_confiable_con_aula_ventilada():
    est = aforo.estimar_por_co2(0.1, 430, 170, "secundaria")
    assert est.confiable is False


def test_tasa_renovacion_desde_decaimiento():
    """Aula vacía: de 1200 a 700 ppm en 30 min."""
    c0, c1, mins = 1200.0, 700.0, 30.0
    ach = aforo.tasa_renovacion_desde_decaimiento(c0, c1, mins)
    esperado = -math.log((c1 - 420) / (c0 - 420)) / (mins / 60)
    assert ach is not None
    assert abs(ach - esperado) < 0.01


def test_decaimiento_invalido_devuelve_none():
    assert aforo.tasa_renovacion_desde_decaimiento(700, 1200, 30) is None


# --------------------------------------------------------------- reglas
def test_motor_ventila_anticipadamente_y_registra_motivo():
    from app.services import reglas

    st = reglas.EstadoAula(aula_id=1, volumen_m3=170)
    kw = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
              ventana_s=300, anticipacion_s=300, ttl_s=600)

    d = None
    base = 1_700_000_000.0
    # CO2 subiendo 25 ppm/min desde 820 -> cruza 1000 en ~7 min
    for i in range(6):
        d = reglas.evaluar(
            st,
            {"ts": base + i * 30, "co2_ppm": 820 + i * 12.5, "temp_c": 23, "hum_pct": 55},
            **kw,
        )

    assert d.comando is not None
    assert d.comando["accion"] == "on"
    assert "proyeccion_cruce_umbral" in d.comando["motivo"]
    assert d.actuacion["origen"] == "automatico"
    assert d.pendiente_ppm_min > 20


def test_motor_no_repite_la_orden_de_encendido():
    from app.services import reglas

    st = reglas.EstadoAula(aula_id=1)
    kw = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
              ventana_s=300, anticipacion_s=300, ttl_s=600)
    base = 1_700_000_000.0
    comandos = []
    for i in range(10):
        d = reglas.evaluar(st, {"ts": base + i * 30, "co2_ppm": 900 + i * 15,
                                "temp_c": 23, "hum_pct": 55}, **kw)
        if d.comando:
            comandos.append(d.comando)
    assert len([c for c in comandos if c["accion"] == "on"]) == 1


def test_motor_apaga_al_normalizar():
    from app.services import reglas

    st = reglas.EstadoAula(aula_id=1)
    kw = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
              ventana_s=300, anticipacion_s=300, ttl_s=600)
    base = 1_700_000_000.0
    for i in range(6):
        reglas.evaluar(st, {"ts": base + i * 30, "co2_ppm": 950 + i * 20,
                            "temp_c": 23, "hum_pct": 55}, **kw)
    assert st.ventilacion_on is True

    apagados = []
    for i in range(6):
        d = reglas.evaluar(st, {"ts": base + 200 + i * 30, "co2_ppm": 800 - i * 10,
                                "temp_c": 23, "hum_pct": 55}, **kw)
        if d.comando:
            apagados.append(d.comando)

    assert st.ventilacion_on is False
    # apaga una sola vez, sin repetir la orden en cada lectura
    assert len(apagados) == 1
    assert apagados[0]["accion"] == "off"
    assert apagados[0]["motivo"].startswith("co2_normalizado")


def test_motor_genera_evento_al_cambiar_de_estado():
    from app.services import reglas

    st = reglas.EstadoAula(aula_id=1)
    kw = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
              ventana_s=300, anticipacion_s=300, ttl_s=600)
    d = reglas.evaluar(st, {"ts": 1_700_000_000.0, "co2_ppm": 1120,
                            "temp_c": 23, "hum_pct": 55}, **kw)
    tipos = [e["tipo"] for e in d.eventos]
    assert "co2_alerta" in tipos
