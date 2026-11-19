"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AulaCard from "@/components/AulaCard";
import { api } from "@/lib/api";
import { ORDEN_ESTADO } from "@/lib/formato";
import { SEDE_ACTUAL } from "@/lib/sede";
import { useRealtime } from "@/lib/useRealtime";
import type { AulaEstado, Estado, Sede } from "@/lib/tipos";

type Filtro = "todas" | Estado;

export default function Page() {
  // una sola sede por ahora (ver lib/sede.ts): sin selector
  const [sede, setSede] = useState<Sede | null>(null);
  const [aulas, setAulas] = useState<AulaEstado[]>([]);
  const [filtro, setFiltro] = useState<Filtro>("todas");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  const { conectado, porAula } = useRealtime();

  const cargar = useCallback(async () => {
    try {
      setAulas(await api.estado(SEDE_ACTUAL));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    api
      .sedes()
      .then((ss) => setSede(ss.find((s) => s.slug === SEDE_ACTUAL) ?? null))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 20000);
    return () => clearInterval(t);
  }, [cargar]);

  // Un solo criterio de estado para todo: el punto de cada tarjeta, el orden,
  // el filtro y los contadores salen de aqui. Un aula sin lectura de CO2 cuenta
  // como "sin sensores" aunque el backend diga otra cosa, porque la tarjeta la
  // va a mostrar con guion; si no, los contadores no sumarian el total.
  const estadoDe = useCallback(
    (a: AulaEstado): Estado => {
      const vivo = porAula[a.aula_id];
      if ((vivo?.co2_ppm ?? a.co2_ppm) === null) return "sin_datos";
      return vivo?.estado ?? a.estado;
    },
    [porAula],
  );

  const ordenadas = useMemo(
    () =>
      [...aulas].sort((a, b) => {
        const d = ORDEN_ESTADO[estadoDe(a)] - ORDEN_ESTADO[estadoDe(b)];
        return d !== 0 ? d : a.codigo.localeCompare(b.codigo);
      }),
    [aulas, estadoDe],
  );

  const visibles = useMemo(
    () => (filtro === "todas" ? ordenadas : ordenadas.filter((a) => estadoDe(a) === filtro)),
    [ordenadas, filtro, estadoDe],
  );

  const cuenta = useCallback(
    (e: Estado) => aulas.filter((a) => estadoDe(a) === e).length,
    [aulas, estadoDe],
  );

  const criticas = cuenta("critico");
  const alertas = cuenta("alerta");
  const normales = cuenta("ok");
  const sinDatos = cuenta("sin_datos");
  const atencion = criticas + alertas;
  // solo cuentan las que necesitan atencion: decir "ya las esta ventilando"
  // tiene que ser cierto para ESAS aulas, no para cualquiera
  const ventilandoAtencion = aulas.filter((a) => {
    const e = estadoDe(a);
    return (e === "critico" || e === "alerta") &&
      (porAula[a.aula_id]?.ventilacion_on ?? a.ventilacion_on);
  }).length;
  const conSensores = aulas.length - sinDatos;

  const resumen = (() => {
    if (cargando || conSensores === 0) return null;
    if (atencion > 0) {
      const detalle =
        ventilandoAtencion === atencion
          ? `El sistema ya ${atencion === 1 ? "la" : "las"} está ventilando solo.`
          : ventilandoAtencion > 0
            ? `El sistema ya ventila ${ventilandoAtencion} de ${atencion}; en el resto la ventilación está apagada.`
            : `La ventilación está apagada en ${atencion === 1 ? "ella" : "ellas"}: revisa si alguien la desactivó.`;
      // rojo si hay al menos una critica, ambar si solo hay alertas: el mismo
      // color que el punto de la tarjeta mas urgente del grid
      return {
        alerta: true,
        titulo: `${atencion} ${atencion === 1 ? "aula necesita" : "aulas necesitan"} atención`,
        detalle,
        clase: criticas > 0 ? "border-danger/40 bg-danger/5 text-danger" : "border-amber/40 bg-amber/5 text-amber",
      };
    }
    return {
      alerta: false,
      titulo: "Todas las aulas están en condiciones adecuadas",
      detalle: `${conSensores} ${conSensores === 1 ? "aula medida" : "aulas medidas"} por debajo de 1000 ppm de CO₂.`,
      clase: "border-sea/40 bg-sea/5 text-sea",
    };
  })();

  const chips: { id: Filtro; texto: string; n: number; clase: string }[] = [
    { id: "todas", texto: "todas", n: aulas.length, clase: "text-ink" },
    { id: "critico", texto: criticas === 1 ? "crítica" : "críticas", n: criticas, clase: "text-danger" },
    { id: "alerta", texto: "en alerta", n: alertas, clase: "text-amber" },
    { id: "ok", texto: normales === 1 ? "normal" : "normales", n: normales, clase: "text-sea" },
    { id: "sin_datos", texto: "sin sensores", n: sinDatos, clase: "text-slate-400" },
  ];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Panel general</p>
          <h1 className="mt-1 text-[26px] font-bold leading-tight tracking-tight">Estado de las aulas</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <span
            className={`pill ${
              conectado ? "border-sea/30 bg-sea/10 text-sea" : "border-slate-200 bg-slate-100 text-slate-500"
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full bg-current ${conectado ? "latido" : ""}`} />
            {conectado ? "Datos en vivo" : "Reconectando"}
          </span>
          {/* Sede fija: hoy el sistema opera en un solo colegio. No es un
              boton porque no hay nada que elegir; cuando haya mas sedes
              vuelve a ser un selector. */}
          <div className="flex items-center gap-2.5 rounded-xl border border-line bg-white py-1.5 pl-2 pr-3.5 shadow-card">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-teal/10 text-teal">
              <IconoSede />
            </span>
            <div className="leading-tight">
              <p className="text-[13px] font-semibold">{sede?.nombre ?? "Cargando sede…"}</p>
              <p className="text-[11px] text-muted">
                {sede?.distrito ? `${sede.distrito} · ` : ""}
                {aulas.length} {aulas.length === 1 ? "aula" : "aulas"}
              </p>
            </div>
          </div>
        </div>
      </header>

      {resumen && (
        <div className={`flex items-center gap-3.5 rounded-xl border p-4 ${resumen.clase}`}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white shadow-card">
            <IconoBanner alerta={resumen.alerta} />
          </span>
          <div>
            <p className="font-semibold text-ink">{resumen.titulo}</p>
            <p className="mt-0.5 text-sm text-muted">{resumen.detalle}</p>
          </div>
        </div>
      )}

      {/* Contadores que a la vez son filtros. Siempre suman el total porque
          cada aula cae en exactamente un estado (ver estadoDe). En movil
          desplazan en horizontal en vez de partir en dos filas. La leyenda
          "Como leer el CO2" se quito: el punto de color de cada tarjeta y el
          banner ya cuentan lo mismo sin ocupar una franja entera. */}
      <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
        {chips.map((c) => {
          const activo = filtro === c.id;
          return (
            <button
              key={c.id}
              onClick={() => setFiltro(c.id)}
              disabled={c.n === 0 && c.id !== "todas"}
              aria-pressed={activo}
              className={`flex min-h-[44px] min-w-[84px] shrink-0 flex-col items-start rounded-xl border px-3 py-2 text-left transition disabled:opacity-40 ${
                activo ? "border-deep bg-deep text-white shadow-card" : "border-line bg-white hover:border-teal/30 hover:bg-mist"
              }`}
            >
              <span className={`text-xl font-semibold leading-tight tabular-nums ${activo ? "text-white" : c.clase}`}>
                {c.n}
              </span>
              <span className={`text-xs ${activo ? "text-white/80" : "text-muted"}`}>{c.texto}</span>
            </button>
          );
        })}
      </div>

      {error && (
        <div className="card border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          <strong>No se pudo conectar con la API.</strong>
          <p className="mt-1 break-all font-mono text-xs">{error}</p>
        </div>
      )}

      {cargando ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="card h-[136px] animate-pulse bg-slate-50" />
          ))}
        </div>
      ) : visibles.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="font-medium">
            {aulas.length === 0 ? "No hay aulas registradas" : "Ninguna aula en esta categoria"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visibles.map((a) => (
            <AulaCard key={a.aula_id} base={a} vivo={porAula[a.aula_id]} estado={estadoDe(a)} />
          ))}
        </div>
      )}
    </div>
  );
}

function IconoSede() {
  return (
    <svg
      className="h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M3 21h18" />
      <path d="M5 21V9l7-5 7 5v12" />
      <path d="M10 21v-5h4v5" />
      <path d="M10 11h4" />
    </svg>
  );
}

// triangulo cuando hay algo que atender, check cuando todo esta bien: la forma
// distingue los dos casos aunque no se perciba bien el color
function IconoBanner({ alerta }: { alerta: boolean }) {
  return (
    <svg
      className="h-5 w-5 shrink-0"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {alerta ? (
        <>
          <path d="M10.3 3.9 2.4 17.6A2 2 0 0 0 4.1 20.6h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
          <path d="M12 9v4" />
          <path d="M12 17h.01" />
        </>
      ) : (
        <>
          <circle cx="12" cy="12" r="9" />
          <path d="m8 12.5 2.5 2.5L16 9.5" />
        </>
      )}
    </svg>
  );
}
