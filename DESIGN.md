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

## Ronda 0.3.0 — Motor genérico: tarjetas Motores y Nuevo motor (26 oct 2026)

- **Dónde:** página Modelos, justo después de «Quién responde». Dos
  tarjetas nuevas, construidas con CustomTkinter según el veredicto del
  piloto (superficie por superficie, con la versión tkinter clásica de
  respaldo: sin customtkinter, CTk roto, `"piloto_ctk": false` o
  `GROWI_BRIDGE_CTK=0`). Las dos versiones son el mismo código con distinto
  juego de piezas, así que el respaldo es la misma superficie.
- **Motores:** etiqueta de sección apagada fuera de la tarjeta (como Ajustes),
  tarjeta con esquinas 10 y borde fino, selector (esquinas 8) + «Comprobar
  ahora», y la ficha como lista de dos columnas: etiqueta apagada a la
  izquierda, valor a la derecha. El color nunca va solo: verde de texto
  (#1F7A33) para «disponible / respondió / encontrado», rojo #C81E1E para «no
  disponible / sin credencial», naranja de texto (#9A5200) para «sin
  verificar en vivo», «sin dato» y lo que el motor no puede. Siempre con
  palabras.
- **Nuevo motor:** campos uno debajo de otro con el título en semibold y la
  ayuda apagada debajo (estilo BFF), formato de salida en control segmentado
  en píldora, y un solo botón de acento: **Probar**. Al lado, una línea de
  estado (azul mientras prueba, verde «Guardado», rojo «No se guardó») y
  debajo el resultado en palabras: salida, costo y turnos (o «no los da») y
  si reanuda.
- **Sin tecnicismos de más:** «motor», «comando», «formato de salida», «URL
  base», «credencial», «sin dato». Lo técnico (rutas JSON, evento:ruta) solo
  aparece en los campos de JSON, que se apagan con «Texto normal».
- **Coste de arranque medido:** ver ESTADO-MOTOR-GENERICO.md (≈ +0,3 s con
  CTk; la clásica no añade).

## Ronda 0.3.0 — Guardrail siempre a la vista (26 oct 2026)

- **Fila fija de Tareas** (fuera del scroll, CustomTkinter con respaldo
  clásico): tarjeta de esquinas 10 y borde fino; «Permisos» apagado + nivel en
  semibold; «N esperando tu aprobación» en semibold; «Cambiar nivel» (botón
  gris, esquinas 8) a la derecha; debajo, una línea apagada que explica.
- **Colores del nivel:** «Siempre pregunta» verde de texto (es lo seguro),
  «Solo lo delicado» texto normal, «Sin preguntar» rojo. **Contador:** rojo
  con ≥1, apagado con 0. Rojo #FF6363 solo en oscuro; en claro #C81E1E
  (6,3:1 sobre blanco; nunca #FF6363 sobre blanco, 2,91:1).
- **Popup:** tarjeta CustomTkinter (respaldo clásico), título semibold con el
  número exacto, una línea apagada con el nivel, «Ver tareas» (único botón de
  acento azul) + «Cerrar». Abajo a la derecha, encima de la bandeja.
- **Distintivo de la bandeja** (el mismo lienzo de `_tray_image`, no otro
  mecanismo): ámbar #FF9F0A con número #1D1D1F (9,6:1) arriba a la derecha +
  punto ámbar abajo a la izquierda; «!» blanco sobre #D70015 (5,6:1) para «Sin
  preguntar»; «?» blanco sobre #6E6E73 para «no se pudo leer». Borde #1D1D1F
  de 2 px para que se vea sobre barra clara y oscura. Manda sobre el % de
  cuota (que sigue en el tooltip).
- **Coste de arranque medido:** +0,03 s (la fila tarda 10-11 ms). Ver
  ESTADO-GUARDRAIL-VISIBLE.md.

## Ronda 0.3.0 — Vencimiento de las aprobaciones (26 oct 2026)

- **Dónde:** dentro de la tarjeta «Esperan tu aprobación» que ya existía en
  Tareas (tkinter clásico, no se reconstruyó: no es superficie nueva). No hay
  página nueva.
- **Dos líneas nuevas por tarea, debajo de «Lo hizo sensible»:** «Nivel R2,
  irreversible o externo. Motivo: …» (apagado, 9) y «Vence el lun 26/10 a las
  05:32, hora de Caracas (quedan 1 h 59 min). Si no respondes, no se hace.»
  (semibold 10, texto normal; naranja de texto #9A5200 en los últimos 15 min y
  al vencer). La cuenta atrás se repinta sin rehacer la tarjeta. El color nunca
  va solo: la frase dice el tiempo.
- **Columna Estado:** «vencida» / «R3 denegada» (corto para que quepa); el
  motivo completo y el approval_id van en DETALLE.
- **Sin tecnicismos:** «nivel», «vence», «hora de Caracas», «tardía,
  descartada». El approval_id solo aparece en DETALLE y en el pedido de WhatsApp.

## Ronda 0.3.0 — Checkpoint por ronda (26 oct 2026)

- **Dónde:** no hay página nueva ni superficie nueva. Lo visible va como líneas
  dentro de la tarjeta DETALLE de Tareas (el `tk.Label` que ya existía, así que
  sigue en tkinter clásico; la regla CustomTkinter no aplica porque no se
  construyó ninguna fila ni control nuevo) y en el banner de trabajo.
- **Líneas de DETALLE**, en el mismo cuerpo 10 y color de texto normal que el
  resto del detalle, debajo de «Recuperada tras corte»:
  «Último estado conocido (al volver a arrancar, 2026-10-26 04:25): ronda 2,
  siguiente_paso revisar (murió con Claude corriendo; se reanuda la ronda 2 con la
  misma sesión y la misma carpeta). Gastado hasta ese punto: $0.02 eq.» ·
  «Checkpoint: ronda 2 (intento 2), motor corriendo, siguiente_paso revisar;
  reanudada desde «ronda 2»» · «Plan …: fase 1 a medias, fase 2 pendiente» ·
  «Ronda 2: se reanudó sin la sesión original (…)».
- **Banner:** el paso añade «(reanuda tras corte)» cuando la ronda viene del
  checkpoint, o «Revisando … (reanuda tras corte: solo la revisión)».
- **Palabras:** «último estado conocido», «siguiente_paso», «sesión», «resumen
  del checkpoint». `siguiente_paso` se deja tal cual porque es lo que Leandro
  pidió leer y lo que Growi lee en la VM; nada de JSON ni ids de sesión en la
  ventana (el id solo va en la base, el transcript y el resultado).
- **Dineros:** el «gastado hasta ese punto» usa la misma celda que la columna
  Costo (real / eq. / $0 local); lo que llevaba el paso cortado sale como «~$x
  estimado en vivo; no se suma» porque no hay cifra final.

## Ronda 0.3.0 — Criterios tipados y doble juez (26 oct 2026)

- **Dónde:** no hay página nueva ni superficie nueva. Lo visible va como líneas
  dentro de la tarjeta DETALLE de Tareas (el `tk.Label` que ya existía) y en la
  columna Revisión. No se construyó ninguna fila ni control nuevo, así que la
  regla CustomTkinter no aplica (igual que en el checkpoint). La corrección de
  Leandro va por la paleta Ctrl+K (dos acciones nuevas en la lista que ya
  existía) con el `messagebox` de confirmación de siempre.
- **Líneas de DETALLE**, debajo de «Revisión (…)», sangradas, cuerpo 10, color
  de texto normal: «Comprobado por código (pasa / FALLA): [lineas] informe.md
  tiene al menos 150 líneas: … tiene 20 líneas reales (pedido: al menos 150):
  no» (FALLA en mayúsculas: la palabra dice el estado, el color nunca va solo);
  «Juez: Local Hermes 3 directo $0 dijo aprobado (completitud 5, corrección 5,
  no-regresión 5, evidencia 4)»; «… aprobó, pero un check determinista falla:
  no se aprueba (los hechos mandan)»; «Segundo juez (…): claude haiku, valido,
  41.7 s, $0.0077 eq.» o «Sin segundo juez: tarea R0: …»; el recorte del
  contexto si lo hubo; «Tu etiqueta: «rechazado» (…, corrige al revisor)» o la
  pista «¿La revisión se equivocó? Ctrl+K → «Corregir la revisión»».
- **Desacuerdo:** «Revisión (llama): necesita tu decisión (los dos jueces no
  coinciden)» y un bloque «Los dos veredictos:» con «– Juez 1: …» y «– Juez 2:
  …», cada uno con su sí/no, las cuatro puntuaciones y lo que falta. La columna
  Revisión dice «Jueces en desacuerdo: decide tú».
- **Palabras:** «comprobado por código», «juez», «veredicto», «rúbrica»,
  «segundo juez», «tu etiqueta». El detalle de un esquema que no valida va al
  `.revision.json` y al registro; en la ventana solo sale «sin veredicto
  válido» con el motivo corto (p. ej. «la respuesta no trae ningún JSON»).
  En ese caso la columna Revisión dice «sin revisión» (en texto plano, sin
  tilde: sin revision), nunca «Sí».
- **Dineros:** el costo del segundo juez sale como «$x eq.» (sesión Max, a
  precio de lista), igual que la columna Costo.

## Ronda 0.3.0 — Gateway unificado: Estado como panel de control y Claves (26 oct 2026)

- **Dónde:** página Estado, tarjeta **Gateway** justo debajo de Servicios (antes
  del Mapa de disponibilidad), y tarjeta **Claves** al final de Ajustes. Las dos
  son superficies nuevas: CustomTkinter con la versión tkinter clásica de
  respaldo (el mismo código con el kit `_KitCtk` / `_KitTk`, como Motores). Las
  tablas, el Registro, los Canvas y la mascota no se tocaron.
- **Gateway:** etiqueta de sección apagada fuera de la tarjeta, tarjeta de
  esquinas 10 con borde fino, una línea de explicación apagada y una línea de
  estado; debajo, grupos con su título en semibold (Proceso, Cola, Skills,
  Modelos y respaldo, Canales, Motores, Recarga en caliente) y filas de dos
  columnas: etiqueta apagada a la izquierda, valor a la derecha (estilo ficha de
  Motores). Cada motor lleva dos filas sangradas: Credencial (proveedor, clave
  activa, «termina en XXXX») y Base URL.
- **Matriz de estados:** cargando (azul de texto), sin conexión y error (rojo
  #C81E1E, con «Reintentar», botón gris de esquinas 8), vacío (naranja de texto
  #9A5200, «no hay ningún motor descrito»), contenido («Leído en vivo a las
  HH:MM:SS», apagado). El color nunca va solo: la frase dice el estado.
- **Colores de valor:** verde de texto #1F7A33 para vivo / disponible /
  conectado, rojo para no disponible / sin credencial, naranja de texto para
  avisos (re-encoladas al arrancar, esperas, sin túnel). La mascota apagada se
  dice «apagada» en gris, no en rojo (no es un fallo).
- **Claves:** por referencia, el título «proveedor, referencia «etiqueta»» en
  semibold, «La usa: …» apagado, un selector (esquinas 8) con las claves
  guardadas del mismo proveedor («clave-b (termina en 2222)») + «Usar esta», y
  una línea verde «Activa: …» o roja si no está guardada. Se dibuja la primera
  vez que se abre Ajustes (no suma al arranque).
- **Sin tecnicismos de más:** «gateway», «plano de control», «token» y «túnel»
  solo en esta tarjeta, que es justamente lo que enseña; nada de JSON ni pids
  fuera de la fila Proceso.
- **Coste de arranque medido:** +0,035 s de media (`build_gui` 2,005 → 2,039 s,
  3 veces cada uno); el panel tarda 63-65 ms; Claves 218 ms al abrir Ajustes.
  Ver ESTADO-GATEWAY.md.

## Ronda 0.3.0 — Skills nativas: sección Skills de Bridge (26 oct 2026)

- **Dónde:** página Skills (la que ya existía en la barra lateral), arriba, antes
  de la lista de Claude Code (que sigue en tkinter clásico con su Treeview). Dos
  tarjetas nuevas: **Skills de Bridge** y **Borradores**. Superficie nueva:
  CustomTkinter con la versión clásica de respaldo (el mismo código con el kit
  `_KitCtk` / `_KitTk`, como Motores y Gateway).
- **Skills de Bridge:** etiqueta de sección apagada fuera de la tarjeta, tarjeta
  de esquinas 10 con borde fino, línea de explicación apagada, una fila de
  botones (esquinas 8): **Validar skills** (el único acento azul), «Volver a
  leer» y «Abrir la carpeta» (grises). Debajo, la línea de estado y una fila por
  skill separada por una línea fina: nombre en semibold + «versión X, origen»
  apagado; la descripción en texto normal; «Requisitos: …» en semibold y una
  línea sangrada por requisito. Luego «No se cargaron (N)» con la ruta en
  semibold, el motivo en rojo y la evidencia redactada en apagado.
- **Colores (los de THEME, sin paleta nueva):** verde de texto para «está /
  todos cumplidos / pasa», rojo #C81E1E para «falta / no pasa / no se carga»,
  naranja de texto para avisos (`always`, más de 6 niveles), azul de texto
  mientras lee. El color nunca va solo: la frase dice el estado.
- **Matriz de estados:** leyendo (azul), vacía (naranja, «La carpeta está, pero
  no hay ninguna skill»), error (rojo, con el motivo y «Volver a leer» como
  reintento), sin conexión (rojo, «Sin conexión con la carpeta de skills: … no
  existe o no se puede abrir») y contenido («N cargadas, M no se cargaron. Leído
  a las …; requisitos comprobados en vivo a las …», apagado).
- **Borradores:** misma tarjeta; por borrador, nombre semibold + «(borrador, no
  activo)», descripción, de qué tarea vino (apagado) y dos botones grises
  «Editar» y «Aprobar». Sin acento: aprobar es una decisión, no la acción
  principal de la página.
- **Evidencia redactada:** una skill con un secreto (p. ej. la de prueba con
  `sk-ant-falso123`) sale «skills\con-secreto (sospechosa)», el motivo en rojo y
  la línea en apagado ya redactada: «ANTHROPIC_API_KEY=[REDACTED CREDENTIAL]». El
  secreto nunca se pinta.
- **Sin tecnicismos de más:** «skill», «requisito», «programa», «variable»,
  «borrador», «tapada», «sospechosa». YAML, frontmatter y PATH solo en los
  motivos exactos del validador (son lo que hay que corregir).
- **Coste de arranque medido:** +0,094 s de media (`build_gui` 1,905 → 1,998 s,
  3 veces cada uno, copias aisladas); la sección tarda 31-36 ms en CTk y 9 ms en
  clásico. Ver ESTADO-SKILLS.md.

## Ronda 0.3.0 — Skills semilla (26 oct 2026)

- **Sin superficie nueva:** la siembra (`--sembrar-skills`) es de consola. Las 7
  skills instaladas salen en la tarjeta **Skills de Bridge** que ya existía, con
  su descripción y sus requisitos en vivo (p. ej. «Programa «blender»: falta: no
  está en el PATH» en rojo). Ver ESTADO-SKILLS-SEMILLA.md.

## Ronda 0.3.0 — Memoria en el PC (26 oct 2026)

- **La memoria es un archivo, no una pantalla:** no hay pestaña nueva. Se ve
  abriendo `memory\MEMORY.md` o la nota del día (paleta: «Abrir la memoria»,
  «Abrir la nota de hoy…», «Abrir la carpeta de la memoria»).
- **Confirmación de cada escritura:** ventanita «Memoria» (tema claro, Segoe
  UI): título semibold «Guardado en la memoria», el mensaje con dónde quedó y
  por qué («Guardado en la nota de hoy (2026-10-26.md): «…». Porque es de un día
  concreto («25 oct»). Archivo: …»), y dos botones: **Abrir el archivo** (azul
  #007AFF, el único acento) y **Cerrar** (gris). Esc cierra. Un fallo sale con
  el mensaje en rojo y sin «Abrir». Bajo Enviar, en Tareas, la fila de estado
  repite el mensaje con «✓».
- **Paleta Ctrl+K:** al escribir «recuerda esto: …» o «/nuevo», la lista se
  reduce a una sola sección «Memoria» con una fila: «Recordar: «…»» (el hecho
  recortado a 40 caracteres con «…», para que no choque con el chip Enter) o
  «Sesión nueva: guardar el snapshot y empezar otra».
- **Conflictos de sync:** aviso de bandeja «Memoria: N conflicto(s) con la VM»
  que lleva al Registro; nada de diálogos que bloqueen.
- Capturas: `share\outbox\capturas-memoria\r3-*.png`. Ver ESTADO-MEMORIA.md.


## Ronda 0.3.0 — Claves BYOK: una fila por clave (26 oct 2026)

- **Dónde:** Ajustes → Claves (sustituye la tarjeta «clave activa por
  referencia» del gateway) y la página APIs (sustituye la tabla y las filas «una
  por servicio»). Es la misma superficie dibujada dos veces, la primera vez que
  se abre cada página (no suma al arranque). CustomTkinter con la versión
  tkinter clásica de respaldo (kit `_KitCtk` / `_KitTk`), colores de THEME,
  esquinas 10 en tarjetas y 8 en botones.
- **Estructura:** tarjeta «Claves» con la explicación, «Dónde se guardan» y la
  advertencia honesta (apagadas); un mensaje de la última acción; grupos por
  proveedor con el título en semibold (y la nota de Gemini apagada); cada clave
  es una sub-tarjeta: «Proveedor «etiqueta» ••••1234» en semibold + «Activa»
  (verde de texto) o «Inactiva» (gris) + «Usar esta» a la derecha; URL base
  editable + «Guardar URL»; línea de gasto; «Tope del mes $» + «Guardar tope»;
  «Probar sin gastar» y «Borrar»; resultado de la prueba. Debajo, la línea de la
  sesión Max y la tarjeta «Añadir o reemplazar una clave» (Guardar en azul).
- **Colores:** verde de texto solo para «Activa», guardado y clave válida; rojo
  para clave incorrecta, URL rechazada y tope alcanzado; naranja de texto para
  el 75–99 % del tope, el aviso de «borrada aquí no es revocada» y apis.json en
  texto plano. El color nunca va solo: la frase lo dice.
- **Medido:** abrir la superficie 338–414 ms con CTk (146–159 ms la clásica);
  `build_gui` sin diferencia fuera del ruido. Ver ESTADO-CREDENCIALES.md.

## Ronda 0.3.0 — Atajos personalizables: Ajustes → Atajos (27 oct 2026)

- **Patrón:** Flow Launcher (el campo se pulsa, no se escribe) + la tabla de
  conflictos de Fluent Search (interno / reservado / otra app). Superficie
  nueva con CustomTkinter (regla del piloto), con la clásica de respaldo: la
  misma sección sale en `_build_ajustes_tk` con el mismo «kit» de filas.
- **Estructura:** sección «Atajos» justo después de General. Una fila de
  explicación (y el aviso de settings.json dañado, si lo hay); «Dentro de
  Bridge» y «En cualquier aplicación» como subtítulos (semibold + explicación
  apagada); cada acción es una fila: título + explicación a la izquierda,
  campo blanco (esquina 8, borde fino #E5E5EA) + «Quitar» a la derecha. Debajo
  del título, el mensaje de la última acción y, si hay sugerencia, un botón
  azul «Usar Ctrl + Alt + …».
- **Estados del campo:** «Sin atajo» en gris; la combinación en texto normal
  («Ctrl + Alt + T», palabras normales con espacios); capturando: borde del
  azul de acento de THEME (#0066CC, el mismo del foco en el piloto) de 2 px y
  «Pulsa la combinación…», que se va completando
  («Ctrl + Alt + …»).
- **Colores:** verde de texto solo para «Guardado…»; rojo para rechazos y
  conflictos; gris para «Cancelado» y la ayuda. El color nunca va solo: la frase
  dice el motivo. Sin colores nuevos (THEME).
- **Medido:** la sección Atajos 117–146 ms (CTk); página Ajustes entera
  1,42–1,80 s antes y 1,55–1,75 s después (ruido del PC mayor que la
  diferencia). Ver ESTADO-ATAJOS.md.

## Ronda 0.3.0 — Comandos de IA guardados (27 oct 2026)

- **Patrón:** Raycast AI Commands (título, prompt con marcadores, icono,
  modelo, creatividad; integrados que se duplican para adaptarlos).
- **Paleta Ctrl+K (tkinter clásico, como manda el piloto):** sección nueva
  «Comandos de IA» con la lista vacía (entre Frecuentes y Todas las acciones);
  cada comando es una fila con su icono a la izquierda en gris apagado (un
  símbolo de texto, nunca un emoji) y su título; «(motor no disponible)» en el
  propio título cuando el motor no existe. El aviso de archivo dañado va el
  primero de la sección. Chip = su atajo, si lo tiene.
- **Formulario «Nuevo comando de IA»** (superficie nueva: CustomTkinter con la
  clásica de respaldo, kit `_KitCtk` / `_KitTk`): ventana propia con scroll,
  tarjeta de esquinas 10 y borde fino; cada campo con el título en semibold y la
  ayuda apagada debajo (estilo BFF); creatividad y salida en control segmentado;
  el atajo con el mismo campo «pulsa la combinación» de Ajustes → Atajos (el
  mensaje va debajo, a lo ancho). Un solo acento azul: **Guardar**. «Borrar
  este comando» gris, a la derecha, con confirmación.
- **Ventana del comando** (misma regla): título con el icono, línea apagada con
  creatividad y salida, línea del motor (azul mientras comprueba, verde de
  texto «disponible», rojo «no disponible»), «Texto seleccionado» con su origen
  apagado, un campo por dato pedido, **Ejecutar** (el único acento), la línea de
  estado y, al terminar, el resultado editable con «Copiar» y «Reemplazar el
  texto» (grises).
- **Confirmación del reemplazo** (guardrail «Preguntarme siempre»): título
  semibold, permisos apagados, el texto nuevo completo y el que se sustituye
  (de solo lectura), **Reemplazar** (acento) y «Cancelar». Modal; Esc cancela.
- **Colores:** los de THEME. Verde de texto para «disponible», «Guardado» y
  «Reemplazado… con tu confirmación»; naranja de texto para «sin preguntar» y
  «esperando tu sí»; rojo para «motor no disponible», «Falta …» y archivo
  dañado. El color nunca va solo: la frase dice el estado.
- **Medido:** ver ESTADO-COMANDOS-IA.md (arranque sin diferencia fuera del
  ruido; el formulario se abre en 0,2–0,5 s con CTk, 0,05 s en clásico).

## Ronda 0.3.0 — Asistentes personalizados = perfiles (27 oct 2026)

- **Qué es:** un asistente NO es un modelo nuevo: nombre + foto + para qué
  sirve + instrucciones + modelo por defecto (id de motor) + modelo de revisión
  + canales + skills + tono + carpetas + guardrail. Un archivo por perfil en
  `asistentes\<id>.md` (frontmatter YAML + instrucciones en Markdown).
- **Paleta Ctrl+K (tkinter clásico, como manda el piloto):** fila fija arriba,
  bajo la ayuda, en el gris de tarjeta: foto redonda de 28 px, «Trabajas con
  Growi» en semibold y debajo, apagado, «Claude, todas las de Carpetas, sin
  preguntar (el perfil: siempre pregunta)»; a la derecha el chip gris
  «Cambiar» (filtra la lista a los perfiles). Sección nueva «Asistentes» entre
  Frecuentes y Comandos de IA: una fila por perfil con su foto de 20 px
  («Usar Contable», «Growi (activo)»), «Nuevo asistente» y «Abrir la carpeta de
  asistentes». El aviso «Asistentes: N no se cargaron (ver por qué)» va primero
  con «!». Junto a «Recordar: …» sale «Recordar solo para <perfil> (sus notas
  propias)».
- **Bandeja:** «Asistente: Growi» con submenú de casillas de radio (los perfiles
  con canal bandeja), «Nuevo asistente…» y el aviso de los que no cargan. El
  tooltip suma la línea «Asistente: Growi». Los menús de pystray no dibujan
  imágenes: la foto sale en el aviso del cambio.
- **Aviso del cambio** (superficie nueva: CustomTkinter con la clásica de
  respaldo): tarjeta abajo a la derecha, como el popup del guardrail; foto de
  40 px, «Ahora trabajas con …» (título semibold), «Antes: …» apagado, y tres
  líneas: modelo, carpetas y permisos (con el nivel de antes si cambió).
  «Cerrar» gris; se va solo a los 8 s.
- **Formulario «Nuevo asistente»** (superficie nueva: CTk con la clásica de
  respaldo, kit `_KitCtk` / `_KitTk`): ventana con scroll, tarjeta de esquinas
  10, cada campo con título semibold y ayuda apagada (estilo BFF). Foto con
  vista previa redonda y «Elegir…»; modelo y revisión en desplegable; tono y
  guardrail en control segmentado; canales en casillas (WhatsApp «(no
  existe)» y apagado si el canal no existe); carpetas en segmentado «Todas las
  de Carpetas / Solo estas / Ninguna de trabajo» + filas «ruta · Solo leer /
  Leer y escribir · Quitar». Un solo acento azul: **Guardar**; «Abrir el
  archivo (avanzado)» gris. Al elegir «Hazlo sin preguntar» la explicación se
  pone roja y aparece, en semibold rojo, «Para bajar los permisos, escribe SIN
  PREGUNTAR (sin eso no se guarda)» con su campo.
- **Avatar por defecto:** círculo #E8E8ED con la inicial en #1D1D1F (colores
  que ya estaban en THEME / _DARK_MAP). Sin colores nuevos.
- **Colores:** verde de texto para «Guardado» y «Están todas» (skills); naranja
  de texto para foto que no existe y skills que faltan; rojo para motor no
  disponible, carpeta que no existe, «nunca» y los rechazos. El color nunca va
  solo: la frase lo dice.
- **Medido:** ver ESTADO-ASISTENTES.md (leer los perfiles 4,7 ms; arranque sin
  diferencia fuera del ruido; formulario 0,6–1,9 s con CTk, 0,09 s clásico).

## Ronda 0.3.0 — Temas: Claro / Oscuro Raycast / Según el sistema (27 oct 2026)

- **Sustituye** al párrafo «Tema oscuro (Dirección Raycast), siguiendo a
  Windows» de más arriba (#1E1E20…): ese oscuro ya no se usa.
- **Archivos:** `temas\claro.json` (el de siempre, estilo Mac, por defecto) y
  `temas\oscuro-raycast.json`. Cada uno: `nombre`, `tipo` (claro/oscuro),
  `tokens` (los de THEME: bg, sidebar, card, field, text, muted, line, green,
  green_text, blue, orange, orange_text, red), `fuente` (Segoe UI 22/11/10/9),
  `fijos` (botones grises, acento y su texto) y `mapa` (los grises fijos del
  claro → su par en oscuro). THEME sigue siendo la única fuente de verdad: el
  tema solo rellena THEME.
- **Oscuro Raycast:** fondo #0F0F0F, tarjetas y barra lateral #1A1A1C, texto
  #F4F4F5, apagado #A1A1AA (7,48:1), líneas #2C2C30, verde #34C759 (verde de
  texto #4CD964), acento #FF6363 con texto #0F0F0F encima (6,59:1; blanco
  sobre #FF6363 no llega), rojo de error #FF453A, naranja de texto #FFB340.
- **Claro:** sin cambios. Nunca texto #FF6363 en claro (2,91:1): ahí el rojo
  es #C81E1E (5,74:1).
- **Selector (Ajustes → Apariencia, CTk con la clásica de respaldo):** control
  segmentado «Claro / Oscuro / Según el sistema» (esquinas 8), debajo «Tema
  por nombre» (desplegable con los temas de la carpeta) + «Abrir la carpeta de
  temas», una línea apagada «Ahora: …» y, en rojo de texto, un renglón por
  archivo que no se cargó con el motivo («le falta el token «line»», «no es
  JSON válido (línea 1…)», «contraste 1,69:1 de «muted» sobre «bg»…»).
- **Cambio en caliente:** una tapa del tema nuevo («Cambiando a «…»…») cubre
  la ventana mientras se re-pinta; nunca se ve mitad clara y mitad oscura. Si
  algo no se puede re-pintar (otra fuente o tamaños, colores ambiguos, un
  widget con un color fuera del tema) no se toca nada, se guarda y se pide
  reiniciar (reinicio honesto). El texto del estado («Conectado», «Todo
  encendido») es el mismo en los dos temas.
- **Lo que no es tema:** layout, bordes de ventana, esquinas, sombras,
  transparencias, animaciones, el dibujo del icono de la bandeja y de la
  mascota. Alto contraste de Windows: fuera de este cambio.
