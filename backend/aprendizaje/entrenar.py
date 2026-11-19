"""Ensena al pronostico con el historial, lo examina y guarda lo aprendido.

    docker compose exec api python -m aprendizaje.entrenar
    docker compose exec api python -m aprendizaje.entrenar --dias 14

Solo aprende con lecturas que guardan si se estaba ventilando (ver ejemplos.py).

Pasos:
  1. Arma los ejemplos del pasado (ejemplos.py).
  2. Separa por fecha: aprende con lo mas viejo y se examina con lo mas
     nuevo, que NO vio al aprender. Asi el examen se parece a la vida real:
     adivinar un futuro que todavia no conoce.
  3. Compara contra la linea recta (el metodo que el sistema usa hoy).
  4. Guarda lo aprendido SOLO si le gana. Si no, deja lo anterior.

Como aprende: con muchos arboles de decision chicos ("si hay mas de 25
personas y la ventilacion esta apagada, el CO2 sube mucho"), donde cada
arbol nuevo corrige los errores de los anteriores. En la libreria se llama
HistGradientBoostingRegressor. Funciona bien con pocos datos, es rapido y no
necesita equipos especiales.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from app.config import settings
from aprendizaje import ejemplos as ej
from aprendizaje import que_mira

POCOS_EJEMPLOS = 3000       # con menos que esto no vale la pena intentarlo
PARTE_PARA_EXAMEN = 0.2     # el 20 % mas reciente se usa para examinar


def nuevo_alumno() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.08, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=0,
    )


def calificar(adivinado: np.ndarray, real: np.ndarray, ahora: np.ndarray) -> dict:
    """Notas en palabras simples. Todas son 'de cada 100' para poder compararlas."""
    zonas_adivinadas = np.array([que_mira.como_esta_el_aire(v) for v in adivinado])
    zonas_reales = np.array([que_mira.como_esta_el_aire(v) for v in real])

    # los momentos que importan: el aire estaba bien y en 10 min se iba a cargar
    se_iba_a_cargar = (ahora < settings.CO2_UMBRAL_ALERTA) & (real >= settings.CO2_UMBRAL_ALERTA)
    aviso = adivinado >= settings.CO2_UMBRAL_ALERTA
    sin_problema = (ahora < settings.CO2_UMBRAL_ALERTA) & (real < settings.CO2_UMBRAL_ALERTA)

    def de_cada_100(parte: np.ndarray, total: np.ndarray) -> float | None:
        return round(100.0 * parte.sum() / total.sum(), 1) if total.sum() else None

    return {
        "error_promedio_ppm": round(float(np.mean(np.abs(adivinado - real))), 1),
        "acerto_como_iba_a_estar_el_aire": de_cada_100(zonas_adivinadas == zonas_reales, np.ones(len(real), bool)),
        "aviso_a_tiempo": de_cada_100(se_iba_a_cargar & aviso, se_iba_a_cargar),
        "falsas_alarmas": de_cada_100(sin_problema & aviso, sin_problema),
        "veces_que_se_iba_a_cargar": int(se_iba_a_cargar.sum()),
    }


def fecha(t: float) -> str:
    return datetime.fromtimestamp(t, tz=que_mira.HORA_PERU).strftime("%d/%m/%Y %H:%M")


async def entrenar(dias: int, incluir_viejas: bool = False) -> int:
    print("== Pronostico del aire: aprendiendo del pasado ==")
    datos = await ej.armar(dias, incluir_viejas)
    n = len(datos)
    print(f"Ejemplos del pasado: {n:,} de {len(np.unique(datos.aula)) if n else 0} aulas".replace(",", "."))

    if n < POCOS_EJEMPLOS:
        print(f"Todavia son pocos (hacen falta al menos {POCOS_EJEMPLOS:,}). "
              "Deja el sistema funcionando un rato mas y vuelve a intentar.".replace(",", "."))
        return 1

    corte = int(n * (1 - PARTE_PARA_EXAMEN))
    print(f"  aprende con: {fecha(datos.momento[0])} a {fecha(datos.momento[corte - 1])}")
    print(f"  examen con:  {fecha(datos.momento[corte])} a {fecha(datos.momento[-1])} (no lo vio al aprender)")

    alumno = nuevo_alumno()
    alumno.fit(datos.tabla[:corte], datos.respuesta[:corte])
    adivinado = que_mira.limitar(alumno.predict(datos.tabla[corte:]))

    real = datos.respuesta[corte:]
    ahora = datos.tabla[corte:, 0]
    nota_pronostico = calificar(adivinado, real, ahora)
    nota_linea = calificar(datos.linea_recta[corte:], real, ahora)

    def fila(texto: str, clave: str, sufijo: str = "") -> None:
        a, b = nota_pronostico[clave], nota_linea[clave]
        a = "-" if a is None else a
        b = "-" if b is None else b
        print(f"  {texto:<46} {str(a) + sufijo:>10}   {str(b) + sufijo:>10}")

    print("\nResultado del examen")
    print(f"  {'':<46} {'pronostico':>10}   {'linea recta':>10}  <- el metodo de hoy")
    fila("Error promedio, en ppm (menos es mejor)", "error_promedio_ppm")
    fila("Acerto como iba a estar el aire, de cada 100", "acerto_como_iba_a_estar_el_aire")
    fila("Aviso a tiempo que se iba a cargar, de cada 100", "aviso_a_tiempo")
    fila("Falsas alarmas, de cada 100 (menos es mejor)", "falsas_alarmas")

    gana = nota_pronostico["error_promedio_ppm"] < nota_linea["error_promedio_ppm"]
    if not gana:
        print("\nEl pronostico NO le gano a la linea recta. No se guarda nada; "
              "el sistema sigue como esta.")
        return 2

    # Ya aprobo el examen: ahora aprende con TODO, incluida la parte mas
    # reciente, que es la que mas se parece a lo que viene.
    alumno_final = nuevo_alumno()
    alumno_final.fit(datos.tabla, datos.respuesta)

    informe = {
        "entrenado_el": datetime.now(timezone.utc).isoformat(),
        "ejemplos": n,
        "aulas": int(len(np.unique(datos.aula))),
        "desde": datetime.fromtimestamp(datos.momento[0], tz=timezone.utc).isoformat(),
        "hasta": datetime.fromtimestamp(datos.momento[-1], tz=timezone.utc).isoformat(),
        "minutos_adelante": que_mira.MINUTOS_ADELANTE,
        "datos_que_mira": datos.columnas,
        "examen": {"pronostico": nota_pronostico, "linea_recta": nota_linea},
        "con_simulador": settings.SIM_VELOCIDAD != 1.0,
    }
    que_mira.CARPETA_GUARDADO.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"alumno": alumno_final, "datos_que_mira": datos.columnas,
         "minutos_adelante": que_mira.MINUTOS_ADELANTE, "velocidad": settings.SIM_VELOCIDAD},
        que_mira.ARCHIVO_APRENDIDO,
    )
    que_mira.ARCHIVO_INFORME.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nEl pronostico le gano a la linea recta. Guardado en {que_mira.ARCHIVO_APRENDIDO}")
    print("El worker lo empieza a usar solo (en modo prueba) en menos de un minuto.")
    if informe["con_simulador"]:
        print("OJO: aprendio con datos del SIMULADOR. Sirve para probar el circuito; "
              "hay que volver a entrenarlo con datos reales del ESP32.")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Ensena al pronostico del aire con el historial.")
    p.add_argument("--dias", type=int, default=30, help="cuantos dias hacia atras usar (por defecto 30)")
    p.add_argument("--incluir-viejas", action="store_true",
                   help="usar tambien las lecturas de antes del arreglo de la ventilacion (no recomendado)")
    args = p.parse_args()
    raise SystemExit(asyncio.run(entrenar(args.dias, args.incluir_viejas)))


if __name__ == "__main__":
    main()
