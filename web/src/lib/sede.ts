// Por ahora el sistema opera en UNA sola sede. Todas las pantallas filtran por
// este slug; cuando se sumen mas sedes basta con volver a poner un selector
// que cambie este valor. Se puede sobreescribir con NEXT_PUBLIC_SEDE.
export const SEDE_ACTUAL = process.env.NEXT_PUBLIC_SEDE ?? 'lima-norte';
