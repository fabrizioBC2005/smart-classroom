'use client';

import { useEffect, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { hora } from '@/lib/formato';
import type { Lectura } from '@/lib/tipos';

// mismos umbrales que el backend (app/config.py): sobre 26 °C el sistema
// ventila si hay gente; sobre 70 % genera alerta de humedad
const TEMP_ALERTA = 26;
const HUM_ALERTA = 70;

export const COLOR_TEMP = '#D98324';
export const COLOR_HUM = '#028090';

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
 * Temperatura (eje izquierdo, °C) y humedad (eje derecho, %) en el mismo
 * rango de horas que la curva de CO2, para leerlas una debajo de la otra:
 * cuando el aula se llena sube todo junto, y al ventilar baja todo junto.
 */
export default function SerieClima({ datos }: { datos: Lectura[] }) {
  const esMovil = useEsMovil();
  const serie = datos
    .filter((d) => d.temp_c !== null || d.hum_pct !== null)
    .map((d) => ({ t: hora(d.ts), temp: d.temp_c, hum: d.hum_pct }));

  if (serie.length === 0) {
    return (
      <div className="grid h-44 place-items-center text-sm text-muted sm:h-56">
        Sin lecturas de temperatura ni humedad en el periodo
      </div>
    );
  }

  const temps = serie.map((s) => s.temp).filter((v): v is number => v !== null);
  const hums = serie.map((s) => s.hum).filter((v): v is number => v !== null);
  // el eje incluye siempre el umbral, para que la linea de referencia se vea
  const tMin = Math.floor(Math.min(...temps, 20) - 1);
  const tMax = Math.ceil(Math.max(...temps, TEMP_ALERTA) + 1);
  const hMin = Math.max(0, Math.floor((Math.min(...hums, 40) - 5) / 10) * 10);
  const hMax = Math.min(100, Math.ceil((Math.max(...hums, HUM_ALERTA) + 5) / 10) * 10);

  return (
    <ResponsiveContainer width="100%" height={esMovil ? 200 : 240}>
      <LineChart data={serie} margin={{ top: 10, right: 4, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E2ECED" vertical={false} />
        <XAxis dataKey="t" tick={{ fontSize: 11, fill: '#5C7178' }} minTickGap={esMovil ? 60 : 40} />
        <YAxis
          yAxisId="temp"
          domain={[tMin, tMax]}
          allowDecimals={false}
          tick={{ fontSize: 11, fill: COLOR_TEMP }}
          tickFormatter={(v: number) => `${v}°`}
          width={esMovil ? 32 : 40}
        />
        <YAxis
          yAxisId="hum"
          orientation="right"
          domain={[hMin, hMax]}
          tick={{ fontSize: 11, fill: COLOR_HUM }}
          tickFormatter={(v: number) => `${v}%`}
          width={esMovil ? 36 : 44}
        />
        <Tooltip
          contentStyle={{ borderRadius: 10, border: '1px solid #DDE7E8', fontSize: 12 }}
          formatter={(v: number, nombre: string) =>
            nombre === 'temp' ? [`${v.toFixed(1)} °C`, 'Temperatura'] : [`${Math.round(v)} %`, 'Humedad']
          }
        />
        <ReferenceLine
          yAxisId="temp"
          y={TEMP_ALERTA}
          stroke={COLOR_TEMP}
          strokeDasharray="5 4"
          strokeOpacity={0.6}
          label={{ value: `${TEMP_ALERTA}° calor`, fontSize: 10, fill: COLOR_TEMP, position: 'insideTopLeft' }}
        />
        <ReferenceLine
          yAxisId="hum"
          y={HUM_ALERTA}
          stroke={COLOR_HUM}
          strokeDasharray="5 4"
          strokeOpacity={0.6}
          label={{ value: `${HUM_ALERTA}% húmedo`, fontSize: 10, fill: COLOR_HUM, position: 'insideTopRight' }}
        />
        <Line yAxisId="temp" type="monotone" dataKey="temp" stroke={COLOR_TEMP} strokeWidth={2}
          dot={false} connectNulls />
        <Line yAxisId="hum" type="monotone" dataKey="hum" stroke={COLOR_HUM} strokeWidth={2}
          dot={false} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}
