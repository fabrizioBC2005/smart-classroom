import { CLASES_ESTADO, ETIQUETA_ESTADO } from '@/lib/formato';
import type { Estado } from '@/lib/tipos';

export default function Semaforo({ estado, className = '' }: { estado: Estado; className?: string }) {
  return (
    <span className={`pill ${CLASES_ESTADO[estado]} ${className}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {ETIQUETA_ESTADO[estado]}
    </span>
  );
}
