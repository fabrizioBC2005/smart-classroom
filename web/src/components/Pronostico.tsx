'use client';

import Ayuda from '@/components/Ayuda';
import { UMBRAL_ALERTA, ZONAS_AIRE, zonaAire } from '@/lib/formato';
import type { PronosticoAhora, PronosticoAula } from '@/lib/tipos';

// Lo que el sistema espera del aire en los proximos minutos. Va en el panel
// izquierdo del aula, asi que habla como el resto de ese panel: zonas en
// palabras ("cargado"), sin ppm ni porcentajes. Esta "en prueba": solo
// avisa, la ventilacion la sigue manejando el sistema de siempre.
export default function Pronostico({
  datos,
  vivo,
  co2,
  ventilando,
}: {
  datos: PronosticoAula | null;
  vivo?: PronosticoAhora | null;
  co2: number | null;
  ventilando: boolean;
}) {
  const ahora = vivo ?? datos?.ahora ?? null;
  const minutos = Math.round(ahora?.minutos_adelante ?? 10);

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-1.5 text-sm font-semibold">
            Pronóstico del aire
            <Ayuda texto="El sistema aprendió de lo que pasó antes en las aulas: cuánta gente había, si estaba ventilando y cómo venía subiendo el aire. Con eso adivina cómo va a estar el aire dentro de un rato." />
          </h3>
          <p className="text-xs text-muted">dentro de {minutos} minutos</p>
        </div>
        <span className="pill shrink-0 whitespace-nowrap border-teal/25 bg-teal/5 text-teal">En prueba</span>
      </div>

      {datos === null ? (
        <p className="mt-3 text-sm text-muted">Cargando…</p>
      ) : datos.aprendiendo ? (
        <p className="mt-3 text-sm text-muted">
          Todavía estamos aprendiendo cómo se comporta el aire de esta aula. Cuando haya
          suficientes datos, aquí vas a ver qué esperar.
        </p>
      ) : !ahora || co2 === null ? (
        <p className="mt-3 text-sm text-muted">Juntando las primeras lecturas de esta aula…</p>
      ) : (
        <Prevision co2={co2} previsto={ahora.co2_previsto} ventilando={ventilando} />
      )}

      {datos?.revision && datos.revision.revisados >= 5 && (
        <Aciertos {...datos.revision} />
      )}

      <p className="mt-3 text-[11px] leading-snug text-muted">
        Por ahora solo avisa: no enciende ni apaga la ventilación.
      </p>
    </div>
  );
}

function Prevision({ co2, previsto, ventilando }: { co2: number; previsto: number; ventilando: boolean }) {
  const zonaAhora = zonaAire(co2);
  const zonaLuego = zonaAire(previsto);
  const posAhora = ZONAS_AIRE.indexOf(zonaAhora);
  const posLuego = ZONAS_AIRE.indexOf(zonaLuego);

  // un consejo solo cuando hace falta que alguien haga algo
  let consejo: string | null = null;
  if (previsto >= UMBRAL_ALERTA && co2 < UMBRAL_ALERTA) {
    consejo = ventilando
      ? 'La ventilación ya está encendida.'
      : 'Conviene abrir ventanas o encender la ventilación ya.';
  }

  const cambio =
    posLuego > posAhora
      ? `Va a empeorar: ahora está ${zonaAhora.nombre}.`
      : posLuego < posAhora
        ? `Va a mejorar: ahora está ${zonaAhora.nombre}.`
        : 'Se va a mantener como está ahora.';

  return (
    <div className="mt-3">
      <p className="text-sm text-muted">El aire va a estar</p>
      <p className="mt-0.5 text-2xl font-semibold tracking-tight" style={{ color: zonaLuego.colorTexto }}>
        {zonaLuego.nombre}
      </p>
      <p className="mt-1.5 flex items-center gap-1.5 text-sm">
        <Flecha sube={posLuego > posAhora} baja={posLuego < posAhora} />
        {cambio}
      </p>
      {consejo && (
        <p className="mt-3 rounded-lg bg-amber/10 px-3 py-2 text-sm font-medium text-amber">{consejo}</p>
      )}
    </div>
  );
}

function Aciertos({ horas, revisados, acerto, acerto_linea_recta }: NonNullable<PronosticoAula['revision']>) {
  const deCada10 = (n: number) => Math.round((n / revisados) * 10);
  const nuevo = deCada10(acerto);
  const antes = deCada10(acerto_linea_recta);
  return (
    <div className="mt-4 rounded-lg bg-mist px-3 py-2.5">
      <p className="text-xs text-muted">¿Qué tan bien viene adivinando? (últimas {horas} horas)</p>
      <div className="mt-2 space-y-1.5">
        <BarraAcierto texto="Este pronóstico" valor={nuevo} destacado />
        <BarraAcierto texto="Cálculo de hoy" valor={antes} />
      </div>
      <p className="mt-2 text-[11px] text-muted">Aciertos de cada 10 veces, comparando con lo que de verdad pasó.</p>
    </div>
  );
}

function BarraAcierto({ texto, valor, destacado = false }: { texto: string; valor: number; destacado?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`w-[104px] shrink-0 ${destacado ? 'font-medium text-ink' : 'text-muted'}`}>{texto}</span>
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-white">
        <span
          className={`block h-full rounded-full ${destacado ? 'bg-teal' : 'bg-slate-300'}`}
          style={{ width: `${valor * 10}%` }}
        />
      </span>
      <span className={`w-8 text-right tabular-nums ${destacado ? 'font-semibold text-ink' : 'text-muted'}`}>
        {valor}/10
      </span>
    </div>
  );
}

function Flecha({ sube, baja }: { sube: boolean; baja: boolean }) {
  const color = sube ? 'text-amber' : baja ? 'text-sea' : 'text-muted';
  return (
    <svg className={`h-4 w-4 shrink-0 ${color}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {sube ? <path d="M7 17 17 7M9 7h8v8" /> : baja ? <path d="M7 7l10 10M17 9v8H9" /> : <path d="M5 12h14" />}
    </svg>
  );
}
