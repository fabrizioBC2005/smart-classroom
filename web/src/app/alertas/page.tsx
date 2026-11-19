import { redirect } from 'next/navigation';

// La pantalla de alertas repetia lo que ya muestra la principal. Se
// reemplazo por /pendientes (solo lo que necesita a una persona).
export default function Page() {
  redirect('/pendientes');
}
