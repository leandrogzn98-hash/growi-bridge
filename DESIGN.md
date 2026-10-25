# Brief — Growi Bridge v2.1 (rediseño de interfaz)

## 1. Para quién es y qué le preocupa

Leandro, una sola persona, de noche, en su PC. Le preocupa: saber de un
vistazo si el puente y el runner están vivos (si se caen, Growi no lo
alcanza), encender/apagar el proxy sin pensar, y que la app no parezca un
programa genérico hecho por una IA. La v2.0 funcionaba pero se veía fea:
ventana gris clara, widgets por defecto de tkinter, campos apretados, icono
invisible en la barra de tareas (foto con fondo blanco a 16 px).

## 2. La única acción

Encender o apagar todo con el botón grande. Todo lo demás es estado y
configuración, no decisiones.

## 3. Los hechos reales

- 4 pestañas: Estado, Carpetas, Skills, Pantalla. La principal es Estado.
- Estado real: puente (puerto 8787), runner (tareas hechas), proxy
  (host:puerto), sincronización (último archivo), administrador (sí/no),
  versión.
- El proxy real de Leandro: 2.25.244.222:18080, usuario leandro.
- La foto de Growi existe (avatar crema, suéter negro). Es el único asset
  visual; no hay logo ni fotos de stock.

## 4. El look + never-list

Tres palabras: **consola nocturna, compañero, precisa.**
Referencia tangible: el panel de un piloto de noche, no una landing de SaaS.

- Fondo azul noche profundo, texto crema cálido, un solo acento verde
  (encendido/OK) + naranja Guaro solo para el proxy y avisos.
- La mascota (foto de Growi) es la cara del programa; todo lo demás es
  quieto y disciplinado.
- El botón grande es el único showstopper: orbe verde con pulso cuando
  todo está encendido.

Never-list:
- Sin gradientes (el morado es la firma del slop; aquí tampoco va ningún
  degradado).
- Sin tarjetas idénticas picadas por todos lados: el estado va en lista
  con líneas finas, como ajustes de iOS.
- Sin fondo crema + serif + terracota, sin negro casi negro + un solo
  verde ácido (clichés de Anthropic).
- Sin eyebrow en MAYÚSCULAS con tracking, sin meta-strings con puntos
  medios ("A · B · C"), sin "→" en botones, sin una sola palabra del
  titular acentuada, sin marcadores 01/02/03.
- Sin Inter, Roboto, Arial ni Space Grotesk como personalidad: la UI es
  de escritorio Windows, así que Segoe UI (nativa) con pesos intencionales;
  la personalidad la carga la foto, no la fuente.
- Sin emojis en la interfaz (el estado se dice con puntos de color y
  palabras, no con caritas).
- Sin animaciones regadas: un solo pulso (el botón grande) y el icono de
  sincronización cuando hay actividad.

## 5. Tres direcciones (se elige una)

- **A — Consola nocturna (ELEGIDA):** fondo azul noche #0B1B2B, tarjetas
  #12283C, texto crema, acento verde #2FD9A6, naranja #FA5102 solo para
  proxy. El botón grande es un orbe verde. Se siente como el panel de
  control de un agente que trabaja de noche.
- **B — Papel y tinta:** fondo crema, tinta azul noche, acento naranja.
  Cálida, pero a las 11 de la noche en una pantalla oscura cansa y el
  avatar crema se pierde en el fondo.
- **C — Gris sistema:** la v2.0 tal cual (fondo #F7F8FA, ttk por
  defecto). Es lo que el usuario llamó feo: sin decisiones, sin carácter.

Se roba de B el calor del texto crema; de C, nada.

## 6. Auditoría (contra brief + never-list)

- [x] Un solo showstopper: el orbe del botón grande. Lo demás quieto.
- [x] Sin gradientes, sin tarjetas idénticas, sin eyebrow en mayúsculas.
- [x] El estado se lee en 2 segundos: puntos de color + una línea por
  servicio.
- [x] El icono de la barra de tareas: .ico propio con fondo azul noche
  (la foto con fondo blanco era invisible a 16 px).
- [x] La prueba del logo intercambiable: sin la foto de Growi esto no se
  sostiene; la cara del programa es el asset, no el cromo.
- [ ] Puerta móvil (390 px): no aplica, es una app de escritorio Windows.
  La ventana tiene tamaño mínimo y no se rompe al achicarla.

## Tokens

Ver `THEME` en `growi-bridge.py` (una sola fuente de verdad):

- Fondo ventana: #0B1B2B · fondo tarjetas: #12283C · fondo campos: #0A1622
- Texto: #F5F1E8 · texto suave: #9AB0C2 · líneas: #1E3A52
- Acento (encendido/OK): #2FD9A6 · Proxy/aviso: #FA5102 · Error: #E5484D
- Tipo: Segoe UI — título 20 bold, sección 11 bold, cuerpo 10, pie 9
- Radios: tarjetas 10, campos 6, botón grande círculo (Canvas)
- Espaciado: 8 / 12 / 16 / 24
