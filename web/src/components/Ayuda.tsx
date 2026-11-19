'use client';

import { useEffect, useId, useRef, useState } from 'react';

// Icono de ayuda contextual para terminos tecnicos (ppm, ACH, r2, etc.).
// En escritorio se abre con el mouse encima; en movil no hay "hover", asi
// que el tap alterna mostrar/ocultar. Es un uso puntual y pequeno: no
// justifica sumar una libreria de tooltips, con CSS + useState alcanza.
export default function Ayuda({ texto }: { texto: string }) {
  const [abierto, setAbierto] = useState(false);
  const raizRef = useRef<HTMLSpanElement>(null);
  const idTooltip = useId();

  // Un tap fuera del icono cierra el tooltip en movil (en escritorio ya lo
  // cierra el mouseleave). pointerdown cubre mouse y tactil con un solo listener.
  useEffect(() => {
    if (!abierto) return;
    const cerrarSiAfuera = (e: PointerEvent) => {
      if (raizRef.current && !raizRef.current.contains(e.target as Node)) {
        setAbierto(false);
      }
    };
    document.addEventListener('pointerdown', cerrarSiAfuera);
    return () => document.removeEventListener('pointerdown', cerrarSiAfuera);
  }, [abierto]);

  return (
    <span
      ref={raizRef}
      className="relative inline-flex align-middle"
      onMouseEnter={() => setAbierto(true)}
      onMouseLeave={() => setAbierto(false)}
    >
      <button
        type="button"
        aria-label={`Ayuda: ${texto}`}
        aria-describedby={idTooltip}
        aria-expanded={abierto}
        onClick={(e) => {
          // el icono suele ir junto a un dato dentro de una tarjeta clicable
          // (AulaCard es un <Link>): sin esto, el tap tambien navegaria.
          e.preventDefault();
          e.stopPropagation();
          setAbierto((v) => !v);
        }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setAbierto(false)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') setAbierto(false);
          // evita que Enter/espacio disparen tambien la navegacion del Link contenedor
          if (e.key === 'Enter' || e.key === ' ') e.stopPropagation();
        }}
        className="grid h-4 w-4 shrink-0 place-items-center rounded-full border border-muted/60 text-[10px] font-bold normal-case leading-none text-muted transition hover:border-teal hover:text-teal focus:border-teal focus:text-teal focus:outline-none focus-visible:ring-2 focus-visible:ring-teal/40"
      >
        ?
      </button>
      <span
        role="tooltip"
        id={idTooltip}
        className={`pointer-events-none absolute bottom-full left-1/2 z-40 mb-1.5 w-56 -translate-x-1/2 rounded-lg bg-deep px-2.5 py-2 text-xs font-normal normal-case leading-snug text-white shadow-lg transition-opacity duration-150 ${
          abierto ? 'opacity-100' : 'opacity-0'
        }`}
      >
        {texto}
        <span className="absolute left-1/2 top-full h-2 w-2 -translate-x-1/2 -translate-y-1 rotate-45 bg-deep" />
      </span>
    </span>
  );
}
