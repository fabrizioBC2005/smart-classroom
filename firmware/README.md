# Firmware — nodo de aula

## Conexionado

Todos los sensores I2C comparten SDA=21 y SCL=22 (3.3 V).

| Componente          | Conexion                        |
|---------------------|---------------------------------|
| SCD41 (CO2)         | I2C 0x62                        |
| BME280              | I2C 0x76 (o 0x77)               |
| BH1750 (lux)        | I2C 0x23                        |
| OLED SSD1306        | I2C 0x3C                        |
| VL53L0X A           | I2C + XSHUT -> GPIO 16          |
| VL53L0X B           | I2C + XSHUT -> GPIO 17          |
| Rele ventilacion    | GPIO 26                         |
| Rele iluminacion    | GPIO 27                         |
| LED verde/ambar/rojo| GPIO 32 / 33 / 25 (con R 220 R) |
| Buzzer              | GPIO 14                         |

El ventilador va con fuente propia de 12 V. El ESP32 solo conmuta el rele:
nunca alimentes el motor desde el pin del microcontrolador.

## Por que SCD41 y no MQ-135

El MQ-135 **no mide CO2**. Es un sensor de oxidos metalicos sensible a
compuestos volatiles, amoniaco, alcohol y humo. Su curva de CO2 no
entrega ppm confiables, deriva con la humedad y tiene fuerte reactividad
cruzada. Como toda la propuesta descansa sobre la medicion de CO2, usarlo
invalidaria el resultado.

Alternativa mas barata: **MH-Z19C** (NDIR por UART). Mas lento pero valido.

## Pasos

1. Arduino IDE -> Gestor de tarjetas -> instalar "esp32 by Espressif".
2. Instalar las librerias listadas al inicio de `smart_classroom.ino`.
3. `cp config.h.example config.h` y editar WiFi + IP de la laptop.
4. Placa: "ESP32 Dev Module". Subir.
5. Monitor serie a 115200 para ver el diagnostico de cada sensor.

## Red

El WiFi institucional suele usar WPA2-Enterprise, que el ESP32 no maneja
de forma directa. Para la demo usa el **hotspot de un celular** y conecta
ahi la laptop y el ESP32.

## Prueba sin sensores

Si el hardware aun no llega, levanta el simulador:

    docker compose --profile sim up -d simulator

Publica en los mismos topics con el mismo payload.
