import type { Estado } from './tipos';

export const COLOR_ESTADO: Record<Estado, string> = {
  ok: '#00A896',
  alerta: '#D98324',
  critico: '#C0392B',
  sin_datos: '#94A3B8',
};

export const ETIQUETA_ESTADO: Record<Estado, string> = {
  ok: 'Normal',
  alerta: 'Alerta',
  critico: 'Critico',
  sin_datos: 'Sin datos',
};

export const CLASES_ESTADO: Record<Estado, string> = {
  ok: 'bg-sea/10 text-sea border-sea/30',
  alerta: 'bg-amber/10 text-amber border-amber/30',
  critico: 'bg-danger/10 text-danger border-danger/30',
  sin_datos: 'bg-slate-100 text-slate-500 border-slate-200',
};

/** Prioridad de ordenamiento: lo urgente primero, lo vacio al final. */
export const ORDEN_ESTADO: Record<Estado, number> = {
  critico: 0,
  alerta: 1,
  ok: 2,
  sin_datos: 3,
};

// Traduccion a lenguaje humano: "2549 ppm" no dice nada a quien no conoce
// el tema; "aire muy cargado" si. El numero queda, con su significado.

export const UMBRAL_ALERTA = 1000;
export const UMBRAL_CRITICO = 1400;
export const CO2_MIN_ESCALA = 400;
export const CO2_MAX_ESCALA = 2000;

export function nivelAire(co2: number | null | undefined) {
  if (co2 === null || co2 === undefined) {
    return { texto: 'Sin medicion', detalle: '', color: '#94A3B8' };
  }
  if (co2 < 800) {
    return { texto: 'Aire limpio', detalle: 'Ventilacion adecuada', color: '#00A896' };
  }
  if (co2 < UMBRAL_ALERTA) {
    return { texto: 'Aire aceptable', detalle: 'Cerca del umbral', color: '#00A896' };
  }
  if (co2 < UMBRAL_CRITICO) {
    return { texto: 'Aire cargado', detalle: 'Sobre el umbral normativo', color: '#D98324' };
  }
  return { texto: 'Aire muy cargado', detalle: 'Requiere ventilacion', color: '#C0392B' };
}

export function etiquetaIndice(v: number | null | undefined) {
  if (v === null || v === undefined) return 'sin datos';
  if (v >= 80) return 'buena';
  if (v >= 60) return 'regular';
  if (v >= 40) return 'deficiente';
  return 'muy deficiente';
}

// "^" y "v" se leen como letras, no como flechas: se usan los caracteres
// unicode ▲▼● para que no haya ambiguedad visual.
export function tendencia(ppmMin: number | null | undefined) {
  if (ppmMin === null || ppmMin === undefined) {
    return { flecha: '', texto: '', tono: 'text-muted' };
  }
  if (ppmMin > 15) {
    return { flecha: '▲', texto: `subiendo rápido ${ppmMin.toFixed(0)} ppm/min`, tono: 'text-danger' };
  }
  if (ppmMin > 3) {
    return { flecha: '▲', texto: `subiendo ${ppmMin.toFixed(0)} ppm/min`, tono: 'text-amber' };
  }
  if (ppmMin < -3) {
    return { flecha: '▼', texto: `bajando ${Math.abs(ppmMin).toFixed(0)} ppm/min`, tono: 'text-sea' };
  }
  return { flecha: '●', texto: 'estable', tono: 'text-muted' };
}

/** Posicion de un valor de CO2 en la barra, en porcentaje. */
export function posicionEnEscala(co2: number) {
  const pct = ((co2 - CO2_MIN_ESCALA) / (CO2_MAX_ESCALA - CO2_MIN_ESCALA)) * 100;
  return Math.min(100, Math.max(0, pct));
}

export const n1 = (v: number | null | undefined, suf = '') =>
  v === null || v === undefined ? '-' : `${v.toFixed(1)}${suf}`;

export const n0 = (v: number | null | undefined, suf = '') =>
  v === null || v === undefined ? '-' : `${Math.round(v)}${suf}`;

export const hora = (iso: string) =>
  new Date(iso).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' });

export const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString('es-PE', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });

export const minutos = (segundos: number | null) =>
  segundos === null ? '-' : `${(segundos / 60).toFixed(1)} min`;

// "-" solo, sin contexto, no dice si el umbral ya se paso o si el aire esta
// estable. Con el CO2 actual a la mano se puede distinguir ambos casos.
export function etaTexto(
  etaS: number | null,
  co2Actual: number | null,
  umbral = UMBRAL_ALERTA,
): string {
  if (etaS !== null) return minutos(etaS);
  if (co2Actual !== null && co2Actual >= umbral) return 'ya superado';
  return 'estable';
}

// Nota corta para que la pendiente del CO2 se entienda sin hacer la cuenta
// mental de "cuanto es 35 ppm/min en la practica".
export function implicacionPendiente(ppmMin: number): string {
  if (ppmMin > 15) return 'a este ritmo el aire se carga muy rápido';
  if (ppmMin > 3) return 'a este ritmo el aire se carga rápido';
  if (ppmMin < -3) return 'el aire se está limpiando';
  return 'el nivel se mantiene estable';
}

// "127 min" no se lee de un vistazo; "2 h 7 min" si. Se usa en el reporte
// de cumplimiento para el tiempo medido de cada aula.
export function horasYMinutos(mins: number): string {
  const totalMin = Math.round(mins);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m} min`;
  if (m === 0) return `${h} h`;
  return `${h} h ${m} min`;
}

// El backend guarda "motivo" como registro auditable en formato de maquina
// (ej. "proyeccion_cruce_umbral:4.2min|pendiente:23.4ppm_min|r2:0.97"). Ese
// string NO cambia: es la evidencia. Esto solo lo traduce para mostrarlo;
// si el formato no matchea ninguno conocido, se muestra tal cual en vez de
// arriesgar una traduccion inventada.
export function explicarMotivo(motivo: string): string {
  if (motivo === 'override_manual') {
    return 'Activado a mano desde el panel';
  }

  const luz = motivo.match(/^luz_insuficiente:([\d.]+)lux/);
  if (luz) return `Había gente y poca luz (${luz[1]} lux)`;
  const vacia = motivo.match(/^aula_vacia:([\d.]+)min/);
  if (vacia) return `El aula llevaba ${vacia[1]} minutos vacía`;
  const calor = motivo.match(/^temperatura_alta:([\d.]+)C/);
  if (calor) return `Hacía calor (${calor[1]} °C) con gente adentro`;
  const fresco = motivo.match(/^temperatura_normalizada:([\d.]+)C/);
  if (fresco) return `La temperatura bajó a ${fresco[1]} °C`;

  const sobreUmbral = motivo.match(/^co2_sobre_umbral:([\d.]+)ppm$/);
  if (sobreUmbral) {
    return `Reaccionó: el CO₂ ya estaba en ${sobreUmbral[1]} ppm, por encima del umbral`;
  }

  const normalizado = motivo.match(/^co2_normalizado:([\d.]+)ppm/);
  if (normalizado) {
    return `El aire se normalizó: bajó a ${normalizado[1]} ppm`;
  }

  const proyeccion = motivo.match(
    /^proyeccion_cruce_umbral:([\d.]+)min\|pendiente:([\d.]+)ppm_min\|r2:([\d.]+)$/
  );
  if (proyeccion) {
    const [, minutosStr, pendienteStr, r2Str] = proyeccion;
    const r2 = Number(r2Str);
    const confianza = r2 >= 0.9 ? 'alta' : r2 >= 0.7 ? 'media' : 'baja';
    return `Se anticipó: subiendo a ${pendienteStr} ppm por minuto, iba a superar el umbral en ${minutosStr} minutos (confianza ${confianza})`;
  }

  return motivo;
}

// Explicacion en lenguaje llano para la segunda linea de la linea de tiempo.
// explicarMotivo() conserva los numeros (ppm, minutos, confianza) y por eso
// queda para "Ver dato técnico"; esto dice lo mismo sin cifras. Si no hay una
// explicacion que agregue algo al titulo, devuelve '' y no se muestra nada:
// repetir el titulo con otras palabras solo hace la lista mas larga.
export function motivoLlano(motivo: string): string {
  if (motivo.startsWith('proyeccion_cruce_umbral')) {
    return 'El sistema vio que el aire iba a empeorar y ventiló antes';
  }
  if (motivo.startsWith('co2_sobre_umbral')) {
    return 'El aire ya estaba cargado, así que el sistema ventiló';
  }
  if (motivo.startsWith('co2_normalizado')) {
    return 'El aire ya se había limpiado, así que apagó la ventilación';
  }
  // override_manual: el titulo ya dice "manualmente"
  return '';
}

/** Lo mismo para eventos sin actuacion asociada. Nunca usa `mensaje`: trae ppm. */
export const EXPLICACION_EVENTO: Record<string, string> = {
  co2_critico: 'Con el aire así cuesta concentrarse; hay que ventilar cuanto antes',
  co2_alerta: 'Conviene ventilar para que no siga subiendo',
  prediccion_riesgo: 'El sistema vio que el aire iba a empeorar y se adelantó',
  temp_alerta: 'Si hay gente, el sistema ventila para refrescar el aula',
  hum_alerta: 'El sistema no controla la humedad: conviene revisar el aula',
};

// Los "tipo" de evento son slugs internos (co2_critico, prediccion_riesgo...)
// pensados para filtrar/loguear, no para leerse. Se muestran siempre
// traducidos; si aparece un tipo nuevo que no esta en el mapa, se cae al
// mensaje original en vez de mostrar el slug crudo.
export const ETIQUETA_EVENTO: Record<string, string> = {
  co2_critico: 'El aire llegó a nivel crítico',
  co2_alerta: 'El aire superó el nivel recomendado',
  normalizado: 'El aire volvió a la normalidad',
  prediccion_riesgo: 'El sistema detectó que el aire iba a empeorar',
  temp_alerta: 'La temperatura subió por encima de lo recomendado',
  hum_alerta: 'La humedad subió por encima de lo recomendado',
  modo_manual: 'Un equipo pasó a control manual',
  modo_automatico: 'Un equipo volvió a control automático',
};

export const NOMBRE_ACTUADOR: Record<string, string> = {
  ventilacion: 'la ventilación',
  iluminacion: 'las luces',
};

/** Frase en lenguaje llano para una actuacion: "El sistema encendió la ventilación". */
export function textoActuacion(actuador: string, accion: string, origen: string): string {
  const dispositivo = NOMBRE_ACTUADOR[actuador] ?? actuador;
  const verbo = accion === 'on' ? 'encendió' : 'apagó';
  if (origen === 'manual') {
    // la forma impersonal concuerda con el dispositivo: "se encendió la
    // ventilación" pero "se encendieron las luces"
    const plural = /^(las|los) /.test(dispositivo);
    const verboSe = plural ? (accion === 'on' ? 'encendieron' : 'apagaron') : verbo;
    return `Se ${verboSe} ${dispositivo} manualmente desde el panel`;
  }
  return `El sistema ${verbo} ${dispositivo}`;
}

// ------------------------------------------------ detalle de aula en llano

// Zonas de la barra del detalle de aula. La escala va de 400 (aire exterior)
// a 2200: mas ancha que CO2_MAX_ESCALA para que "muy cargado" tenga espacio y
// el marcador no quede pegado al borde en los picos. El ancho de cada zona es
// proporcional a su rango, asi la barra no exagera ni minimiza ninguna.
// Colores: los de la paleta; "bien" es el mismo verde con transparencia, para
// no introducir un verde nuevo.
export const BARRA_MIN = 400;
export const BARRA_MAX = 2200;

export type ZonaAire = { id: string; nombre: string; hasta: number; color: string; colorTexto: string };

export const ZONAS_AIRE: ZonaAire[] = [
  { id: 'limpio', nombre: 'limpio', hasta: 800, color: '#00A896', colorTexto: '#00A896' },
  { id: 'bien', nombre: 'bien', hasta: UMBRAL_ALERTA, color: '#00A89666', colorTexto: '#00A896' },
  { id: 'cargado', nombre: 'cargado', hasta: UMBRAL_CRITICO, color: '#D98324', colorTexto: '#D98324' },
  { id: 'muy_cargado', nombre: 'muy cargado', hasta: BARRA_MAX, color: '#C0392B', colorTexto: '#C0392B' },
];

export function zonaAire(co2: number): ZonaAire {
  return ZONAS_AIRE.find((z) => co2 < z.hasta) ?? ZONAS_AIRE[ZONAS_AIRE.length - 1];
}

/** Posicion (0-100) de un valor en la barra de zonas. */
export function posicionEnBarra(co2: number) {
  const pct = ((co2 - BARRA_MIN) / (BARRA_MAX - BARRA_MIN)) * 100;
  return Math.min(100, Math.max(0, pct));
}

// Juicios de "Ahora mismo": el numero solo no dice si esta bien o mal.
export function juicioTemperatura(c: number) {
  if (c < 18) return 'fría';
  if (c <= 26) return 'agradable';
  return 'calurosa';
}

export function juicioHumedad(pct: number) {
  if (pct < 40) return 'seca';
  if (pct <= 70) return 'normal';
  return 'húmeda';
}

export function juicioPersonas(personas: number, aforo: number) {
  if (aforo <= 0) return '';
  const r = personas / aforo;
  // por encima del aforo "casi lleno" se queda corto: es justo lo que hay
  // que ver
  if (r > 1) return 'sobre el aforo';
  if (r > 0.85) return 'casi lleno';
  if (r >= 0.5) return 'normal';
  return 'poca gente';
}
