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

## Ronda 0.1.0-alpha build 3 — pestaña Modelos: Ollama + OpenClaw sin tecnicismos (25 oct 2026)

- **Qué es:** la app pasa a ser un orquestador de modelos estilo Ollama. La
  pestaña **Modelos** (barra lateral, entre APIs y Tareas; el contador es el
  número de modelos instalados) junta lo que aporta Ollama (modelos que viven
  y corren en el PC) con la forma de trabajar de OpenClaw (un solo agente que
  usa herramientas, tiene habilidades, te habla por varios canales y cumple
  tus reglas). Es la arquitectura, no una integración con el binario de
  OpenClaw: no se toca su programa ni su configuración.
- **Frase de arriba:** "Growi Bridge junta lo mejor de Ollama (modelos en tu
  PC) y OpenClaw (un agente que usa herramientas y te habla por varios
  canales), sin que tengas que configurar nada de eso."
- **Secciones, de arriba abajo** (todas son tarjetas #F5F5F7 con etiqueta en
  versales apagada, como el resto de la app):
  1. **TU PC** — resumen en una línea ("RTX 3060 Laptop · 6 GB VRAM · 15 GB
     RAM · 96 GB libres") + botón de acento **Comprobar mi PC** (nvidia-smi,
     RAM, CPU, disco, versión de Ollama; en un hilo; guarda `pc-specs.json`).
     Corre solo la primera vez que se abre la pestaña.
  2. **QUIÉN RESPONDE** — el selector de motor con nombres normales y una
     frase simple ("Claude: el más listo, va por internet", "Hermes 3 8B:
     corre en tu PC, gratis y privado", "OpenAI: otro modelo por internet,
     con tu clave"). El nombre exacto solo se ve si se pulsa "Ver nombre
     exacto". Se guarda en settings.json (`default_engine`; si es local,
     también `ollama_model`).
  3. **EN TU PC** — modelos instalados (`ollama list` pedido al runner), con
     semáforo, tamaño, fecha, "Por defecto" / "Usar por defecto" y Borrar
     (con confirmación). Progreso de la instalación en una línea.
  4. **LIBRERÍA** — `models-catalog.json` (20 modelos, ampliable sin tocar
     código) con semáforo, para qué sirve, tamaño y VRAM necesaria; botón
     Instalar (acento azul; desactivado y gris en los rojos).
  5. **QUÉ PUEDE HACER** — habilidades con interruptor (herramientas del
     runner + skills de `~/.claude/skills/`) en palabras normales ("Leer tus
     archivos", "Buscar en internet", "Hacer videos"). Apagar una la quita de
     `--allowedTools` y la pasa a `--disallowedTools` (herramientas) o la
     prohíbe al principio del prompt (skills). Guardado en settings.json
     (`disabled_abilities`; nombres propios en `ability_names`).
  6. **DÓNDE TE HABLA** — canales de solo lectura (WhatsApp, el chat de Muse,
     la cajita de la mascota) con punto verde/gris y una frase.
  7. **REGLAS** — frases del usuario con interruptor y Quitar; se guardan en
     `rules.json` y el runner las pone al principio de cada prompt (Claude,
     Ollama y APIs) como "Reglas de <nombre>:" (`user_name` en settings.json;
     sin nombre dice "Reglas del usuario:"). Vienen dos: "Pregúntame antes de
     gastar dinero" y "No borres nada sin pedirme permiso".
- **Semáforo** (un círculo de 10 px, sin texto largo, motivo corto al lado):
  verde ≤ 80 % de la VRAM total ("Cabe holgado"), naranja 80–100 % ("Va
  justo: usa ~X% de tu VRAM"; Instalar pide confirmación), rojo si no cabe en
  la VRAM o en el disco ("No cabe: necesita X GB de VRAM y tienes Y GB";
  Instalar desactivado), gris sin comprobar ("Pulsa Comprobar mi PC para ver
  si cabe"). Sin GPU usa la RAM (verde ≤ 50 %, naranja ≤ 90 %, "sin GPU, corre
  en CPU"). VRAM necesaria = tamaño + ~15 %, ya calculada en el catálogo.
  Colores: verde #34C759, naranja #FF9500, rojo #FF3B30, gris #C7C7CC.
- **La ventana y el asistente mueven los mismos botones:** la pestaña escribe
  tasks `{"ollama_action": "pull"|"rm"|"list", "model": ...}` en
  `runner-tasks/`, igual que el asistente desde la VM. El runner las corre en
  un **carril propio** (no esperan detrás de una tarea larga de Claude),
  valida el nombre (solo letras, números, - _ . / :, sin URLs ni flags), solo
  ejecuta `ollama pull|rm|list` sin shell, verifica el pull con `ollama list`
  y devuelve el mismo esquema de resultado (`cost_usd: 0.0`). El progreso del
  pull va a la pestaña, al registro (cada 10 %) y a
  `outbox/runner-results/<id>.progress.json`.
- **APIs ampliada (no duplicada):** tarjeta CONEXIONES con Anthropic, OpenAI,
  Google Gemini, Groq y OpenRouter: clave (enmascarada, solo últimos 4),
  Guardar, **Probar** (petición gratis: listar modelos o ver la clave) y
  estado ("Conectada" / "Falló: motivo"). Motor nuevo `api:<proveedor>:<modelo>`
  en el runner (urllib; /chat/completions con Bearer o /v1/messages con
  x-api-key + anthropic-version 2023-06-01; `cost_usd: null`, `num_turns: 1`).
- **Sin tecnicismos en la ventana:** nada de MCP, gateway, endpoint,
  provider, quantization, context window, JSON ni config. Se dice modelo,
  habilidad, canal, regla.
- **Arreglos de paso:** la rueda del ratón ahora mueve la página que se ve
  (antes solo la última creada); faltaba `import re` (soltar archivos sobre
  la mascota fallaba); las llamadas a `ollama` ya no se cuelgan cuando Ollama
  arranca su servidor de fondo; botones de acento desactivados en gris; los
  `.bat` y el código ya no llevan rutas ni datos de un PC concreto.

## Ronda 0.1.0-alpha — Orquestación: bucle cerrado con revisión (25 oct 2026)

- **Qué cambia:** el runner deja de ser un lanzador de comandos. Cada tarea
  corre con su motor, se revisa sola al terminar y, si falta algo, se corrige
  (máximo 3 rondas) hasta quedar aprobada o en «necesita decisión».
- **Visual (mismo sistema Mac, nada nuevo):** la pestaña Tareas añade
  columnas Motor, Ronda y Revisión, una tarjeta DETALLE (encargo, criterios,
  qué falta, evidencia, reporte) y una tarjeta ESPERANDO TU APROBACIÓN con el
  plan y Aprobar (acento azul) / Rechazar. El color del texto de cada fila
  dice el estado: verde #248A3D aprobada, azul en curso / revisando, naranja
  oscuro #B25E00 necesita decisión o espera aprobación, rojo fallida.
- **Banner de trabajo:** franja #F5F5F7 con barra azul de 3 px a la
  izquierda, el paso actual en negrita, tarea y tiempo en gris, y un botón
  **Parar** (pide confirmación; mata el proceso del motor). Visible en todas
  las páginas mientras un motor trabaja; desaparece al terminar.
- **Ajustes → PERMISOS:** tres opciones en palabras normales, una por línea
  con su explicación debajo (estilo BFF). «Hazlo sin preguntar» exige doble
  confirmación (aviso + escribir SIN PREGUNTAR) y nunca es el valor por
  defecto.
- **Avisos:** un solo toast por tarea, al final (aprobada, necesita
  decisión, fallida o sin revisión), y uno cuando una tarea espera tu
  aprobación. Nada de un aviso por ronda.
- **Sin tecnicismos en la ventana:** «motor», «ronda», «revisión», «qué
  falta», «permisos». Nada de JSON, endpoint ni session_id.

## Ronda 0.1.0-alpha — pestaña Recursos (25 oct 2026)

- **Qué es:** ver lo que Growi tiene andando y cuánto del PC se lleva; no es
  un clon del Administrador de tareas. La vista principal es **Mis procesos**;
  la lista completa del sistema es un interruptor secundario.
- **Nota:** el encargo pedía aplicar la sección «Dirección Raycast» de este
  archivo, pero esa sección no existía (Raycast solo salía como referencia de
  la paleta Ctrl+K). Se aplicó lo que Raycast hace en listas y se deja
  escrito aquí como dirección para las listas y tarjetas que vengan:
- **Dirección Raycast (listas y tarjetas):**
  1. Buscador arriba, ancho completo, con texto de ayuda dentro; filtra al
     escribir (o pegar) sin botón de buscar.
  2. Lista limpia: filas de 28 px, sin rejilla, selección suave #DCEBFF con
     texto oscuro (no el azul sólido de sistema); lo propio (la app) en
     negrita, lo bloqueado en gris apagado.
  3. Barra de acciones abajo: el elemento elegido en negrita («nombre, PID
     N»), una línea que explica (quién lo lanzó, o por qué está bloqueado) y
     la acción principal a la derecha con su atajo en chip (Supr), como el
     panel de acciones de Raycast. Teclado: ↓ desde el buscador baja a la
     lista, Supr cierra, F5 actualiza.
  4. Tarjetas de resumen: cuatro iguales en una fila (aquí sí, porque son
     cuatro medidas del mismo tipo): etiqueta pequeña apagada, número grande
     (17 bold), una línea de contexto y una barra fina de 4 px (azul; naranja
     ≥ 80 %; rojo ≥ 95 %). El número siempre dice el valor: el color nunca va
     solo.
- **Destructivo:** «Cerrar proceso» en rojo #C81E1E (gris desactivado si la
  fila está bloqueada); confirmación siempre con nombre y PID exactos; doble
  confirmación si es Growi Bridge.
- **Barra lateral:** Recursos entre Tareas y Ajustes, contador = % de CPU.
  Atajo Ctrl+0 (Ctrl+1…9 no se movieron). El alto mínimo de la ventana se
  calcula con lo que pide la barra lateral (antes 560 fijo: con 10 secciones
  Registro quedaba tapado); en pantallas bajas las filas se compactan.

## Ronda 0.1.0-alpha — Configuración inicial + Venezuela primero (25 oct 2026)

- **Configuración inicial (4 pasos, pantalla completa sobre la ventana):** ¿Quién
  te ayuda? / Conectar / Tus carpetas / Comprobación. Detección silenciosa antes
  de preguntar (claude, codex, ollama, gemini, Ollama en 11434, sesión de Claude,
  carpetas). «Saltar por ahora» en cada paso; «Lo haré más tarde» en Conectar.
  Barra de progreso de 4 segmentos azules, «Paso N de 4» apagado, título 22.
- **Proxy central:** estado en la barra lateral (bajo el nombre) y en la tarjeta
  Proxy, siempre con punto + palabras. Frase honesta sobre el riesgo de
  suspensión. Campos y modos (mi proxy / del sistema / sin proxy) plegados en
  «Ajustes avanzados». Aviso naranja (barra de 3 px) en todas las páginas cuando
  la nube cae y la app trabaja con el modelo local.
- **Mapa de disponibilidad (Estado):** lista estilo Raycast, una fila por
  servicio: ✓/!/✗ + nombre + chip de latencia y ruta + frase + «Cómo lo sé»
  apagado + acción a la derecha (acento azul solo en «Usar» cuando anda). Todo
  sale de `availability.json`: nada de disponibilidad escrita en el código.
- **Gasto:** tres dineros que nunca se mezclan (real / equivalente Max / $0
  local). Tarjetas de resumen 2×2 + control segmentado Por tarea / proyecto /
  motor. La cuota de Max se marca «no disponible» (no hay forma pública de
  leerla); nunca se inventa.
- **Bandeja:** distintivo verde (conectado) / ámbar (solo local) / rojo (sin
  conexión o puente caído); número de cuota arriba a la izquierda solo si se
  puede leer. Menú corto: Abrir, Paleta, Estado del proxy, Pausar mascota,
  Salir. Clic = desglose del gasto; doble clic = ventana.
- **Reglas P0:** texto regular ≥ 12 px y negrita ≥ 14 px (filtro en la frontera
  con Tk); toasts < 50 letras con su contexto al hacer clic; animaciones con
  ease-out (interruptor ~150 ms, botón grande ~280 ms).
- **Tema oscuro (Dirección Raycast), siguiendo a Windows:** fondo #1E1E20,
  barra lateral #252528, tarjetas #2A2A2D, texto #F2F2F7, apagado #AEAEB2,
  líneas #3A3A3D, azul de texto #4DA3FF, botón de acento #0A64C8 con texto
  blanco (5,7:1), verde #4CD964, naranja #FFB340, rojo #FF6B6B. Todos ≥ 4,5:1.
  En claro, el acento de texto sigue en #0066CC porque #007AFF sobre blanco da
  4,0:1 (no pasa AA); #007AFF/#0A84FF es la familia de acento en los dos temas.

## Ronda 0.1.0-alpha — Consumo en vivo (25 oct 2026)

- **Qué es:** ver lo que una tarea lleva consumiendo mientras corre, por
  tarea y por modelo, sin esperar a que termine. Todo sale de
  `outbox/runner-live.json`; la ventana no calcula nada por su cuenta.
- **Visual (mismo sistema Mac, nada nuevo):** la tabla de Tareas gana dos
  columnas, **Tiempo** y **Tokens ent. / sal.**, y «Motor» pasa a «Motor /
  modelo» («Claude Sonnet 5.5», sin repetir «Claude»). La fila en curso se
  pinta en azul y sus números cambian cada ~5 s. Bajo la tabla, una línea
  apagada (azul mientras corre) con la frase completa: «En vivo: tarea, en
  curso, modelo, lleva 2:17. Tokens entrada / salida: 111.9 k / 470. Hasta
  ahora: ~$0.20 eq. Max (estimado…)». Después, la tarjeta **Consumo de hoy
  por modelo** (tabla estilo Raycast: fila de grupo en negrita por dinero,
  modelos sangrados debajo) y una nota corta.
- **Tres dineros, siempre con su etiqueta:** «$x real», «$x eq.»/«eq. Max»,
  «$0 local». El «~» delante marca estimado; sin «~» es lo que reportó el
  motor. Nada de «cuota restante»: Anthropic no la publica.
- **Honestidad:** sin uso reportado se dice «sin vivo»; mientras Claude
  arranca (a veces 30–60 s antes del primer mensaje), «esperando al motor».
