'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import Ayuda from '@/components/Ayuda';
import { api } from '@/lib/api';
import { SEDE_ACTUAL } from '@/lib/sede';
import { horasYMinutos } from '@/lib/formato';
import type { EstadoCumplimiento, Reporte } from '@/lib/tipos';

export default function Page() {
  const [rep, setRep] = useState<Reporte | null>(null);
  const [dias, setDias] = useState(7);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setRep(await api.reporte(dias, SEDE_ACTUAL));
    } finally {
      setCargando(false);
    }
  }, [dias]);

  useEffect(() => {
    cargar().catch(() => undefined);
  }, [cargar]);

  const total = rep?.filas.length ?? 0;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reporte de cumplimiento</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Porcentaje de tiempo con CO₂ sobre el umbral de ventilación adecuada, por
            ambiente y por periodo.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg bg-white p-1 ring-1 ring-line">
          {[1, 7, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDias(d)}
              className={`flex min-h-[44px] items-center justify-center rounded-md px-3 text-sm transition sm:min-h-0 sm:py-1.5 ${
                dias === d ? 'bg-deep font-semibold text-white' : 'text-muted hover:bg-mist'
              }`}
            >
              {d === 1 ? '24 h' : `${d} días`}
            </button>
          ))}
        </div>
      </header>

      <div className="card border-l-4 border-l-teal bg-white p-4">
        <p className="text-sm">
          <strong>Por qué existe este reporte.</strong> La Norma A.040 del Reglamento
          Nacional de Edificaciones exige un nivel adecuado y constante de renovación de
          aire en locales educativos, pero no define ningún mecanismo de verificación
          durante la operación. Este reporte convierte esa obligación declarativa en un
          indicador medible y auditable.
        </p>
      </div>

      {rep && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Resumen etiqueta="Aulas evaluadas" valor={`${total}`} />
          <Resumen etiqueta="Cumplen" valor={`${rep.aulas_cumplen}`} color="text-sea" />
          <Resumen etiqueta="No cumplen" valor={`${rep.aulas_no_cumplen}`} color="text-danger" />
          <Resumen etiqueta="Sin datos" valor={`${rep.aulas_sin_datos}`} color="text-muted" />
          <Resumen etiqueta="Umbral aplicado" valor={`${rep.umbral_ppm} ppm`} />
        </div>
      )}

      {/* tabla completa solo desde md hacia arriba: en movil el scroll horizontal es mala experiencia */}
      <div className="card hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead className="bg-mist text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3">Aula</th>
              <th className="px-4 py-3 text-right">Lecturas tomadas</th>
              <th className="px-4 py-3 text-right">Tiempo medido</th>
              <th className="px-4 py-3 text-right">CO₂ promedio</th>
              <th className="px-4 py-3 text-right">CO₂ máximo</th>
              <th className="px-4 py-3 text-right">
                <span className="inline-flex items-center gap-1">
                  Habitabilidad promedio <Ayuda texto="Índice de 0 a 100 que combina CO₂, temperatura, humedad, ruido e iluminación en un solo número. Más alto es mejor." />
                </span>
              </th>
              <th className="px-4 py-3 text-right">Tiempo sobre 1000 ppm</th>
              <th className="px-4 py-3">
                <span className="inline-flex items-center gap-1">
                  Proporción del tiempo <Ayuda texto="Porcentaje del periodo evaluado en que el CO₂ estuvo por encima de 1000 ppm, el umbral de ventilación adecuada." />
                </span>
              </th>
              <th className="px-4 py-3 text-center">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {cargando && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-muted">
                  Calculando…
                </td>
              </tr>
            )}
            {!cargando && rep?.filas.length === 0 && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-muted">
                  Sin datos en el periodo
                </td>
              </tr>
            )}
            {!cargando &&
              rep?.filas.map((f) => (
                <tr key={f.aula_id} className="hover:bg-mist/60">
                  <td className="px-4 py-3 font-medium">
                    <Link href={`/aula/${f.aula_id}`} className="text-teal hover:underline">
                      Aula {f.codigo}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted">{f.muestras}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted">
                    {horasYMinutos(f.minutos_registrados)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {f.co2_promedio?.toFixed(0) ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {f.co2_maximo?.toFixed(0) ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {f.indice_promedio?.toFixed(0) ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {f.minutos_sobre_umbral.toFixed(0)}
                  </td>
                  <td className="px-4 py-3">
                    {f.estado === 'sin_datos' ? (
                      <span className="text-xs text-muted">—</span>
                    ) : (
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.min(100, f.pct_sobre_umbral)}%`,
                              background: f.estado === 'cumple' ? '#00A896' : '#C0392B',
                            }}
                          />
                        </div>
                        <span className="tabular-nums text-xs text-muted">
                          {f.pct_sobre_umbral.toFixed(1)}%
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <EstadoChip estado={f.estado} />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {/* listado de tarjetas para movil: misma info que la tabla, priorizando aula/estado/dato principal */}
      <div className="space-y-3 md:hidden">
        {cargando && <div className="card p-8 text-center text-sm text-muted">Calculando…</div>}
        {!cargando && rep?.filas.length === 0 && (
          <div className="card p-8 text-center text-sm text-muted">Sin datos en el periodo</div>
        )}
        {!cargando &&
          rep?.filas.map((f) => (
            <div key={f.aula_id} className="card p-4">
              <div className="flex items-center justify-between gap-2">
                <Link href={`/aula/${f.aula_id}`} className="font-medium text-teal hover:underline">
                  Aula {f.codigo}
                </Link>
                <EstadoChip estado={f.estado} />
              </div>

              {f.estado === 'sin_datos' ? (
                <p className="mt-2 text-xs text-muted">Sin datos en el periodo</p>
              ) : (
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.min(100, f.pct_sobre_umbral)}%`,
                        background: f.estado === 'cumple' ? '#00A896' : '#C0392B',
                      }}
                    />
                  </div>
                  <span className="tabular-nums text-xs text-muted">
                    {f.pct_sobre_umbral.toFixed(1)}% sobre umbral
                  </span>
                </div>
              )}

              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <MetricaMovil etiqueta="CO₂ promedio" valor={f.co2_promedio?.toFixed(0) ?? '—'} />
                <MetricaMovil etiqueta="CO₂ máximo" valor={f.co2_maximo?.toFixed(0) ?? '—'} />
                <MetricaMovil etiqueta="Habitabilidad" valor={f.indice_promedio?.toFixed(0) ?? '—'} />
              </div>
              <p className="mt-2 text-[11px] text-muted">
                {f.muestras} lecturas tomadas · {horasYMinutos(f.minutos_registrados)} medidos ·{' '}
                {horasYMinutos(f.minutos_sobre_umbral)} sobre 1000 ppm
              </p>
            </div>
          ))}
      </div>

      <p className="text-xs text-muted">
        Criterio: se considera que el ambiente cumple si la concentración de CO₂ supera el
        umbral menos del 10 % del tiempo registrado. Umbral de referencia: 1000 ppm
        (ASHRAE 62.1 para ventilación adecuada).
      </p>
    </div>
  );
}

function Resumen({
  etiqueta,
  valor,
  color = 'text-ink',
}: {
  etiqueta: string;
  valor: string;
  color?: string;
}) {
  return (
    <div className="card px-4 py-3">
      <div className={`text-2xl font-bold ${color}`}>{valor}</div>
      <div className="text-xs uppercase tracking-wide text-muted">{etiqueta}</div>
    </div>
  );
}

function MetricaMovil({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="rounded-lg bg-mist py-1.5">
      <div className="text-sm font-semibold tabular-nums">{valor}</div>
      <div className="text-[10px] uppercase tracking-wide text-muted">{etiqueta}</div>
    </div>
  );
}

function EstadoChip({ estado }: { estado: EstadoCumplimiento }) {
  // "sin_datos" va en gris neutro a proposito: no es una tercera variante de
  // color de exito/fallo, es la ausencia de evidencia para evaluar la norma.
  if (estado === 'sin_datos') {
    return <span className="pill border-slate-300 bg-slate-100 text-muted">Sin datos</span>;
  }
  if (estado === 'cumple') {
    return <span className="pill border-sea/30 bg-sea/10 text-sea">Cumple</span>;
  }
  return <span className="pill border-danger/30 bg-danger/10 text-danger">No cumple</span>;
}
