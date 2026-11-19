"""Contratos de entrada/salida de la API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SedeOut(Base):
    id: int
    slug: str
    nombre: str
    distrito: str


class AulaOut(Base):
    id: int
    sede_id: int
    codigo: str
    nivel: str
    volumen_m3: float
    aforo_nominal: int
    instrumentada: bool
    modo_ventilacion: str = "automatico"
    modo_iluminacion: str = "automatico"


class LecturaOut(Base):
    id: int
    aula_id: int
    ts: datetime
    co2_ppm: float | None
    temp_c: float | None
    hum_pct: float | None
    lux: float | None
    db_spl: float | None
    ocupantes_conteo: int | None
    ocupantes_estimado: float | None
    indice: float | None
    estado: str


class EventoOut(Base):
    id: int
    aula_id: int
    ts: datetime
    tipo: str
    severidad: str
    variable: str
    valor: float | None
    indice: float | None
    mensaje: str
    reconocido: bool


class ActuacionOut(Base):
    id: int
    aula_id: int
    ts: datetime
    actuador: str
    accion: str
    motivo: str
    origen: str


class AulaEstado(BaseModel):
    """Lo que consume el grid del dashboard."""
    aula_id: int
    codigo: str
    sede_slug: str
    nivel: str
    aforo_nominal: int
    instrumentada: bool
    ts: datetime | None = None
    co2_ppm: float | None = None
    temp_c: float | None = None
    hum_pct: float | None = None
    lux: float | None = None
    ocupantes: float | None = None
    indice: float | None = None
    estado: str = "sin_datos"
    ventilacion_on: bool = False
    iluminacion_on: bool | None = None
    online: bool = False


class ModoIn(BaseModel):
    actuador: str = Field(pattern="^(ventilacion|iluminacion)$")
    modo: str = Field(pattern="^(automatico|manual)$")


class ComandoIn(BaseModel):
    actuador: str = Field(pattern="^(ventilacion|iluminacion)$")
    accion: str = Field(pattern="^(on|off)$")
    motivo: str = "override_manual"


class FilaReporte(BaseModel):
    aula_id: int
    codigo: str
    muestras: int
    # tiempo real que cubren las lecturas (no la ventana solicitada): es el
    # denominador real del porcentaje, y sin el, "X% sobre umbral" no dice nada.
    minutos_registrados: float
    minutos_sobre_umbral: float
    pct_sobre_umbral: float
    co2_promedio: float | None
    co2_maximo: float | None
    indice_promedio: float | None
    # "sin_datos" es un tercer estado, no un default de "cumple": un aula sin
    # instrumentar no puede evidenciar cumplimiento de la Norma A.040.
    estado: str


class ReporteOut(BaseModel):
    desde: datetime
    hasta: datetime
    umbral_ppm: float
    aulas_cumplen: int
    aulas_no_cumplen: int
    aulas_sin_datos: int
    filas: list[FilaReporte]
