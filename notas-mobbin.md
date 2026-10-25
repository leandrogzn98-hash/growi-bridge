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
