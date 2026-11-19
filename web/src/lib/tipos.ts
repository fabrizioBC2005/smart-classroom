export type Estado = 'ok' | 'alerta' | 'critico' | 'sin_datos';

export interface Sede {
  id: number;
  slug: string;
  nombre: string;
  distrito: string;
}

export interface Aula {
  id: number;
  sede_id: number;
  codigo: string;
  nivel: string;
  volumen_m3: number;
  aforo_nominal: number;
  instrumentada: boolean;
  modo_ventilacion: ModoControl;
  modo_iluminacion: ModoControl;
}

/** Quien maneja un equipo: el sistema o las personas */
export type ModoControl = 'automatico' | 'manual';

export interface AulaEstado {
  aula_id: number;
  codigo: string;
  sede_slug: string;
  nivel: string;
  aforo_nominal: number;
  instrumentada: boolean;
  ts: string | null;
  co2_ppm: number | null;
  temp_c: number | null;
  hum_pct: number | null;
  lux?: number | null;
  ocupantes: number | null;
  indice: number | null;
  estado: Estado;
  ventilacion_on: boolean;
  iluminacion_on?: boolean | null;
  online: boolean;
}

export interface Lectura {
  id: number;
  aula_id: number;
  ts: string;
  co2_ppm: number | null;
  temp_c: number | null;
  hum_pct: number | null;
  lux: number | null;
  db_spl: number | null;
  ocupantes_conteo: number | null;
  ocupantes_estimado: number | null;
  indice: number | null;
  estado: Estado;
}

export interface Evento {
  id: number;
  aula_id: number;
  ts: string;
  tipo: string;
  severidad: 'info' | 'alerta' | 'critico';
  variable: string;
  valor: number | null;
  indice: number | null;
  mensaje: string;
  reconocido: boolean;
}

export interface Actuacion {
  id: number;
  aula_id: number;
  ts: string;
  actuador: string;
  accion: string;
  motivo: string;
  origen: string;
}

export type EstadoCumplimiento = 'cumple' | 'no_cumple' | 'sin_datos';

export interface FilaReporte {
  aula_id: number;
  codigo: string;
  muestras: number;
  minutos_registrados: number;
  minutos_sobre_umbral: number;
  pct_sobre_umbral: number;
  co2_promedio: number | null;
  co2_maximo: number | null;
  indice_promedio: number | null;
  estado: EstadoCumplimiento;
}

export interface Reporte {
  desde: string;
  hasta: string;
  umbral_ppm: number;
  aulas_cumplen: number;
  aulas_no_cumplen: number;
  aulas_sin_datos: number;
  filas: FilaReporte[];
}

/** Mensaje que llega por WebSocket */
export interface MsgTelemetria {
  tipo: 'telemetria';
  aula_id: number;
  sede_slug: string;
  codigo: string;
  ts: string;
  co2_ppm: number | null;
  temp_c: number | null;
  hum_pct: number | null;
  lux?: number | null;
  ocupantes: number | null;
  ocupantes_estimado: number | null;
  indice: number | null;
  estado: Estado;
  subindices: Record<string, number>;
  pendiente_ppm_min: number;
  eta_s: number | null;
  ventilacion_on: boolean;
  // estado de las luces segun el worker (automatico o manual)
  iluminacion_on?: boolean;
  // actuadores en pausa por una orden manual reciente
  override_manual?: Array<'ventilacion' | 'iluminacion'>;
  // modo de cada equipo segun el worker
  modos?: Partial<Record<'ventilacion' | 'iluminacion', ModoControl>>;
  // lo que el pronostico espera (modo prueba). null si aun no aprendio o
  // si el aula acaba de empezar a mandar datos
  pronostico?: PronosticoAhora | null;
}

export interface PronosticoAhora {
  minutos_adelante: number;
  co2_previsto: number;
  co2_linea_recta: number | null;
}

/** Respuesta de /api/aulas/{id}/pronostico */
export interface PronosticoAula {
  aprendiendo: boolean;
  modo_prueba: boolean;
  informe: {
    entrenado_el: string;
    ejemplos: number;
    aulas: number;
    con_simulador: boolean;
  } | null;
  ahora: (PronosticoAhora & { co2_ahora: number | null; ts: string }) | null;
  revision: {
    horas: number;
    revisados: number;
    acerto: number;
    acerto_linea_recta: number;
  } | null;
}

export interface MsgEvento {
  tipo: 'evento';
  aula_id: number;
  codigo: string;
  ts: string;
  severidad: 'info' | 'alerta' | 'critico';
  mensaje: string;
}

export type MsgRealtime = MsgTelemetria | MsgEvento;

/** Algo que necesita a una persona (GET /api/pendientes) */
export interface Pendiente {
  clave: string;
  tipo: 'sin_senal' | 'no_alcanza' | 'ventila_mal' | 'manual' | 'clima';
  prioridad: 'alta' | 'media' | 'baja';
  aula_id: number;
  codigo: string;
  sede_slug: string;
  titulo: string;
  detalle: string;
  accion: string;
  desde: string | null;
  boton: { tipo: 'volver_automatico'; actuador: 'ventilacion' | 'iluminacion' } | null;
}

export interface Pendientes {
  pendientes: Pendiente[];
  ocultos: number;
  resumen: { acciones_automaticas_24h: number; alertas_24h: number };
}

/** Un mensaje de la burbuja del asistente IA */
export interface MensajeAsistente {
  rol: 'usuario' | 'asistente';
  texto: string;
}
