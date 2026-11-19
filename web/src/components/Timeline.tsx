'use client';

import { useEffect, useState } from 'react';
import {
  ETIQUETA_EVENTO, EXPLICACION_EVENTO, explicarMotivo, motivoLlano, textoActuacion,
} from '@/lib/formato';
import type { Actuacion, Evento } from '@/lib/tipos';

const COLOR_SEV: Record<string, string> = {
  info: 'bg-teal',
  alerta: 'bg-amber',
  critico: 'bg-danger',
};

// Un evento y la actuacion que dispara son el mismo hecho contado dos veces
// (el backend genera ambos en el mismo tick de evaluacion, con el mismo
// motivo). Se combinan en una sola entrada cuando ocurren dentro de esta
// ventana; fuera de ella se tratan como hechos independientes.
const VENTANA_MS = 5000;

type Grupo = {
  ts: string;
  evento?: Evento;
  actuacion?: Actuacion;
};

type GrupoColapsado = Grupo & { count: number; tsMin: string; tsMax: string };

function agrupar(eventos: Evento[], actuaciones: Actuacion[]): Grupo[] {
  const eventosLibres = [...eventos];
  const grupos: Grupo[] = [];

  for (const actuacion of actuaciones) {
    let mejorIdx = -1;
    let mejorDelta = Infinity;
    eventosLibres.forEach((ev, idx) => {
      const delta = Math.abs(+new Date(ev.ts) - +new Date(actuacion.ts));
      if (delta <= VENTANA_MS && delta < mejorDelta) {
        mejorDelta = delta;
        mejorIdx = idx;
      }
    });
    const evento = mejorIdx >= 0 ? eventosLibres.splice(mejorIdx, 1)[0] : undefined;
    grupos.push({ ts: actuacion.ts, actuacion, evento });
  }

  for (const evento of eventosLibres) {
    grupos.push({ ts: evento.ts, evento });
  }

  return grupos.sort((a, b) => +new Date(b.ts) - +new Date(a.ts));
}

/** Firma de "es el mismo hecho repetido": mismo actuador+accion+origen+motivo, o mismo tipo+mensaje de evento. */
function firmar(g: Grupo): string {
  if (g.actuacion) {
    return `act:${g.actuacion.actuador}:${g.actuacion.accion}:${g.actuacion.origen}:${g.actuacion.motivo}`;
  }
  return `evt:${g.evento!.tipo}:${g.evento!.mensaje}`;
}

// BUG 3: si el mismo hecho se repite muchas veces seguidas (p.ej. un
// reintento de comando, o una condicion que oscila justo en el umbral), el
// timeline se llena de filas identicas. Se colapsan las que son iguales y
// consecutivas (grupos ya vienen ordenados de mas reciente a mas antiguo) en
// una sola entrada con un contador y el rango horario que cubre.
function colapsar(grupos: Grupo[]): GrupoColapsado[] {
  const resultado: GrupoColapsado[] = [];
  for (const g of grupos) {
    const anterior = resultado.at(-1);
    if (anterior && firmar(anterior) === firmar(g)) {
      anterior.count += 1;
      anterior.tsMin = g.ts; // vamos retrocediendo en el tiempo
    } else {
      resultado.push({ ...g, count: 1, tsMin: g.ts, tsMax: g.ts });
    }
  }
  return resultado;
}

type Modo = 'compacto' | 'detallado';
const CLAVE_MODO = 'sc:timeline-modo';

// localStorage puede no existir o tirar (modo privado, sitio bloqueado): la
// preferencia es una comodidad, nunca debe romper la pantalla.
function leerModo(): Modo {
  try {
    return localStorage.getItem(CLAVE_MODO) === 'detallado' ? 'detallado' : 'compacto';
  } catch {
    return 'compacto';
  }
}

// HH:MM en 24 h: hora() de formato.ts sale "07:30 p. m." en es-PE, que no
// cabe en la columna fija de 38px y obliga a leer dos cosas para una hora.
const hora = (iso: string) =>
  new Date(iso).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });

const diaClave =(iso: string) => new Date(iso).toDateString();

// Encabezado del grupo: "hoy", "ayer" o "11 de octubre". Asi la hora de cada
// fila no tiene que repetir la fecha.
function etiquetaDia(iso: string): string {
  const d = new Date(iso);
  const hoy = new Date();
  const ayer = new Date(hoy);
  ayer.setDate(hoy.getDate() - 1);
  if (d.toDateString() === hoy.toDateString()) return 'hoy';
  if (d.toDateString() === ayer.toDateString()) return 'ayer';
  return d.toLocaleDateString('es-PE', { day: 'numeric', month: 'long' });
}

function textos(g: GrupoColapsado) {
  // titulo: si hubo actuacion es el hecho relevante (que hizo el sistema); si
  // no, el tipo de evento traducido. Un tipo desconocido NO cae al `mensaje`
  // crudo (trae ppm): se dice algo generico y el crudo va al dato tecnico.
  const titulo = g.actuacion
    ? textoActuacion(g.actuacion.actuador, g.actuacion.accion, g.actuacion.origen)
    : ETIQUETA_EVENTO[g.evento!.tipo] ?? 'El sistema registró un aviso';

  const explicacion = g.actuacion
    ? motivoLlano(g.actuacion.motivo)
    : EXPLICACION_EVENTO[g.evento!.tipo] ?? '';

  // si se repitio, el rango horario va en el desplegable: en la fila solo
  // cabe la hora mas reciente
  const repeticion =
    g.count > 1 ? `Pasó ${g.count} veces, entre las ${hora(g.tsMin)} y las ${hora(g.tsMax)}` : '';

  // capa tecnica: la traduccion con numeros (explicarMotivo) y los strings
  // crudos tal cual los guardo el backend, que son la evidencia auditable
  const tecnico: string[] = [];
  if (g.actuacion) {
    const conNumeros = explicarMotivo(g.actuacion.motivo);
    if (conNumeros !== g.actuacion.motivo) tecnico.push(conNumeros);
    tecnico.push(`motivo: ${g.actuacion.motivo}`);
    tecnico.push(`actuacion: ${g.actuacion.actuador}→${g.actuacion.accion} (${g.actuacion.origen})`);
  }
  if (g.evento) tecnico.push(`evento: ${g.evento.tipo} · "${g.evento.mensaje}"`);

  return { titulo, explicacion, repeticion, tecnico };
}

/** Historial combinado de lo que el sistema DETECTO y de lo que DECIDIO. */
export default function Timeline({
  eventos,
  actuaciones,
  limite = 18,
  onHover,
}: {
  eventos: Evento[];
  actuaciones: Actuacion[];
  limite?: number;
  /** Notifica el ts del hecho bajo el mouse (o null al salir), para resaltarlo en el grafico. */
  onHover?: (ts: string | null) => void;
}) {
  const grupos = colapsar(agrupar(eventos, actuaciones)).slice(0, limite);

  const [modo, setModo] = useState<Modo>('compacto');
  // Un solo evento abierto a la vez en modo compacto: ese modo existe para ver
  // el conjunto de un vistazo, y si se pudieran abrir varios la lista volveria
  // a crecer hasta lo que habia antes. Para ver todo abierto esta "detallado".
  const [abierto, setAbierto] = useState<string | null>(null);

  // se lee tras montar: el servidor no conoce localStorage y renderizaria
  // otro modo, con un salto visible al hidratar
  useEffect(() => setModo(leerModo()), []);

  const cambiarModo = (m: Modo) => {
    setModo(m);
    setAbierto(null);
    try {
      localStorage.setItem(CLAVE_MODO, m);
    } catch {
      /* sin persistencia: el modo vale solo para esta visita */
    }
  };

  // filas agrupadas por dia, conservando el orden (mas reciente primero)
  const dias: { clave: string; etiqueta: string; filas: GrupoColapsado[] }[] = [];
  for (const g of grupos) {
    const clave = diaClave(g.tsMax);
    const ult = dias.at(-1);
    if (ult?.clave === clave) ult.filas.push(g);
    else dias.push({ clave, etiqueta: etiquetaDia(g.tsMax), filas: [g] });
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Qué fue pasando</h3>
        <div className="flex shrink-0 gap-0.5 rounded-md bg-mist p-0.5" role="radiogroup" aria-label="Vista">
          {(['compacto', 'detallado'] as const).map((m) => (
            <button
              key={m}
              role="radio"
              aria-checked={modo === m}
              onClick={() => cambiarModo(m)}
              className={`flex min-h-[36px] items-center rounded px-2.5 text-xs capitalize transition sm:min-h-0 sm:py-1 ${
                modo === m ? 'bg-white font-semibold text-ink shadow-card' : 'text-muted hover:text-ink'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {grupos.length === 0 && <p className="py-8 text-center text-sm text-muted">Sin actividad registrada</p>}

      {dias.map((d) => (
        <section key={d.clave} className="mt-3 first:mt-0">
          <h4 className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">{d.etiqueta}</h4>
          <ol>
            {d.filas.map((g) => {
              const clave = `${firmar(g)}-${g.tsMax}`;
              const t = textos(g);
              const expandido = modo === 'detallado' || abierto === clave;
              const color = g.actuacion ? 'bg-deep' : COLOR_SEV[g.evento?.severidad ?? ''] ?? 'bg-slate-400';
              return (
                <li
                  key={clave}
                  // separador fino en lugar de la linea vertical: con filas de
                  // una linea, la linea vertical ya no ordena nada
                  className="entra border-t-[0.5px] border-line first:border-t-0"
                  onMouseEnter={() => onHover?.(g.ts)}
                  onMouseLeave={() => onHover?.(null)}
                >
                  <button
                    onClick={() => setAbierto(expandido ? null : clave)}
                    aria-expanded={expandido}
                    disabled={modo === 'detallado'}
                    // en movil el texto envuelve en vez de cortarse: la fila
                    // crece una linea, pero nunca se pierde que paso
                    className="flex min-h-[36px] w-full items-center gap-2.5 rounded-md px-1 py-1.5 text-left transition hover:bg-mist disabled:cursor-default disabled:hover:bg-transparent"
                  >
                    <span className="w-[38px] shrink-0 text-xs tabular-nums text-muted">{hora(g.tsMax)}</span>
                    <span className={`h-2 w-2 shrink-0 rounded-full ${color}`} />
                    <span className="min-w-0 flex-1 text-sm leading-snug">
                      {t.titulo}
                      {g.count > 1 && (
                        <span className="ml-1.5 whitespace-nowrap rounded bg-slate-200 px-1.5 py-0.5 align-middle text-[10px] font-semibold text-muted">
                          ×{g.count}
                        </span>
                      )}
                    </span>
                    {modo === 'compacto' && (
                      <svg
                        className={`h-4 w-4 shrink-0 text-muted transition-transform ${expandido ? 'rotate-180' : ''}`}
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
                        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
                      >
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    )}
                  </button>

                  {/* indentado bajo el texto: px-1 (4) + hora (38) + gap (10) + punto (8) + gap (10) */}
                  {expandido && (
                    <div className="pb-2 pl-[70px] pr-1">
                      {t.explicacion && <p className="text-xs text-ink/80">{t.explicacion}</p>}
                      {t.repeticion && <p className="text-xs text-muted">{t.repeticion}</p>}
                      {/* segunda capa: el dato tecnico sigue plegado aun en
                          modo detallado, porque solo le sirve a quien audita */}
                      <details className="mt-0.5">
                        <summary className="cursor-pointer text-[11px] text-muted/70 hover:text-muted">
                          Ver dato técnico
                        </summary>
                        <ul className="mt-0.5 space-y-0.5">
                          {t.tecnico.map((x) => (
                            <li key={x} className="break-all font-mono text-[11px] text-muted">
                              {x}
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
