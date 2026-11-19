Diseña un PROTOTIPO INTERACTIVO completo, en español, de "Smart Classroom": un panel web que monitorea la calidad del aire (CO₂), la temperatura, la humedad y la ocupación de las aulas de un colegio, y que enciende la ventilación solo cuando hace falta. Quien lo usa es personal del colegio (dirección, coordinación, mantenimiento), NO técnicos: todo tiene que entenderse sin saber qué es el CO₂.

Quiero que se pueda navegar por TODAS las pantallas haciendo clic, en un orden claro, con un estilo limpio, sereno y profesional. Genera las versiones de escritorio (1440 px de ancho) y de móvil (390 px de ancho), conectadas como prototipo.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. SISTEMA VISUAL (respétalo exactamente)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Colores (usa solo estos):
- Tinta (texto principal): #13272E
- Azul profundo (sidebar, botones activos): #0B3C49
- Teal (enlaces, línea del gráfico, iconos): #028090
- Verde mar (bien / limpio / funcionando): #00A896
- Ámbar (alerta / cargado): #D98324
- Rojo (crítico / muy cargado): #C0392B
- Gris neutro (sin datos / sin señal): #94A3B8
- Bruma (fondos de filas y chips): #F1F6F6
- Línea (bordes y separadores): #DDE7E8
- Texto secundario: #5C7178
- Fondo de página: #F7FAFA; tarjetas en blanco #FFFFFF

Los colores de estado siempre significan lo mismo en todas las pantallas: verde = bien, ámbar = alerta, rojo = crítico, gris = sin datos. Para la zona "bien" de la barra de aire usa el mismo verde al 40 % de opacidad (no inventes otro verde).

Tipografía: sans-serif del sistema (Inter si no hay otra). Títulos de página 24 px bold con tracking ajustado; títulos de tarjeta 14 px semibold; texto 14 px; secundario 12 px; etiquetas de sección 10 px en MAYÚSCULAS con tracking amplio. Los números con cifras tabulares.

Forma: tarjetas blancas con radio 12 px, borde de 0.5–1 px #DDE7E8 y sombra muy suave. Chips y pastillas con radio completo. Espaciado base de 4 px; separación entre tarjetas de 16 px.

Iconos: de línea, trazo de 1.8–2 px, puntas redondeadas (estilo Lucide). Siempre acompañados de texto.

Tono de los textos: lenguaje llano, frases cortas, nada de jerga. Prohibido en las pantallas de Alertas y en el panel izquierdo del detalle de aula: "ppm", "umbral", promedios, índices numéricos y horas exactas como "01:29 a. m.". Usa tiempos relativos ("hace 8 min") y conteos en palabras ("seis veces").

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. NAVEGACIÓN GLOBAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Escritorio: sidebar fijo a la izquierda, fondo #0B3C49.
- Contraído mide 68 px y muestra solo iconos; al pasar el mouse se expande a 240 px con animación suave (300 ms) y muestra los textos.
- Arriba: logo cuadrado verde mar con las letras "SC" y el texto "Smart Classroom".
- Tres enlaces, en este orden: "Aulas" (icono cuadrícula), "Alertas" (icono campana), "Cumplimiento" (icono check en caja). El activo lleva fondo blanco al 15 % y texto en negrita.
- Abajo, separado por una línea: botón "Fijar menú" (icono chincheta) que lo deja expandido.

Móvil: cabecera superior azul profundo con el logo "SC" y "Smart Classroom"; barra de navegación inferior blanca con los mismos tres destinos (icono + texto, 58 px de alto). El activo en teal y negrita.

RECORRIDO GUIADO (para presentar el proyecto): una pastilla flotante abajo a la derecha (en móvil, encima de la barra inferior) con "Paso 2 de 4 · Detalle del aula" y dos botones "← Anterior" / "Siguiente →". El orden es:
  1. Aulas → 2. Detalle del aula → 3. Alertas → 4. Cumplimiento.
Se puede cerrar con una ✕ y la navegación normal sigue funcionando.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. PANTALLA 1 — AULAS (inicio)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pregunta que responde: "¿qué aulas necesitan atención ahora?".

Cabecera: título "Estado de las aulas". A la derecha, una pastilla verde con un punto que late suavemente: "Datos en vivo", y un selector "Todas las sedes".

Banner de resumen (borde y fondo rojos suaves, icono de triángulo de aviso):
- Título: "4 aulas necesitan atención"
- Detalle: "El sistema ya ventila 3 de 4; en el resto la ventilación está apagada."
(Variante cuando todo está bien: fondo verde suave, icono de check en círculo, "Todas las aulas están en condiciones adecuadas".)

Chips-contador que además filtran (número grande arriba, texto pequeño abajo; el activo en fondo azul profundo con texto blanco):
  11 todas · 2 críticas (rojo) · 2 en alerta (ámbar) · 4 normales (verde) · 3 sin sensores (gris)
Al tocar un chip, la cuadrícula muestra solo esas aulas. En móvil los chips se desplazan en horizontal.

Cuadrícula de tarjetas de aula (4 columnas en escritorio, 2 en tablet, 1 en móvil), ordenadas de la más urgente a la menos. Cada tarjeta tiene, de arriba abajo:
- punto de color de estado + "Aula 302"
- un número grande (32 px) en el color del estado
- debajo, qué significa, en minúsculas
- una línea de acción con icono, en el color del estado
Las críticas llevan el borde rojo suave. Las "sin sensores" van atenuadas al 60 %. Al pasar el mouse, la tarjeta se eleva 2 px. TODA la tarjeta es clicable y lleva al detalle del aula.

Datos de ejemplo:
  Aula 302 · crítico · 1520 · aire muy cargado · 🌀 Ventilando
  Aula 303 · crítico · 1450 · aire muy cargado · ⚠ Ventilación apagada
  Aula 402 · alerta · 1120 · aire cargado · 🌀 Ventilando
  Aula 404 · alerta · 1040 · aire cargado · 🌀 Ventilando
  Aula 304 · normal · 860 · aire aceptable · ✓ Sin intervención
  Aula 403 · normal · 910 · aire aceptable · 🌀 Ventilando
  Aula 305 · normal · 720 · aire limpio · ✓ Sin intervención
  Aula 401 · normal · 650 · aire limpio · ✓ Sin intervención
  Aula 201, 202, 203 · sin sensores · "—" · sin sensores · "No medimos aquí"
(Los emojis indican qué icono de línea usar: ventilador, triángulo de aviso, check, guion.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. PANTALLA 2 — DETALLE DEL AULA (Aula 302)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cabecera: enlace "← Volver a las aulas" (vuelve a la Pantalla 1). Título "Aula 302". Subtítulo "Secundaria · 31 alumnos de 34". A la derecha: pastilla de estado roja "Crítico" y pastilla verde "En vivo" con punto que late.

Distribución: escritorio en dos columnas (izquierda de 320 px, derecha flexible). En móvil una sola columna con el gráfico PRIMERO y el panel izquierdo después.

COLUMNA IZQUIERDA (de arriba abajo):

a) Tarjeta del aire, con barra de zonas (sin números):
   - Grande, en rojo: "El aire está muy cargado"
   - Debajo, en gris: "Lleva 14 minutos así y sigue empeorando"
   - Barra horizontal de 12 px de alto, con esquinas redondeadas, dividida en 4 zonas de ancho proporcional y separadas por una línea blanca de 2 px:
       limpio 22 % (verde mar) · bien 11 % (verde mar al 40 %) · cargado 22 % (ámbar) · muy cargado 45 % (rojo)
   - Sobre la barra, un triángulo ▼ pequeño color tinta con la palabra "ahora" encima, situado en la zona "muy cargado" (más o menos al 62 % del ancho).
   - Debajo de cada zona, su nombre en minúsculas, a 10 px; el de la zona actual en negrita.
   - Variantes del texto de contexto: "Lleva 6 minutos mejorando" y "Se mantiene estable".

b) Tarjeta "Ahora mismo": cuatro filas separadas por líneas finas; cada una con icono teal, etiqueta gris a la izquierda y valor a la derecha:
     (viento)     Aire              muy cargado        ← en rojo
     (termómetro) Temperatura       24.4° · agradable
     (gota)       Humedad           63% · normal
     (personas)   Personas dentro   31 · casi lleno

c) Tarjeta "Dispositivos del aula": dos filas con fondo bruma, cada una con un interruptor (switch) a la derecha:
     Ventilador — "Encendido · control automático" — switch encendido (teal)
     Luces      — "Encendido · control manual"     — switch encendido
   Al tocar un switch: pasa a "Apagando…" con el switch atenuado durante 1 s y luego muestra "Apagado · registrado ✓" en verde. Nota pequeña debajo: "Un cambio manual queda registrado. El sistema automático puede volver a tomar el control unos minutos después."

d) Tarjeta de hallazgo (borde y fondo rojos suaves): pastilla "Hallazgo", título "Ventilación deficiente detectada", número grande "0.62" con el texto "renovaciones por hora" y un icono "?" con tooltip; párrafo: "El aire de esta aula se renueva mucho más lento de lo recomendable. Se detectó midiendo qué tan rápido se limpia el aire cuando el aula queda vacía, sin que nadie tenga que entrar a revisar."

e) Tarjeta "Equipos en este salón", con el subtítulo "5 de 5 funcionando". Cada fila tiene un punto verde, la descripción en llano como texto principal y el modelo como texto secundario pequeño:
     ● Mide el aire del salón — SCD41
     ● Mide temperatura y humedad — BME280
     ● Mide cuánta luz hay — BH1750
     ● Cuentan quién entra y quién sale — Dos sensores en la puerta · no son cámaras
     ● Pantallita que muestra el estado — Visible desde dentro del aula
   "no son cámaras" es el argumento de privacidad del proyecto: tiene que verse siempre.
   Variante "aula simulada": subtítulo "Aula simulada · estos equipos todavía no están instalados" y aros vacíos grises en lugar de puntos. Variante "sin señal": punto gris y texto "· sin señal".

COLUMNA DERECHA:

f) Tarjeta "Concentración de CO₂": gráfico de área de las últimas horas, con una línea teal de 2 px y relleno en degradado teal muy suave. Cuadrícula horizontal punteada. Dos líneas de referencia punteadas con etiqueta a la derecha: "alerta 1000" en ámbar y "crítico 1400" en rojo. A la derecha del título, un selector de rango: 3h · 6h · 24h · 72h (el activo en azul profundo). Debajo, en gris: "1.430 lecturas en las últimas 6 horas". El gráfico debe mostrar subidas y bajadas en forma de serrucho cruzando la línea de 1000.

g) Tarjeta "Qué fue pasando" (línea de tiempo compacta). A la derecha del título, un selector segmentado "Compacto | Detallado".
   - Encabezados de día pequeños en MAYÚSCULAS: "HOY", "AYER".
   - Cada evento es UNA fila de unos 36 px: hora en 24 h (columna fija de 38 px, gris, p. ej. "19:30") · punto de color (azul profundo = acción del sistema, rojo = crítico, ámbar = alerta, teal = aviso) · texto · chevron ⌄ a la derecha. Las filas van separadas por líneas de 0.5 px (sin línea vertical de timeline).
   - Algunas filas llevan un contador gris "×4" pegado al texto.
   - Al tocar una fila se despliega, indentada bajo el texto: una explicación en llano (12 px), la línea "Pasó 4 veces, entre las 19:10 y las 19:30" si se repitió, y un segundo nivel plegado "Ver dato técnico" con texto monoespaciado. Solo un evento abierto a la vez: al abrir uno se cierra el anterior.
   - En modo "Detallado" todas las filas aparecen desplegadas (el dato técnico sigue plegado) y no hay chevrons.
   - Al pasar el mouse sobre una fila, se resalta un punto en el gráfico de arriba.
   Eventos de ejemplo (HOY):
     19:30 ● El sistema encendió la ventilación ×4 → "El sistema vio que el aire iba a empeorar y ventiló antes"
     19:25 ● El sistema apagó la ventilación → "El aire ya se había limpiado, así que apagó la ventilación"
     19:24 ● El aire superó el nivel recomendado → "Conviene ventilar para que no siga subiendo"
     19:17 ● El aire llegó a nivel crítico → "Con el aire así cuesta concentrarse; hay que ventilar cuanto antes"
     19:02 ● Se encendieron las luces manualmente desde el panel
   Dato técnico de ejemplo: "motivo: proyeccion_cruce_umbral:0.6min|pendiente:5.7ppm_min|r2:0.62".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. PANTALLA 3 — ALERTAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Pregunta que responde: "¿qué aula tengo que atender?". NO es una lista cronológica: es una tarjeta por aula.

Cabecera: título "Alertas y decisiones". A la derecha, pestañas segmentadas "Qué pasó" | "Qué decidió" (la activa en azul profundo con texto blanco).

PESTAÑA "QUÉ PASÓ":

Tres tarjetas pequeñas de resumen en una fila (también en móvil, de 3 columnas):
  "21" (en rojo) alertas sin revisar · "5" aulas afectadas · "302" la más afectada

Fila de filtros: chips con punto de color y contador → todas 7 · ● críticas 2 · ● alertas 3 · ● avisos 2 · sin revisar 5. A la derecha, el botón "✓ Marcar todo como visto" (en móvil baja a su propia fila, a todo el ancho).

Lista de aulas: una tarjeta colapsable por aula, con cabecera compacta de 48 px:
  chevron › · punto de color · "Aula 302" (negrita) · descripción corta en gris (se recorta con "…" si falta espacio) · tiempo relativo a la derecha · botón de check.
Al expandir aparecen EXACTAMENTE tres puntos de color con una frase corta cada uno, y debajo el enlace "Ver esta aula →" (lleva a la Pantalla 2):
  ● rojo  — qué pasó
  ● verde — qué hizo el sistema
  ● ámbar — si se repite (gris si no hay patrón)
Al tocar el check, la tarjeta se atenúa al 60 %, se colapsa, baja al final de la lista y su descripción cambia a "ya revisada" con un check verde fijo. "Marcar todo como visto" hace eso con todas.

Datos de ejemplo, en este orden (sin revisar primero, por gravedad; las revisadas al final):
  ▾ Aula 302 · ● rojo · se cargó 12 veces y sigue así · hace un momento
      ● El aire se cargó doce veces esta tarde; alguna de ellas llegó a nivel crítico
      ● Encendió el ventilador, pero el aire todavía no se limpia
      ● Vuelve a pasar cada 20 minutos
  ▾ Aula 303 · ● rojo · el aire sigue cargado · hace 4 min
      ● El aire se cargó una vez esta tarde y llegó a nivel crítico
      ● El sistema todavía no ha encendido el ventilador
  ▾ Aula 402 · ● ámbar · se cargó 6 veces · hace 8 min
      ● El aire se cargó seis veces esta tarde
      ● El ventilador lo arregló solo cada vez
      ● Vuelve a pasar cada pocos minutos
  ▾ Aula 404 · ● ámbar · el aire estuvo algo cargado · hace 25 min
      ● El aire se cargó una vez esta tarde
      ● El ventilador lo arregló solo
      ● No se ha vuelto a repetir (punto gris)
  ▾ Aula 401 · ● teal · el sistema se adelantó · hace 1 h
      ● El sistema detectó que el aire iba a empeorar esta tarde
      ● Encendió el ventilador a tiempo y no pasó a más
  › Aula 304 · ● gris · ya revisada · hace 2 h · ✓   (atenuada y colapsada)
  › Aula 305 · ● gris · ya revisada · ayer · ✓       (atenuada y colapsada)

PESTAÑA "QUÉ DECIDIÓ": la misma estructura de tarjetas por aula, ordenadas por la más reciente, sin el botón de check. Solo la primera viene abierta. Ejemplo:
  ▾ Aula 402 · ● verde · encendió la ventilación 6 veces · hace un momento
      ● Casi siempre se adelantó a que el aire se cargara
      ● Encendió la ventilación seis veces esta tarde y la apagó cuando el aire se limpió
      ● Lo hace cada 20 minutos
      ▸ Ver dato técnico   (plegado; al abrirlo muestra los motivos en texto monoespaciado)
      Ver esta aula →
  › Aula 302 · encendió la ventilación 12 veces · hace 4 min
  › Aula 303 · la encendieron a mano · hace 30 min

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
6. PANTALLA 4 — CUMPLIMIENTO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cabecera: título "Reporte de cumplimiento"; subtítulo gris "Porcentaje de tiempo con CO₂ sobre el umbral de ventilación adecuada, por ambiente y por periodo." A la derecha, un selector segmentado: 24 h · 7 días · 30 días (activo: 7 días).

Tarjeta de contexto con el borde izquierdo teal de 4 px: "**Por qué existe este reporte.** La Norma A.040 del Reglamento Nacional de Edificaciones exige un nivel adecuado y constante de renovación de aire en locales educativos, pero no define ningún mecanismo de verificación durante la operación. Este reporte convierte esa obligación declarativa en un indicador medible y auditable."

Cinco tarjetas de resumen (5 columnas en escritorio, 2 en móvil): 11 AULAS EVALUADAS · 5 CUMPLEN (verde) · 3 NO CUMPLEN (rojo) · 3 SIN DATOS (gris) · 1000 ppm UMBRAL APLICADO.

Escritorio: una tabla con cabecera en bruma y en MAYÚSCULAS de 12 px: Aula (enlace teal que lleva a la Pantalla 2) · Lecturas tomadas · Tiempo medido · CO₂ promedio · CO₂ máximo · Habitabilidad promedio (con "?") · Tiempo sobre 1000 ppm · Proporción del tiempo (barrita de 96 px, verde si cumple y roja si no, + porcentaje) · Estado (pastilla "Cumple" verde / "No cumple" roja / "Sin datos" gris). Filas con hover en bruma.
Ejemplos: Aula 302 · 2.410 · 6 h 40 min · 1180 · 1890 · 58 · 152 · 38.0 % · No cumple — Aula 401 · 2.380 · 6 h 35 min · 640 · 980 · 92 · 0 · 0.0 % · Cumple.
Móvil: en lugar de la tabla, una tarjeta por aula (nombre + pastilla de estado, barra de proporción a todo el ancho, tres mini-métricas y una línea gris de resumen).

Pie en gris: "Criterio: el ambiente cumple si el CO₂ supera el umbral menos del 10 % del tiempo registrado. Umbral de referencia: 1000 ppm (ASHRAE 62.1)."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
7. INTERACCIONES DEL PROTOTIPO (todas deben funcionar)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Sidebar / barra inferior: navega entre Aulas, Alertas y Cumplimiento; el sidebar se expande al pasar el mouse.
- Recorrido guiado: "Siguiente →" y "← Anterior" recorren las 4 pantallas en orden.
- Aulas: los chips filtran la cuadrícula; cualquier tarjeta abre el Detalle del aula.
- Detalle: "← Volver a las aulas"; los rangos 3h/6h/24h/72h cambian el gráfico; los switches cambian de estado con el "Apagando…" intermedio; las filas de la línea de tiempo se despliegan de a una; el selector Compacto/Detallado; "Ver dato técnico" se abre y se cierra.
- Alertas: las pestañas Qué pasó / Qué decidió; los chips filtran; las tarjetas se abren y se cierran con el chevron; el check marca el aula como revisada; "Marcar todo como visto"; "Ver esta aula →" va al Detalle.
- Cumplimiento: el selector de periodo; el nombre del aula va al Detalle.
- Transiciones suaves (200–300 ms, ease-out). Estados de hover en todo lo clicable. Áreas táctiles de al menos 44 px en móvil.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
8. ENTREGABLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- 4 pantallas × 2 tamaños (escritorio 1440 y móvil 390), con nombres claros: "1 · Aulas", "2 · Detalle del aula", "3a · Alertas — Qué pasó", "3b · Alertas — Qué decidió", "4 · Cumplimiento".
- Componentes reutilizables: tarjeta de aula, chip-contador, tarjeta colapsable de aula con tres puntos, fila de línea de tiempo (cerrada/abierta), barra de zonas, fila "Ahora mismo", fila de equipo, switch, pastilla de estado.
- Variables de color con los nombres del punto 1.
- El prototipo arranca en "1 · Aulas".
