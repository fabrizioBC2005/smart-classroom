import { ETIQUETA_EVENTO } from './formato';
import type { Actuacion, Evento } from './tipos';

// Resumen por aula de la pantalla de Alertas. Todo se resuelve en el frontend
// con lo que /api/eventos y /api/actuaciones ya devuelven: para el volumen que
// manejamos (hasta 500 filas por pedido) no hace falta un endpoint agregado.
//
// La pantalla NO lista eventos: responde siempre tres preguntas por aula
// (que paso / que hizo el sistema / si se repite). Aca se cuentan las cosas y
// se arman esas frases. Regla dura: ninguna frase lleva ppm, picos, promedios
// ni horas exactas; solo conteos de veces, tiempos relativos y palabras.

export type Severidad = Evento['severidad'];

export const PESO_SEV: Record<Severidad, number> = { critico: 0, alerta: 1, info: 2 };

// Colores de los tres puntos. Son los mismos de la paleta (COLOR_ESTADO): no
// se introduce ningun color nuevo.
export const COLOR_PUNTO = {
  rojo: '#C0392B',
  verde: '#00A896',
  ambar: '#D98324',
  gris: '#94A3B8',
} as const;

export type Punto = { color: string; texto: string };

// ------------------------------------------------------------ parametros

// Patron de repeticion: con 3 cruces ya hay dos intervalos entre ellos, que es
// lo minimo para que "cada X minutos" sea un promedio y no un dato suelto.
// Con 2 cruces solo hay un intervalo: puede ser casualidad.
export const MIN_CRUCES_PATRON = 3;

// Si los intervalos varian mucho (desvio > 50% del promedio), decir "cada 20
// minutos" seria inventar un ritmo que no existe: se dice "sin un ritmo fijo".
const MAX_VARIACION_RITMO = 0.5;

// Si desde el ultimo cruce paso mas del doble del intervalo medio, el patron
// se corto: se dice "se repetia", no "vuelve a pasar".
const FACTOR_PATRON_CORTADO = 2;

// Un hueco de mas de una hora entre cruces no es parte del ritmo: es que el
// sistema estuvo apagado o termino la clase. Con datos reales aparecio un
// hueco de ~41 h entre sesiones que, metido en la media, convertia "cada 2
// minutos" en "cada hora" y hacia que todo pareciera "sin ritmo fijo".
const HUECO_PAUSA_MS = 60 * 60_000;

// Por debajo de esto el texto es "cada pocos minutos", que ya es vago: no
// tiene sentido exigir regularidad (el simulador acelerado alterna rafagas de
// ~2 min con pausas de ~13 min y eso sigue siendo "cada pocos minutos").
const RITMO_SIN_CHEQUEO_MS = 5 * 60_000;

// temp_alerta y hum_alerta, a diferencia del CO2, el backend los emite en CADA
// lectura mientras dure la condicion (no solo al cambiar de estado). Para no
// contar "hizo calor 40 veces" se agrupan en episodios: dos avisos separados
// por menos de esto son el mismo episodio.
const HUECO_EPISODIO_MS = 10 * 60_000;

// La actuacion anticipada se registra en el mismo ciclo que el evento que la
// provoco, pero con un ts que puede quedar unos segundos antes. Este margen
// evita que quede fuera de la ventana del aula.
const MARGEN_VENTANA_MS = 60_000;

const ms = (iso: string) => +new Date(iso);

// ------------------------------------------------------- textos en llano

const NUMEROS = ['cero', 'una', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez', 'once', 'doce'];

/** "una vez", "seis veces": el conteo se lee mejor en palabras que en cifras. */
export function vecesTexto(n: number): string {
  if (n === 1) return 'una vez';
  return `${NUMEROS[n] ?? n} veces`;
}

/** "hace un momento", "hace 8 min", "hace 1 h". Nunca la hora exacta. */
export function haceTexto(iso: string, ahora: number): string {
  const seg = Math.max(0, (ahora - ms(iso)) / 1000);
  if (seg < 60) return 'hace un momento';
  const min = Math.floor(seg / 60);
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `hace ${h} h`;
  const d = Math.floor(h / 24);
  return d === 1 ? 'ayer' : `hace ${d} días`;
}

// La "jornada" empieza a las 5 a. m.: asi un evento de la 1 a. m. pertenece a
// "esta noche" (la de ayer a hoy), como lo diria cualquiera, y no a "hoy".
const INICIO_JORNADA_H = 5;
const jornada = (t: number) => {
  const d = new Date(t - INICIO_JORNADA_H * 3_600_000);
  return Math.floor(+new Date(d.getFullYear(), d.getMonth(), d.getDate()) / 86_400_000);
};
const franja = (t: number) => {
  const h = new Date(t).getHours();
  if (h >= INICIO_JORNADA_H && h < 12) return 'mañana';
  if (h >= 12 && h < 19) return 'tarde';
  return 'noche';
};

/** "esta noche", "hoy", "anoche", "desde ayer"... para situar sin dar horas. */
export function periodoTexto(desde: string, hasta: string, ahora: number): string {
  const t0 = ms(desde);
  const t1 = ms(hasta);
  const [j0, j1, hoy] = [jornada(t0), jornada(t1), jornada(ahora)];
  const misma = franja(t0) === franja(t1);
  if (j0 === hoy && j1 === hoy) return misma ? `esta ${franja(t0)}` : 'hoy';
  if (j0 === hoy - 1 && j1 === hoy - 1) return misma && franja(t0) === 'noche' ? 'anoche' : 'ayer';
  if (j0 === hoy - 1 && j1 === hoy) return 'desde ayer';
  return 'en los últimos días';
}

/** Intervalo medio en palabras redondas: "cada 20 minutos", "cada hora". */
function cadaTexto(intervaloMs: number): string {
  const min = intervaloMs / 60_000;
  if (min < 5) return 'cada pocos minutos';
  if (min < 50) return `cada ${Math.max(5, Math.round(min / 5) * 5)} minutos`;
  if (min < 90) return 'cada hora, más o menos';
  return `cada ${Math.round(min / 60)} horas, más o menos`;
}

// --------------------------------------------------- patron de repeticion

export type Patron = {
  intervaloMs: number;
  /** false si los intervalos son muy dispares: hay repeticion pero no ritmo */
  regular: boolean;
  /** false si el ultimo cruce quedo muy atras respecto del ritmo */
  activo: boolean;
};

/**
 * Recibe los instantes en que algo "volvio a pasar" (cruces del umbral, o
 * encendidos de la ventilacion) en orden cronologico. Hay patron si hay al
 * menos MIN_CRUCES_PATRON; el intervalo es la media de los huecos entre ellos,
 * sin contar las pausas largas (HUECO_PAUSA_MS).
 */
export function detectarPatron(instantes: number[], ahora: number): Patron | null {
  if (instantes.length < MIN_CRUCES_PATRON) return null;
  const huecos = instantes
    .slice(1)
    .map((t, i) => t - instantes[i])
    .filter((h) => h <= HUECO_PAUSA_MS);
  // sin las pausas tienen que quedar al menos dos huecos, igual que antes
  if (huecos.length < MIN_CRUCES_PATRON - 1) return null;
  const media = huecos.reduce((s, h) => s + h, 0) / huecos.length;
  if (media <= 0) return null;
  const desvio = Math.sqrt(huecos.reduce((s, h) => s + (h - media) ** 2, 0) / huecos.length);
  return {
    intervaloMs: media,
    regular: media < RITMO_SIN_CHEQUEO_MS || desvio / media <= MAX_VARIACION_RITMO,
    activo: ahora - instantes[instantes.length - 1] <= FACTOR_PATRON_CORTADO * media,
  };
}

function puntoPatron(p: Patron, sujeto: { activo: string; cortado: string }): Punto {
  const ritmo = p.regular ? cadaTexto(p.intervaloMs) : 'a menudo, sin un ritmo fijo';
  return {
    color: COLOR_PUNTO.ambar,
    texto: p.activo ? `${sujeto.activo} ${ritmo}` : `${sujeto.cortado} ${ritmo}, pero hace rato que no pasa`,
  };
}

function episodios(evs: Evento[]): number {
  let n = 0;
  let ultimo = -Infinity;
  for (const e of evs) {
    if (ms(e.ts) - ultimo > HUECO_EPISODIO_MS) n++;
    ultimo = ms(e.ts);
  }
  return n;
}

// ================================================================ eventos

export type ResumenEventos = {
  aulaId: number;
  /** ids sin reconocer: lo que marca el check del aula */
  pendientes: number[];
  revisada: boolean;
  /** peor severidad dentro de la ventana; decide el filtro y el orden */
  severidad: Severidad;
  /** ts del evento mas reciente de la ventana */
  ultima: string;
  /** cosas que atender: cruces del aire + episodios de calor/humedad */
  peso: number;
  descripcion: string;
  puntos: Punto[];
};

/**
 * Eventos y actuaciones de UNA aula -> resumen en tres puntos.
 *
 * Ventana: si hay eventos sin revisar, se resume desde el mas antiguo de ellos
 * (lo nuevo que hay que atender); si no, todo lo cargado. Asi, al marcar el
 * aula como vista y volver a cargarse, el resumen habla solo de lo nuevo.
 */
export function resumirEventos(
  aulaId: number,
  eventosAula: Evento[],
  actuacionesAula: Actuacion[],
  ahora: number,
): ResumenEventos {
  const cron = [...eventosAula].sort((a, b) => ms(a.ts) - ms(b.ts));
  const pendientes = cron.filter((e) => !e.reconocido);
  const revisada = pendientes.length === 0;
  const inicio = revisada ? -Infinity : ms(pendientes[0].ts);
  const enVentana = cron.filter((e) => ms(e.ts) >= inicio);

  // Maquina de estados del aire sobre TODO el historial (no solo la ventana):
  // si el aula ya estaba cargada cuando empezo la ventana, el primer
  // co2_alerta de la ventana no es un cruce nuevo. Tambien resuelve el caso
  // del backend que emite co2_alerta al BAJAR de critico a alerta: como el
  // estado ya era "cargado", no cuenta como cruce.
  let cargado = false;
  const cruces: number[] = [];
  let normalizaciones = 0;
  for (const e of cron) {
    const t = ms(e.ts);
    if (e.tipo === 'co2_alerta' || e.tipo === 'co2_critico') {
      if (!cargado && t >= inicio) cruces.push(t);
      cargado = true;
    } else if (e.tipo === 'normalizado') {
      if (cargado && t >= inicio) normalizaciones++;
      cargado = false;
    }
  }
  const sigueCargado = cargado;

  const critico = enVentana.some((e) => e.tipo === 'co2_critico');
  const calor = episodios(enVentana.filter((e) => e.tipo === 'temp_alerta'));
  const humedad = episodios(enVentana.filter((e) => e.tipo === 'hum_alerta'));
  const anticipos = enVentana.filter((e) => e.tipo === 'prediccion_riesgo').length;

  const vent = actuacionesAula.filter(
    (a) => a.actuador === 'ventilacion' && a.accion === 'on' && ms(a.ts) >= inicio - MARGEN_VENTANA_MS,
  );
  const ventAuto = vent.filter((a) => a.origen !== 'manual').length;
  const ventManual = vent.length - ventAuto;

  const veces = cruces.length;
  const desde = enVentana[0]?.ts ?? '';
  const ultima = enVentana[enVentana.length - 1]?.ts ?? '';
  const periodo = desde ? periodoTexto(desde, ultima, ahora) : '';
  const severidad = enVentana.reduce<Severidad>(
    (m, e) => (PESO_SEV[e.severidad] < PESO_SEV[m] ? e.severidad : m),
    'info',
  );

  // ---- descripcion corta de la cabecera
  let descripcion: string;
  if (revisada) descripcion = 'ya revisada';
  else if (sigueCargado) descripcion = veces > 1 ? `se cargó ${veces} veces y sigue así` : 'el aire sigue cargado';
  else if (veces > 1) descripcion = `se cargó ${veces} veces`;
  else if (veces === 1) descripcion = critico ? 'el aire llegó a estar muy cargado' : 'el aire estuvo algo cargado';
  else if (calor > 0) descripcion = 'hizo calor';
  else if (humedad > 0) descripcion = 'hubo mucha humedad';
  else if (anticipos > 0) descripcion = 'el sistema se adelantó';
  else descripcion = 'sin novedades';

  const puntos: Punto[] = [];

  // ---- 1. que paso
  const extras = [calor > 0 && 'hizo calor', humedad > 0 && 'hubo mucha humedad'].filter(Boolean);
  if (veces > 0) {
    let t = `El aire se cargó ${vecesTexto(veces)} ${periodo}`;
    if (critico) t += veces === 1 ? ' y llegó a nivel crítico' : '; alguna de ellas llegó a nivel crítico';
    if (extras.length) t += `, y además ${extras.join(' y ')}`;
    puntos.push({ color: COLOR_PUNTO.rojo, texto: t });
  } else if (calor > 0 || humedad > 0) {
    // ETIQUETA_EVENTO ya tiene la frase en llano; solo se le suma cuantas
    // veces y cuando
    const partes = [
      calor > 0 && `${ETIQUETA_EVENTO.temp_alerta} ${vecesTexto(calor)}`,
      humedad > 0 && `${ETIQUETA_EVENTO.hum_alerta.replace(/^La /, 'la ')} ${vecesTexto(humedad)}`,
    ].filter(Boolean);
    puntos.push({ color: COLOR_PUNTO.rojo, texto: `${partes.join(', y ')} ${periodo}` });
  } else if (anticipos > 0) {
    puntos.push({ color: COLOR_PUNTO.rojo, texto: `${ETIQUETA_EVENTO.prediccion_riesgo} ${periodo}` });
  } else if (enVentana.length > 0) {
    const ult = enVentana[enVentana.length - 1];
    puntos.push({ color: COLOR_PUNTO.rojo, texto: ETIQUETA_EVENTO[ult.tipo] ?? ult.mensaje });
  }

  // ---- 2. que hizo el sistema
  if (veces > 0 || anticipos > 0) {
    let t: string;
    if (ventAuto > 0) {
      if (sigueCargado) t = 'Encendió el ventilador, pero el aire todavía no se limpia';
      else if (veces === 0) t = 'Encendió el ventilador a tiempo y no pasó a más';
      else if (veces > 1 && normalizaciones >= veces) t = 'El ventilador lo arregló solo cada vez';
      else t = 'El ventilador lo arregló solo';
      if (ventManual > 0) t += '; además alguien lo encendió a mano';
    } else if (ventManual > 0) {
      t = sigueCargado
        ? 'Alguien encendió el ventilador a mano, pero el aire todavía no se limpia'
        : 'Alguien encendió el ventilador a mano y el aire se limpió';
    } else {
      t = sigueCargado ? 'El sistema todavía no ha encendido el ventilador' : 'Se normalizó solo, sin necesidad de ventilar';
    }
    puntos.push({ color: COLOR_PUNTO.verde, texto: t });
  } else if (calor > 0 || humedad > 0) {
    // el sistema solo actua sobre el CO2 (ver backend, reglas.py): decirlo
    // evita que alguien espere que "lo arregle solo"
    const que = calor > 0 && humedad > 0 ? 'el calor ni la humedad' : calor > 0 ? 'el calor' : 'la humedad';
    puntos.push({ color: COLOR_PUNTO.verde, texto: `El sistema no controla ${que}: conviene revisar el aula` });
  }

  // ---- 3. si se repite
  const patron = detectarPatron(cruces, ahora);
  if (patron) {
    puntos.push(puntoPatron(patron, { activo: 'Vuelve a pasar', cortado: 'Se repetía' }));
  } else if (veces === 2) {
    puntos.push({ color: COLOR_PUNTO.gris, texto: 'Se repitió, pero todavía no hay un patrón' });
  } else if (veces === 1 && !sigueCargado) {
    puntos.push({ color: COLOR_PUNTO.gris, texto: 'No se ha vuelto a repetir' });
  }

  return {
    aulaId,
    pendientes: pendientes.map((e) => e.id),
    revisada,
    severidad,
    ultima,
    peso: veces + calor + humedad,
    descripcion,
    puntos,
  };
}

// ============================================================ actuaciones

export type ResumenActuaciones = {
  aulaId: number;
  ultima: string;
  descripcion: string;
  puntos: Punto[];
  /** strings tecnicos distintos (el mas reciente primero), para el <details> */
  motivos: string[];
};

const MAX_MOTIVOS_TECNICOS = 6;

/** Actuaciones de UNA aula -> mismo formato de tres puntos que los eventos. */
export function resumirActuaciones(aulaId: number, acts: Actuacion[], ahora: number): ResumenActuaciones {
  const cron = [...acts].sort((a, b) => ms(a.ts) - ms(b.ts));
  const vent = cron.filter((a) => a.actuador === 'ventilacion');
  const encendidos = vent.filter((a) => a.accion === 'on');
  const apagados = vent.filter((a) => a.accion === 'off');
  // el motivo es auditable y tiene formato fijo (ver explicarMotivo): por su
  // prefijo se sabe si el sistema se adelanto o reacciono tarde
  const anticipos = encendidos.filter((a) => a.motivo.startsWith('proyeccion')).length;
  const reacciones = encendidos.filter((a) => a.motivo.startsWith('co2_sobre_umbral')).length;
  const manuales = cron.filter((a) => a.origen === 'manual').length;
  const luces = cron.filter((a) => a.actuador === 'iluminacion').length;
  const ventEncendida = vent[vent.length - 1]?.accion === 'on';

  const desde = cron[0]?.ts ?? '';
  const ultima = cron[cron.length - 1]?.ts ?? '';
  const periodo = desde ? periodoTexto(desde, ultima, ahora) : '';

  let descripcion: string;
  if (encendidos.length > 1) descripcion = `encendió la ventilación ${encendidos.length} veces`;
  else if (encendidos.length === 1) descripcion = manuales > 0 && anticipos + reacciones === 0 ? 'la encendieron a mano' : 'encendió la ventilación';
  else if (apagados.length > 0) descripcion = 'apagó la ventilación';
  else if (luces > 0) descripcion = 'cambió las luces';
  else descripcion = 'sin decisiones';

  const puntos: Punto[] = [];

  // ---- 1. por que actuo (lo que paso en el aula)
  let porQue: string | null = null;
  if (anticipos > 0 && reacciones === 0) porQue = 'Vio venir que el aire se iba a cargar y se adelantó';
  else if (reacciones > 0 && anticipos === 0) porQue = 'Reaccionó cuando el aire ya estaba cargado';
  else if (anticipos > 0) {
    porQue = anticipos >= reacciones
      ? 'Casi siempre se adelantó a que el aire se cargara'
      : 'Casi siempre reaccionó cuando el aire ya estaba cargado';
  } else if (manuales > 0) porQue = 'Alguien lo pidió a mano desde el panel';
  else if (apagados.length > 0) porQue = 'El aire ya estaba limpio';
  if (porQue && manuales > 0 && anticipos + reacciones > 0) porQue += ', y alguien intervino a mano';
  if (porQue) puntos.push({ color: COLOR_PUNTO.rojo, texto: porQue });

  // ---- 2. que hizo
  let hizo: string | null = null;
  if (encendidos.length > 0) {
    hizo = `Encendió la ventilación ${vecesTexto(encendidos.length)} ${periodo}`;
    hizo += ventEncendida
      ? apagados.length > 0 ? ', y ahora sigue encendida' : ' y sigue encendida'
      : ' y la apagó cuando el aire se limpió';
  } else if (apagados.length > 0) {
    hizo = `Apagó la ventilación ${periodo}`;
  }
  if (luces > 0) hizo = hizo ? `${hizo}; también movió las luces` : `Cambió las luces ${periodo}`;
  if (hizo) puntos.push({ color: COLOR_PUNTO.verde, texto: hizo });

  // ---- 3. si se repite: mismo detector que los eventos, sobre los encendidos
  const patron = detectarPatron(encendidos.map((a) => ms(a.ts)), ahora);
  if (patron) {
    puntos.push(puntoPatron(patron, { activo: 'Lo hace', cortado: 'Lo hacía' }));
  } else if (encendidos.length === 2) {
    puntos.push({ color: COLOR_PUNTO.gris, texto: 'Lo repitió, pero todavía no hay un patrón' });
  } else if (encendidos.length === 1) {
    puntos.push({ color: COLOR_PUNTO.gris, texto: 'No lo ha vuelto a hacer' });
  }

  const motivos = Array.from(new Set([...cron].reverse().map((a) => a.motivo))).slice(0, MAX_MOTIVOS_TECNICOS);

  return { aulaId, ultima, descripcion, puntos, motivos };
}

/** Agrupa cualquier lista por aula_id conservando el orden de entrada. */
export function porAula<T extends { aula_id: number }>(xs: T[]): Map<number, T[]> {
  const m = new Map<number, T[]>();
  for (const x of xs) {
    const l = m.get(x.aula_id);
    if (l) l.push(x);
    else m.set(x.aula_id, [x]);
  }
  return m;
}
