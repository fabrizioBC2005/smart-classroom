'use client';

import { useEffect, useRef, useState } from 'react';
import { WS } from './api';
import type { MsgRealtime, MsgTelemetria } from './tipos';

/**
 * Suscripcion al WebSocket de la API con reconexion automatica.
 * Devuelve el ultimo snapshot por aula y el estado de la conexion.
 */
export function useRealtime(onMensaje?: (m: MsgRealtime) => void) {
  const [conectado, setConectado] = useState(false);
  const [porAula, setPorAula] = useState<Record<number, MsgTelemetria>>({});
  const cbRef = useRef(onMensaje);
  cbRef.current = onMensaje;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let ping: ReturnType<typeof setInterval> | null = null;
    let reintento: ReturnType<typeof setTimeout> | null = null;
    let cerrado = false;

    const conectar = () => {
      if (cerrado) return;
      try {
        ws = new WebSocket(`${WS}/ws`);
      } catch {
        reintento = setTimeout(conectar, 3000);
        return;
      }

      ws.onopen = () => {
        setConectado(true);
        ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('ping'), 25000);
      };

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data) as MsgRealtime;
          if (msg.tipo === 'telemetria') {
            setPorAula((prev) => ({ ...prev, [msg.aula_id]: msg }));
          }
          cbRef.current?.(msg);
        } catch {
          /* mensaje no valido: se ignora */
        }
      };

      ws.onclose = () => {
        setConectado(false);
        if (ping) clearInterval(ping);
        if (!cerrado) reintento = setTimeout(conectar, 3000);
      };

      ws.onerror = () => ws?.close();
    };

    conectar();
    return () => {
      cerrado = true;
      if (ping) clearInterval(ping);
      if (reintento) clearTimeout(reintento);
      ws?.close();
    };
  }, []);

  return { conectado, porAula };
}
