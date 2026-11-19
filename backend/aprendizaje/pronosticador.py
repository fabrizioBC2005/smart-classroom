"""El pronostico en vivo. Lo usa el worker cada vez que llega una lectura.

MODO PRUEBA: el pronostico solo dice lo que espera; NO enciende ni apaga la
ventilacion. Eso lo sigue haciendo services/reglas.py. Cada pronostico se
anota en la tabla `pronosticos` para revisar despues si acerto, y recien
cuando gane de forma sostenida con datos reales tendria sentido dejarlo
decidir.

Si todavia no se entreno (no existe el archivo), no pasa nada: anota el
historial igual y devuelve None. Si alguien lo vuelve a entrenar, lo nota
solo y carga lo nuevo sin reiniciar el worker.
"""
from __future__ import annotations

import logging
import time
from collections import deque

import joblib
import numpy as np

from aprendizaje import que_mira

log = logging.getLogger("pronostico")

REVISAR_ARCHIVO_CADA_S = 30.0


class Pronosticador:
    def __init__(self, velocidad: float) -> None:
        self.velocidad = velocidad
        # cuanto historial guardar por aula: lo justo para mirar 15 min atras
        self.guardar_s = que_mira.segundos_de_reloj(15, velocidad) * 1.5
        self.historial: dict[int, deque[tuple[float, float]]] = {}
        self.aprendido: dict | None = None
        self._fecha_archivo: float | None = None
        self._ultima_revision = 0.0
        self._revisar_archivo()

    @property
    def listo(self) -> bool:
        return self.aprendido is not None

    def _revisar_archivo(self) -> None:
        self._ultima_revision = time.monotonic()
        archivo = que_mira.ARCHIVO_APRENDIDO
        if not archivo.exists():
            if self.aprendido is not None:
                log.info("se borro lo aprendido; el pronostico queda apagado")
            self.aprendido, self._fecha_archivo = None, None
            return
        fecha = archivo.stat().st_mtime
        if fecha == self._fecha_archivo:
            return
        try:
            cargado = joblib.load(archivo)
        except Exception:
            log.exception("no se pudo leer %s", archivo)
            return
        self._fecha_archivo = fecha
        if cargado.get("velocidad") != self.velocidad:
            log.warning(
                "el pronostico aprendio con SIM_VELOCIDAD=%s y ahora es %s: no se usa "
                "hasta volver a entrenarlo", cargado.get("velocidad"), self.velocidad,
            )
            self.aprendido = None
            return
        self.aprendido = cargado
        log.info("pronostico cargado (%s)", archivo.name)

    def anotar_y_prever(
        self,
        *,
        aula_id: int,
        ts: float,
        co2: float | None,
        personas: float | None,
        ventilacion: bool,
        temperatura: float | None,
        humedad: float | None,
        ruido: float | None,
        tamano_aula: float,
    ) -> float | None:
        """Guarda la lectura en el historial del aula y devuelve el CO2 que
        espera dentro de MINUTOS_ADELANTE, o None si no puede opinar."""
        if time.monotonic() - self._ultima_revision > REVISAR_ARCHIVO_CADA_S:
            self._revisar_archivo()

        if co2 is None:
            return None
        hist = self.historial.setdefault(aula_id, deque())
        hist.append((ts, co2))
        while hist and hist[0][0] < ts - self.guardar_s:
            hist.popleft()

        if self.aprendido is None:
            return None

        ts_hist = np.array([h[0] for h in hist])
        co2_hist = np.array([h[1] for h in hist])
        columnas = self.aprendido["datos_que_mira"]

        def uno(v: float | None) -> np.ndarray:
            return np.array([np.nan if v is None else float(v)])

        tabla = que_mira.armar_tabla(
            ts_historial=ts_hist, co2_historial=co2_hist, momentos=np.array([ts]),
            co2_ahora=uno(co2), personas=uno(personas), ventilacion=uno(float(ventilacion)),
            temperatura=uno(temperatura), humedad=uno(humedad), ruido=uno(ruido),
            tamano_aula=tamano_aula, velocidad=self.velocidad,
            con_horario=que_mira.DATOS_DE_HORARIO[0] in columnas,
        )
        # recien llegado (sin 5 minutos de historial): mejor no opinar
        if np.isnan(tabla[0, 1]):
            return None
        try:
            previsto = self.aprendido["alumno"].predict(tabla)
        except Exception:
            log.exception("fallo el pronostico del aula %s", aula_id)
            return None
        return float(que_mira.limitar(previsto)[0])
