"use client";

// El hueco a la izquierda es el ancho
// del sidebar contraido por defecto, ancho expandido si esta fijado. Nav
// publica ese estado como <html data-sidebar="fijo">, asi que aqui no hace
// falta leer localStorage ni escuchar eventos.
export default function Contenido({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-[1480px] px-4 py-6 pb-24 transition-[padding] duration-300 sm:px-6 md:py-8 md:pb-8 md:pl-[100px] md:pr-8 [html[data-sidebar=fijo]_&]:md:pl-[272px]">
      {children}
    </main>
  );
}
