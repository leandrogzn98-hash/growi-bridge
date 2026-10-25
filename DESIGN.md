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

---

## Ronda v2.2 — Mobbin + funciones pedidas (24 oct 2026, noche)

- **ADN extraído de Mobbin** (ver `notas-mobbin.md` con los links):
  - [NordVPN](https://mobbin.com/screens/1177908c-4365-4109-bd1f-f9b65de8faf3) — un solo CTA dominante, tarjetas de radio grande, etiquetas de sección pequeñas y apagadas, estado con punto + píldora de valor.
  - [Saily](https://mobbin.com/screens/910fda01-de82-4e0e-9677-3255d2ee9571) — punto verde de estado en la esquina de la tarjeta, valor en píldora, número grande como héroe.
  - [Philips Hue](https://mobbin.com/screens/e47e76e7-97ec-45f6-824b-3e179596016a) — el control vive dentro de la tarjeta (interruptor a la derecha), etiquetas de sección en versales, una sola tarjeta de color + mucho aire.
  - [BFF](https://mobbin.com/screens/0cd6db75-566c-4e31-95be-830c00018ca0) — ajustes como filas con interruptor iOS a la derecha y texto explicativo apagado debajo.
- **Dirección:** consola nocturna (se mantiene) + controles dentro de las filas. El botón grande sigue siendo el único showstopper.
- **3 cambios exactos:**
  1. Cada servicio (Puente, Runner, Proxy) lleva su propio interruptor a la derecha de su fila + píldora de valor; el estado ya no es solo texto.
  2. Etiquetas de sección en versales apagadas (ESTADO, PROXY, AJUSTES, PC, REGISTRO); el registro baja de 8 a 6 líneas para dar aire.
  3. Los ajustes son interruptores, no casillas: actualización automática, inicio automático, mascota. La sección PC añade Apagar / Reiniciar (con confirmación y 60 s de margen) / Cancelar.
- **Nuevas funciones (pedidas por Leandro):**
  - Auto-update: con el interruptor activado, la app comprueba cada 6 h y se actualiza sola desde GitHub (descarga todos los archivos y se reinicia, sin preguntar).
  - Pestaña APIs: claves guardadas solo en el PC (apis.json), clave enmascarada; se añade desde la app o desde WhatsApp (Growi empuja el archivo por el puente y la app lo importa en segundos y borra el archivo de entrega).
  - Pantalla: intervalos 0.5 s y 1 s; cada grabación crea su propia carpeta `outbox/screens/AAAAMMDD-HHMMSS/` con `frame-NNNN.jpg`; sesiones de más de 7 días se borran solas.
  - Mascota: tres animaciones (idle, working, wave) según el estado; celebra cuando Claude termina una tarea; saludo al hacer clic.
- **Regla de Leandro (24 oct 2026):** para borrar algo fuera de las carpetas permitidas, Growi debe pedirle autorización explícita cada vez. La app no borra nada fuera de sus carpetas salvo la limpieza de sesiones viejas de pantalla (que el propio usuario puede desactivar borrando el botón).
