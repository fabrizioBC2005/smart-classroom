"""Modelo de datos.

Diseño pensado para series de tiempo: `lecturas` es la tabla que crece
y por eso lleva índice compuesto (dispositivo_id, ts DESC).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Sede(Base):
    __tablename__ = "sedes"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    distrito: Mapped[str] = mapped_column(String(120), default="")

    aulas: Mapped[list["Aula"]] = relationship(back_populates="sede", cascade="all, delete-orphan")


class Aula(Base):
    __tablename__ = "aulas"

    id: Mapped[int] = mapped_column(primary_key=True)
    sede_id: Mapped[int] = mapped_column(ForeignKey("sedes.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(String(32), index=True)
    nivel: Mapped[str] = mapped_column(String(32), default="secundaria")
    volumen_m3: Mapped[float] = mapped_column(Float, default=170.0)
    aforo_nominal: Mapped[int] = mapped_column(Integer, default=32)
    # true = aula con hardware real conectado; false = alimentada por el simulador
    instrumentada: Mapped[bool] = mapped_column(Boolean, default=False)
    # quien maneja cada equipo: "automatico" (el motor de reglas) o "manual"
    # (solo las personas, desde el dashboard; el sistema no lo toca)
    modo_ventilacion: Mapped[str] = mapped_column(String(16), default="automatico")
    modo_iluminacion: Mapped[str] = mapped_column(String(16), default="automatico")

    sede: Mapped["Sede"] = relationship(back_populates="aulas")
    dispositivos: Mapped[list["Dispositivo"]] = relationship(
        back_populates="aula", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_aula_sede_codigo", "sede_id", "codigo", unique=True),)


class Dispositivo(Base):
    __tablename__ = "dispositivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    firmware: Mapped[str] = mapped_column(String(32), default="")
    ultimo_visto: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    aula: Mapped["Aula"] = relationship(back_populates="dispositivos")


class Lectura(Base):
    """Una muestra de sensores. Es la tabla que crece sin parar."""
    __tablename__ = "lecturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    dispositivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("dispositivos.id", ondelete="SET NULL"), default=None
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)

    co2_ppm: Mapped[float | None] = mapped_column(Float, default=None)
    temp_c: Mapped[float | None] = mapped_column(Float, default=None)
    hum_pct: Mapped[float | None] = mapped_column(Float, default=None)
    lux: Mapped[float | None] = mapped_column(Float, default=None)
    db_spl: Mapped[float | None] = mapped_column(Float, default=None)

    # dos vías independientes para la ocupación (ver services/aforo.py)
    ocupantes_conteo: Mapped[int | None] = mapped_column(Integer, default=None)
    ocupantes_estimado: Mapped[float | None] = mapped_column(Float, default=None)

    indice: Mapped[float | None] = mapped_column(Float, default=None)
    estado: Mapped[str] = mapped_column(String(16), default="ok")  # ok | alerta | critico
    # si la ventilacion estaba encendida en ese momento. Es lo que el
    # pronostico necesita para aprender que ventilar baja el CO2. Las
    # lecturas viejas lo tienen vacio (ver aprendizaje/ejemplos.py).
    ventilacion_on: Mapped[bool | None] = mapped_column(Boolean, default=None)

    __table_args__ = (
        Index("ix_lectura_aula_ts", "aula_id", "ts"),
        Index("ix_lectura_disp_ts", "dispositivo_id", "ts"),
    )


class Evento(Base):
    """Cruce de umbral, dispositivo caído, proyección de riesgo, etc."""
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    tipo: Mapped[str] = mapped_column(String(48))       # co2_alerta, co2_critico, temp_alerta...
    severidad: Mapped[str] = mapped_column(String(16))  # info | alerta | critico
    variable: Mapped[str] = mapped_column(String(32), default="")
    valor: Mapped[float | None] = mapped_column(Float, default=None)
    indice: Mapped[float | None] = mapped_column(Float, default=None)
    mensaje: Mapped[str] = mapped_column(Text, default="")
    reconocido: Mapped[bool] = mapped_column(Boolean, default=False)
    resuelto_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (Index("ix_evento_aula_ts", "aula_id", "ts"),)


class Actuacion(Base):
    """Registro auditable de cada orden enviada a un actuador.

    El campo `motivo` es la evidencia de que el sistema DECIDIÓ y no solo midió.
    """
    __tablename__ = "actuaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    actuador: Mapped[str] = mapped_column(String(32))   # ventilacion | iluminacion
    accion: Mapped[str] = mapped_column(String(16))     # on | off
    motivo: Mapped[str] = mapped_column(String(160), default="")
    origen: Mapped[str] = mapped_column(String(24), default="automatico")  # automatico | manual

    __table_args__ = (Index("ix_actuacion_aula_ts", "aula_id", "ts"),)


class PendienteResuelto(Base):
    """Pendiente que una persona marco como resuelto: se oculta 24 h y vuelve
    a aparecer si el problema sigue."""
    __tablename__ = "pendientes_resueltos"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)


class Umbral(Base):
    """Permite sobreescribir por aula los umbrales globales."""
    __tablename__ = "umbrales"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    variable: Mapped[str] = mapped_column(String(32))
    valor_alerta: Mapped[float] = mapped_column(Float)
    valor_critico: Mapped[float] = mapped_column(Float)

    __table_args__ = (Index("ix_umbral_aula_var", "aula_id", "variable", unique=True),)


class Pronostico(Base):
    """Lo que el pronostico dijo que iba a pasar, para revisar despues si acerto.

    Se guarda en "modo prueba": el pronostico todavia NO maneja la
    ventilacion, solo se anota aqui junto con lo que habria dicho el metodo
    actual (la linea recta de prediccion.py), y se compara contra la lectura
    real cuando llega el momento.
    """
    __tablename__ = "pronosticos"

    id: Mapped[int] = mapped_column(primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("aulas.id", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # el momento (reloj real) para el que se hizo el pronostico
    ts_objetivo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    minutos_adelante: Mapped[float] = mapped_column(Float)
    co2_ahora: Mapped[float] = mapped_column(Float)
    co2_previsto: Mapped[float] = mapped_column(Float)
    co2_linea_recta: Mapped[float | None] = mapped_column(Float, default=None)

    __table_args__ = (Index("ix_pronostico_aula_obj", "aula_id", "ts_objetivo"),)
