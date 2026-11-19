"""Configuración central. Todo se lee de variables de entorno (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- infraestructura ---
    DATABASE_URL: str = "postgresql+asyncpg://sc:sc_dev_password@db:5432/smartclassroom"
    REDIS_URL: str = "redis://redis:6379/0"

    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_USER: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_BASE_TOPIC: str = "smartclassroom"

    # --- umbrales de las reglas ---
    CO2_UMBRAL_ALERTA: float = 1000.0     # ppm — referencia ASHRAE 62.1
    CO2_UMBRAL_CRITICO: float = 1400.0    # ppm
    TEMP_UMBRAL_ALERTA: float = 26.0      # °C
    HUM_UMBRAL_ALERTA: float = 70.0       # %

    # --- control predictivo ---
    PREDICCION_VENTANA_S: int = 300       # ventana móvil para la regresión
    PREDICCION_ANTICIPACION_S: int = 300  # actúa si el cruce llega antes de esto
    VENTILACION_TTL_S: int = 600          # cuánto dura una orden de ventilación

    # --- automatizacion de iluminacion y override ---
    LUX_MINIMO: float = 300.0             # lux en el pupitre (EN 12464-1: aulas 300-500)
    LUZ_APAGAR_VACIA_S: int = 600         # apaga luces tras 10 min de aula vacia
    TEMP_HISTERESIS: float = 1.0          # °C bajo TEMP_UMBRAL_ALERTA para apagar
    # tras una orden manual desde el dashboard, la automatizacion no toca ese
    # actuador durante este tiempo (en tiempo del aula). Igual al TTL de la
    # ventilacion para que coincida con cuanto dura la orden en el aparato.
    OVERRIDE_MANUAL_S: int = 600

    # cuanto acelera el tiempo el simulador (ver simulator/main.py). 1.0 = sin
    # aceleracion, que es lo correcto con hardware real. Sirve para des-acelerar
    # la pendiente de CO2 antes de mostrarla o de usarla en el balance de masa:
    # los timestamps de las lecturas son de reloj real, pero el CO2 avanzo a
    # razon de tiempo SIMULADO, asi que sin corregir sale multiplicado por este
    # factor (ver services/reglas.py).
    SIM_VELOCIDAD: float = 1.0

    # --- asistente IA (Claude). Vacio = la burbuja avisa que falta configurar ---
    ANTHROPIC_API_KEY: str = ""

    # --- canales de Redis ---
    CANAL_TELEMETRIA: str = "rt:telemetria"
    CANAL_EVENTOS: str = "rt:eventos"

    @property
    def topic_telemetria(self) -> str:
        return f"{self.MQTT_BASE_TOPIC}/+/+/telemetria"

    @property
    def topic_comandos(self) -> str:
        return f"{self.MQTT_BASE_TOPIC}/+/+/comando"

    @property
    def topic_estado(self) -> str:
        return f"{self.MQTT_BASE_TOPIC}/+/+/estado"

    @property
    def topic_modos(self) -> str:
        return f"{self.MQTT_BASE_TOPIC}/+/+/modo"

    def topic_modo(self, sede: str, aula: str) -> str:
        return f"{self.MQTT_BASE_TOPIC}/{sede}/{aula}/modo"

    def topic_comando(self, sede: str, aula: str) -> str:
        return f"{self.MQTT_BASE_TOPIC}/{sede}/{aula}/comando"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
