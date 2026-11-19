import type { Lectura } from '@/lib/tipos';

// Tarjeta "Equipos en este salón": que hay instalado y si esta funcionando,
// dicho en llano. El modelo va como texto secundario para quien le de
// mantenimiento; a los demas les basta con saber que mide cada cosa.

// Un equipo se considera "sin señal" si su variable vino null en TODAS las
// ultimas N lecturas: una sola lectura null puede ser un hipo del bus I2C, no
// una falla. ~15 s entre lecturas -> unos 2-3 minutos de margen.
const LECTURAS_A_MIRAR = 10;

// Si la ultima lectura es mas vieja que esto, el aula dejo de reportar y
// ningun equipo se puede dar por funcionando aunque sus ultimos datos esten bien.
const MAX_ANTIGUEDAD_MS = 5 * 60_000;

type Equipo = {
  id: string;
  que: string;
  detalle: string;
  /** campos de la lectura que produce; con que uno llegue, reporta */
  campos: (keyof Lectura)[];
};

const EQUIPOS: Equipo[] = [
  { id: 'aire', que: 'Mide el aire del salón', detalle: 'SCD41', campos: ['co2_ppm'] },
  { id: 'clima', que: 'Mide temperatura y humedad', detalle: 'BME280', campos: ['temp_c', 'hum_pct'] },
  { id: 'luz', que: 'Mide cuánta luz hay', detalle: 'BH1750', campos: ['lux'] },
  // "no son cámaras" es deliberado: es el argumento de privacidad del
  // proyecto y tiene que estar a la vista, no escondido en una ayuda
  {
    id: 'puerta',
    que: 'Cuentan quién entra y quién sale',
    detalle: 'Dos sensores en la puerta · no son cámaras',
    campos: ['ocupantes_conteo'],
  },
  // la pantalla no manda telemetria propia: la maneja el mismo ESP32 que
  // envia las lecturas, asi que si llega cualquier dato, esta encendida
  { id: 'pantalla', que: 'Pantallita que muestra el estado', detalle: 'Visible desde dentro del aula', campos: [] },
];

export default function Sensores({
  lecturas,
  instrumentada,
}: {
  lecturas: Lectura[];
  instrumentada: boolean;
}) {
  const recientes = lecturas.slice(-LECTURAS_A_MIRAR);
  const ultima = recientes.at(-1);
  const alDia = !!ultima && Date.now() - +new Date(ultima.ts) <= MAX_ANTIGUEDAD_MS;

  const estado = EQUIPOS.map((e) => ({
    ...e,
    reporta:
      alDia &&
      (e.campos.length === 0 || recientes.some((l) => e.campos.some((c) => l[c] !== null))),
  }));
  const funcionando = estado.filter((e) => e.reporta).length;

  // En un aula simulada los datos los inventa el simulador (con luz y conteo
  // incluidos), asi que derivar "funcionando" de ellos seria mentir: se
  // muestra la lista para que se vea que se instalaria, pero sin estado.
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold">Equipos en este salón</h3>
      <p className="mt-0.5 text-xs text-muted">
        {instrumentada
          ? `${funcionando} de ${EQUIPOS.length} funcionando`
          : 'Aula simulada · estos equipos todavía no están instalados'}
      </p>
      <ul className="mt-3 space-y-2.5">
        {estado.map((e) => (
          <li key={e.id} className="flex gap-2.5">
            {instrumentada ? (
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${e.reporta ? 'bg-sea' : 'bg-slate-400'}`}
                aria-label={e.reporta ? 'funcionando' : 'sin señal'}
              />
            ) : (
              // aro vacio: "esto iria aca", sin afirmar que funcione
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full border border-slate-400" aria-hidden="true" />
            )}
            <div className="min-w-0">
              <p className={`text-sm ${instrumentada && !e.reporta ? 'text-muted' : ''}`}>
                {e.que}
                {instrumentada && !e.reporta && <span className="text-xs"> · sin señal</span>}
              </p>
              <p className="text-[11px] text-muted">{e.detalle}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
