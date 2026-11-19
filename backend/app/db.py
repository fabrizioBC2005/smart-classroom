"""Conexión a PostgreSQL (SQLAlchemy 2.0 async)."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)

from app.config import settings
from app.models import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def crear_tablas() -> None:
    """Para un proyecto de curso basta con esto en vez de Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all crea tablas nuevas pero no agrega columnas a las que ya
        # existen; las columnas nuevas se agregan aqui a mano.
        await conn.execute(text(
            "ALTER TABLE lecturas ADD COLUMN IF NOT EXISTS ventilacion_on BOOLEAN"
        ))
        for col in ("modo_ventilacion", "modo_iluminacion"):
            await conn.execute(text(
                f"ALTER TABLE aulas ADD COLUMN IF NOT EXISTS {col} "
                "VARCHAR(16) NOT NULL DEFAULT 'automatico'"
            ))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
