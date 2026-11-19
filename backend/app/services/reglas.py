"""Motor de reglas.

Toma una lectura nueva, la combina con la ventana reciente del aula y
decide tres cosas:
  1. el índice de habitabilidad
  2. si hay que generar un evento
  3. si hay que actuar sobre la ventilación (y con qué motivo auditable)

Es intencionalmente puro: no toca base de datos ni MQTT. Eso lo hace el
worker. Así se puede testear sin levantar infraestructura.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from app.services import aforo as aforo_svc
from app.services import indice as indice_svc
from app.services import prediccion as pred_svc


@dataclass
class Muestra:
    ts: float          # epoch segundos
    co2: float | None
    temp: float | None
    hum: float | None


@dataclass
class EstadoAula:
    """Ventana móvil en memoria. Evita ir a la base en cada lectura."""
    aula_id: int
    volumen_m3: float = 170.0
    nivel: str = "secundaria"
    ventana: deque[Muestra] = field(default_factory=lambda: deque(maxlen=240))
    ventilacion_on: bool = False
    # El ventilador se apaga solo cuando vence su temporizador (ttl_s). Antes
    # la orden se mandaba UNA vez y el worker seguia creyendo que ventilaba
    # aunque el aparato ya se hubiera apagado: el CO2 subia a 3000+ con el
    # panel diciendo "Ventilando". Aqui guardamos cuando hay que renovarla.
    ventilacion_renovar_ts: float = 0.0
    ultimo_motivo: str = ""
    ultimo_estado: str = "ok"
    # por que se encendio la ventilacion: "co2" o "temperatura". Decide la
    # condicion de apagado (no se apaga por CO2 normal si se prendio por calor).
    ventilacion_causa: str = ""

    # iluminacion: el rele del ESP32 no tiene temporizador, queda como se
    # le ordeno. Se enciende si hay gente y falta luz; se apaga cuando el aula
    # lleva un rato vacia (NO por lux alto: con las luces prendidas el luxometro
    # mide la propia luz artificial y el sistema se pondria a parpadear).
    iluminacion_on: bool = False
    vacia_desde_ts: float | None = None

    # override manual: hasta cuando la automatizacion no toca cada actuador.
    # Lo llena el worker cuando ve una orden con origen "manual".
    override_hasta: dict[str, float] = field(default_factory=dict)

    # modo de cada equipo: "automatico" o "manual". En manual el sistema no
    # enciende ni apaga nada por su cuenta: solo mantiene viva la orden de la
    # persona (renueva el temporizador del ventilador).
    modo: dict[str, str] = field(
        default_factory=lambda: {"ventilacion": "automatico", "iluminacion": "automatico"}
    )

    def es_manual(self, actuador: str) -> bool:
        return self.modo.get(actuador) == "manual"

    def en_override(self, actuador: str, ts: float) -> bool:
        return self.es_manual(actuador) or ts < self.override_hasta.get(actuador, 0.0)

    def cambiar_modo(self, actuador: str, modo: str) -> None:
        self.modo[actuador] = modo
        if modo == "automatico":
            # vuelve a mandar el sistema desde la siguiente lectura
            self.override_hasta.pop(actuador, None)

    def aplicar_manual(self, actuador: str, accion: str, ts: float, duracion_s: float) -> None:
        """Registra una orden manual: el estado pasa a ser el pedido y la
        automatizacion se pausa `duracion_s` para ese actuador."""
        on = accion == "on"
        self.override_hasta[actuador] = ts + duracion_s
        if actuador == "ventilacion":
            self.ventilacion_on = on
            self.ventilacion_causa = "manual" if on else ""
            # la orden manual ya trae su propio ttl; en modo manual se renueva
            # antes de que venza para que el ventilador no se apague solo
            self.ventilacion_renovar_ts = ts + 0.8 * duracion_s
            self.ultimo_motivo = "override_manual"
        elif actuador == "iluminacion":
            self.iluminacion_on = on

    def agregar(self, m: Muestra, ventana_s: int) -> None:
        self.ventana.append(m)
        corte = m.ts - ventana_s
        while self.ventana and self.ventana[0].ts < corte:
            self.ventana.popleft()

    def serie_co2(self) -> tuple[list[float], list[float]]:
        ts, vals = [], []
        for m in self.ventana:
            if m.co2 is not None:
                ts.append(m.ts)
                vals.append(m.co2)
        return ts, vals


@dataclass
class Decision:
    indice: float
    estado: str
    subindices: dict
    pendiente_ppm_min: float
    eta_s: float | None
    ocupantes_estimado: float | None
    eventos: list[dict]
    comando: dict | None       # ventilacion: lo que se publica en MQTT
    actuacion: dict | None     # ventilacion: lo que se registra en la base
    # TODAS las ordenes de esta lectura (ventilacion + iluminacion). El worker
    # publica y registra estas; comando/actuacion se mantienen por compatibilidad.
    comandos: list[dict] = field(default_factory=list)
    actuaciones: list[dict] = field(default_factory=list)


def evaluar(
    estado: EstadoAula,
    lectura: dict,
    *,
    co2_alerta: float,
    co2_critico: float,
    temp_alerta: float,
    hum_alerta: float,
    ventana_s: int,
    anticipacion_s: int,
    ttl_s: int,
    factor_aceleracion: float = 1.0,
    lux_minimo: float = 300.0,
    luz_apagar_vacia_s: float = 600.0,
    temp_histeresis: float = 1.0,
) -> Decision:
    ts = lectura.get("ts") or datetime.now(timezone.utc).timestamp()
    co2 = lectura.get("co2_ppm")
    temp = lectura.get("temp_c")
    hum = lectura.get("hum_pct")

    estado.agregar(Muestra(ts=ts, co2=co2, temp=temp, hum=hum), ventana_s)

    # ---- 1. índice ----
    res = indice_svc.calcular(
        co2_ppm=co2, temp_c=temp, hum_pct=hum,
        db_spl=lectura.get("db_spl"), lux=lectura.get("lux"),
        co2_alerta=co2_alerta, co2_critico=co2_critico,
    )

    # ---- 2. tendencia y aforo ----
    ts_serie, co2_serie = estado.serie_co2()
    tend = pred_svc.proyectar(ts_serie, co2_serie, umbral=co2_alerta)

    # tend.pendiente_ppm_min sale en ppm por minuto de RELOJ REAL (los ts de
    # la ventana son reales), pero con el simulador acelerado el CO2 avanzo a
    # razon de tiempo simulado: sale multiplicado por factor_aceleracion (con
    # hardware real factor_aceleracion=1.0 y esto no hace nada). "tend" original
    # SIGUE siendo la que decide cuando actuar mas abajo (valor_actual/eta_s en
    # tiempo real, correcto); "tend_mostrar" es solo para lo que se calcula con
    # la pendiente como magnitud fisica o se le muestra a una persona.
    tend_mostrar = replace(
        tend, pendiente_ppm_min=round(tend.pendiente_ppm_min / factor_aceleracion, 2)
    )

    ocupantes_est = None
    if co2 is not None:
        est = aforo_svc.estimar_por_co2(
            tend_mostrar.pendiente_ppm_min, co2, estado.volumen_m3, estado.nivel
        )
        if est.confiable:
            ocupantes_est = est.ocupantes

    # ---- 3. eventos ----
    eventos: list[dict] = []

    def ev(tipo, sev, var, valor, msg):
        eventos.append({
            "tipo": tipo, "severidad": sev, "variable": var,
            "valor": valor, "mensaje": msg, "indice": res.valor,
        })

    if res.estado != estado.ultimo_estado:
        if res.estado == "critico":
            ev("co2_critico", "critico", "co2_ppm", co2,
               f"CO2 en nivel critico ({co2:.0f} ppm)" if co2 else "Condicion critica")
        elif res.estado == "alerta":
            ev("co2_alerta", "alerta", "co2_ppm", co2,
               f"CO2 sobre el umbral de {co2_alerta:.0f} ppm")
        else:
            ev("normalizado", "info", "co2_ppm", co2, "Condiciones normalizadas")
        estado.ultimo_estado = res.estado

    if temp is not None and temp >= temp_alerta:
        ev("temp_alerta", "alerta", "temp_c", temp, f"Temperatura alta ({temp:.1f} C)")
    if hum is not None and hum >= hum_alerta:
        ev("hum_alerta", "alerta", "hum_pct", hum, f"Humedad alta ({hum:.0f} %)")

    # ---- 4. ocupacion ----
    # conteo directo (VL53L0X en la puerta) si existe; si no, lo inferido por
    # balance de CO2. None = no sabemos: la iluminacion no actua a ciegas.
    conteo = lectura.get("ocupantes")
    if conteo is not None:
        ocupada: bool | None = conteo > 0
    elif ocupantes_est is not None:
        ocupada = ocupantes_est >= 1
    else:
        ocupada = None

    if ocupada is False:
        if estado.vacia_desde_ts is None:
            estado.vacia_desde_ts = ts
    elif ocupada is True:
        estado.vacia_desde_ts = None

    comandos: list[dict] = []
    actuaciones: list[dict] = []

    def ordenar(actuador: str, accion: str, motivo: str, ttl: int, registrar: bool = True):
        cmd = {"actuador": actuador, "accion": accion, "motivo": motivo,
               "ttl_s": ttl, "origen": "automatico"}
        comandos.append(cmd)
        if registrar:
            actuaciones.append({"actuador": actuador, "accion": accion,
                                "motivo": motivo, "origen": "automatico"})
        return cmd

    # ---- 5. ventilacion (CO2 predictivo + temperatura) ----
    # tend_mostrar: mismo valor_actual/eta_s que tend (decide igual, en tiempo
    # real), solo cambia el "pendiente_ppm_min" que queda en el motivo auditable.
    ventilar, motivo = (False, "")
    if co2 is not None:
        ventilar, motivo = pred_svc.debe_ventilar(tend_mostrar, co2_alerta, anticipacion_s)
    causa = "co2" if ventilar else ""

    # calor con gente adentro: meter aire de afuera. No se ventila un aula
    # vacia por temperatura (no hay a quien aliviar y gasta energia).
    if not ventilar and temp is not None and temp >= temp_alerta and ocupada is not False:
        ventilar, motivo, causa = True, f"temperatura_alta:{temp:.1f}C", "temperatura"

    co2_ok = co2 is None or pred_svc.debe_apagar(co2, co2_alerta)
    temp_ok = temp is None or temp <= temp_alerta - temp_histeresis
    # se apaga solo cuando AMBAS cosas estan bien (si no, una regla apagaria
    # lo que la otra acaba de prender). Con el aula vacia el calor no cuenta.
    puede_apagar = co2_ok and (temp_ok or ocupada is False)

    # el temporizador del ventilador corre en tiempo del aparato: con el
    # simulador acelerado dura ttl_s / factor_aceleracion segundos reales.
    # Se renueva al 80 % para que no quede un hueco apagado entre ordenes.
    renovar_cada_s = 0.8 * ttl_s / max(factor_aceleracion, 1e-6)

    comando = None
    actuacion = None
    if estado.en_override("ventilacion", ts):
        # una persona decide (modo manual u orden manual reciente). En modo
        # manual el ventilador encendido se mantiene encendido: se renueva la
        # orden antes de que el aparato se apague por su temporizador.
        if (estado.es_manual("ventilacion") and estado.ventilacion_on
                and ts >= estado.ventilacion_renovar_ts):
            estado.ventilacion_renovar_ts = ts + renovar_cada_s
            comando = {"actuador": "ventilacion", "accion": "on",
                       "motivo": "renovacion|modo_manual", "ttl_s": ttl_s, "origen": "manual"}
            comandos.append(comando)
    elif ventilar and not estado.ventilacion_on:
        estado.ventilacion_on = True
        estado.ventilacion_causa = causa
        estado.ventilacion_renovar_ts = ts + renovar_cada_s
        estado.ultimo_motivo = motivo
        comando = ordenar("ventilacion", "on", motivo, ttl_s)
        actuacion = actuaciones[-1]
        if motivo.startswith("proyeccion"):
            ev("prediccion_riesgo", "info", "co2_ppm", co2,
               f"Ventilacion anticipada: {motivo}")

    elif estado.ventilacion_on and not ventilar and puede_apagar:
        estado.ventilacion_on = False
        estado.ventilacion_causa = ""
        if co2 is not None:
            motivo_off = f"co2_normalizado:{co2:.0f}ppm"
        else:
            motivo_off = f"temperatura_normalizada:{temp:.1f}C" if temp is not None else "condiciones_normales"
        if temp is not None and estado.ultimo_motivo.startswith("temperatura"):
            motivo_off += f"|temp:{temp:.1f}C"
        estado.ultimo_motivo = motivo_off
        comando = ordenar("ventilacion", "off", motivo_off, 0)
        actuacion = actuaciones[-1]

    elif estado.ventilacion_on and ts >= estado.ventilacion_renovar_ts:
        # sigue haciendo falta ventilar (el aire aun no bajo lo suficiente):
        # se repite la orden antes de que el aparato se apague solo. No se
        # guarda como actuacion nueva: es la misma, solo se mantiene viva.
        estado.ventilacion_renovar_ts = ts + renovar_cada_s
        comando = ordenar("ventilacion", "on", f"renovacion|{estado.ultimo_motivo}",
                          ttl_s, registrar=False)

    # ---- 6. iluminacion ----
    lux = lectura.get("lux")
    if not estado.en_override("iluminacion", ts):
        if (not estado.iluminacion_on and ocupada is True
                and lux is not None and lux < lux_minimo):
            estado.iluminacion_on = True
            ordenar("iluminacion", "on",
                    f"luz_insuficiente:{lux:.0f}lux|minimo:{lux_minimo:.0f}lux", 0)
        elif estado.iluminacion_on and estado.vacia_desde_ts is not None:
            # tiempo del aula (con el simulador acelerado pasa mas rapido)
            vacia_s = (ts - estado.vacia_desde_ts) * factor_aceleracion
            if vacia_s >= luz_apagar_vacia_s:
                estado.iluminacion_on = False
                ordenar("iluminacion", "off", f"aula_vacia:{vacia_s / 60:.0f}min", 0)

    return Decision(
        indice=res.valor,
        estado=res.estado,
        subindices=res.subindices,
        pendiente_ppm_min=tend_mostrar.pendiente_ppm_min,
        eta_s=tend.eta_s,
        ocupantes_estimado=ocupantes_est,
        eventos=eventos,
        comando=comando,
        actuacion=actuacion,
        comandos=comandos,
        actuaciones=actuaciones,
    )
