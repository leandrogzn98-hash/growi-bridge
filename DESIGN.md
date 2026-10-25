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

---

## Ronda v2.3 — "Mac" + magia (25 oct 2026, 00:00)

- **ADN extraído de Mobbin** (ver `notas-mobbin.md`):
  - [Superlist](https://mobbin.com/screens/f056c26d-f67f-49e2-b682-e290d350e56c) — barra lateral gris clara con icono + etiqueta, ítem activo con píldora + barra de acento, título enorme, píldoras de metadatos, mucho aire.
  - [Plain](https://mobbin.com/screens/150cc4a9-6311-444b-9902-01e491c25a5f) — riel + barra lateral, contadores a la derecha de cada ítem, control segmentado en píldoras, avatar abajo en la barra lateral, título enorme.
- **Dirección:** que parezca de Mac. Tema claro (contenido blanco, barra lateral #F5F5F7, texto #1D1D1F, acento #007AFF, interruptores verdes #34C759). Nada de pestañas arriba: navegación por barra lateral.
- **3 cambios exactos:**
  1. Barra lateral con las 5 secciones (Estado, Carpetas, Skills, Pantalla, APIs), ítem activo con píldora + barra azul, contadores a la derecha (carpetas, skills, APIs).
  2. Título grande (22 pt) en cada página y contenido con scroll vertical (nada queda fuera de la ventana, aunque sea pequeña; el botón de la mascota ya no se pierde abajo).
  3. La mascota vive en el pie de la barra lateral (avatar + interruptor, siempre a la vista) y en la pantalla es una ventana pequeña de 96×96, siempre encima, con las esquinas transparentes.
- **Magia (micro-interacciones):**
  - El botón grande anima al encender/apagar (~360 ms): el relleno cambia de color, el símbolo se dibuja poco a poco, el círculo rebota y sale una onda que se expande y se desvanece; con sombra suave debajo.
  - La mascota saluda al arrancar, trabaja mientras Claude corre una tarea, celebra cuando Claude termina una, levanta la mano cuando le acercas un archivo y se inclina hacia el cursor como buscándolo.
  - El icono de la bandeja lleva un distintivo como OneDrive: punto verde que pulsa mientras sincroniza, rojo si el puente se cae; el menú de la bandeja muestra qué se está sincronizando.
- **Mascota con arrastre (drag & drop):** soltar un archivo sobre Growi lo copia al Inbox del puente (llega a Growi por la sincronización). Más de 200 MB: aviso con "No mostrar durante 30 min". Requiere `tkinterdnd2` (el instalador lo pone).
- **Arreglo del combobox "Fotograma cada":** ancho 8 (antes 6) para que el valor se vea completo; la queja era que en v2.1 se veía cortado y la interfaz parecía de Windows XP.
- **Lección del instalador v2.2:** el runner solo recoge archivos `*.task.json` en `runner-tasks/`; un task llamado `*.json` se ignora en silencio. La v2.2 nunca se instaló por eso; todo su contenido se plegó en la v2.3.

## Renumeración (25 oct 2026, 00:06)

- La app pasa de la línea 2.x a **0.1.0-alpha** (pedido de Leandro: es una
  Alpha, no una 2.x). El número baja, así que la comparación de versiones
  lleva una regla de migración: cualquier 0.x se considera más nueva que
  cualquier 2.x (una sola vez; después la comparación es normal dentro de
  la línea 0.x). `_version_tuple` ya entiende pre-release (alpha < beta <
  rc < final).

## Ronda 0.1.0-alpha build 2 — "Orquestador" (25 oct 2026, 00:20)

- **Tendencias 2026 (artículo Medium de Design Studio UI/UX, 13 mar 2026):**
  - Command Palette (Cmd+K, estilo Raycast): paleta flotante que filtra
    acciones mientras escribes y las ejecuta al instante. Implementada
    (Ctrl+K) con 21 acciones: ir a cada pestaña, encender/apagar servicios,
    pedirle algo a Claude, abrir Inbox/Outbox, apagar/reiniciar PC, salir.
  - Micro-interactions: los interruptores ahora animan (la perilla se
    desliza ~150 ms y el color funde de gris a verde); el botón grande ya
    animaba; la mascota celebra cuando Claude termina una tarea.
  - Cross-App Drag and Drop: ya estaba (arrastrar archivos a la mascota).
  - AI Conversational Interface: la cajita "Escríbeme" + la nueva cajita
    "Pedirle algo" en la pestaña Tareas.
  - Smart Autocomplete: el filtrado de la paleta mientras escribes.
  - Liquid Glass: NO se hizo (tkinter no tiene desenfoque de fondo real;
    forzarlo quedaría embarrado, no cristal).
  - Spatial UI, Infinite Canvas, Gesture Navigation, Live Data Maps: no
    aplican a una utilidad de escritorio.
- **Las 6 funciones pedidas por Leandro (25 oct 00:17):**
  1. Aviso al terminar tarea: toast de Windows (pystray notify) + la
     mascota celebra; vigila `outbox/runner-results/` cada 5 s.
  2. Historial con costo: pestaña Tareas (tabla + total del día y total
     general, desde los result.json del runner).
  3. Cajita "Pedirle algo": en Tareas, con selector de motor (Claude
     Sonnet/Opus/Haiku o Local Hermes 3 por Ollama, $0).
  4. No suspender mientras trabaja: `SetThreadExecutionState` + ajuste.
  5. Atajo global Ctrl+Alt+G (paquete `keyboard`, con fallback si falta).
  6. Resumen diario: cron de la VM a las 21:00 (lo hace Growi, no la app).
- **Orquestador local (diagnóstico del PC, 25 oct 00:22, $0.01):** Ollama
  0.40.10 instalado con Hermes 3 8B Q4 (4.9 GB, `hf.co/NousResearch/
  Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M`); OpenClaw 2026.10.5 instalado; RTX
  3060 Laptop 6 GB; LM Studio no instalado; 100 GB libres; Node v24.20.
  El runner ahora acepta `model: "ollama:<modelo>"` (rama `_run_ollama`,
  un turno, $0). Regla honesta: Hermes 3 8B sirve para lo rápido y
  gratis; Claude sigue siendo el motor para el trabajo pesado (código,
  Blender, video). OpenClaw queda como opción futura, no se migró nada.
- **Pestañas nuevas (pedido de Leandro 25 oct 00:25):** Ajustes y Registro
  salen de la página Estado y son pestañas propias en la barra lateral.
  Estado queda solo con encendido, servicios, sync y proxy.
- **Mascota (pedido 25 oct 00:19):** 128×128 (antes 96), 16 fotogramas
  por juego (antes 8), fondo blanco puro con rembg + erosión de 1 px
  (sin cuadro blanco), loop a 120 ms. Animación de trabajo nueva:
  sentado con la laptop en las piernas tecleando (clip generado por
  video, verificado visualmente). Los marcos se regeneraron con rembg
  (venv `~/.venv-rembg`, el pip del sistema rechaza numpy por PEP 668).
- **Cajita "Escríbeme" rediseñada (pedido 25 oct 00:20):** 380×230, con
  avatar, campo con borde, botón de acento y pie explicativo.
- **Nitidez (pedido 25 oct 00:15):** la app se declara consciente del DPI
  antes de crear la ventana (`SetProcessDpiAwareness` + `tk scaling`) y
  los iconos se regeneraron desde la foto 1600×1600 con afilado.
- **Versión:** se mantiene 0.1.0-alpha (pedido de Leandro); este es el
  build 2 de esa versión.
