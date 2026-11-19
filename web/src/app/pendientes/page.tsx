'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { explicarMotivo, hora, textoActuacion } from '@/lib/formato';
import type { Actuacion, AulaEstado, Pendiente, Pendientes } from '@/lib/tipos';

// La pantalla principal responde "¿como estan las aulas?". Esta responde
// "¿que tengo que hacer yo?": solo lo que el sistema no puede resolver solo.
// Lo que ya resolvio (ventilar, prender luces) no se lista: se cuenta abajo.

const REFRESCO_MS = 30_000;

const ESTILO: Record<Pendiente['prioridad'], { borde: string; pill: string; texto: string }> = {
  alta: { borde: 'border-danger/40', pill: 'border-danger/30 bg-danger/10 text-danger', texto: 'Urgente' },
  media: { borde: 'border-amber/40', pill: 'border-amber/30 bg-amber/10 text-amber', texto: 'Importante' },
  baja: { borde: 'border-line', pill: 'border-line bg-mist text-muted', texto: 'Para planificar' },
};

function IconoTipo({ tipo }: { tipo: Pendiente['tipo'] }) {
  const comun = {
    className: 'h-5 w-5', viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true,
  };
  switch (tipo) {
    case 'sin_senal':
      return (
        <svg {...comun}>
          <path d="M2 8.8a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0" />
          <path d="M12 20h.01M3 3l18 18" />
        </svg>
      );
    case 'no_alcanza':
      return (
        <svg {...comun}>
          <path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h7" />
        </svg>
      );
    case 'ventila_mal':
      return (
        <svg {...comun}>
          <path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.8-.7-.7-2.8z" />
        </svg>
      );
    case 'manual':
      return (
        <svg {...comun}>
          <path d="M18 11V6a2 2 0 0 0-4 0M14 10V4a2 2 0 0 0-4 0v2M10 10.5V6a2 2 0 0 0-4 0v8" />
          <path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.4l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15" />
        </svg>
      );
    default:
      return (
        <svg {...comun}>
          <path d="M14 14.8V4a2 2 0 0 0-4 0v10.8a4 4 0 1 0 4 0Z" />
        </svg>
      );
  }
}

export default function Page() {
  const [datos, setDatos] = useState<Pendientes | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [verAcciones, setVerAcciones] = useState(false);
  const [acciones, setAcciones] = useState<Actuacion[]>([]);
  const [aulas, setAulas] = useState<AulaEstado[]>([]);

  const cargar = useCallback(async () => {
    try {
      setDatos(await api.pendientes());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudieron cargar los pendientes');
    }
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, REFRESCO_MS);
    return () => clearInterval(t);
  }, [cargar]);

  useEffect(() => {
    if (!verAcciones) return;
    Promise.all([api.actuaciones(undefined, 100), api.estado()])
      .then(([ac, es]) => {
        setAcciones(ac.filter((a) => a.origen === 'automatico').slice(0, 10));
        setAulas(es);
      })
      .catch(() => undefined);
  }, [verAcciones]);

  const resolver = async (p: Pendiente) => {
    setOcupado(p.clave);
    try {
      if (p.boton?.tipo === 'volver_automatico') {
        await api.modo(p.aula_id, p.boton.actuador, 'automatico');
      } else {
        await api.resolverPendiente(p.clave);
      }
      await cargar();
      window.dispatchEvent(new Event('pendientes-cambiaron'));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo guardar');
    } finally {
      setOcupado(null);
    }
  };

  const lista = datos?.pendientes ?? [];
  const codigo = (id: number) => aulas.find((a) => a.aula_id === id)?.codigo ?? id;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Pendientes</h1>
        <p className="mt-1 text-sm text-muted">
          Lo que necesita a una persona. Lo que el sistema puede resolver solo, ya lo resolvió.
        </p>
      </div>

      {error && (
        <p className="rounded-xl border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">{error}</p>
      )}

      {datos === null && !error && (
        <div className="card p-6 text-sm text-muted">Revisando las aulas…</div>
      )}

      {datos && lista.length === 0 && (
        <div className="card flex items-center gap-4 border-sea/30 bg-sea/5 p-5">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white text-sea">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.2}>
              <path d="M5 12.5 10 17.5 19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <div>
            <p className="font-semibold">Todo en orden</p>
            <p className="text-sm text-muted">No hay nada que requiera tu atención ahora.</p>
          </div>
        </div>
      )}

      <ul className="space-y-3">
        {lista.map((p) => {
          const e = ESTILO[p.prioridad];
          return (
            <li key={p.clave} className={`card border p-4 ${e.borde}`}>
              <div className="flex gap-3">
                <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-mist text-deep">
                  <IconoTipo tipo={p.tipo} />
                </span>
                <div className="min-w-0 flex-1">
                  {/* sin "hace X": el detalle ya dice cuanto tiempo lleva, en tiempo del aula */}
                  <span className={`pill ${e.pill}`}>{e.texto}</span>
                  <h2 className="mt-1.5 font-semibold leading-snug">{p.titulo}</h2>
                  <p className="mt-1 text-sm text-muted">{p.detalle}</p>
                  <p className="mt-2 text-sm">
                    <span className="font-medium">Qué hacer:</span> {p.accion}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => resolver(p)}
                      disabled={ocupado === p.clave}
                      className="rounded-lg bg-deep px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-teal disabled:opacity-50"
                    >
                      {ocupado === p.clave
                        ? 'Guardando…'
                        : p.boton?.tipo === 'volver_automatico'
                          ? 'Volver a automático'
                          : 'Ya lo resolví'}
                    </button>
                    <Link
                      href={`/aula/${p.aula_id}`}
                      className="rounded-lg px-3 py-1.5 text-xs font-medium text-teal hover:bg-mist"
                    >
                      Ver aula {p.codigo} →
                    </Link>
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      {datos && datos.ocultos > 0 && (
        <p className="text-xs text-muted">
          {datos.ocultos} {datos.ocultos === 1 ? 'pendiente marcado' : 'pendientes marcados'} como
          resuelto: vuelve a aparecer mañana si el problema sigue.
        </p>
      )}

      {datos && (
        <div className="card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm">
              <span className="font-semibold">En las últimas 24 h el sistema actuó solo{' '}
                {datos.resumen.acciones_automaticas_24h.toLocaleString('es-PE')} veces</span>
              <span className="text-muted"> ante {datos.resumen.alertas_24h.toLocaleString('es-PE')} subidas del CO₂.</span>
            </p>
            <button
              onClick={() => setVerAcciones((v) => !v)}
              className="text-xs font-medium text-teal hover:underline"
            >
              {verAcciones ? 'Ocultar detalle' : 'Ver detalle'}
            </button>
          </div>
          {verAcciones && (
            <ul className="mt-3 divide-y divide-line text-sm">
              {acciones.length === 0 && <li className="py-2 text-muted">Cargando…</li>}
              {acciones.map((a) => (
                <li key={a.id} className="flex gap-3 py-2">
                  <span className="w-[4.75rem] shrink-0 whitespace-nowrap pt-0.5 text-xs tabular-nums text-muted">{hora(a.ts)}</span>
                  <span className="min-w-0">
                    <span className="font-medium">Aula {codigo(a.aula_id)}:</span>{' '}
                    {textoActuacion(a.actuador, a.accion, a.origen)}
                    <span className="block text-xs text-muted">{explicarMotivo(a.motivo)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
