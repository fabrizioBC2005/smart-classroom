"""Arma los ejemplos del pasado: "lo que sabiamos en ese momento" y
"lo que paso 10 minutos despues", a partir de la tabla de lecturas.

Cada lectura guardada se convierte en una pregunta con su respuesta:

    CO2 850, subiendo rapido, 28 personas, ventilacion apagada  ->  1080
    CO2 900, bajando, 3 personas, ventilacion encendida         ->   640

Miles de filas asi son el "libro de experiencias" del que aprende.

Por defecto SOLO usa las lecturas nuevas, las que guardan si la ventilacion
estaba encendida. Las viejas son de cuando la orden de ventilar no se
renovaba: el ventilador se apagaba solo a los pocos minutos y el CO2 volvia
a subir. Con esos datos el pronostico aprende algo falso ("ventilar casi no
sirve"). Se pueden incluir con incluir_viejas=True, pero no conviene.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import text

from app.config import settings
from app.db import engine
from aprendizaje import que_mira


@dataclass
class Ejemplos:
    tabla: np.ndarray          # lo que sabiamos (una fila por momento)
    respuesta: np.ndarray      # el CO2 que hubo 10 minutos despues
    momento: np.ndarray        # cuando fue (segundos, reloj real)
    aula: np.ndarray           # de que aula es cada fila
    linea_recta: np.ndarray    # lo que habria dicho el metodo actual
    columnas: list[str]

    def __len__(self) -> int:
        return len(self.respuesta)


async def _leer(dias: int):
    async with engine.connect() as conn:
        lecturas = (await conn.execute(text("""
            SELECT aula_id, EXTRACT(EPOCH FROM ts) AS segundos, co2_ppm, temp_c, hum_pct, db_spl,
                   COALESCE(ocupantes_conteo, ocupantes_estimado) AS personas, ventilacion_on
            FROM lecturas
            WHERE co2_ppm IS NOT NULL AND ts > now() - make_interval(days => :dias)
            ORDER BY aula_id, ts
        """), {"dias": dias})).all()
        ordenes = (await conn.execute(text("""
            SELECT aula_id, EXTRACT(EPOCH FROM ts) AS segundos, accion
            FROM actuaciones
            WHERE actuador = 'ventilacion' AND ts > now() - make_interval(days => :dias + 1)
            ORDER BY aula_id, ts
        """), {"dias": dias})).all()
        tamanos = dict((await conn.execute(text("SELECT id, volumen_m3 FROM aulas"))).all())
    return lecturas, ordenes, tamanos


def _ventilacion_de_lecturas_viejas(ts: np.ndarray, ordenes, velocidad: float) -> np.ndarray:
    """Las lecturas viejas no guardaban si se estaba ventilando: se deduce de
    las ordenes. Una orden de encender dura lo que el temporizador del
    ventilador (VENTILACION_TTL_S) o hasta la orden de apagar, lo que pase antes.
    """
    if not ordenes:
        return np.zeros(len(ts))
    t_orden = np.array([float(o.segundos) for o in ordenes])
    encender = np.array([o.accion == "on" for o in ordenes])
    duracion = que_mira.segundos_de_reloj(settings.VENTILACION_TTL_S / 60.0, velocidad)
    ultima = np.searchsorted(t_orden, ts, side="right") - 1
    hay = ultima >= 0
    ultima = np.clip(ultima, 0, len(t_orden) - 1)
    return (hay & encender[ultima] & (ts - t_orden[ultima] <= duracion)).astype(float)


async def armar(dias: int = 30, incluir_viejas: bool = False) -> Ejemplos:
    velocidad = settings.SIM_VELOCIDAD
    con_horario = velocidad == 1.0
    lecturas, ordenes, tamanos = await _leer(dias)

    por_aula: dict[int, list] = {}
    for f in lecturas:
        por_aula.setdefault(f.aula_id, []).append(f)
    ordenes_por_aula: dict[int, list] = {}
    for o in ordenes:
        ordenes_por_aula.setdefault(o.aula_id, []).append(o)

    adelante = que_mira.segundos_de_reloj(que_mira.MINUTOS_ADELANTE, velocidad)
    partes = []
    for aula_id, filas in por_aula.items():
        ts = np.array([float(f.segundos) for f in filas])
        co2 = np.array([f.co2_ppm for f in filas], dtype=float)
        guardada = np.array([np.nan if f.ventilacion_on is None else float(f.ventilacion_on) for f in filas])
        deducida = _ventilacion_de_lecturas_viejas(ts, ordenes_por_aula.get(aula_id, []), velocidad)
        ventilacion = np.where(np.isnan(guardada), deducida, guardada)

        tabla = que_mira.armar_tabla(
            ts_historial=ts, co2_historial=co2, momentos=ts, co2_ahora=co2,
            personas=np.array([np.nan if f.personas is None else f.personas for f in filas], dtype=float),
            ventilacion=ventilacion,
            temperatura=np.array([np.nan if f.temp_c is None else f.temp_c for f in filas], dtype=float),
            humedad=np.array([np.nan if f.hum_pct is None else f.hum_pct for f in filas], dtype=float),
            ruido=np.array([np.nan if f.db_spl is None else f.db_spl for f in filas], dtype=float),
            tamano_aula=tamanos.get(aula_id, 170.0),
            velocidad=velocidad, con_horario=con_horario,
        )
        respuesta = que_mira.co2_en(ts, co2, ts + adelante, que_mira.margen_de_busqueda(adelante))

        # solo sirven los momentos con respuesta y con la subida de los
        # ultimos 5 minutos (sin eso tampoco la linea recta puede opinar)
        sirve = ~np.isnan(respuesta) & ~np.isnan(tabla[:, 1])
        if not incluir_viejas:
            sirve &= ~np.isnan(guardada)
        partes.append((tabla[sirve], respuesta[sirve], ts[sirve], np.full(sirve.sum(), aula_id)))

    columnas = que_mira.columnas(con_horario)
    if not partes:
        vacio = np.empty((0, len(columnas)))
        return Ejemplos(vacio, np.empty(0), np.empty(0), np.empty(0), np.empty(0), columnas)

    tabla = np.vstack([p[0] for p in partes])
    respuesta = np.concatenate([p[1] for p in partes])
    momento = np.concatenate([p[2] for p in partes])
    aula = np.concatenate([p[3] for p in partes])
    orden = np.argsort(momento, kind="stable")
    tabla, respuesta, momento, aula = tabla[orden], respuesta[orden], momento[orden], aula[orden]

    return Ejemplos(
        tabla=tabla, respuesta=respuesta, momento=momento, aula=aula,
        linea_recta=que_mira.linea_recta(tabla[:, 0], tabla[:, 1]),
        columnas=columnas,
    )
