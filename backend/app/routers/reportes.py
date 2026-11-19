"""Reporte de cumplimiento.

Este es el endpoint que conecta el sistema con el argumento normativo del
proyecto: la Norma A.040 exige "renovacion de aire adecuada y constante"
pero no define un mecanismo de verificacion. Aqui convertimos esa
obligacion declarativa en un indicador medible y auditable por ambiente
y por periodo.

Criterio de cumplimiento: porcentaje de tiempo de ocupacion con CO2 por
debajo de 1000 ppm (referencia ASHRAE 62.1 para ventilacion adecuada).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Aula, Lectura, Sede
from app.schemas import FilaReporte, ReporteOut
from app.services import aforo as aforo_svc

router = APIRouter(prefix="/api", tags=["reportes"])

# tolerancia: se considera que cumple si supera el umbral menos del 10% del tiempo
PCT_TOLERANCIA = 10.0

# cota superior del intervalo entre muestras: sin esto, un hueco largo sin
# lecturas (p.ej. un fin de semana sin clases) se contaria como tiempo "sobre
# umbral" e inflaria el reporte con minutos que nadie midio.
MAX_MIN_POR_MUESTRA = 5.0


@router.get("/reporte/cumplimiento", response_model=ReporteOut)
async def reporte_cumplimiento(
    dias: int = Query(7, ge=1, le=90),
    sede: str | None = None,
    umbral: float | None = None,
    db: AsyncSession = Depends(get_session),
):
    umbral_ppm = umbral or settings.CO2_UMBRAL_ALERTA
    hasta = datetime.now(timezone.utc)
    desde = hasta - timedelta(days=dias)

    q_aulas = select(Aula).join(Sede, Aula.sede_id == Sede.id).order_by(Aula.codigo)
    if sede:
        q_aulas = q_aulas.where(Sede.slug == sede)
    aulas = (await db.execute(q_aulas)).scalars().all()

    filas: list[FilaReporte] = []

    for aula in aulas:
        base = select(
            func.count(Lectura.id),
            func.avg(Lectura.co2_ppm),
            func.max(Lectura.co2_ppm),
            func.avg(Lectura.indice),
            func.min(Lectura.ts),
            func.max(Lectura.ts),
        ).where(
            Lectura.aula_id == aula.id,
            Lectura.ts >= desde,
            Lectura.co2_ppm.isnot(None),
        )
        total, prom, maximo, indice_prom, ts_min, ts_max = (await db.execute(base)).one()
        total = int(total or 0)

        if total == 0:
            filas.append(_fila_sin_datos(aula.id, aula.codigo))
            continue

        sobre = (
            await db.execute(
                select(func.count(Lectura.id)).where(
                    Lectura.aula_id == aula.id,
                    Lectura.ts >= desde,
                    Lectura.co2_ppm >= umbral_ppm,
                )
            )
        ).scalar_one()
        sobre = int(sobre or 0)

        filas.append(
            _fila_desde_agregados(
                aula_id=aula.id, codigo=aula.codigo, total=total, sobre=sobre,
                prom=prom, maximo=maximo, indice_prom=indice_prom,
                ts_min=ts_min, ts_max=ts_max,
            )
        )

    aulas_cumplen = sum(1 for f in filas if f.estado == "cumple")
    aulas_no_cumplen = sum(1 for f in filas if f.estado == "no_cumple")
    aulas_sin_datos = sum(1 for f in filas if f.estado == "sin_datos")

    return ReporteOut(
        desde=desde, hasta=hasta, umbral_ppm=umbral_ppm,
        aulas_cumplen=aulas_cumplen, aulas_no_cumplen=aulas_no_cumplen,
        aulas_sin_datos=aulas_sin_datos, filas=filas,
    )


def _fila_sin_datos(aula_id: int, codigo: str) -> FilaReporte:
    # aula sin lecturas: no se puede afirmar que cumple ni que incumple la
    # norma, solo que no fue evidenciada en el periodo.
    return FilaReporte(
        aula_id=aula_id, codigo=codigo, muestras=0,
        minutos_registrados=0.0,
        minutos_sobre_umbral=0.0, pct_sobre_umbral=0.0,
        co2_promedio=None, co2_maximo=None,
        indice_promedio=None, estado="sin_datos",
    )


def _fila_desde_agregados(
    *, aula_id: int, codigo: str, total: int, sobre: int,
    prom: float | None, maximo: float | None, indice_prom: float | None,
    ts_min: datetime | None, ts_max: datetime | None,
) -> FilaReporte:
    """Construye una fila a partir de los agregados ya calculados en SQL.

    Separado de la consulta para poder probar la logica de estado y de
    minutos sin necesitar una base de datos.
    """
    # el intervalo se deriva del propio dato (span real entre ts_min y
    # ts_max), no de la ventana solicitada: la ventana pedida (p.ej. 7 dias)
    # no es el tiempo que el sistema realmente estuvo midiendo.
    minutos_por_muestra = _intervalo_estimado_min(ts_min, ts_max, total)
    minutos_registrados = (
        (ts_max - ts_min).total_seconds() / 60.0 if ts_min and ts_max else 0.0
    )
    pct = sobre / total * 100.0
    estado = "cumple" if pct <= PCT_TOLERANCIA else "no_cumple"

    return FilaReporte(
        aula_id=aula_id,
        codigo=codigo,
        muestras=total,
        minutos_registrados=round(minutos_registrados, 1),
        minutos_sobre_umbral=round(sobre * minutos_por_muestra, 1),
        pct_sobre_umbral=round(pct, 1),
        co2_promedio=round(float(prom), 1) if prom is not None else None,
        co2_maximo=round(float(maximo), 1) if maximo is not None else None,
        indice_promedio=round(float(indice_prom), 1) if indice_prom is not None else None,
        estado=estado,
    )


def _intervalo_estimado_min(ts_min: datetime | None, ts_max: datetime | None, muestras: int) -> float:
    if muestras <= 1 or ts_min is None or ts_max is None:
        return 0.0
    intervalo = (ts_max - ts_min).total_seconds() / (muestras - 1) / 60.0
    # se acota para que un hueco largo sin lecturas (aula cerrada un fin de
    # semana) no se interprete como minutos reales sobre el umbral.
    return min(intervalo, MAX_MIN_POR_MUESTRA)


@router.get("/reporte/renovacion/{aula_id}")
async def tasa_renovacion(
    aula_id: int,
    dias: int = Query(7, ge=1, le=60),
    db: AsyncSession = Depends(get_session),
):
    """Firma de decaimiento: ACH real del aula.

    Busca tramos donde el CO2 baja de forma sostenida (aula vaciandose) y
    calcula la tasa de renovacion de aire. Un ACH anormalmente bajo indica
    ventilacion deficiente y genera una orden de mantenimiento priorizada,
    sin necesidad de inspeccion fisica.
    """
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    res = await db.execute(
        select(Lectura.ts, Lectura.co2_ppm, Lectura.ocupantes_conteo)
        .where(Lectura.aula_id == aula_id, Lectura.ts >= desde, Lectura.co2_ppm.isnot(None))
        .order_by(Lectura.ts.asc())
    )
    puntos = res.all()
    # si hay conteo en la puerta, solo valen los tramos con el aula VACIA: con
    # gente adentro el CO2 que se genera frena la caida y el ACH sale bajo
    hay_conteo = any(p[2] is not None for p in puntos)
    # los ts son de reloj real; con el simulador acelerado el aire cambia en
    # tiempo del aula (SIM_VELOCIDAD veces mas rapido). Con hardware real = 1.
    factor = settings.SIM_VELOCIDAD
    if len(puntos) < 20:
        return {"aula_id": aula_id, "ach": None, "tramos": 0,
                "detalle": "datos insuficientes"}

    tramos: list[float] = []
    inicio = None
    for i in range(1, len(puntos)):
        ts_prev, c_prev, _ = puntos[i - 1]
        ts_act, c_act, ocup = puntos[i]
        bajando = c_act < c_prev - 1.0 and (not hay_conteo or ocup == 0)

        if bajando and inicio is None:
            inicio = (ts_prev, c_prev)
        elif not bajando and inicio is not None:
            t0, c0 = inicio
            minutos = (ts_prev - t0).total_seconds() / 60.0 * factor
            if minutos >= 8:
                ach = aforo_svc.tasa_renovacion_desde_decaimiento(c0, c_prev, minutos)
                if ach and 0.05 < ach < 25:
                    tramos.append(ach)
            inicio = None

    if not tramos:
        return {"aula_id": aula_id, "ach": None, "tramos": 0,
                "detalle": "no se hallaron tramos de decaimiento validos"}

    tramos.sort()
    mediana = tramos[len(tramos) // 2]
    return {
        "aula_id": aula_id,
        "ach": round(mediana, 2),
        "tramos": len(tramos),
        "min": round(tramos[0], 2),
        "max": round(tramos[-1], 2),
        "diagnostico": _diagnostico_ach(mediana),
    }


def _diagnostico_ach(ach: float) -> str:
    if ach < 1.0:
        return "Ventilacion deficiente: revisar ventanas, rejillas o extractor."
    if ach < 3.0:
        return "Ventilacion limitada: aceptable con aforo bajo, insuficiente en aula llena."
    return "Ventilacion adecuada."
