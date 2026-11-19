'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';
import Ayuda from '@/components/Ayuda';
import BarraZonas from '@/components/BarraZonas';
import Pronostico from '@/components/Pronostico';
import Semaforo from '@/components/Semaforo';
import Sensores from '@/components/Sensores';
import SerieClima, { COLOR_HUM, COLOR_TEMP } from '@/components/SerieClima';
import SerieCO2 from '@/components/SerieCO2';
import Timeline from '@/components/Timeline';
import { api } from '@/lib/api';
import {
  horasYMinutos, juicioHumedad, juicioPersonas, juicioTemperatura, n0, zonaAire,
} from '@/lib/formato';
import { useRealtime } from '@/lib/useRealtime';
import type { Actuacion, Aula, Evento, Lectura, ModoControl, Pendiente, PronosticoAula } from '@/lib/tipos';

type ActuadorId = 'ventilacion' | 'iluminacion';

const NOMBRE_DISPOSITIVO: Record<ActuadorId, string> = {
  ventilacion: 'Ventilador',
  iluminacion: 'Luces',
};

// Cuanto esperar por una confirmacion real antes de soltar el candado del
// toggle igual. Sin esto, un aula offline (o un comando que se pierde) lo
// dejaria trabado en "enviando" para siempre.
const TIMEOUT_CONFIRMACION_MS = 8000;

/** Actuacion mas reciente de ese actuador especifico, o undefined si no hay registro. */
function ultimaPorActuador(actuaciones: Actuacion[], actuador: ActuadorId): Actuacion | undefined {
  return actuaciones
    .filter((a) => a.actuador === actuador)
    .sort((a, b) => +new Date(b.ts) - +new Date(a.ts))[0];
}

export default function Page({ params }: { params: { id: string } }) {
  const aulaId = Number(params.id);

  const [aula, setAula] = useState<Aula | null>(null);
  const [lecturas, setLecturas] = useState<Lectura[]>([]);
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [actuaciones, setActuaciones] = useState<Actuacion[]>([]);
  const [pronostico, setPronostico] = useState<PronosticoAula | null>(null);
  const [avisos, setAvisos] = useState<Pendiente[]>([]);
  const [horas, setHoras] = useState(6);
  const [grafico, setGrafico] = useState<'co2' | 'clima'>('co2');
  const [verTodo, setVerTodo] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  // ts del hecho del timeline sobre el que esta el mouse, para resaltar el punto en el grafico.
  const [resaltadoTs, setResaltadoTs] = useState<string | null>(null);

  // Estado de los toggles de dispositivos:
  // - enviando: bloquea el boton mientras hay una orden en vuelo.
  // - pendiente: que accion se pidio, para mostrar "apagando..." en vez de mentir.
  // - confirmado: check transitorio cuando la orden ya quedo registrada.
  const [enviando, setEnviando] = useState<Partial<Record<ActuadorId, boolean>>>({});
  const [pendiente, setPendiente] = useState<Partial<Record<ActuadorId, 'on' | 'off'>>>({});
  const [confirmado, setConfirmado] = useState<Partial<Record<ActuadorId, boolean>>>({});
  // Candado SINCRONICO por ref. Esta es la causa raiz del BUG 1: un boolean de
  // React (state) se aplica en el siguiente render y se liberaba apenas
  // resolvia el POST, no cuando el cambio real llegaba; con telemetria
  // entrando seguido por WebSocket el panel se re-renderiza todo el tiempo, y
  // ese hueco entre "el click ocurrio" y "React ya pinto el boton
  // deshabilitado" era suficiente para que una segunda invocacion se colara
  // como una orden nueva e independiente. Un ref se lee/escribe al instante,
  // sin esperar al ciclo de render, y cierra esa ventana de verdad.
  const enviandoRef = useRef<Partial<Record<ActuadorId, boolean>>>({});
  // modo elegido en esta pagina mientras el PUT esta en vuelo (respuesta inmediata)
  const [modoLocal, setModoLocal] = useState<Partial<Record<ActuadorId, ModoControl>>>({});

  const { conectado, porAula } = useRealtime();
  const vivo = porAula[aulaId];

  const cargar = useCallback(async () => {
    const [a, l, e, ac] = await Promise.all([
      api.aula(aulaId),
      api.lecturas(aulaId, horas),
      api.eventosAula(aulaId),
      api.actuaciones(aulaId),
    ]);
    setAula(a);
    setLecturas(l);
    setEventos(e);
    setActuaciones(ac);
    api.pronostico(aulaId).then(setPronostico).catch(() => undefined);
    api.pendientes()
      .then((d) => setAvisos(d.pendientes.filter((p) => p.aula_id === aulaId)))
      .catch(() => undefined);
  }, [aulaId, horas]);

  useEffect(() => {
    cargar().catch(() => undefined);
    const t = setInterval(() => cargar().catch(() => undefined), 30000);
    return () => clearInterval(t);
  }, [cargar]);

  const ultima = lecturas.at(-1);
  const co2 = vivo?.co2_ppm ?? ultima?.co2_ppm ?? null;
  const temp = vivo?.temp_c ?? ultima?.temp_c ?? null;
  const hum = vivo?.hum_pct ?? ultima?.hum_pct ?? null;
  const lux = vivo?.lux ?? ultima?.lux ?? null;
  const ocup = vivo?.ocupantes ?? ultima?.ocupantes_conteo ?? ultima?.ocupantes_estimado ?? null;
  // El indice de habitabilidad sigue existiendo (backend y reporte de
  // cumplimiento) pero no se muestra aca: la barra de zonas dice lo mismo
  // sin obligar a interpretar un numero.
  const contexto = co2 === null ? null : contextoAire(lecturas, co2, vivo?.pendiente_ppm_min ?? null);
  const estado = vivo?.estado ?? ultima?.estado ?? 'sin_datos';

  // "acaba de llegar un dato": destella brevemente los valores en pantalla
  // cuando cambia el ts del ultimo mensaje por WebSocket.
  const [flash, setFlash] = useState(false);
  const ultimoTsRef = useRef<string | null>(null);
  useEffect(() => {
    if (!vivo || ultimoTsRef.current === vivo.ts) return;
    ultimoTsRef.current = vivo.ts;
    setFlash(true);
    const t = setTimeout(() => setFlash(false), 900);
    return () => clearTimeout(t);
  }, [vivo]);

  // BUG 2 - una sola fuente de verdad para lo que se muestra: el estado de la
  // ventilacion es SIEMPRE el real reportado por el worker (vivo.ventilacion_on),
  // nunca la ultima orden enviada — la orden y el estado real pueden divergir
  // por varios segundos mientras el rele conmuta y el ESP32 reporta de vuelta.
  // Solo se recurre a la ultima actuacion cuando todavia no llego ningun dato
  // en vivo (recien se entro a la pagina, o el aula esta offline), porque ahi
  // no hay estado real disponible y una orden pasada es la mejor pista. La
  // iluminacion no tiene sensor de estado en el firmware: el worker reporta
  // el estado que ordeno (vivo.iluminacion_on); sin dato en vivo se infiere
  // de la ultima actuacion registrada.
  const ultimaVent = ultimaPorActuador(actuaciones, 'ventilacion');
  const ultimaLuz = ultimaPorActuador(actuaciones, 'iluminacion');
  // el worker es la fuente de verdad en vivo; si no hay dato, lo guardado en la base
  const modoDe = (a: ActuadorId): ModoControl =>
    modoLocal[a] ?? vivo?.modos?.[a] ?? (a === 'ventilacion' ? aula?.modo_ventilacion : aula?.modo_iluminacion) ?? 'automatico';

  const cambiarModo = (actuador: ActuadorId, modo: ModoControl) => {
    if (modoDe(actuador) === modo) return;
    setModoLocal((p) => ({ ...p, [actuador]: modo }));
    setAviso(null);
    api
      .modo(aulaId, actuador, modo)
      .then((a) => setAula(a))
      .catch((e) => {
        setAviso(e instanceof Error ? e.message : 'No se pudo cambiar el modo');
        soltarModo(actuador);
      });
  };

  const soltarModo = (actuador: ActuadorId) =>
    setModoLocal((p) => {
      const n = { ...p };
      delete n[actuador];
      return n;
    });

  // la eleccion local se suelta recien cuando el worker confirma el modo en
  // vivo; si se soltara al responder el PUT, el ultimo dato en vivo (todavia
  // con el modo anterior) la pisaria unos segundos
  useEffect(() => {
    (Object.keys(modoLocal) as ActuadorId[]).forEach((a) => {
      if (vivo?.modos?.[a] === modoLocal[a]) soltarModo(a);
    });
  }, [vivo, modoLocal]);

  const dispositivos: Array<{ actuador: ActuadorId; on: boolean | null; origen: string | null }> = [
    {
      actuador: 'ventilacion',
      on: vivo ? vivo.ventilacion_on : ultimaVent ? ultimaVent.accion === 'on' : null,
      origen: ultimaVent?.origen ?? null,
    },
    {
      actuador: 'iluminacion',
      on:
        vivo && typeof vivo.iluminacion_on === 'boolean'
          ? vivo.iluminacion_on
          : ultimaLuz
            ? ultimaLuz.accion === 'on'
            : null,
      origen: ultimaLuz?.origen ?? null,
    },
  ];

  const liberar = useCallback((actuador: ActuadorId, exito: boolean) => {
    enviandoRef.current[actuador] = false;
    setEnviando((p) => ({ ...p, [actuador]: false }));
    setPendiente((p) => {
      const n = { ...p };
      delete n[actuador];
      return n;
    });
    if (exito) {
      setConfirmado((p) => ({ ...p, [actuador]: true }));
      setTimeout(() => setConfirmado((p) => ({ ...p, [actuador]: false })), 2000);
    }
  }, []);

  // Suelta el candado en cuanto el dato real (websocket, o el registro de
  // actuaciones despues del refresco de cargar()) confirma la accion pedida.
  // Esto es lo que libera de verdad; el timeout dentro de enviar() es solo la
  // red de seguridad para el caso offline.
  useEffect(() => {
    (Object.keys(pendiente) as ActuadorId[]).forEach((actuador) => {
      const accionPedida = pendiente[actuador];
      if (!accionPedida) return;
      const enVivo =
        actuador === 'ventilacion' ? vivo?.ventilacion_on : vivo?.iluminacion_on;
      const confirmadoEnVivo = typeof enVivo === 'boolean' && enVivo === (accionPedida === 'on');
      const confirmadoPorRegistro = ultimaPorActuador(actuaciones, actuador)?.accion === accionPedida;
      if (confirmadoEnVivo || confirmadoPorRegistro) {
        liberar(actuador, true);
      }
    });
  }, [vivo, actuaciones, pendiente, liberar]);

  const enviar = (actuador: ActuadorId, accion: 'on' | 'off') => {
    // Idempotencia: si el estado real ya es el pedido, no hay nada que enviar.
    const actual = dispositivos.find((d) => d.actuador === actuador)?.on;
    if (actual === (accion === 'on')) return;

    // Candado sincronico: si ya hay una orden de este dispositivo en vuelo, se ignora el click.
    if (enviandoRef.current[actuador]) return;
    enviandoRef.current[actuador] = true;

    setEnviando((p) => ({ ...p, [actuador]: true }));
    setPendiente((p) => ({ ...p, [actuador]: accion }));
    setAviso(null);

    api
      .comando(aulaId, actuador, accion)
      .then(() => {
        setTimeout(() => cargar().catch(() => undefined), 800);
        setTimeout(() => {
          if (enviandoRef.current[actuador]) liberar(actuador, false);
        }, TIMEOUT_CONFIRMACION_MS);
      })
      .catch((e) => {
        setAviso(e instanceof Error ? e.message : 'No se pudo enviar el comando');
        liberar(actuador, false);
      });
  };

  function estadoTexto(actuador: ActuadorId, on: boolean | null): string {
    const accionPedida = pendiente[actuador];
    if (accionPedida) return accionPedida === 'on' ? 'Encendiendo…' : 'Apagando…';
    if (on === null) return 'Sin registro';
    return on ? 'Encendido' : 'Apagado';
  }

  // el pronostico esta en prueba: solo se muestra cuando ya tiene algo que
  // decir, no el mensaje de "todavia estamos aprendiendo"
  const hayPronostico = !!pronostico && !pronostico.aprendiendo && !!vivo?.pronostico;
  const zona = co2 !== null ? zonaAire(co2) : null;
  const luzBaja = lux !== null && lux < 300;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/" className="text-sm text-teal hover:underline">
            ← Volver a las aulas
          </Link>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            Aula {aula?.codigo ?? aulaId}
          </h1>
          <p className="mt-0.5 text-sm text-muted">{aula ? capitalizar(aula.nivel) : '—'}</p>
        </div>
        <div className="flex items-center gap-3">
          <Semaforo estado={estado} />
          <span
            className={`pill ${
              conectado ? 'border-sea/30 bg-sea/10 text-sea' : 'border-slate-200 bg-slate-100 text-slate-500'
            }`}
          >
            <span className={`h-1.5 w-1.5 rounded-full bg-current ${conectado ? 'latido' : ''}`} />
            {conectado ? 'En vivo' : 'Reconectando'}
          </span>
        </div>
      </div>

      {/* 1. lo primero que hay que saber: como esta el aula, en una frase y en
             lo que mide cada sensor, cada valor con su juicio al lado */}
      <div className="card grid gap-5 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] lg:items-center lg:p-5">
        <BarraZonas co2={co2} contexto={contexto} pulso={flash} />
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Valor
            icono="aire" etiqueta="Aire" pulso={flash}
            valor={co2 !== null ? `${n0(co2)} ppm` : '—'}
            juicio={zona?.nombre}
            color={zona?.colorTexto}
          />
          <Valor
            icono="temp" etiqueta="Temperatura" pulso={flash}
            valor={temp !== null ? `${temp.toFixed(1)} °C` : '—'}
            juicio={temp !== null ? juicioTemperatura(temp) : undefined}
            alerta={temp !== null && temp > 26}
          />
          <Valor
            icono="humedad" etiqueta="Humedad" pulso={flash}
            valor={hum !== null ? `${Math.round(hum)} %` : '—'}
            juicio={hum !== null ? juicioHumedad(hum) : undefined}
            alerta={hum !== null && hum > 70}
          />
          <Valor
            icono="luz" etiqueta="Luz" pulso={flash}
            valor={lux !== null ? `${n0(lux)} lux` : '—'}
            juicio={dispositivos[1].on ? 'luces encendidas' : lux !== null ? (luzBaja ? 'poca luz' : 'buena') : undefined}
            alerta={luzBaja && !dispositivos[1].on}
          />
          <Valor
            icono="personas" etiqueta="Personas" pulso={flash}
            valor={ocup !== null ? `${Math.round(ocup)}${aula ? ` de ${aula.aforo_nominal}` : ''}` : '—'}
            juicio={ocup !== null && aula ? juicioPersonas(ocup, aula.aforo_nominal) || undefined : undefined}
          />
        </ul>
      </div>

      {/* 2. solo si hay un problema de fondo que alguien tiene que resolver */}
      {avisos.map((p) => (
        <div
          key={p.clave}
          className={`card flex flex-col gap-1 p-4 sm:flex-row sm:items-center sm:gap-4 ${
            p.prioridad === 'alta' ? 'border-danger/40 bg-danger/5' : 'border-amber/40 bg-amber/5'
          }`}
        >
          <span
            className={`pill w-fit shrink-0 ${
              p.prioridad === 'alta'
                ? 'border-danger/30 bg-danger/10 text-danger'
                : 'border-amber/30 bg-amber/10 text-amber'
            }`}
          >
            Revisar
          </span>
          <p className="text-sm text-ink">
            <span className="font-semibold">{p.titulo}.</span> {p.accion}{' '}
            <Ayuda texto={p.detalle} />
          </p>
        </div>
      ))}

      {/* en movil una sola columna con el grafico primero (order-1/2) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <div className="order-2 space-y-4 lg:order-1">
          <div className="card p-4">
            <h3 className="text-sm font-semibold">Equipos del aula</h3>
            <div className="mt-3 space-y-2">
              {dispositivos.map((d) => {
                const ocupado = !!enviando[d.actuador];
                const modo = modoDe(d.actuador);
                const auto = modo === 'automatico';
                return (
                  <div key={d.actuador} className="rounded-lg bg-mist px-3 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{NOMBRE_DISPOSITIVO[d.actuador]}</p>
                      <p className="text-xs text-muted">
                        {estadoTexto(d.actuador, d.on)}
                        {!pendiente[d.actuador] && confirmado[d.actuador] && (
                          <span className="ml-1 font-medium text-sea">· listo ✓</span>
                        )}
                        {!pendiente[d.actuador] && !confirmado[d.actuador] && (
                          <span className="ml-1">· {auto ? 'lo maneja el sistema' : 'lo manejas tú'}</span>
                        )}
                      </p>
                    </div>
                    <button
                      role="switch"
                      aria-checked={!!d.on}
                      aria-busy={ocupado}
                      aria-label={`${NOMBRE_DISPOSITIVO[d.actuador]}: ${d.on ? 'encendido' : 'apagado'}`}
                      onClick={() => enviar(d.actuador, d.on ? 'off' : 'on')}
                      // en automatico el interruptor solo muestra el estado: para
                      // manejarlo hay que pasar a manual (asi nadie pelea con el sistema)
                      disabled={ocupado || auto}
                      title={auto ? 'Cambia a Manual para encender o apagar' : undefined}
                      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
                        ocupado ? 'disabled:cursor-wait' : 'disabled:cursor-not-allowed'
                      } ${d.on ? 'bg-teal' : 'bg-slate-300'}`}
                    >
                      <span
                        className={`absolute left-0 top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform ${
                          d.on ? 'translate-x-[22px]' : 'translate-x-0.5'
                        }`}
                      />
                    </button>
                  </div>
                  {/* quien manda: el sistema o la persona */}
                  <div
                    role="radiogroup"
                    aria-label={`Modo de ${NOMBRE_DISPOSITIVO[d.actuador].toLowerCase()}`}
                    className="mt-2 grid grid-cols-2 gap-1 rounded-md bg-white p-0.5"
                  >
                    {([['automatico', 'Automático'], ['manual', 'Manual']] as const).map(([id, nombre]) => (
                      <button
                        key={id}
                        role="radio"
                        aria-checked={modo === id}
                        onClick={() => cambiarModo(d.actuador, id)}
                        className={`rounded px-2 py-1 text-xs font-medium transition ${
                          modo === id ? 'bg-deep text-white' : 'text-muted hover:text-ink'
                        }`}
                      >
                        {nombre}
                      </button>
                    ))}
                  </div>
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-muted">
              <span className="font-medium text-ink">Automático:</span> el sistema lo enciende y apaga solo.{' '}
              <span className="font-medium text-ink">Manual:</span> solo tú lo manejas con el interruptor.
            </p>
            {aviso && <p className="mt-2 break-all text-xs text-danger">{aviso}</p>}
          </div>

          {hayPronostico && (
            <Pronostico
              datos={pronostico}
              vivo={vivo?.pronostico}
              co2={co2}
              ventilando={dispositivos[0].on === true}
            />
          )}

          {/* para mantenimiento: cerrado por defecto */}
          {aula && (
            <details className="card group p-4">
              <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold">
                Sensores instalados
                <svg className="h-4 w-4 text-muted transition group-open:rotate-180" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                  <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </summary>
              <div className="mt-3 [&>.card]:border-0 [&>.card]:p-0 [&>.card]:shadow-none">
                <Sensores lecturas={lecturas} instrumentada={aula.instrumentada} />
              </div>
            </details>
          )}
        </div>

        <div className="order-1 space-y-4 lg:order-2">
          {/* un solo grafico con pestañas: CO2 o temperatura/humedad */}
          <div className="card p-4">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex w-fit gap-1 rounded-lg bg-mist p-1" role="tablist">
                {([['co2', 'Aire (CO₂)'], ['clima', 'Temperatura y humedad']] as const).map(([id, nombre]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={grafico === id}
                    onClick={() => setGrafico(id)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                      grafico === id ? 'bg-white text-ink shadow-card' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {nombre}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                {[3, 6, 24, 72].map((h) => (
                  <button
                    key={h}
                    onClick={() => setHoras(h)}
                    className={`flex min-h-[44px] items-center justify-center rounded-md px-3 text-xs transition sm:min-h-0 sm:px-2.5 sm:py-1 ${
                      horas === h ? 'bg-deep font-semibold text-white' : 'bg-mist text-muted hover:bg-line'
                    }`}
                  >
                    {h}h
                  </button>
                ))}
              </div>
            </div>
            {grafico === 'co2' ? (
              <SerieCO2 datos={lecturas} resaltadoTs={resaltadoTs} />
            ) : (
              <>
                <div className="mb-2 flex flex-wrap items-center gap-4 text-xs">
                  <span className="flex items-center gap-1.5">
                    <span className="h-0.5 w-4 rounded" style={{ background: COLOR_TEMP }} />
                    <span className="text-muted">Temperatura</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-0.5 w-4 rounded" style={{ background: COLOR_HUM }} />
                    <span className="text-muted">Humedad</span>
                  </span>
                </div>
                <SerieClima datos={lecturas} />
              </>
            )}
            <p className="mt-2 text-xs text-muted">
              {grafico === 'co2'
                ? 'Sube cuando el aula se llena y baja al ventilar. Sobre 1000 ppm el sistema ventila solo.'
                : 'Sobre 26 °C con gente adentro, el sistema ventila solo.'}
            </p>
          </div>

          <div className="card p-4">
            <Timeline
              eventos={eventos}
              actuaciones={actuaciones}
              onHover={setResaltadoTs}
              limite={verTodo ? 18 : 6}
            />
            <button
              onClick={() => setVerTodo((v) => !v)}
              className="mt-2 text-xs font-medium text-teal hover:underline"
            >
              {verTodo ? 'Ver menos' : 'Ver más sucesos'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const capitalizar = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

// Debajo de este cambio por minuto el aire se considera estable. Es el mismo
// corte que usa tendencia() en formato.ts, para que las pantallas no se
// contradigan.
const PENDIENTE_ESTABLE = 3;

// Cuantas lecturas usar para estimar la pendiente cuando todavia no llego
// telemetria en vivo (recien se abrio la pagina o el aula esta offline). Por
// cantidad y no por minutos: con una ventana de 5 min, el simulador acelerado
// alcanzaba a bajar y volver a subir dentro de ella y la pendiente salia al
// reves ("mejorando" con el aire subiendo). 6 lecturas = ~1.5 min con el
// hardware real (una cada ~15 s).
const LECTURAS_PENDIENTE = 6;

// Al buscar desde cuando viene bajando, una subida menor a esto entre dos
// lecturas es ruido del sensor y no corta la racha.
const TOLERANCIA_RUIDO = 15;

function duracion(ms: number) {
  const min = Math.floor(ms / 60_000);
  if (min < 1) return 'menos de un minuto';
  if (min === 1) return '1 minuto';
  if (min < 60) return `${min} minutos`;
  return horasYMinutos(min);
}

/**
 * Linea de contexto bajo el estado del aire: cuanto lleva asi y hacia donde va.
 * - subiendo: tiempo desde que entro a la zona actual ("lleva 14 minutos así")
 * - bajando: tiempo desde el ultimo pico ("lleva 6 minutos mejorando")
 * - estable: sin tiempo, solo "se mantiene estable"
 * Si la racha empieza antes de lo cargado en el grafico, se dice "más de".
 */
function contextoAire(lecturas: Lectura[], co2: number, pendienteVivo: number | null): string {
  const serie = lecturas
    .filter((l): l is Lectura & { co2_ppm: number } => l.co2_ppm !== null)
    .sort((a, b) => +new Date(a.ts) - +new Date(b.ts));
  const ahora = Date.now();

  let pendiente = pendienteVivo;
  if (pendiente === null) {
    const ventana = serie.slice(-LECTURAS_PENDIENTE);
    if (ventana.length >= 2) {
      const [p, u] = [ventana[0], ventana[ventana.length - 1]];
      const min = (+new Date(u.ts) - +new Date(p.ts)) / 60_000;
      pendiente = min > 0 ? (u.co2_ppm - p.co2_ppm) / min : 0;
    } else {
      pendiente = 0;
    }
  }

  if (Math.abs(pendiente) <= PENDIENTE_ESTABLE || serie.length === 0) return 'Se mantiene estable';

  const sigue = (i: number) =>
    pendiente! > 0
      ? zonaAire(serie[i].co2_ppm).id === zonaAire(co2).id
      : i === serie.length - 1 || serie[i].co2_ppm >= serie[i + 1].co2_ppm - TOLERANCIA_RUIDO;
  let i = serie.length - 1;
  while (i > 0 && sigue(i - 1)) i--;
  const desdeElInicio = i === 0;
  const tiempo = `${desdeElInicio ? 'más de ' : ''}${duracion(ahora - +new Date(serie[i].ts))}`;

  return pendiente > 0 ? `Lleva ${tiempo} así y sigue empeorando` : `Lleva ${tiempo} mejorando`;
}

type TipoIcono = 'aire' | 'temp' | 'humedad' | 'luz' | 'personas';

function Valor({
  icono, etiqueta, valor, juicio, color, alerta = false, pulso,
}: {
  icono: TipoIcono; etiqueta: string; valor: string; juicio?: string;
  color?: string; alerta?: boolean; pulso?: boolean;
}) {
  return (
    <li className={`min-w-0 rounded-lg px-3 py-2.5 ${alerta ? 'bg-amber/10' : 'bg-mist'}`}>
      <p className="flex items-center gap-1.5 text-xs text-muted">
        <IconoAhora tipo={icono} />
        {etiqueta}
      </p>
      <p className={`mt-1 truncate text-base font-semibold tabular-nums transition-colors duration-500 ${
        alerta ? 'text-amber' : 'text-ink'} ${pulso ? 'destello' : ''}`}>
        {valor}
      </p>
      {juicio && (
        <p className={`truncate text-xs ${alerta ? 'text-amber' : 'text-muted'}`} style={color ? { color } : undefined}>
          {juicio}
        </p>
      )}
    </li>
  );
}

function IconoAhora({ tipo }: { tipo: TipoIcono }) {
  const trazos: Record<typeof tipo, React.ReactNode> = {
    aire: (
      <>
        <path d="M3 8h11a3 3 0 1 0-3-3" />
        <path d="M3 12h16a3 3 0 1 1-3 3" />
        <path d="M3 16h7" />
      </>
    ),
    temp: <path d="M14 14.76V4a2 2 0 1 0-4 0v10.76a4 4 0 1 0 4 0z" />,
    humedad: <path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z" />,
    luz: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
    personas: (
      <>
        <circle cx="9" cy="8" r="3.5" />
        <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
        <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8" />
        <path d="M18.5 20a6.5 6.5 0 0 0-3-5.5" />
      </>
    ),
  };
  return (
    <svg
      className="h-3.5 w-3.5 shrink-0 text-teal"
      viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    >
      {trazos[tipo]}
    </svg>
  );
}
