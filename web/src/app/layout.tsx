import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Contenido from "@/components/Contenido";
import Nav from "@/components/Nav";
import Asistente from "@/components/Asistente";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "Smart Classroom - Innova Schools",
  description: "Monitoreo ambiental y de ocupacion de aulas en tiempo real",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={inter.variable}>
      <body>
        <Nav />
        <Contenido>{children}</Contenido>
        <Asistente />
      </body>
    </html>
  );
}
