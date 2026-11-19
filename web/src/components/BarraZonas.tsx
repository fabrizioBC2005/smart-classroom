import { BARRA_MAX, BARRA_MIN, ZONAS_AIRE, posicionEnBarra, zonaAire } from '@/lib/formato';

// Reemplaza al medidor semicircular del indice de habitabilidad: un "50 sobre
// 100" obligaba a saber que significa 50 y de que. La barra responde sola a
// "¿como esta el aire?": se ve en que zona esta el marcador y como se llama.
// Ninguna cifra de CO2 se muestra; el valor solo se usa para ubicar el marcador.

export default function BarraZonas({
  co2,
  contexto,
  pulso,
}: {
  co2: number | null;
  /** "Lleva 14 minutos así y sigue empeorando", etc. Se arma en la pagina. */
  contexto: string | null;
  pulso?: boolean;
}) {
  const zona = co2 === null ? null : zonaAire(co2);
  const pos = co2 === null ? null : posicionEnBarra(co2);

  return (
    <div>
      <p
        className={`text-xl font-bold leading-tight transition-colors duration-500 ${pulso ? 'destello' : ''}`}
        style={{ color: zona?.colorTexto }}
      >
        {zona ? `El aire está ${zona.nombre}` : 'Todavía no hay datos del aire'}
      </p>
      {contexto && <p className="mt-1 text-sm text-muted">{contexto}</p>}

      {/* espacio arriba de la barra reservado para el marcador */}
      <div className="relative mt-8">
        {pos !== null && (
          <div
            className="absolute -top-5 transition-[left] duration-700 ease-out"
            style={{ left: `${pos}%` }}
            aria-hidden="true"
          >
            {/* el texto se corre en proporcion a la posicion para no salirse
                de la tarjeta en los extremos; el triangulo queda centrado */}
            <span
              className="absolute bottom-3 whitespace-nowrap text-[10px] font-medium text-ink"
              style={{ transform: `translateX(-${pos}%)` }}
            >
              ahora
            </span>
            <svg className="h-3 w-3 -translate-x-1/2 text-ink" viewBox="0 0 12 12" fill="currentColor">
              <path d="M1 2h10L6 10z" />
            </svg>
          </div>
        )}

        <div
          className="flex h-3 overflow-hidden rounded-full"
          role="img"
          aria-label={zona ? `Zona actual: ${zona.nombre}` : 'Sin datos'}
        >
          {ZONAS_AIRE.map((z, i) => (
            <div
              key={z.id}
              style={{ flexGrow: ancho(i), flexBasis: 0, background: zona ? z.color : '#DDE7E8' }}
              className={i > 0 ? 'border-l-2 border-white' : ''}
            />
          ))}
        </div>

        <div className="mt-1.5 flex">
          {ZONAS_AIRE.map((z, i) => (
            <span
              key={z.id}
              style={{ flexGrow: ancho(i), flexBasis: 0 }}
              className={`min-w-0 truncate text-center text-[10px] ${
                zona?.id === z.id ? 'font-semibold text-ink' : 'text-muted'
              }`}
            >
              {z.nombre}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ancho proporcional al rango de la zona dentro de la escala
function ancho(i: number) {
  const desde = i === 0 ? BARRA_MIN : ZONAS_AIRE[i - 1].hasta;
  return (ZONAS_AIRE[i].hasta - desde) / (BARRA_MAX - BARRA_MIN);
}
