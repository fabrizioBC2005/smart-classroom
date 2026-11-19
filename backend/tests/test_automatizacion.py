"""Automatizacion sin supervision: luces, ventilacion por calor y respeto
de las ordenes manuales."""
from app.services import reglas

KW = dict(co2_alerta=1000, co2_critico=1400, temp_alerta=26, hum_alerta=70,
          ventana_s=300, anticipacion_s=300, ttl_s=600,
          lux_minimo=300, luz_apagar_vacia_s=600)
BASE = 1_700_000_000.0


def _lect(i, **kw):
    d = {"ts": BASE + i * 30, "co2_ppm": 600.0, "temp_c": 23.0, "hum_pct": 55.0}
    d.update(kw)
    return d


def _ordenes(d, actuador):
    return [c for c in d.comandos if c["actuador"] == actuador]


def test_prende_luces_si_hay_gente_y_falta_luz():
    st = reglas.EstadoAula(aula_id=1)
    d = reglas.evaluar(st, _lect(0, lux=150, ocupantes=25), **KW)
    luz = _ordenes(d, "iluminacion")
    assert luz and luz[0]["accion"] == "on"
    assert luz[0]["motivo"].startswith("luz_insuficiente")
    assert any(a["actuador"] == "iluminacion" for a in d.actuaciones)


def test_no_prende_luces_en_aula_vacia_ni_con_luz_natural():
    st = reglas.EstadoAula(aula_id=1)
    assert not _ordenes(reglas.evaluar(st, _lect(0, lux=150, ocupantes=0), **KW), "iluminacion")
    assert not _ordenes(reglas.evaluar(st, _lect(1, lux=500, ocupantes=25), **KW), "iluminacion")


def test_no_apaga_luces_por_su_propia_luz():
    """Con las luces prendidas el luxometro sube: eso no debe apagarlas."""
    st = reglas.EstadoAula(aula_id=1)
    reglas.evaluar(st, _lect(0, lux=150, ocupantes=25), **KW)
    for i in range(1, 20):
        d = reglas.evaluar(st, _lect(i, lux=570, ocupantes=25), **KW)
        assert not _ordenes(d, "iluminacion")
    assert st.iluminacion_on


def test_apaga_luces_tras_aula_vacia_un_rato():
    st = reglas.EstadoAula(aula_id=1)
    reglas.evaluar(st, _lect(0, lux=150, ocupantes=25), **KW)
    apagados = []
    for i in range(1, 30):   # 30 s por lectura -> 10 min vacia en la lectura 21
        d = reglas.evaluar(st, _lect(i, lux=560, ocupantes=0), **KW)
        apagados += _ordenes(d, "iluminacion")
    assert len(apagados) == 1 and apagados[0]["accion"] == "off"
    assert apagados[0]["motivo"].startswith("aula_vacia")


def test_ventila_por_calor_y_no_apaga_por_co2_bajo():
    st = reglas.EstadoAula(aula_id=1)
    d = reglas.evaluar(st, _lect(0, temp_c=27.5, ocupantes=25), **KW)
    v = _ordenes(d, "ventilacion")
    assert v and v[0]["accion"] == "on" and v[0]["motivo"].startswith("temperatura_alta")
    # CO2 bajo pero sigue haciendo calor: no se apaga
    d = reglas.evaluar(st, _lect(1, temp_c=26.5, ocupantes=25, co2_ppm=500), **KW)
    assert not any(c["accion"] == "off" for c in _ordenes(d, "ventilacion"))
    # baja bajo la histeresis (25 C): ahora si
    d = reglas.evaluar(st, _lect(2, temp_c=24.8, ocupantes=25, co2_ppm=500), **KW)
    assert [c["accion"] for c in _ordenes(d, "ventilacion")] == ["off"]


def test_no_ventila_por_calor_un_aula_vacia():
    st = reglas.EstadoAula(aula_id=1)
    d = reglas.evaluar(st, _lect(0, temp_c=28, ocupantes=0), **KW)
    assert not _ordenes(d, "ventilacion")


def test_override_manual_pausa_la_automatizacion():
    st = reglas.EstadoAula(aula_id=1)
    # el docente apaga las luces a mano (proyector) con el aula oscura
    st.aplicar_manual("iluminacion", "off", BASE, duracion_s=600)
    for i in range(10):     # 5 min: dentro de la pausa
        d = reglas.evaluar(st, _lect(i, lux=80, ocupantes=25), **KW)
        assert not _ordenes(d, "iluminacion")
    # vencida la pausa, la automatizacion vuelve
    d = reglas.evaluar(st, _lect(25, lux=80, ocupantes=25), **KW)
    assert [c["accion"] for c in _ordenes(d, "iluminacion")] == ["on"]


def test_override_manual_de_ventilacion_no_se_apaga_solo():
    st = reglas.EstadoAula(aula_id=1)
    st.aplicar_manual("ventilacion", "on", BASE, duracion_s=600)
    d = reglas.evaluar(st, _lect(1, co2_ppm=500, ocupantes=25), **KW)
    assert not _ordenes(d, "ventilacion")
    assert st.ventilacion_on


def test_modo_manual_el_sistema_no_toca_el_equipo():
    st = reglas.EstadoAula(aula_id=1)
    st.cambiar_modo("ventilacion", "manual")
    st.cambiar_modo("iluminacion", "manual")
    # CO2 alto, calor y aula oscura con gente: en automatico actuaria todo
    for i in range(20):
        d = reglas.evaluar(st, _lect(i, co2_ppm=1300 + i * 10, temp_c=28,
                                     lux=80, ocupantes=30), **KW)
        assert not d.comandos
    assert not st.ventilacion_on and not st.iluminacion_on


def test_modo_manual_mantiene_encendido_el_ventilador():
    """El aparato se apaga solo al vencer su ttl: en manual se renueva."""
    st = reglas.EstadoAula(aula_id=1)
    st.cambiar_modo("ventilacion", "manual")
    st.aplicar_manual("ventilacion", "on", BASE, duracion_s=600)
    renovaciones = []
    for i in range(1, 60):   # 30 min
        d = reglas.evaluar(st, _lect(i, co2_ppm=500, ocupantes=0), **KW)
        renovaciones += [c for c in d.comandos if c["actuador"] == "ventilacion"]
    assert renovaciones and all(c["accion"] == "on" for c in renovaciones)
    assert all(c["motivo"] == "renovacion|modo_manual" for c in renovaciones)
    assert not d.actuaciones          # renovar no es una actuacion nueva
    assert st.ventilacion_on


def test_volver_a_automatico_retoma_el_control():
    st = reglas.EstadoAula(aula_id=1)
    st.cambiar_modo("iluminacion", "manual")
    assert not reglas.evaluar(st, _lect(0, lux=80, ocupantes=30), **KW).comandos
    st.cambiar_modo("iluminacion", "automatico")
    d = reglas.evaluar(st, _lect(1, lux=80, ocupantes=30), **KW)
    assert [c["accion"] for c in d.comandos if c["actuador"] == "iluminacion"] == ["on"]
