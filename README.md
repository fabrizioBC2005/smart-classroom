# Smart Classroom

Plataforma IoT de monitoreo ambiental y de ocupación para aulas.
No se queda en *medir y mostrar*: **mide, analiza, decide y actúa antes**
de que se cruce el umbral crítico.

```
Sensores → ESP32 → MQTT → Worker → PostgreSQL
                             │
                             ├── Redis → WebSocket → Dashboard
                             └── MQTT → Relé de ventilación
```

---

## Arranque rápido

Necesitas Docker Desktop y Node.js. **No hace falta hardware**: el simulador
genera telemetría realista en los mismos topics MQTT que usará el ESP32.

En Linux/Mac con `make` disponible, `make up` sigue funcionando igual que
antes. En **Windows no hay `make`** por defecto, así que la forma soportada
de arrancar es el script `start.ps1` (ver abajo). El `Makefile` se mantiene
como referencia rápida de los comandos `docker compose` subyacentes.

### Windows (PowerShell)

El backend corre en Docker; el frontend corre **nativo** con `npm run dev`
fuera de Docker, porque con volúmenes montados desde Windows el hot-reload
de Next.js en un contenedor es demasiado lento para desarrollar cómodo. El
servicio `web` sí está definido en `docker-compose.yml` pero vive en el
profile `docker-web`, que `docker compose up` no incluye por defecto — así
no choca con el `npm run dev` local en el puerto 3000.

```powershell
cp .env.example .env      # o copy .env.example .env
.\start.ps1
```

`start.ps1` hace todo el arranque de punta a punta:

1. Verifica que Docker Desktop esté corriendo (si no, avisa claro en vez de
   tirar un stack trace).
2. Valida `docker-compose.yml` con `docker compose config`.
3. Levanta el backend con `docker compose --profile sim up -d --build`.
4. Se asegura de que el contenedor `web` (profile `docker-web`) esté
   detenido, por si alguien lo encendió a mano.
5. Espera a que la API responda en `http://localhost:8001/salud`.
6. Carga los datos de ejemplo (`app.seed`) **solo si la base está vacía**.
7. Abre el frontend (`npm run dev`) en otra ventana de PowerShell — usa
   `.\start.ps1 -NoFrontend` si prefieres arrancarlo tú mismo.

Las variables `NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_WS_URL` ya están en
`web/.env.local` (ignorado por git), así que no hace falta exportarlas a
mano en cada sesión de PowerShell.

| Servicio             | URL / puerto en el host          |
|----------------------|-----------------------------------|
| Dashboard (nativo)   | http://localhost:3000             |
| API + documentación  | http://localhost:8001/docs        |
| Salud de la API      | http://localhost:8001/salud       |
| Broker MQTT          | `localhost:1883`                  |
| Redis                | `localhost:6380`                  |
| PostgreSQL           | sin puerto expuesto al host       |

La API quedó publicada en el puerto **8001** (no 8000) porque el 8000 solía
estar ocupado en desarrollo; Redis quedó en **6380** por la misma razón.
Dentro de la red de Docker los servicios se siguen hablando por sus puertos
internos normales (`api:8000`, `redis:6379`) — solo cambia el mapeo hacia el
host. `db` no expone puerto porque nada fuera de Docker necesita conectarse
directo a Postgres.

En un par de minutos verás las aulas cambiar de color solas y, cuando el
CO₂ empiece a subir, el sistema encenderá la ventilación por su cuenta.

```powershell
docker compose logs -f api worker simulator   # ver qué está decidiendo el worker
docker compose ps
docker compose down                           # apagar el backend
docker compose down -v                        # apagar y borrar la base de datos
```

### Linux / Mac

```bash
cp .env.example .env
make up          # levanta el backend con el profile sim
make seed        # carga 2 sedes y 11 aulas de ejemplo
cd web && npm run dev   # frontend nativo, igual que en Windows
```

---

## Los servicios

| Servicio     | Qué hace                                                        |
|--------------|-----------------------------------------------------------------|
| `mosquitto`  | Broker MQTT. Punto de entrada de toda la telemetría              |
| `db`         | PostgreSQL 16. Histórico de lecturas, eventos y actuaciones      |
| `redis`      | Canal pub/sub entre el worker y los WebSocket, más caché         |
| `api`        | FastAPI. REST + WebSocket para el dashboard                      |
| `worker`     | Consume MQTT, aplica reglas, persiste y publica comandos         |
| `simulator`  | Genera telemetría realista mientras no haya hardware             |
| `web`        | Dashboard en Next.js 14 + Tailwind + Recharts                    |

API y worker corren separados a propósito: así se pueden escalar de forma
independiente y un reinicio del dashboard no interrumpe la ingesta.

---

## Lo que hace distinto al sistema

### 1. Índice de Habitabilidad (`app/services/indice.py`)

Traduce CO₂, temperatura, humedad, ruido e iluminación a un solo número
de 0 a 100. Si falta un sensor, su peso se redistribuye, de modo que el
índice sigue siendo comparable entre aulas con distinto equipamiento.

Se presenta como **indicador de gestión**, no como medición de desempeño
cognitivo: la evidencia sobre CO₂ y cognición es fuerte pero está en
disputa (Allen et al. 2016 frente al estudio danés del mismo año).

### 2. Control predictivo (`app/services/prediccion.py`)

Regresión lineal sobre ventana móvil de 5 minutos, proyección del cruce
de umbral y actuación anticipada. Sin redes neuronales: el volumen de
datos no las justifica y un modelo sobredimensionado sería un punto
débil, no una fortaleza.

Cada orden se guarda con su motivo auditable:

```
proyeccion_cruce_umbral:4.2min|pendiente:23.4ppm_min|r2:0.97
```

### 2b. Automatización sin supervisión (`app/services/reglas.py`)

El aula se maneja sola; el dashboard es para mirar, no para operar.

| Actuador | Se enciende cuando | Se apaga cuando |
|---|---|---|
| Ventilación | CO₂ va a cruzar 1000 ppm (predictivo) o ya lo cruzó; **o** temperatura ≥ 26 °C con gente adentro | CO₂ ≤ 880 ppm **y** temperatura ≤ 25 °C (o el aula quedó vacía) |
| Luces | hay gente y la luz en el pupitre es < 300 lux | el aula lleva 10 min vacía |

- Las luces **no** se apagan por lux alto: con ellas prendidas el luxómetro mide
  su propia luz y el sistema se pondría a parpadear.
- **Modo por equipo**: en el detalle del aula, cada equipo tiene
  *Automático* (lo maneja el sistema; el interruptor queda bloqueado) o
  *Manual* (solo las personas; el sistema no lo toca, pero sigue generando
  alertas). Se guarda en la base (`aulas.modo_ventilacion`,
  `aulas.modo_iluminacion`) y sobrevive reinicios.
- **La persona manda**: una orden manual desde el dashboard pausa la
  automatización de ese actuador por `OVERRIDE_MANUAL_S` (10 min). Así el
  docente puede apagar las luces para el proyector sin que se vuelvan a prender.
- Umbrales en `.env`: `LUX_MINIMO`, `LUZ_APAGAR_VACIA_S`, `TEMP_HISTERESIS`,
  `OVERRIDE_MANUAL_S`. Cada orden queda en `actuaciones` con su motivo
  (`luz_insuficiente:84lux|minimo:300lux`, `aula_vacia:10min`, `temperatura_alta:27.5C`).

### 2c. Asistente IA en burbuja (`app/services/asistente.py`)

Botón flotante en todas las pantallas del dashboard. El personal pregunta en
lenguaje normal ("¿por qué el aula 303 siempre está mal?") y Claude responde
consultando los datos con herramientas de **solo lectura** (estado en vivo,
resumen por aula, eventos, actuaciones, renovación de aire, cumplimiento A.040).
No puede controlar equipos: el control sigue siendo el motor de reglas.

Para activarlo, pon tu clave en `.env` y reinicia la API:

```
ANTHROPIC_API_KEY=sk-ant-...
docker compose up -d api
```

Sin clave, la burbuja aparece igual y avisa que falta configurarla.

### 2d. Pendientes (`app/services/pendientes.py`)

La pantalla **Pendientes** (menú lateral, con un número) lista solo lo que el
sistema **no puede resolver solo** y necesita a una persona. Lo que ya resolvió
(ventilar, prender luces) no aparece: se cuenta en una línea al final.

| Pendiente | Cuándo aparece | Prioridad |
|---|---|---|
| Sin señal | un aula deja de enviar datos (2 min) o un sensor deja de medir | urgente |
| El ventilador no alcanza | 20 min ventilando y el CO₂ sigue sobre 1000 ppm | urgente |
| El aula ventila mal | renovación de aire < 1 por hora, o menos de la mitad que las demás aulas de la sede | importante |
| Equipo olvidado en manual | más de 1 h en modo Manual (con botón "Volver a automático") | importante |
| Calor o humedad que se repite | alerta de temperatura o humedad en 3 de los últimos 7 días | para planificar |

"Ya lo resolví" lo oculta 24 h; si el problema sigue, vuelve a aparecer.
Los tiempos se miden en tiempo del aula (con el simulador acelerado pasan más rápido).

### 3. Aforo sin datos personales (`app/services/aforo.py`)

Dos vías independientes:

- **Conteo directo** con dos sensores de distancia en el marco de la
  puerta. El orden de activación da la dirección.
- **Inferencia por balance de masa de CO₂**:

  ```
  dC/dt = (N·G)/V − (Q/V)·(C − C_ext)
  ```

Ninguna captura información que identifique a una persona. No es un
accidente del diseño: es un requisito derivado de la Ley 29733, y es lo
que hace viable el sistema en un colegio con menores de edad.

El resultado experimental del proyecto es el **error de la vía B medido
contra la vía A**.

### 4. Firma de decaimiento (`/api/reporte/renovacion/{id}`)

Con el aula vacía, la curva de caída del CO₂ revela la tasa de renovación
de aire real (ACH). Un aula que decae demasiado lento tiene ventilación
deficiente, y el sistema lo detecta sin inspección física.

### 5. Reporte de cumplimiento (`/api/reporte/cumplimiento`)

La Norma A.040 del RNE exige renovación de aire adecuada y constante pero
no define mecanismo de verificación. Este reporte convierte esa
obligación declarativa en un indicador medible y auditable por ambiente y
por periodo.

### 6. Pronóstico del aire (`backend/aprendizaje/`) — en prueba

El sistema aprende de lo que pasó antes en las aulas para adivinar cómo va
a estar el aire **dentro de 10 minutos**. La línea recta de
`prediccion.py` solo sigue la subida de los últimos minutos. El pronóstico
también mira cuánta gente hay, si se está ventilando, la temperatura y el
tamaño del aula.

| Archivo | Qué hace |
|---|---|
| `que_mira.py` | Lo que mira para adivinar. Lo usan el entrenamiento y el worker, con el mismo código |
| `ejemplos.py` | Convierte el historial en ejemplos: "lo que sabíamos" → "lo que pasó 10 min después" |
| `entrenar.py` | Aprende, se examina con los datos más recientes y lo guarda solo si le gana a la línea recta |
| `pronosticador.py` | Lo usa el worker en vivo y recarga solo lo aprendido si se vuelve a entrenar |

```powershell
docker compose exec api python -m aprendizaje.entrenar    # o: make pronostico
```

Está en **modo prueba**: muestra su pronóstico en el detalle de cada aula y
anota cada uno en la tabla `pronosticos` para compararlo con lo que pasó
de verdad, pero **no maneja la ventilación**. Si se entrena con el
simulador, aprende cómo funciona el simulador. Hay que volver a entrenarlo
con unas semanas de datos reales del ESP32.

---

## Tests

```bash
make test
# o en local:
cd backend && pytest -q
```

Cubren el índice, la regresión, la histéresis, el estimador de aforo, el
motor de reglas y el **lazo cerrado completo** (simulador físico + reglas).

Este último es el que produce el resultado a presentar:

```bash
cd backend && pytest tests/test_lazo_cerrado.py -s
```

```
reactivo   ->  2.0 min sobre 1000 ppm | pico 1017 ppm
predictivo ->  0.0 min sobre 1000 ppm | pico  919 ppm
```

> La magnitud de la mejora depende de la capacidad del ventilador. Lo
> sólido es la dirección: el control predictivo no llega a cruzar el
> umbral; el reactivo sí, por definición.

---

## Conectar el hardware real

1. Compra y arma según `firmware/README.md`.
2. `cp firmware/config.h.example firmware/config.h` y edita WiFi + la IP
   de la laptop donde corre Docker (**no** `localhost`).
3. Sube el sketch desde Arduino IDE.
4. Apaga el simulador para no mezclar datos:

```bash
make sim-off
```

El aula `302` viene marcada como instrumentada en el seed. Si usas otro
código, ajústalo en `config.h` y en `app/seed.py`.

### Sobre los sensores

**El MQ-135 no mide CO₂.** Es un sensor de óxidos metálicos sensible a
compuestos volátiles, amoniaco y humo; su curva de CO₂ no entrega ppm
confiables. Como toda la propuesta descansa sobre el CO₂, usarlo
invalidaría la medición. Va **SCD41** (NDIR fotoacústico) o, más barato,
**MH-Z19C**.

**El PIR no cuenta personas.** Detecta movimiento, no cantidad. Para
contar se usan dos **VL53L0X** en la puerta.

### Sobre la red

El WiFi institucional suele usar WPA2-Enterprise, que el ESP32 no maneja
directamente. Para la demo: **hotspot de celular**, con la laptop y el
ESP32 en la misma red.

La lógica crítica vive en el firmware, no en el servidor: si se cae la
red, el ventilador igual se enciende y el OLED sigue mostrando el estado.

---

## Contrato MQTT

**Telemetría** → `smartclassroom/{sede}/{aula}/telemetria`

```json
{
  "device_id": "esp32-302",
  "ts": 1731000000.0,
  "co2_ppm": 812.4,
  "temp_c": 24.1,
  "hum_pct": 62.0,
  "lux": 340,
  "db_spl": 58.2,
  "ocupantes": 34,
  "fw": "1.0.0"
}
```

**Comando** → `smartclassroom/{sede}/{aula}/comando`

```json
{
  "actuador": "ventilacion",
  "accion": "on",
  "motivo": "proyeccion_cruce_umbral:4.2min|pendiente:23.4ppm_min|r2:0.97",
  "ttl_s": 600
}
```

**Estado** (retained, con LWT) → `smartclassroom/{sede}/{aula}/estado`

---

## Estructura

```
backend/
  app/
    config.py            variables de entorno
    models.py            modelo de datos
    schemas.py           contratos de la API
    db.py  realtime.py   infraestructura
    routers/             aulas, eventos, control, reportes
    services/
      indice.py          índice de habitabilidad
      prediccion.py      control predictivo
      aforo.py           balance de masa de CO₂
      reglas.py          motor de decisión (puro, testeable)
    seed.py
  worker/main.py         ingesta MQTT → reglas → BD → comando
  tests/
simulator/main.py        modelo físico de aula con horario escolar
firmware/                ESP32 con lógica de seguridad local
web/src/
  app/                   4 vistas del dashboard
  components/            AulaCard, Gauge, SerieCO2, Timeline
  lib/                   cliente API, tipos, WebSocket
```

---

## Ajustes útiles

En `.env`:

| Variable                   | Efecto                                          |
|----------------------------|-------------------------------------------------|
| `CO2_UMBRAL_ALERTA`        | Umbral de alerta (1000 ppm por defecto)         |
| `PREDICCION_ANTICIPACION_S`| Cuánto se anticipa. `0` = control reactivo      |
| `SIM_VELOCIDAD`            | `60` = 1 min simulado por segundo real          |
| `SIM_INTERVALO_S`          | Frecuencia de publicación del simulador         |

Para la demo, subir `SIM_VELOCIDAD` hace que la curva de acumulación se
vea en segundos en lugar de horas.
