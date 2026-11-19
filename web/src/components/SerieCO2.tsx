'use client';

import { useEffect, useState } from 'react';
import {
  Area, AreaChart, CartesianGrid, ReferenceDot, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { hora } from '@/lib/formato';
import type { Lectura } from '@/lib/tipos';

/**
 * Detecta viewport angosto para ajustar el grafico (altura, ticks, labels).
 * Recharts necesita valores JS, no clases de Tailwind, para estas props.
 */
function useEsMovil() {
  const [esMovil, setEsMovil] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 639px)');
    setEsMovil(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setEsMovil(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return esMovil;
}

/**
 * Curva de CO2 con las bandas de umbral marcadas.
 * Este grafico es el que hace visible el fenomeno: el patron en dientes
 * de sierra de acumulacion durante la clase y decaimiento en el recreo.
 */
export default function SerieCO2({
  datos,
  umbralAlerta = 1000,
  umbralCritico = 1400,
  resaltadoTs = null,
}: {
  datos: Lectura[];
  umbralAlerta?: number;
  umbralCritico?: number;
  /** ts (ISO) de la entrada del timeline sobre la que esta el mouse, para marcar el punto mas cercano. */
  resaltadoTs?: string | null;
}) {
  const esMovil = useEsMovil();
  const serie = datos
    .filter((d) => d.co2_ppm !== null)
    .map((d) => ({
      t: hora(d.ts),
      ts: d.ts,
      co2: d.co2_ppm as number,
      ocup: d.ocupantes_conteo ?? d.ocupantes_estimado ?? null,
    }));

  if (serie.length === 0) {
    return (
      <div className="grid h-56 place-items-center text-sm text-muted sm:h-72">
        Sin lecturas en el periodo
      </div>
    );
  }

  const max = Math.max(...serie.map((s) => s.co2), umbralCritico + 200);

  // Punto de la curva mas cercano en el tiempo a la entrada del timeline que
  // se esta hovereando. Si el mas cercano queda a mas de 15 min (el evento
  // cayo fuera del rango de horas que se esta viendo), no se marca nada.
  let puntoResaltado: { t: string; co2: number } | null = null;
  if (resaltadoTs) {
    let mejorDelta = Infinity;
    for (const p of serie) {
      const delta = Math.abs(+new Date(p.ts) - +new Date(resaltadoTs));
      if (delta < mejorDelta) {
        mejorDelta = delta;
        puntoResaltado = { t: p.t, co2: p.co2 };
      }
    }
    if (mejorDelta > 15 * 60 * 1000) puntoResaltado = null;
  }

  return (
    // altura fija en JS: ResponsiveContainer no acepta clases de Tailwind para la altura
    <ResponsiveContainer width="100%" height={esMovil ? 220 : 300}>
      {/* margen derecho amplio: sin espacio las etiquetas "alerta 1000" /
          "critico 1400" de las ReferenceLine quedan cortadas */}
      <AreaChart data={serie} margin={{ top: 10, right: esMovil ? 54 : 66, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gco2" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#028090" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#028090" stopOpacity={0.02} />
          </linearGradient>
        </defs>

        <CartesianGrid strokeDasharray="3 3" stroke="#E2ECED" vertical={false} />
        {/* mas minTickGap en movil para que las etiquetas del eje X no se amontonen */}
        <XAxis dataKey="t" tick={{ fontSize: 11, fill: '#5C7178' }} minTickGap={esMovil ? 60 : 40} />
        <YAxis
          domain={[350, Math.ceil(max / 200) * 200]}
          tick={{ fontSize: 11, fill: '#5C7178' }}
          width={esMovil ? 36 : 48}
          label={
            esMovil
              ? undefined
              : { value: 'ppm', angle: -90, position: 'insideLeft', fontSize: 11, fill: '#5C7178' }
          }
        />
        <Tooltip
          contentStyle={{ borderRadius: 10, border: '1px solid #DDE7E8', fontSize: 12 }}
          formatter={(v: number) => [`${Math.round(v)} ppm`, 'CO₂']}
        />

        <ReferenceLine
          y={umbralAlerta}
          stroke="#D98324"
          strokeDasharray="5 4"
          label={{ value: `alerta ${umbralAlerta}`, fontSize: 10, fill: '#D98324', position: 'right' }}
        />
        <ReferenceLine
          y={umbralCritico}
          stroke="#C0392B"
          strokeDasharray="5 4"
          label={{ value: `crítico ${umbralCritico}`, fontSize: 10, fill: '#C0392B', position: 'right' }}
        />

        <Area type="monotone" dataKey="co2" stroke="#028090" strokeWidth={2} fill="url(#gco2)" />

        {puntoResaltado && (
          <ReferenceDot
            x={puntoResaltado.t}
            y={puntoResaltado.co2}
            r={7}
            fill="#028090"
            stroke="#fff"
            strokeWidth={2}
            isFront
          />
        )}
      </AreaChart>
    </ResponsiveContainer>
  );
}
