"""Carga sedes y aulas de ejemplo.

  docker compose exec api python -m app.seed
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db import SessionLocal, crear_tablas
from app.models import Aula, Dispositivo, Sede

SEDES = [
    ("lima-norte", "Innova Schools Lima Norte", "Los Olivos"),
    ("lima-sur", "Innova Schools Lima Sur", "Villa El Salvador"),
]

# (codigo, nivel, volumen_m3, aforo, instrumentada)
AULAS_LN = [
    ("302", "secundaria", 172.0, 34, True),    # <- aula piloto con ESP32 real
    ("303", "secundaria", 168.0, 32, False),
    ("304", "secundaria", 175.0, 34, False),
    ("305", "secundaria", 165.0, 30, False),
    ("401", "primaria", 158.0, 28, False),
    ("402", "primaria", 160.0, 28, False),
    ("403", "primaria", 155.0, 26, False),
    ("404", "inicial", 140.0, 22, False),
]
AULAS_LS = [
    ("201", "secundaria", 170.0, 32, False),
    ("202", "secundaria", 170.0, 32, False),
    ("203", "primaria", 160.0, 28, False),
]


async def main() -> None:
    await crear_tablas()
    async with SessionLocal() as db:
        for slug, nombre, distrito in SEDES:
            existe = (await db.execute(select(Sede).where(Sede.slug == slug))).scalar_one_or_none()
            if not existe:
                db.add(Sede(slug=slug, nombre=nombre, distrito=distrito))
        await db.commit()

        ln = (await db.execute(select(Sede).where(Sede.slug == "lima-norte"))).scalar_one()
        ls = (await db.execute(select(Sede).where(Sede.slug == "lima-sur"))).scalar_one()

        for sede, lista in ((ln, AULAS_LN), (ls, AULAS_LS)):
            for codigo, nivel, vol, aforo, instr in lista:
                existe = (
                    await db.execute(
                        select(Aula).where(Aula.sede_id == sede.id, Aula.codigo == codigo)
                    )
                ).scalar_one_or_none()
                if existe:
                    continue
                aula = Aula(
                    sede_id=sede.id, codigo=codigo, nivel=nivel,
                    volumen_m3=vol, aforo_nominal=aforo, instrumentada=instr,
                )
                db.add(aula)
                await db.flush()
                if instr:
                    db.add(Dispositivo(aula_id=aula.id, device_id=f"esp32-{codigo}"))
        await db.commit()

    print("Seed listo: 2 sedes, 11 aulas. El aula 302 esta marcada como instrumentada.")


if __name__ == "__main__":
    asyncio.run(main())
