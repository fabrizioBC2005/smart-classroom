import type {
  MensajeAsistente,
  ModoControl,
  Pendientes,
  Actuacion, Aula, AulaEstado, Evento, Lectura, PronosticoAula, Reporte, Sede,
} from './tipos';

export const API =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export const WS =
  process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${ruta}`, { cache: 'no-store', ...init });
  if (!r.ok) {
    const detalle = await r.text().catch(() => '');
    throw new Error(`${r.status} ${r.statusText} — ${ruta} ${detalle}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  modo: (aulaId: number, actuador: 'ventilacion' | 'iluminacion', modo: ModoControl) =>
    pedir<Aula>(`/api/aulas/${aulaId}/modo`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actuador, modo }),
    }),
  pendientes: () => pedir<Pendientes>('/api/pendientes'),
  resolverPendiente: (clave: string) =>
    pedir<{ ok: boolean }>('/api/pendientes/resolver', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clave }),
    }),
  asistenteEstado: () =>
    pedir<{ configurado: boolean; modelo: string }>('/api/asistente/estado'),
  asistente: (mensajes: MensajeAsistente[]) =>
    pedir<{ respuesta: string }>('/api/asistente', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensajes }),
    }),
  sedes: () => pedir<Sede[]>('/api/sedes'),
  aulas: (sede?: string) =>
    pedir<Aula[]>(`/api/aulas${sede ? `?sede=${sede}` : ''}`),
  estado: (sede?: string) =>
    pedir<AulaEstado[]>(`/api/estado${sede ? `?sede=${sede}` : ''}`),
  aula: (id: number) => pedir<Aula>(`/api/aulas/${id}`),
  lecturas: (id: number, horas = 6) =>
    pedir<Lectura[]>(`/api/aulas/${id}/lecturas?horas=${horas}`),
  eventosAula: (id: number) => pedir<Evento[]>(`/api/aulas/${id}/eventos`),
  // limite: el backend devuelve 100 por defecto (max 500). La pantalla de
  // alertas agrupa por aula y necesita ventana suficiente para ver los ciclos.
  eventos: (soloAbiertos = false, limite = 100) =>
    pedir<Evento[]>(`/api/eventos?solo_abiertos=${soloAbiertos}&limite=${limite}`),
  reconocer: (id: number) =>
    pedir<Evento>(`/api/eventos/${id}/reconocer`, { method: 'POST' }),
  actuaciones: (aulaId?: number, limite = 100) =>
    pedir<Actuacion[]>(
      `/api/actuaciones?limite=${limite}${aulaId ? `&aula_id=${aulaId}` : ''}`,
    ),
  reporte: (dias = 7, sede?: string) =>
    pedir<Reporte>(`/api/reporte/cumplimiento?dias=${dias}${sede ? `&sede=${sede}` : ''}`),
  renovacion: (id: number) =>
    pedir<{ aula_id: number; ach: number | null; tramos: number; diagnostico?: string }>(
      `/api/reporte/renovacion/${id}`,
    ),
  pronostico: (id: number) => pedir<PronosticoAula>(`/api/aulas/${id}/pronostico`),
  comando: (aulaId: number, actuador: string, accion: 'on' | 'off') =>
    pedir<{ ok: boolean }>(`/api/aulas/${aulaId}/comando`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ actuador, accion, motivo: 'override_manual' }),
    }),
};
