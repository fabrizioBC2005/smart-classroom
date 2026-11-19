"use client";

import Link from "next/link";
import { COLOR_ESTADO, n0, nivelAire } from "@/lib/formato";
import type { AulaEstado, Estado, MsgTelemetria } from "@/lib/tipos";

// La vista principal responde una sola pregunta: ¿que aulas necesitan
// atencion? Por eso la tarjeta se queda con cuatro cosas, de arriba abajo:
// punto de estado + nombre, el numero de CO2, que significa, los otros tres
// sensores del aula (clima, luz, conteo en la puerta) y que hace el sistema. Temperatura, humedad, habitabilidad, tendencia, aforo y la barra
// de umbrales viven en el detalle del aula, que es donde se va a profundizar.
// Antes eran once elementos compitiendo y el subtitulo se cortaba con "…".
export default function AulaCard({
  base,
  vivo,
  estado,
}: {
  base: AulaEstado;
  vivo?: MsgTelemetria;
  // el estado lo calcula la pagina (no la tarjeta) para que el punto de color
  // y los contadores de arriba usen exactamente el mismo criterio y sumen
  // siempre el total
  estado: Estado;
}) {
  const co2 = vivo?.co2_ppm ?? base.co2_ppm;
  const vent = vivo?.ventilacion_on ?? base.ventilacion_on;
  const temp = vivo?.temp_c ?? base.temp_c;
  const hum = vivo?.hum_pct ?? base.hum_pct;
  const lux = vivo?.lux ?? base.lux ?? null;
  const luces = vivo?.iluminacion_on ?? base.iluminacion_on ?? null;
  const personas = vivo?.ocupantes ?? base.ocupantes;
  const sinDatos = estado === "sin_datos";
  const color = COLOR_ESTADO[estado];
  const accion = accionDelSistema(estado, vent);

  return (
    <Link
      href={`/aula/${base.aula_id}`}
      className={`group relative flex h-full flex-col overflow-hidden rounded-xl border bg-white p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:shadow-lift focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/50 ${
        // el borde solo se tiñe en las criticas: las conecta con el banner rojo
        // de arriba sin que las de alerta o normales metan ruido de color
        estado === "critico" ? "border-danger/50" : "border-line"
      } ${sinDatos ? "opacity-60" : ""}`}
    >
      {/* franja superior del color de estado: se lee de lejos sin competir con el numero */}
      <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: color, opacity: sinDatos ? 0.5 : 0.85 }} />
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
        <h3 className="truncate text-sm font-semibold">Aula {base.codigo}</h3>
        <svg className="ml-auto h-4 w-4 shrink-0 text-muted opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
      </div>

      <p
        className="mt-4 text-[34px] font-semibold leading-none tracking-tight tabular-nums"
        style={{ color }}
      >
        {sinDatos ? "—" : n0(co2)}
        {/* unidad visible y discreta: sin ella el numero solo no se entiende.
            aria-label para que el lector de pantalla diga "ppm de CO2" */}
        {!sinDatos && (
          <span
            className="ml-1.5 text-xs font-medium tracking-normal text-muted"
            aria-label="ppm de CO₂"
          >
            ppm CO₂
          </span>
        )}
      </p>

      <p className="mt-1.5 text-xs text-muted">
        {sinDatos ? "sin sensores" : nivelAire(co2).texto.toLowerCase()}
      </p>

      {/* lo que miden los otros sensores del aula (el del aire es el numero
          grande): temperatura y humedad, luz, y conteo en la puerta */}
      {!sinDatos && (
        <dl className="mb-4 mt-4 grid grid-cols-2 gap-1.5">
          <Dato
            icono="temp"
            valor={temp === null ? "—" : `${temp.toFixed(1)} °C`}
            etiqueta="temperatura"
            alerta={temp !== null && temp >= TEMP_ALERTA}
          />
          <Dato
            icono="hum"
            valor={hum === null ? "—" : `${n0(hum)} %`}
            etiqueta="humedad"
            alerta={hum !== null && hum >= HUM_ALERTA}
          />
          <Dato
            icono="luz"
            valor={lux === null ? "—" : `${n0(lux)} lux`}
            etiqueta={luces ? "luz · luces on" : "luz"}
            alerta={lux !== null && lux < LUX_MINIMO && !luces}
          />
          <Dato
            icono="personas"
            valor={personas === null || personas === undefined ? "—" : n0(personas)}
            extra={`/${base.aforo_nominal}`}
            etiqueta="personas"
          />
        </dl>
      )}
      {sinDatos && <div className="mb-4" />}

      <p
        className="mt-auto flex items-center gap-1.5 border-t border-line/70 pt-3 text-xs font-medium"
        style={{ color: sinDatos ? COLOR_ESTADO.sin_datos : color }}
      >
        <Icono tipo={accion.icono} />
        {accion.texto}
      </p>
    </Link>
  );
}

// mismos umbrales que el backend (app/config.py)
const TEMP_ALERTA = 26;
const LUX_MINIMO = 300;
const HUM_ALERTA = 70;

type TipoDato = "temp" | "hum" | "luz" | "personas";

function Dato({
  icono, valor, extra, etiqueta, alerta = false,
}: {
  icono: TipoDato; valor: string; extra?: string; etiqueta: string; alerta?: boolean;
}) {
  return (
    <div className={`min-w-0 rounded-lg px-2 py-1.5 ${alerta ? "bg-amber/10" : "bg-mist"}`}>
      <dt className="sr-only">{etiqueta}</dt>
      <dd className={`flex items-center gap-1 text-[13px] font-semibold tabular-nums ${alerta ? "text-amber" : "text-ink"}`}>
        <IconoDato tipo={icono} />
        <span className="truncate">
          {valor}
          {extra && <span className="ml-0.5 text-[11px] font-medium text-muted">{extra}</span>}
        </span>
      </dd>
      <p aria-hidden className="mt-0.5 truncate text-[10px] text-muted">{etiqueta}</p>
    </div>
  );
}

function IconoDato({ tipo }: { tipo: TipoDato }) {
  const comun = {
    className: "h-3.5 w-3.5 shrink-0 text-muted",
    viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2,
    strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true,
  };
  if (tipo === "hum") {
    return (
      <svg {...comun}>
        <path d="M12 3s6 6.4 6 11a6 6 0 0 1-12 0c0-4.6 6-11 6-11Z" />
      </svg>
    );
  }
  if (tipo === "temp") {
    return (
      <svg {...comun}>
        <path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0Z" />
      </svg>
    );
  }
  if (tipo === "luz") {
    return (
      <svg {...comun}>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    );
  }
  return (
    <svg {...comun}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" />
      <path d="M16 4.8a3.2 3.2 0 0 1 0 6.4M18 14.8c1.9.7 3 2.6 3 5.2" />
    </svg>
  );
}

type TipoIcono = "ventilador" | "aviso" | "check" | "nada";

// Solo describe lo que el sistema ESTA haciendo ahora, no lo que hara. La
// version anterior anunciaba "Ventilara en X min" a partir de eta_s, que es
// el tiempo hasta CRUZAR 1000 ppm (no hasta ventilar) y ademas viene en
// segundos de reloj real, sin normalizar por SIM_VELOCIDAD: por eso aparecia
// "aire limpio" junto a "ventilara en 5 min". La proyeccion sigue disponible
// en el detalle del aula, con su contexto.
function accionDelSistema(estado: Estado, vent: boolean): { texto: string; icono: TipoIcono } {
  if (estado === "sin_datos") return { texto: "No medimos aquí", icono: "nada" };
  if (vent) return { texto: "Ventilando", icono: "ventilador" };
  // en alerta o critico sin ventilacion: normalmente alguien la apago a mano;
  // hay que decirlo, porque es justo el caso que necesita una persona
  if (estado === "critico" || estado === "alerta") {
    return { texto: "Ventilación apagada", icono: "aviso" };
  }
  return { texto: "Sin intervención", icono: "check" };
}

function Icono({ tipo }: { tipo: TipoIcono }) {
  // mismo trazo que los iconos de Nav, para que se lean como una familia
  const comun = {
    className: "h-3.5 w-3.5 shrink-0",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (tipo === "ventilador") {
    return (
      <svg {...comun}>
        <circle cx="12" cy="12" r="1.6" />
        <path d="M12 10.4c0-3.4 1-6.4 3.6-6.4 2.2 0 2.6 2.8.6 4.4-1.3 1-2.8 1.5-4.2 2" />
        <path d="M13.6 12c3.4 0 6.4 1 6.4 3.6 0 2.2-2.8 2.6-4.4.6-1-1.3-1.5-2.8-2-4.2" />
        <path d="M12 13.6c0 3.4-1 6.4-3.6 6.4-2.2 0-2.6-2.8-.6-4.4 1.3-1 2.8-1.5 4.2-2" />
        <path d="M10.4 12C7 12 4 11 4 8.4 4 6.2 6.8 5.8 8.4 7.8c1 1.3 1.5 2.8 2 4.2" />
      </svg>
    );
  }
  if (tipo === "aviso") {
    return (
      <svg {...comun}>
        <path d="M10.3 3.9 2.4 17.6A2 2 0 0 0 4.1 20.6h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
        <path d="M12 9v4" />
        <path d="M12 17h.01" />
      </svg>
    );
  }
  if (tipo === "check") {
    return (
      <svg {...comun}>
        <path d="M5 12.5 10 17.5 19 7" />
      </svg>
    );
  }
  return (
    <svg {...comun}>
      <path d="M6 12h12" />
    </svg>
  );
}
