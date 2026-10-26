# Growi Bridge 0.1.0 Alpha (build 2: orquestador + paleta + tareas) — puente + runner + proxy + pantalla + mascota + APIs en uno

Un solo proceso, una ventana con pestañas y un icono en la bandeja (la foto
de Growi). Reemplaza al servidor viejo (`pc-server.py`), al runner y a la
v1.0 de la app.

## Qué hace

- **Puente** — el servidor de archivos PC ↔ VM (puerto 8787, secreto en
  `secret.txt`). Sin él, Growi no te alcanza. El indicador de
  sincronización muestra qué se está descargando o enviando en cada momento.
- **Runner** — vigila `share\inbox\runner-tasks\` y corre `claude -p` sin
  ventana con las tareas que Growi manda; devuelve el resultado al outbox.
  Con sesiones continuas (`session_id`).
- **Proxy** — interruptor propio para encender/apagar el proxy (host, puerto,
  usuario y clave configurables en la ventana; cada quien usa los suyos).
  Encendido, Claude sale por el proxy; apagado, deja de usarlo.
- **Carpetas** — pestaña para elegir qué carpetas puede ver Claude Code.
  Por defecto: el Inbox del puente + tu carpeta principal. Growi también
  puede modificar esta lista pidiéndole a Claude que edite `folders.json`.
- **Skills** — pestaña con las skills instaladas de Claude Code
  (`~/.claude/skills/`).
- **Pantalla** — compartir pantalla con Growi: fotogramas comprimidos (JPEG,
  máx. 1280px) cada 0.5 s, 1 s, 5 s, 10 s o 30 s, solo cuando tú lo activas.
  Cada grabación crea su propia carpeta `outbox/screens/AAAAMMDD-HHMMSS/` con
  todos los fotogramas (`frame-NNNN.jpg`); las sesiones de más de 7 días se
  borran solas al empezar una nueva. Growi mira un fotograma cuando se lo
  pides o cuando hace falta; no es video en vivo.
- **APIs** — pestaña para guardar claves de APIs privadas (solo en este PC,
  `apis.json`; la clave se muestra enmascarada). Se añade desde la app o
  desde WhatsApp: le dices a Growi la API y la clave, y llega al PC en
  segundos por el puente. Cada proveedor (Anthropic, OpenAI, Gemini, Groq,
  OpenRouter) tiene su botón Probar (consulta gratis) y su estado.
- **Modelos** — orquestador de modelos estilo Ollama: Comprobar mi PC (GPU,
  VRAM, RAM, disco), librería de 20 modelos (`models-catalog.json`) con
  semáforo verde/naranja/rojo según tu PC, instalar/borrar/elegir el modelo
  local por defecto, quién responde, habilidades con interruptor, canales y
  reglas (`rules.json`, van al principio de cada tarea). Growi hace lo mismo
  desde la VM con tasks `ollama_action` (pull / rm / list), y el runner
  acepta `model: "api:<proveedor>:<modelo>"`.
- **Tareas (orquestación)** — el runner ya no solo lanza comandos: cada
  tarea se revisa sola al terminar. Si falta algo, Growi lo corrige hasta 3
  veces (rondas de corrección); si aun así no queda, la tarea queda en
  «necesita decisión» con un reporte honesto. La pestaña Tareas muestra el
  estado (pendiente, en curso, revisando, aprobada, necesita decisión,
  fallida), el motor, la ronda (1/3), el costo acumulado y la revisión. Un
  banner arriba dice qué está haciendo el motor, con un botón **Parar** que
  mata el proceso de verdad. Un solo aviso al terminar cada tarea.
- **Motores** — `engines.json` describe cada motor: Claude (el principal),
  Hermes 3 directo por llama.cpp ($0; si no está encendido, el runner lo
  arranca solo), Ollama ($0), Codex (si está instalado) y Meshy (3D). Cada
  tarea elige el suyo; sin decir nada, Claude.
- **Permisos** — antes de borrar, publicar, gastar o enviar algo, la tarea
  espera tu aprobación en Tareas (Ajustes → Permisos: «Preguntarme siempre»,
  «Preguntarme solo lo delicado» o «Hazlo sin preguntar», que pide doble
  confirmación).
- **Recursos** — monitor del PC (barra lateral, entre Tareas y Ajustes;
  Ctrl+0; el contador es el % de CPU). Cuatro tarjetas que se actualizan
  cada 2 s: CPU, RAM usada/total, GPU % + VRAM usada/total (por
  `nvidia-smi`; sin GPU NVIDIA o si no responde dice «sin GPU NVIDIA», nunca
  inventa números) y disco libre del sistema. Debajo, **Mis procesos**: lo
  que Growi tiene andando (la app, lo que lanzó el runner o Modelos y sus
  hijos, claude, ollama, llama-server, codex, meshy, browser-server) con
  PID, CPU %, RAM (MB, memoria privada activa, como el Administrador de
  tareas) y quién lo lanzó; ordenado por CPU, con buscador y Actualizar.
  «Ver todos los procesos» muestra el sistema entero. **Cerrar proceso**
  (o Supr) siempre pide confirmación con el nombre y el PID y mata con
  `taskkill /F`; los críticos de Windows (System, System Idle Process,
  csrss, smss, winlogon, services, lsass, svchost, explorer, Registry,
  fontdrvhost, dwm y wininit) están bloqueados; cerrar Growi Bridge pide
  doble confirmación. Lee en un hilo aparte solo con la pestaña a la vista
  (en otra pestaña o minimizada, se pausa). Usa psutil; si falta, lo instala
  con pip (solo psutil) y, si no puede, usa tasklist (sin CPU por proceso)
  y lo dice abajo de la lista.
- **Mascota** — Growi en la esquina inferior derecha, con animaciones según
  el estado: descansa, trabaja mientras Claude corre una tarea, saluda al
  hacer clic y celebra cuando Claude termina una tarea. Clic para escribirle
  un mensaje rápido; el mensaje llega a Growi por el puente y la respuesta
  llega en el chat.
- **Botón grande** — enciende/apaga puente + runner juntos, con animación.
  Cada servicio tiene además su propio interruptor en su fila.
- **Ajustes** — actualización automática (se actualiza sola desde GitHub
  cuando hay una versión nueva, sin preguntar), inicio automático al
  encender la PC, mascota visible.
- **PC** — botones para apagar o reiniciar el PC (con confirmación y 60 s
  de margen, cancelable) y para cancelar un apagado programado.
- **Actualizaciones** — busca nuevas versiones en GitHub y se actualiza
  sola (descarga todos los archivos y se reinicia).
- **Administrador** — la app detecta si corre elevada; el instalador la
  deja en arranque automático con privilegios máximos para no tener
  problemas de permisos.

## Seguridad (acotada, pero sin amarrar las manos)

- Solo ejecuta `claude -p`, nunca shell directo con nada que venga de un
  task. Las tareas solo llegan por el puente (secreto compartido).
- Claude Code solo trabaja dentro de las carpetas de la pestaña Carpetas.
- **Borrar fuera de las carpetas permitidas requiere tu autorización
  explícita cada vez.** Growi no borra nada fuera de esas carpetas sin que
  tú lo autorices. La única excepción automática es la limpieza de sesiones
  viejas de pantalla (más de 7 días), que se hace al empezar una grabación
  nueva.
- Ningún resultado dice que algo funcionó si no se comprobó contra archivos
  reales; si no se pudo confirmar, dice «Lo intenté pero no pude confirmar
  que funcionara».
- Todo queda registrado (task en `done/`, resultado en outbox,
  `growi-bridge.log`).

## Instalar (una sola vez)

1. Cierra la ventana del servidor viejo, del runner o de la app v1.0 si
   están abiertas (el instalador también las cierra solo).
2. Doble clic a `instalar-growi-bridge.bat` (está en el Inbox).
3. Busca mi foto en la bandeja del sistema, abajo a la derecha.
4. La primera vez: abre la ventana y configura el proxy. Si ya tenías las
   variables `HTTPS_PROXY` puestas, la app las hereda sola.

Para probar en ventana visible antes de instalar: `probar-growi-bridge.bat`.

## La ventana

- **Estado:** foto, botón grande de encendido, estado de puente/runner/
  proxy con su interruptor y su píldora de valor, indicador de
  sincronización, configuración del proxy, ajustes (actualización
  automática, inicio automático, mascota), botones de PC (apagar/reiniciar/
  cancelar), botones (Inbox, Outbox, actualizaciones, salir) y registro.
- **Carpetas:** añadir/quitar/restablecer las carpetas permitidas.
- **Skills:** lista de skills instaladas de Claude Code.
- **Pantalla:** compartir/dejar de compartir, cada cuántos segundos
  (0.5 s, 1 s, 5 s, 10 s, 30 s), limpiar sesiones viejas, abrir la carpeta
  de sesiones.
- **APIs:** lista de APIs privadas, añadir/quitar, añadir por WhatsApp.
- **Recursos:** CPU, RAM, GPU y disco en vivo; los procesos de Growi
  primero (o todos), buscar, cerrar un proceso con confirmación.

La X minimiza (la ventana queda minimizada y la mascota sigue en su
esquina). Salir de verdad es con el botón Salir o desde el menú de la
bandeja (clic derecho al icono).

## El menú de la bandeja

Clic derecho a mi foto: Mostrar ventana, Puente, Runner, Proxy (✓ cuando
está encendido), Mascota (✓), Compartir pantalla (✓), Salir. Doble clic
muestra la ventana.

## La cola sobrevive a apagones (cola.db)

- Cada tarea que entra a `runner-tasks/` se apunta en `cola.db` (SQLite,
  junto al programa, modo WAL + `synchronous=FULL`) **antes** de recogerla:
  estado (en_cola / en_curso / esperando_aprobacion / terminada / fallida /
  necesita_decision / archivada), intentos, reintentos, motor, ronda,
  tarea_padre, fase y horas. El `.task.json` sigue siendo el encargo.
- **Si se va la luz** con una tarea corriendo, al volver a abrir la app esa
  tarea vuelve a la cola (intentos+1) y se repite entera; su resultado dice
  «Recuperada tras corte». Si se corta 3 veces seguidas corriendo, queda
  fallida con el motivo (para no entrar en bucle).
- **Errores pasajeros** (red, timeout del motor, llama-server u Ollama
  caídos, proxy caído, 429/5xx): se reintenta a los ~30 s, ~2 min y ~8 min
  (con algo de azar); el resultado trae `reintentos`. **Errores definitivos**
  (motor que no existe, falta la clave, parada o rechazada por ti): fallida
  en el acto, sin reintentos.
- Tareas muestra «reintento HH:MM:SS» en la fila, el motivo en DETALLE y
  «en cola: N · próximo reintento …» arriba. `runner-status.json` trae
  `cola_pendiente` y `proximo_reintento`.
- Lo que quedó a medias en `processing/` de antes de existir la cola **no se
  repite solo** (podría ser una instalación vieja): sale como «necesita
  decisión». Para repetir algo: elígelo en Tareas → **Volver a la cola**
  (o Ctrl+K → «Volver a encolar la tarea elegida»).
- A los 30 días las terminadas/fallidas pasan a «archivada» y dejan de
  salir en Tareas. No se borra nada: `.task.json`, `.result.json` y
  `.revision.json` siguen donde estaban.

## Consumo en vivo (runner-live.json)

- Mientras una tarea corre, la pestaña **Tareas** muestra en su fila, cada
  ~5 s: estado (en curso / revisando / terminado), motor y modelo, tiempo,
  tokens de entrada / salida hasta ahora y costo hasta ahora. Debajo de la
  lista, **Consumo de hoy por modelo**: lo terminado hoy, separado en
  $ real (APIs con tu clave), $ equivalente Max (sesión Max, a precio de
  lista; no se cobra aparte) y $0 local. **No hay cuota de Max**: Anthropic
  no publica cuánto te queda; solo se ve lo acumulado.
- Claude corre con `--output-format stream-json` y un hilo va leyendo cada
  mensaje según llega. El costo en vivo es un **estimado** (~$) a precio de
  lista con la tabla `precios` de `engines.json`; al terminar vale el que
  reporta Claude (`cost_usd_final` = `cost_usd` del resultado). Si Claude no
  entiende stream-json, la tarea se corre como antes (`--output-format
  json`) y el vivo dice «sin vivo». Nunca se inventan números.
- Hermes directo (llama) y Ollama van en streaming: cada trozo que llega
  suma un token de salida; al final manda el uso que reporta el servidor.
  Siempre $0.
- `share\outbox\runner-live.json` es la única fuente de verdad en vivo
  (la ventana lo lee; el puente lo sincroniza a la VM como el resto del
  outbox). Campos: `task_id`, `raiz`, `motor`, `modelo`, `modelo_real`,
  `estado`, `started_at`, `elapsed_s`, `tokens_in`, `tokens_out`,
  `cost_usd_estimado`, `cost_usd_final` (null hasta terminar), `ronda`,
  `tarea_padre`, `dinero` (real / equiv / local), `modo_vivo` (en vivo /
  sin vivo / al cerrar), `por_modelo`, `revision` (los tokens de la
  revisión van aparte), `nota`. Al acabar queda con `estado: "terminado"`.
- El latido ya no se congela: `runner-status.json` se reescribe cada 60 s
  también mientras una tarea corre, y `current` trae `{id, motor, modelo}`
  de la tarea en curso (null si no hay). **Un `last_poll` de hace más de
  2 min significa problema, no «Claude trabajando».**
- Cada `.result.json` trae además `uso` (tokens de entrada / salida, modelo
  real, por modelo y su desglose). Los demás campos son los de siempre.

## Si algo falla

- **Puerto 8787 ocupado:** sigue corriendo el `pc-server.py` viejo.
  Ciérralo y reinicia la app.
- **Falta secret.txt:** el puente no arranca; el archivo vive en la misma
  carpeta que `growi-bridge.py`.
- **Falta configurar el proxy:** el interruptor te lo pide; pon host,
  puerto, usuario y clave y guarda.
- **Sin icono en la bandeja:** falta `pystray` (`pip install pystray
  pillow`); la ventana sigue funcionando.
- **Registro completo:** `growi-bridge.log` junto al programa.

## Configuración inicial y Venezuela primero

- **Configuración inicial** (la primera vez, o en Ajustes → «Volver a hacer la
  configuración inicial»): eliges tu asistente principal (Muse, Claude Code,
  Grok, Dot, Codex u otro), conectas (sesión, clave o «Lo haré más tarde», y el
  botón **Conectar** que prueba tu proxy sin pedirte nada), eliges carpetas y
  nivel (Solo mirar / Mirar y cambiar / Preguntarme siempre) y la app prueba
  que todo anda. Todo se guarda en `settings.json`.
- **Mapa de disponibilidad** (Estado): Claude, ChatGPT, Gemini, Ollama local,
  Proxy VPS e Internet, comprobados de verdad (con y sin proxy) al arrancar,
  cada 10 min y con «Volver a comprobar». Las reglas están en
  `availability.json`, no en el código.
- **Proxy:** estado siempre visible (barra lateral y bandeja), «Probar proxy»,
  «Exportar mis conversaciones» y ajustes avanzados aparte. Si la nube cae, lo
  que pides desde la app pasa solo al modelo local y te lo dice.
- **Gasto:** en el icono de la bandeja (pasa el ratón): real / equivalente Max /
  local. Clic = desglose en Tareas. La cuota de Max sale «no disponible»
  porque no hay forma pública de leerla.
- **Modo oscuro** siguiendo a Windows (o elígelo en Ajustes → Apariencia).

## Dos carriles (puerto configurable)

- **Puerto del puente:** `settings.json` → `bridge_port` (por defecto 8787) o la
  variable de entorno `GROWI_BRIDGE_PORT` (gana la variable).
- **Carril A** = esta carpeta, puerto 8787, la app de siempre: acepta tasks sin
  `"lane"` o con `"lane": "a"` (rechaza los marcados `"lane": "b"`).
- **Carril B** = `C:\Users\forte\growi-bridge-lane2\`, puerto 8788, cola y
  share propios (`settings.json` con `"lane": "b"`). Solo corre tasks con
  `"lane": "b"` y una lista `"archivos"` dentro de su carpeta; nunca
  growi-bridge.py, runner.py, engines.json, settings.json ni
  `share\inbox\growi-bridge-app\` del carril A. Solo motores de nube (claude,
  codex). Si declara `"lee"` con rutas del carril A, espera (máx. 10 min) a que
  el carril A esté libre. Sin asistente inicial, mascota, atajo global ni
  auto-actualización.
- **Sin fusión automática:** cada carril es dueño de su carpeta; lo que pase de
  uno a otro lo mueve la VM por el puente, a mano y con verificación.
- Tarea programada `GrowiBridgeLane2` (al iniciar sesión) y el vigilante
  (`watchdog\watchdog.ps1`) mira 8787 y 8788 con un tope por carril.
  Detalles: `share\outbox\ESTADO-DOS-CARRILES.md`.
