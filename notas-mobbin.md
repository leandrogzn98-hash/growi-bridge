# Notas Mobbin — Growi Bridge v2.2

Investigación 24 oct 2026 (noche). Tres búsquedas, una pantalla por consulta.
Las decisiones salen de lo visto en las capturas, no de los metadatos.

## 1. NordVPN — pantalla principal (conectar)

- mobbin_url: https://mobbin.com/screens/1177908c-4365-4109-bd1f-f9b65de8faf3
- Lo visto: fondo claro, un solo CTA grande tipo píldora arriba
  ("Secure my connection"); tarjetas blancas de radio grande (~24 px)
  con sombra suave; etiquetas de sección pequeñas y apagadas ("Recents",
  "Statistics"); tarjetas horizontales con icono + nombre + subtítulo
  ("San Francisco, United States / Fastest"); tarjeta de estadísticas con
  gráfico de barras grises y una línea de promedio; leyenda con píldoras
  ("0h Secured" con punto azul, "120h Not secured" con punto gris).
- Decisiones que entran:
  - El estado se lee con **punto de color + píldora de valor** (no solo
    texto): cada servicio muestra su dato en una píldora
    ("puerto 8787", "0 tareas", "2.25.244.222:18080").
  - Etiquetas de sección pequeñas y apagadas, no títulos en negrita con
    marco (adiós a los LabelFrame).
  - Una sola acción domina la pantalla: el botón grande sigue siendo el
    showstopper; el resto es estado, no más CTAs compitiendo.

## 2. Saily — pantalla principal (eSIM)

- mobbin_url: https://mobbin.com/screens/910fda01-de82-4e0e-9677-3255d2ee9571
- Lo visto: zona superior azul clara con un número enorme (saldo de datos)
  y una píldora de estado arriba ("eSIM #1 • Installed"); tres acciones
  circulares en fila (icono en círculo blanco + etiqueta debajo: Add data,
  Auto top-up, My plans); tarjeta oscura promocional como único elemento
  atrevido; sección "Security" con tarjetas horizontales que llevan el
  icono arriba a la izquierda, un **punto verde pequeño arriba a la
  derecha** y el valor en una píldora ("United S... / Disconnect", "On").
- Decisiones que entran:
  - **Punto de estado en la esquina** de cada tarjeta de servicio
    (verde = activo, gris = parado), como el punto verde de Saily.
  - El valor del servicio va en una píldora, no en texto corrido.
  - La tarjeta oscura única como acento: en Growi Bridge ese papel ya lo
    tiene la foto de Growi; no se añade otro elemento oscuro decorativo.

## 3. Philips Hue — pantalla Home (control de luces)

- mobbin_url: https://mobbin.com/screens/e47e76e7-97ec-45f6-824b-3e179596016a
- Lo visto: fondo casi negro con tinte morado; título enorme "Home";
  etiqueta de sección en versales con tracking ("ROOMS"); **una sola
  tarjeta grande de color saturado** que ES el control: icono + nombre +
  interruptor a la derecha + deslizador abajo; un interruptor grande
  arriba a la derecha (encendido global); barra inferior con 5 iconos,
  el activo en blanco y los demás apagados; muchísimo espacio vacío
  (la pantalla es una tarjeta y aire).
- Decisiones que entran:
  - **El control vive dentro de la tarjeta**: cada servicio (Puente,
    Runner, Proxy) lleva su propio interruptor a la derecha de su fila.
    El botón grande sigue como maestro, pero ya no es la única forma de
    encender/apagar.
  - Etiquetas de sección en versales pequeñas ("ESTADO", "PROXY",
    "AJUSTES", "PC", "REGISTRO").
  - Aire: la pestaña Estado se aligera (el registro pasa de 8 a 6 líneas;
    se quitan marcos y títulos que no aportan).

## 4. BFF — pantalla Dark Mode (ajustes)

- mobbin_url: https://mobbin.com/screens/0cd6db75-566c-4e31-95be-830c00018ca0
- Lo visto: fondo casi negro; título centrado; filas con etiqueta a la
  izquierda e **interruptor iOS a la derecha** (azul cuando está
  encendido, gris cuando no, perilla blanca); texto explicativo apagado
  debajo de la etiqueta; sin tarjetas: solo filas sobre el fondo plano,
  con mucho espacio vertical.
- Decisiones que entran:
  - **Los ajustes son interruptores, no casillas**: mascota, auto-update
    e inicio automático se controlan con un interruptor dibujado (píldora
    + perilla), no con Checkbutton.
  - Las opciones llevan una línea explicativa apagada debajo.
  - Las filas van sobre el fondo plano, sin tarjeta por opción.

## Respaldo cruzado

- Interruptor dentro de la fila: Philips Hue + BFF (dos productos).
- Punto de estado + píldora de valor: NordVPN + Saily (dos productos).
- Etiquetas de sección pequeñas: NordVPN + Philips Hue (dos productos).
- Una sola acción dominante + aire: NordVPN + Philips Hue (dos productos).

## Lo que NO entra (y por qué)

- El gráfico de barras de NordVPN: Growi Bridge no tiene una serie
  temporal que mostrar; inventar un gráfico sería decoración vacía.
- El degradado morado de la tarjeta de Philips Hue: la never-list del
  proyecto prohíbe gradientes.
- La barra inferior de navegación de las cuatro apps: Growi Bridge ya
  tiene pestañas arriba; duplicar la navegación no aporta nada.

---

## 5. Superlist — pantalla principal (web, 24 oct 2026, noche)

- mobbin_url: https://mobbin.com/screens/f056c26d-f67f-49e2-b682-e290d350e56c
- Lo visto: fondo claro; barra lateral gris muy clara con navegación por
  icono + etiqueta (Inbox, Today, Tasks, Messages), etiquetas de sección
  pequeñas y apagadas ("Recent", "Lists"), el ítem activo con fondo de
  píldora gris claro y una barra de acento roja en el borde derecho; el
  contenido en blanco con un título enorme y en negrita ("User Interview
  Prep"); píldoras pequeñas de metadatos ("Share", "This list is private");
  la fila seleccionada con fondo lavanda claro y barra roja a la izquierda;
  casillas como círculos; mucho espacio en blanco; divisores finos de 1 px;
  avatar pequeño abajo a la izquierda.
- Decisiones que entran (v2.3 "Mac"):
  - **Barra lateral con icono + etiqueta** en vez de pestañas arriba.
  - Ítem activo = fondo de píldora + barra de acento en el borde.
  - **Título enorme** en el contenido (22 pt).
  - Metadatos en píldoras; divisores finos; mucho aire; nada de tarjetas
    pesadas.

## 6. Plain — pantalla de tareas (web, 24 oct 2026, noche)

- mobbin_url: https://mobbin.com/screens/150cc4a9-6311-444b-9902-01e491c25a5f
- Lo visto: tres columnas — riel de iconos fino a la izquierda (logo,
  iconos, avatar abajo), barra lateral clara con cabecera ("Support /
  Product Design"), ítems de navegación con icono + contador a la derecha
  (0, 1, 4), el ítem activo con fondo de píldora azul-gris; contenido en
  blanco con título enorme ("Tasks"), control segmentado en píldoras
  ("My tasks / All tasks / Done"), filas con casilla + título en negrita +
  avatar; panel de detalle a la derecha; un toast oscuro abajo a la derecha
  ("Deleted TASK-4" con check verde y X).
- Decisiones que entran (v2.3 "Mac"):
  - **Contadores a la derecha** de los ítems de navegación (Runner: tareas
    hechas; APIs: cantidad).
  - Control segmentado en píldoras para los filtros (si hace falta).
  - Avatar del usuario (Growi) abajo en la barra lateral, junto al
    interruptor de la mascota: así el botón de la mascota siempre está a
    la vista.
  - Tema claro: contenido blanco, barra lateral gris muy clara, texto casi
    negro (#1D1D1F), apagado #6E6E73, acento azul #007AFF, interruptores
    verdes #34C759.

## Respaldo cruzado (v2.3)

- Barra lateral con icono + etiqueta: Superlist + Plain (dos productos).
- Ítem activo = píldora + barra de acento: Superlist + Plain (dos).
- Título enorme en el contenido: Superlist + Plain (dos).
- Contadores a la derecha del ítem: Plain + NordVPN (la píldora de valor).
- Avatar abajo en la barra lateral: Superlist + Plain (dos).

## Lo que NO entra (y por qué)

- El riel de iconos fino de Plain: Growi Bridge tiene 5 secciones, no 10;
  un riel más la barra lateral sería dos navegaciones para lo mismo.
- El panel de detalle a la derecha de Plain: no hay un ítem seleccionable
  que lo justifique; las secciones ya muestran su detalle.
- El toast oscuro de Plain: el registro de la app ya cumple ese papel.
