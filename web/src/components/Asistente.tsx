'use client';

import { Fragment, useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type { MensajeAsistente } from '@/lib/tipos';

const SUGERENCIAS = [
  '¿Qué aula tiene peor aire ahora?',
  '¿Por qué el aula 303 siempre está mal?',
  '¿Cumplimos la Norma A.040 esta semana?',
  '¿Qué hizo el sistema en la última hora?',
];

const CLAVE = 'sc-asistente-conversacion';

/** Negritas (**x**) y listas simples; el resto como texto plano. */
function Texto({ texto }: { texto: string }) {
  const lineas = texto.split('\n');
  return (
    <>
      {lineas.map((l, i) => {
        const vineta = /^\s*[-*•]\s+/.test(l);
        const contenido = l.replace(/^\s*[-*•]\s+/, '').replace(/^#+\s*/, '');
        const partes = contenido.split(/(\*\*[^*]+\*\*)/g).map((p, j) =>
          p.startsWith('**') && p.endsWith('**') ? (
            <strong key={j} className="font-semibold">{p.slice(2, -2)}</strong>
          ) : (
            <Fragment key={j}>{p}</Fragment>
          ),
        );
        if (!contenido.trim()) return <div key={i} className="h-2" />;
        return vineta ? (
          <div key={i} className="flex gap-2 pl-1">
            <span className="text-teal">•</span>
            <span>{partes}</span>
          </div>
        ) : (
          <p key={i}>{partes}</p>
        );
      })}
    </>
  );
}

function IconoChat({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" />
      <path d="M8.5 11h.01M12 11h.01M15.5 11h.01" strokeWidth={2.6} />
    </svg>
  );
}

export default function Asistente() {
  const [abierto, setAbierto] = useState(false);
  const [mensajes, setMensajes] = useState<MensajeAsistente[]>([]);
  const [texto, setTexto] = useState('');
  const [pensando, setPensando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [configurado, setConfigurado] = useState<boolean | null>(null);
  const finRef = useRef<HTMLDivElement>(null);
  const entradaRef = useRef<HTMLTextAreaElement>(null);

  // conversacion de la pestaña: sobrevive a cambiar de pagina, no se comparte
  useEffect(() => {
    try {
      const g = sessionStorage.getItem(CLAVE);
      if (g) setMensajes(JSON.parse(g));
    } catch {}
  }, []);
  useEffect(() => {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(mensajes));
    } catch {}
  }, [mensajes]);

  useEffect(() => {
    if (!abierto || configurado !== null) return;
    api.asistenteEstado()
      .then((e) => setConfigurado(e.configurado))
      .catch(() => setConfigurado(null));
  }, [abierto, configurado]);

  useEffect(() => {
    if (abierto) {
      finRef.current?.scrollIntoView({ behavior: 'smooth' });
      entradaRef.current?.focus();
    }
  }, [abierto, mensajes, pensando]);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false);
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, []);

  const enviar = async (pregunta: string) => {
    const q = pregunta.trim();
    if (!q || pensando) return;
    const nuevos: MensajeAsistente[] = [...mensajes, { rol: 'usuario', texto: q }];
    setMensajes(nuevos);
    setTexto('');
    setError(null);
    setPensando(true);
    try {
      const r = await api.asistente(nuevos);
      setMensajes([...nuevos, { rol: 'asistente', texto: r.respuesta }]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      const detalle = msg.match(/"detail":"([^"]+)"/)?.[1];
      setError(detalle ?? 'No se pudo contactar al asistente.');
      if (msg.startsWith('503')) setConfigurado(false);
    } finally {
      setPensando(false);
    }
  };

  return (
    <>
      {abierto && (
        <section
          role="dialog"
          aria-label="Asistente de calidad del aire"
          className="fixed bottom-36 right-4 z-40 flex h-[min(560px,calc(100vh-11rem))] w-[calc(100vw-2rem)] max-w-sm flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-lift md:bottom-24 md:right-6"
        >
          <header className="flex items-center gap-3 bg-deep px-4 py-3 text-white">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-sea/90">
              <IconoChat className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold leading-tight">Asistente del aire</p>
              <p className="text-xs text-white/70">Consulta los datos de las aulas · solo lectura</p>
            </div>
            {mensajes.length > 0 && (
              <button
                onClick={() => { setMensajes([]); setError(null); }}
                className="rounded-md px-2 py-1 text-xs text-white/80 hover:bg-white/10"
              >
                Nueva
              </button>
            )}
            <button
              onClick={() => setAbierto(false)}
              aria-label="Cerrar asistente"
              className="rounded-md p-1 text-white/80 hover:bg-white/10"
            >
              <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
              </svg>
            </button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-page px-4 py-4 text-sm text-ink">
            {configurado === false && (
              <div className="rounded-xl border border-amber/40 bg-amber/10 p-3 text-xs leading-relaxed">
                <p className="font-semibold">El asistente no está configurado</p>
                <p className="mt-1 text-muted">
                  Agrega <code className="font-mono">ANTHROPIC_API_KEY</code> en el archivo{' '}
                  <code className="font-mono">.env</code> y reinicia la API con{' '}
                  <code className="font-mono">docker compose up -d api</code>.
                </p>
              </div>
            )}

            {mensajes.length === 0 && (
              <div className="space-y-3">
                <p className="leading-relaxed text-muted">
                  Hola. Puedo revisar el estado de las aulas, explicar por qué el sistema prendió la
                  ventilación o las luces, y resumir el cumplimiento de la norma.
                </p>
                <div className="flex flex-col gap-2">
                  {SUGERENCIAS.map((s) => (
                    <button
                      key={s}
                      onClick={() => enviar(s)}
                      disabled={configurado === false}
                      className="rounded-xl border border-line bg-white px-3 py-2 text-left text-ink transition hover:border-teal hover:text-teal disabled:opacity-50"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((m, i) =>
              m.rol === 'usuario' ? (
                <div key={i} className="flex justify-end">
                  <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-teal px-3 py-2 text-white">
                    {m.texto}
                  </p>
                </div>
              ) : (
                <div key={i} className="flex">
                  <div className="max-w-[90%] space-y-1 rounded-2xl rounded-bl-md border border-line bg-white px-3 py-2 leading-relaxed shadow-card">
                    <Texto texto={m.texto} />
                  </div>
                </div>
              ),
            )}

            {pensando && (
              <div className="flex">
                <div className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-line bg-white px-3 py-3 shadow-card">
                  {[0, 1, 2].map((d) => (
                    <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal"
                      style={{ animationDelay: `${d * 150}ms` }} />
                  ))}
                  <span className="ml-2 text-xs text-muted">Consultando los datos…</span>
                </div>
              </div>
            )}

            {error && configurado !== false && (
              <p className="rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-xs text-danger">
                {error}
              </p>
            )}
            <div ref={finRef} />
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); enviar(texto); }}
            className="flex items-end gap-2 border-t border-line bg-white p-3"
          >
            <textarea
              ref={entradaRef}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(texto); }
              }}
              rows={1}
              maxLength={2000}
              placeholder="Escribe tu pregunta…"
              disabled={configurado === false}
              className="max-h-28 min-h-[40px] flex-1 resize-none rounded-xl border border-line px-3 py-2 text-sm text-ink outline-none focus:border-teal disabled:bg-mist"
            />
            <button
              type="submit"
              disabled={!texto.trim() || pensando || configurado === false}
              aria-label="Enviar"
              className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-teal text-white transition hover:bg-deep disabled:opacity-40"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2.2}>
                <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </form>
        </section>
      )}

      <button
        onClick={() => setAbierto((v) => !v)}
        aria-label={abierto ? 'Cerrar asistente' : 'Abrir asistente'}
        aria-expanded={abierto}
        className="fixed bottom-20 right-4 z-40 grid h-14 w-14 place-items-center rounded-full bg-teal text-white shadow-lift transition hover:scale-105 hover:bg-deep md:bottom-6 md:right-6"
      >
        {abierto ? (
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : (
          <IconoChat className="h-6 w-6" />
        )}
      </button>
    </>
  );
}
