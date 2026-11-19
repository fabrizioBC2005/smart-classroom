"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

// Escritorio: sidebar que se expande al pasar el mouse y se contrae al
// salir. El boton de pin lo deja fijo abierto para quien prefiera eso.
// Movil: barra inferior, que es donde el pulgar llega sin esfuerzo.
const LINKS = [
  { href: "/", label: "Aulas", icono: "grid" },
  { href: "/pendientes", label: "Pendientes", icono: "campana" },
  { href: "/reporte", label: "Cumplimiento", icono: "check" },
] as const;

const CLAVE = "sc:sidebar-fijo";

// cuantos pendientes hay, para el numerito del menu. Se refresca cada 30 s y
// cuando la pagina de pendientes avisa que algo se resolvio.
function useCantidadPendientes() {
  const [n, setN] = useState(0);
  useEffect(() => {
    let vivo = true;
    const cargar = () =>
      api.pendientes().then((d) => vivo && setN(d.pendientes.length)).catch(() => undefined);
    cargar();
    const t = setInterval(cargar, 30_000);
    window.addEventListener("pendientes-cambiaron", cargar);
    return () => {
      vivo = false;
      clearInterval(t);
      window.removeEventListener("pendientes-cambiaron", cargar);
    };
  }, []);
  return n;
}

function Numerito({ n, className = "" }: { n: number; className?: string }) {
  if (n <= 0) return null;
  return (
    <span
      aria-label={`${n} pendientes`}
      className={`grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[10px] font-bold leading-none text-white ${className}`}
    >
      {n > 9 ? "9+" : n}
    </span>
  );
}

function Icono({ tipo, className = "" }: { tipo: string; className?: string }) {
  const comun = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  if (tipo === "grid") {
    return (
      <svg {...comun}>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </svg>
    );
  }
  if (tipo === "campana") {
    return (
      <svg {...comun}>
        <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.7 21a2 2 0 0 1-3.4 0" />
      </svg>
    );
  }
  if (tipo === "pin") {
    return (
      <svg {...comun}>
        <path d="M12 17v5" />
        <path d="M9 10.76V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v5.76a2 2 0 0 0 .59 1.42l1.12 1.11a1 1 0 0 1-.71 1.71H7a1 1 0 0 1-.71-1.71l1.12-1.11A2 2 0 0 0 9 10.76z" />
      </svg>
    );
  }
  return (
    <svg {...comun}>
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  );
}

export default function Nav() {
  const path = usePathname();
  const [fijo, setFijo] = useState(false);
  const pendientes = useCantidadPendientes();
  const [hover, setHover] = useState(false);
  const [montado, setMontado] = useState(false);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  // localStorage se lee tras el montaje: el servidor no lo conoce y
  // renderizaria un ancho distinto, provocando un salto visible.
  useEffect(() => {
    setFijo(localStorage.getItem(CLAVE) === "1");
    setMontado(true);
  }, []);

  // el contenido se corre segun este atributo (ver Contenido.tsx)
  useEffect(() => {
    if (fijo) document.documentElement.dataset.sidebar = "fijo";
    else delete document.documentElement.dataset.sidebar;
  }, [fijo]);

  const abierto = fijo || hover;

  const entrar = () => {
    if (temporizador.current) clearTimeout(temporizador.current);
    setHover(true);
  };

  // pequeno retardo al salir: evita que se cierre de golpe si el mouse
  // roza el borde de camino a otra cosa
  const salir = () => {
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => {
      setHover(false);
    }, 180);
  };

  const alternarFijo = () => {
    setFijo((v) => {
      localStorage.setItem(CLAVE, v ? "0" : "1");
      return !v;
    });
  };

  useEffect(() => () => {
    if (temporizador.current) clearTimeout(temporizador.current);
  }, []);

  const activo = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <>
      <aside
        onMouseEnter={entrar}
        onMouseLeave={salir}
        className={`fixed left-0 top-0 z-30 hidden h-screen flex-col overflow-hidden border-r border-white/10 bg-deep md:flex ${
          montado ? "transition-[width] duration-300 ease-out" : ""
        } ${abierto ? "w-60" : "w-[68px]"} ${hover && !fijo ? "shadow-2xl" : ""}`}
      >
        <div className="flex items-center gap-2.5 px-4 py-5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sea text-sm font-bold text-white">
            SC
          </span>
          <span
            className={`whitespace-nowrap text-[15px] font-semibold tracking-tight text-white transition-opacity duration-200 ${
              abierto ? "opacity-100" : "opacity-0"
            }`}
          >
            Smart Classroom
          </span>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              title={abierto ? undefined : l.label}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                activo(l.href)
                  ? "bg-white/15 font-semibold text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span className="relative shrink-0">
                <Icono tipo={l.icono} className="h-[18px] w-[18px]" />
                {l.href === "/pendientes" && !abierto && (
                  <Numerito n={pendientes} className="absolute -right-2.5 -top-2" />
                )}
              </span>
              <span
                className={`whitespace-nowrap transition-opacity duration-200 ${
                  abierto ? "opacity-100" : "opacity-0"
                }`}
              >
                {l.label}
              </span>
              {l.href === "/pendientes" && abierto && <Numerito n={pendientes} className="ml-auto" />}
            </Link>
          ))}
        </nav>

        <div className="border-t border-white/10 px-3 py-3">
          <button
            onClick={alternarFijo}
            aria-label={fijo ? "Soltar menu" : "Fijar menu abierto"}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition hover:bg-white/10 ${
              fijo ? "text-sea" : "text-white/50 hover:text-white"
            }`}
          >
            <Icono tipo="pin" className="h-[18px] w-[18px] shrink-0" />
            <span
              className={`whitespace-nowrap transition-opacity duration-200 ${
                abierto ? "opacity-100" : "opacity-0"
              }`}
            >
              {fijo ? "Menu fijo" : "Fijar menu"}
            </span>
          </button>
        </div>
      </aside>

      {/* ---------- movil ---------- */}
      <header className="sticky top-0 z-30 flex items-center gap-2.5 border-b border-white/10 bg-deep px-4 py-3 md:hidden">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-sea text-sm font-bold text-white">
          SC
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-white">
          Smart Classroom
        </span>
      </header>

      <nav className="fixed bottom-0 left-0 right-0 z-30 grid grid-cols-3 border-t border-line bg-white md:hidden">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`flex min-h-[58px] flex-col items-center justify-center gap-1 text-[11px] transition ${
              activo(l.href) ? "font-semibold text-teal" : "text-muted"
            }`}
          >
            <span className="relative">
              <Icono tipo={l.icono} className="h-5 w-5" />
              {l.href === "/pendientes" && (
                <Numerito n={pendientes} className="absolute -right-2.5 -top-1.5" />
              )}
            </span>
            {l.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
