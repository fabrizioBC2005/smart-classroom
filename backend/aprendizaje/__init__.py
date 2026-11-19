"""Pronostico del aire: el sistema aprende del pasado para adivinar el CO2.

    que_mira.py    lo que el pronostico mira para adivinar (lo usan todos)
    ejemplos.py    arma los ejemplos del pasado desde la base de datos
    entrenar.py    aprende de esos ejemplos, se examina y guarda lo aprendido
    pronosticador.py   lo usa el worker en vivo, cada vez que llega una lectura

Para entrenarlo:  docker compose exec api python -m aprendizaje.entrenar
"""
