# Growi Bridge 0.1.0 Alpha (build 2: orquestador + paleta + tareas) — puente + runner + proxy + pantalla + mascota + APIs en uno

Un solo proceso, una ventana con pestañas y un icono en la bandeja (la foto
de Growi). Reemplaza al servidor viejo (`pc-server.py`), al runner y a la
v1.0 de la app.

## Qué hace

- **Puente** — el servidor de archivos PC ↔ VM (puerto 8787, solo en
  127.0.0.1 y en la IP de Tailscale de este PC; token cifrado fuera de la
  carpeta, ver «Gateway unificado»). Sin él, Growi no te alcanza. El indicador de
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
- **Skills** — skills nativas de Bridge (`skills\` junto al programa: el
  runner le pasa al motor solo las que la tarea pide, por su descripción; ver
  «Skills nativas») y, debajo, las skills instaladas de Claude Code
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
- **Motores** — `engines.json` (esquema 2) DESCRIBE cada motor con datos:
  Claude (el principal), Hermes 3 directo por llama.cpp ($0; si no está
  encendido, el runner lo arranca solo), Ollama ($0), Codex (segundo motor
  de código: entra con la sesión ChatGPT Plus del CLI, sin clave; verificado
  en vivo y reanuda la sesión; no da costo: «sin dato»), Gemini (por
  Antigravity CLI, `agy`: entra con la sesión de agy o con clave) y Meshy
  (3D). El runner no tiene código especial por motor.
  Cada tarea elige el suyo; sin decir nada, el de `por_defecto` (Claude).
  En Modelos → **Motores** cada uno tiene su ficha honesta y en **Nuevo
  motor** se añade uno pegando su comando (ver «Motores descritos con datos»).
- **Permisos** — antes de borrar, publicar, gastar o enviar algo, la tarea
  espera tu aprobación en Tareas (Ajustes → Permisos: «Preguntarme siempre»,
  «Preguntarme solo lo delicado» o «Hazlo sin preguntar», que pide doble
  confirmación). Cada pedido lleva su nivel R0–R3 y **vence**: si no
  respondes, no se hace (ver «Niveles de riesgo y vencimiento»).
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
- **Skills:** skills de Bridge (versión, origen, descripción y requisitos
  comprobados en vivo), «Validar skills», borradores del runner y, debajo, la
  lista de skills de Claude Code.
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
está encendido), Mascota (✓), Compartir pantalla (✓), Salir. Justo debajo de
«Abrir Growi Bridge», dos líneas dicen cuántas tareas esperan tu aprobación y el nivel de
permisos (clic: abre Tareas filtrada / Ajustes → Permisos). Un clic abre Tareas
filtrada a las que esperan tu aprobación (si no hay ninguna, Tareas sin filtro
y lo dice); doble clic muestra la ventana.

## Permisos y tareas en espera, siempre a la vista

- **Bandeja:** con ≥1 tarea en «esperando_aprobacion» el icono lleva un
  distintivo ámbar con el número (9+ si pasa de 9) y un punto ámbar abajo a la
  izquierda; con «Hazlo sin preguntar», un distintivo rojo «!»; si no se puede
  leer el estado, uno gris «?». El tooltip dice «N tareas esperando tu
  aprobación» (o «Ninguna tarea esperando») + «Permisos: Siempre pregunta /
  Solo lo delicado / Sin preguntar». Sin tareas en espera, el icono vuelve a
  lo normal en el mismo ciclo (≈1-2 s).
- **Tareas:** fila fija arriba (fuera del scroll) con el nivel, «N esperando tu
  aprobación» (0 cuando no hay ninguna; nunca se esconde) y «Cambiar nivel»
  (abre Ajustes → Permisos). Clic en el número: la lista se filtra a las que
  esperan, cada una con encargo, motor, carpeta, permisos, qué la hizo
  sensible y Aprobar / Rechazar; «Ver todas» quita el filtro.
- **Popup:** al arrancar con tareas en espera, y cuando entra alguna nueva:
  «N tareas están esperando por su aprobación» (o «1 tarea está…») + «Ver
  tareas». Las que entran juntas van en un solo popup; no se repite por la
  misma espera; no sale si estás mirando Tareas.
- **El número es el real:** un hilo aparte lee cada 2 s `cola.db` (y al
  instante tras aprobar, rechazar o cambiar el nivel) cruzándola con la
  carpeta `esperando\`. Si no puede leer, dice «No se pudo leer el estado» en
  vez de un 0. La ventana nunca se congela esperando a la base.
- Fila y popup son CustomTkinter con la versión clásica de respaldo
  (`GROWI_BRIDGE_CTK=0`, `"piloto_ctk": false`, sin customtkinter o CTk roto).
  Detalles y pruebas: `share\outbox\ESTADO-GUARDRAIL-VISIBLE.md`.

## Vista de Agentes (arriba de Tareas)

Tres columnas, en lugar de la tarjeta «Agentes» de antes (t-vista-agentes-052):

- **Trabajando:** lo que está en curso o revisándose, con su hueco, motor y
  cubo de cuota (`chatgpt-plus`, `claude-max`, `google-agy`...), cuánto lleva,
  el paso actual, tokens y costo en vivo.
- **Te necesitan:** lo que espera tu sí (con **Aprobar** y **Rechazar** en un
  clic, la misma puerta que la tarjeta de aprobaciones, y cuándo vence), lo
  que necesita tu decisión, las fallidas y las de cuarentena, con el motivo y
  desde cuándo esperan. Las aprobaciones, siempre; lo demás, de la última
  semana (como mucho 12 tarjetas; «y N más en la lista de abajo»).
- **Terminadas:** las de las últimas 24 h (como mucho 10), con el resultado,
  el motor, la duración, el costo («costo sin dato» si el motor no da cifra,
  como codex o agy) y si la revisión aprobó.
- **Ver** selecciona la tarea en la lista de abajo y abre su detalle. Debajo,
  cuántas hay en cola y por qué esperan (p. ej. «espera hueco»).
- Una tarjeta por encargo (sus rondas van dentro). Sale de lo que ya existe:
  `cola.db`, la familia `*.orquestacion.json`, el `result.json`, los huecos en
  vivo y el pedido de aprobación; nada nuevo que sincronizar. Se lee cada 3 s
  en un hilo (la ventana no se congela); si solo cambian los tiempos, se
  repintan sin rehacer las tarjetas. Si `cola.db` no se puede leer, lo dice en
  rojo en vez de mostrar columnas vacías.
- **En JSON:** `GET /gateway/agentes` (el mismo puerto y token que
  `/gateway/estado`) devuelve lo mismo, para la oficina u otro cliente sin
  tocar `cola.db`.

## Workflows reutilizables (debajo del tablero de agentes)

Una secuencia de pasos guardada que se ejecuta con un clic (t-workflows-052).
Cada uno es un archivo `workflows\<id>.json` junto a `growi-bridge.py` (como
`comandos-ia.json`); se escribe a mano o desde el detalle de un plan con
**Guardar como workflow**. Vienen dos de ejemplo: `resumen-reunion` y
`pipeline-video` (este necesita las skills de video).

```json
{
  "id": "resumen-reunion",
  "nombre": "Resumen de reunión",
  "descripcion": "Transcripción → resumen → correo",
  "parametros": [
    {"nombre": "archivo", "pregunta": "¿Qué transcripción?"},
    {"nombre": "idioma", "por_defecto": "es"}
  ],
  "motor": "haiku",
  "al_fallar": "pedir_decision",
  "pasos": [
    {"id": "limpiar", "prompt": "Limpia {archivo}; deja limpio.md", "criterios": ["limpio.md existe"]},
    {"id": "resumir", "prompt": "Resume limpio.md en {idioma}", "motor": "motor:codex"},
    {"id": "correo", "prompt": "Redacta correo con {resultado:resumir}", "depende_de": ["resumir"]}
  ]
}
```

- **Orden:** un paso sin `depende_de` espera al anterior; con `depende_de` dices
  de cuáles (`[]` = empieza solo). Ciclos o dependencias que no existen se
  rechazan antes de ejecutar nada, con el motivo.
- **Parámetros:** `{nombre}`, solo los declarados (uno sin declarar es un error
  al validar, nunca al ejecutar). Sin `por_defecto` se piden al pulsar
  **Ejecutar**, en un formulario dentro de la tarjeta.
- **De un paso al siguiente:** todos comparten la carpeta de la ejecución
  (`share\inbox\workflows\<ejecución>\`): lo normal es pasarse archivos.
  `{resultado:<paso>}` pone lo que respondió ese paso (hasta 2 000
  caracteres); solo vale de un paso del que dependa.
- **Por paso:** `motor` (lo mismo que en «Pedirle algo»: `haiku`, `sonnet`,
  `motor:codex`, `motor:gemini`…), `criterios`, `acciones`, `revisar`,
  `al_fallar` y `titulo`. Lo que no diga el paso sale del workflow.
- **Ejecutar** lo convierte en un plan con fases (el mismo motor de planes de
  siempre): cada paso entra en la cola cuando termina el anterior y pasa por
  tus aprobaciones, la revisión y las rondas como cualquier tarea. En el
  tablero, cada paso dice «paso 2/3 de …».
- **Costo estimado antes de ejecutar**, paso a paso: el historial de ese mismo
  paso en ejecuciones anteriores (primero las de la misma versión de los
  pasos); si no hay, tus tareas parecidas del mismo motor; si tampoco, una
  cuenta por tokens («estimado grueso»). Los pasos de codex y agy dicen «$0
  extra (va con la suscripción)» y los locales «$0 local»: nunca un $0.00
  inventado. Real y equivalente Max van aparte. Ejemplo: «Costo estimado:
  $0.040 eq. Max (rango $0.035–$0.051), basado en 3 ejecuciones previas».
- **Umbral por plan** (Ajustes, «por plan $», 5 por defecto): si el peor caso
  lo pasa, **Ejecutar** no encola y la tarjeta ofrece **Ejecutar igual**.
- **Última ejecución:** estimado contra real (la suma de sus pasos), para ver
  si el estimado acierta.
- Un archivo roto o mal escrito sale en la lista en rojo con su motivo, sin
  botón de ejecutar. **En JSON:** `GET /gateway/workflows` (mismo puerto y
  token que `/gateway/estado`).

## Niveles de riesgo y vencimiento de las aprobaciones

El silencio nunca es consentimiento: ningún pedido de aprobación espera para
siempre y, si vence, **se deniega** (nunca se aprueba solo).

- **Niveles (tabla editable `riesgos.json`, junto al programa):**
  - **R0** reversible y local (leer, listar, compilar, escribir en la carpeta
    de trabajo de la tarea): no pregunta.
  - **R1** reversible con costo o alcance (escribir fuera de la carpeta de
    trabajo, gastar hasta $0,50, crear archivos en el proyecto): una vez por
    tipo y por tarea; **vence a las 24 h**.
  - **R2** irreversible o externo (borrar archivos, git push, publicar,
    enviar correo o mensaje, gastar más de $0,50): siempre, por acción
    exacta (un «sí» vale una sola vez); **vence a las 2 h**.
  - **R3** nunca sin ti delante (rm -rf, git push --force, cambiar claves,
    tocar `.claude/` o credenciales, apagar el PC): **solo en la app**; si
    llega por un canal remoto (WhatsApp) se deniega al instante. Vence a las 2 h.
- **Cómo se clasifica:** por tipo de acción y alcance, no por palabras
  sueltas. Manda lo que la tarea declara en `"acciones": [{"tipo": "borrar",
  "ruta": "…"}, {"tipo": "gastar", "usd": 0.3}]`; se suma lo marcado como
  `sensible` y lo que se deduce del encargo frase por frase (verbo + objeto;
  «No borres nada» no cuenta). Nunca menos que lo declarado. El alcance
  cambia el nivel (dentro/fuera de la carpeta, cifra del gasto, rutas como
  `.claude`). Si `riesgos.json` no se puede leer, **todo es R3** y lo dice.
- **Desde qué nivel pregunta:** «Preguntarme siempre» desde R1, «solo lo
  delicado» desde R2, «Hazlo sin preguntar» solo R3 (R3 pregunta siempre).
- **Dónde se ve:** la tarjeta «Esperan tu aprobación» de Tareas dice el nivel,
  el motivo y «Vence el lun 26/10 a las 05:32, hora de Caracas (quedan 1 h 59
  min). Si no respondes, no se hace.» (naranja en los últimos 15 min). El pedido
  para WhatsApp queda en `share\outbox\aprobaciones\<approval_id>.pedido.json`
  (`texto_whatsapp`, con el vencimiento) y `runner-status.json` trae
  `aprobaciones_pendientes`. Mandarlo por WhatsApp es cosa de Growi
  (t-aprobacion-whatsapp-030); la app no envía nada.
- **Al vencer:** el runner lo aplica solo (cada vuelta de la cola, cada 10 s
  mientras un motor trabaja y al arrancar). La tarea pasa a «necesita
  decisión» con el motivo `aprobacion vencida (R2, 2 h sin respuesta)`; el
  encargo va de `esperando\` a `done\` sin pasar por el motor; el reporte dice
  que se intentó, que faltó tu aprobación y que no se ejecutó nada. En Tareas
  sale como «vencida». El contador de «esperando tu aprobación» baja solo.
- **Aprobación tardía:** un «Aprobar» que llega después (aunque el botón
  siguiera en pantalla) no vale: se apunta como «tardía, descartada» y no
  ejecuta nada. Para hacerla: Tareas → «Volver a la cola» → sale un pedido
  **nuevo** (otro approval_id, otro vencimiento).
- **Apagones:** al arrancar, lo que venció con la app cerrada se marca
  vencido («aplicado al arrancar»); no resucita como pendiente. Una tarea que
  ya esperaba de antes de esta versión recibe su pedido contando desde que
  llegó.
- **Registro:** `cola.db` → tabla `aprobaciones` (approval_id, tarea, nivel,
  motivo, pedido, creado/vence en hora de Caracas, estado, resultado, tardías)
  y `share\outbox\aprobaciones-registro.jsonl` (una línea por evento: pedido,
  aprobada, rechazada, vencida, tardia_descartada, denegada_remota). No se
  borra nada. Solo se guardan **políticas** (`politicas` de `riesgos.json`,
  solo R1); las aprobaciones concretas viven en memoria.
- **Para probar sin esperar 2 h:** `GROWI_BRIDGE_VENCE_PRUEBA="R2=60"` acorta el
  vencimiento **solo** en una instancia aislada (share y mutex propios,
  `GROWI_BRIDGE_SHARE` + `GROWI_BRIDGE_MUTEX`); en la app instalada se ignora.
  Detalles: `share\outbox\ESTADO-VENCIMIENTO-APROBACION.md`.

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

## Checkpoint por ronda: tras un apagón sigue donde iba, no desde cero

- **Una fila por ronda/intento** en la misma `cola.db` (tabla `checkpoints`,
  WAL + `synchronous=FULL`, como la cola): `task_id`, `run_id` (el id del task
  original, también en rondas, revisiones y aprobaciones), `ronda`, `intento`,
  `motor_usado`, `session_id` (y la de entrada), `cwd` exacto,
  `criterios_pendientes`, `costo_acumulado` (reintentos y revisiones
  incluidos), `estado`, `paso` y `siguiente_paso` («revisar», «ronda N»,
  «fase siguiente», «esperar_aprobacion:<approval_id>», «terminada»). Se escribe
  **antes** de lanzar cada paso, en cuanto el motor anuncia su sesión, y
  **después** de cada resultado y de cada revisión.
- **Transcript por ronda:** `share\outbox\runner-results\<id>.ronda-N.json`
  con el prompt enviado, el resultado y la revisión (prompt y respuesta cruda)
  de cada intento. Es lo que deja depurar un fallo de tres pasos atrás.
- **Al volver la luz** el runner reanuda desde `siguiente_paso`:
  - murió **revisando** (el motor ya había terminado) → repite **solo la
    revisión**; el costo del motor no se cuenta dos veces;
  - murió con el **motor corriendo** → repite **esa misma ronda** con el
    `session_id` y la carpeta guardados (la sesión de Claude va atada a la
    carpeta) y le avisa que se cortó y que siga;
  - murió justo **después** de revisar → no repite nada (o, si la ronda
    siguiente no llegó a encolarse, repite solo la revisión).
  La tarea vuelve a la cola con intentos+1 y «recuperada tras corte», como
  antes; el reporte dice «se reanudó desde el checkpoint (ronda 2), no desde cero».
- **Si la sesión ya no sirve** (Claude dice «No conversation found with session
  ID», el checkpoint perdió el id, o la ronda la hace otro motor que no puede
  continuarla): **sesión nueva con el resumen del checkpoint** (encargo, lo hecho,
  criterios pendientes, archivos tocados) en vez de fallar. Queda en el
  checkpoint (`degradado`, motivo) y en el resultado (`reanudacion`,
  «se reanudó sin la sesión original»). El motor solo cambia entre rondas.
- **Plan** (fases encadenadas): tablas `planes` y `plan_fases` (plan_id, cada
  fase con su tarea, de qué fase depende y su estado). No es un DAG (eso es
  t-dag-fases-030): solo lo que hace falta para reanudar un plan a medias.
- **Supervisor al arrancar** (antes de reponer la cola): mira el checkpoint y
  deja en cada tarea cortada su **último estado conocido** («ronda 2,
  siguiente_paso revisar…»), marca la fase a medias y la que sigue pendiente,
  y escribe `share\outbox\supervisor-arranque.json`. Una tarea de antes del
  checkpoint queda «sin estado previo» y se repone como antes (desde el
  principio), sin inventarle un paso. En **Tareas → DETALLE** salen el último
  estado conocido, el checkpoint actual, el plan y, si hubo, la reanudación sin
  sesión. El banner dice «(reanuda tras corte)».

## Criterios tipados y doble juez: el juez opina, los hechos mandan

- **Dos clases de criterio** en `"criterios"` del `.task.json`: frases libres
  (las juzga el juez, como siempre) y **objetos tipados** (los comprueba el
  código, $0):
  - `{"tipo": "existe", "archivo": "informe.md"}`
  - `{"tipo": "lineas", "archivo": "informe.md", "min": 150}` (o `max`, o los dos)
  - `{"tipo": "contiene", "archivo": "informe.md", "texto": "## Conclusiones"}` (marcador exacto)
  - `{"tipo": "compila", "archivo": "calc.py"}` (python -m py_compile, el .pyc va
    a %TEMP%; `.js` con `node --check`) o `{"tipo": "compila", "comando": "npm run build"}`
  - `{"tipo": "comando", "comando": "python -m pytest -q", "texto": "passed"}`
    (sale con exit 0 —o el `exit` que digas, `null` = no mirar— y/o su salida
    contiene el texto). Opcionales: `timeout_s` (1-600, por defecto 60) y `descripcion`.
  Las rutas son relativas a la carpeta de la tarea y tienen que estar dentro
  de las carpetas permitidas.
- **Mal formado = rechazado al encolar**, con el motivo («tipo desconocido
  'tamano'», «falta la ruta del archivo», «campo desconocido 'minimo'»…); la
  tarea no corre. Nada se interpreta a ojo.
- **Comandos sin shell:** un solo programa de `revision.comandos_permitidos`
  (python, py, node, npm, npx, pnpm, yarn, pytest, git, dotnet, cargo, go, tsc)
  con sus argumentos; se rechazan `& | < > ^ ; \` $(` y `%VARIABLES%`; git solo
  para leer. Corren ocultos, en la carpeta de la tarea, con tope de tiempo.
  Es la única excepción a «nunca shell con algo que venga de un task», y por
  eso va tan acotada.
- **Orden de la revisión:** (1) los checks tipados (y lo comprobable de las
  frases, como en 0.2.0) contra los archivos reales; (2) el juez —Hermes por
  llama-server; si no responde, el siguiente de `revision.orden`— recibe el
  encargo, los criterios, los HECHOS, el parte del motor y **la obra** (los
  archivos tocados con su contenido relevante) y devuelve un JSON con
  **rúbrica fija**: `puntuacion` (completitud, correccion, no_regresion,
  evidencia, de 1 a 5), `aprobado` (si/no), `que_falta` (cada cosa con su
  `arreglo`) y `evidencia`. llama-server y Ollama fuerzan la salida a ese
  esquema; igual se valida al llegar.
- **Reglas que mandan:** si un check falla, **no hay aprobación** aunque el
  juez diga que sí. Un JSON que no cumple el esquema = **«sin revisión»**, nunca
  aprobado (y no se salta al siguiente juez). Sin juez disponible = «sin
  revisión».
  (En texto plano, sin tilde: sin revision = la tarea terminó pero ningún juez
  dio un veredicto válido; nunca cuenta como aprobada.) «Sí» con alguna dimensión por debajo de `rubrica.umbral_min` (3)
  cuenta como «no». Una evidencia que cita un archivo que no existe «no cuenta».
- **Segundo juez (Claude Haiku, solo lectura)** solo si un check falló o la
  tarea es R2/R3; **nunca en R0** (Haiku tampoco entra como reserva del primer
  juez en una R0). Si los dos no coinciden —o aprueban contra un check que
  falla— la tarea queda **«necesita decisión»** sin más rondas, con los dos
  veredictos en Tareas → DETALLE. Medido: 41,7 s y $0,0077 eq. (1 check
  fallado, R1) y 71,4 s y $0,0125 eq. (R2); ver ESTADO-CRITERIOS-TIPADOS.md.
- **Contexto de Hermes (8192 tokens por petición):** la revisión pregunta el
  tamaño real al servidor (`/props`) y cuenta los tokens con su tokenizador;
  si no cabe, recorta primero el parte del motor y luego la obra (los hechos
  nunca) y lo dice en el prompt, en el `.revision.json` y en DETALLE. Si ni
  recortado cabe, ese juez no se usa y lo dice.
- **Auto-crítica:** a cada tarea de código (criterios compila/comando,
  archivos de código o palabras como «script», «función») se le añade al
  final del prompt «Antes de darlo por hecho, comprueba…» con lo que se va a
  verificar (compila, marcadores, líneas, archivos de la lista).
- **Calibración contra ti:** cada revisión queda en `cola.db` → tabla
  `revisiones` y en `share\outbox\revisiones-registro.jsonl`. Si la revisión
  se equivocó: elige la tarea en Tareas y **Ctrl+K → «Corregir la revisión: yo
  la apruebo / yo la rechazo»**. Es solo una etiqueta: no cambia la tarea ni el
  umbral. `share\outbox\calibracion-revisor.json` lleva la tasa de acuerdo
  (juez 1, juez 2 y decisión final contra ti) por bloques de 30 casos y dice
  cuándo toca revisarla; el umbral se cambia a mano en `engines.json`.
- **Todo en `<id>.revision.json`:** `checks_deterministas` (pasa/falla +
  evidencia: archivo, nº de líneas reales, línea encontrada, exit y salida),
  `veredictos` (cada juez: puntuación, tiempo, costo, tokens, recorte),
  `segundo_juez` (llamado o por qué no), `decision` y `calibracion_id`.

## Los motores se lanzan sin ventana

- Todo lo que lanza el runner (Claude, Codex, revisiones, rondas,
  llama-server, ollama, `taskkill`, la prueba de «Nuevo motor») va con
  `CREATE_NO_WINDOW` (0x08000000) + `STARTUPINFO` con `SW_HIDE`. El registro
  dice «lanzado oculto (…), pid N» y el resultado trae `lanzamiento`. Si un
  lanzamiento falla, el error va al resultado y al registro; nunca se
  reintenta con ventana visible. «Está trabajando» lo dicen el banner, Tareas
  y `runner-live.json`, no una consola.
- `schtasks` (inicio automático) y `shutdown` (botones del PC) también, porque
  desde la app sin consola abrían una ventana negra al arrancar.
- **El parpadeo de cada 3 min venía del vigilante:** la tarea programada
  `GrowiBridgeWatchdog` corre `powershell.exe -WindowStyle Hidden …` y en
  Windows 11 la terminal se abre antes de esconderse. El arreglo es
  `watchdog\lanzar-oculto.pyw` (ver ESTADO-CHECKPOINT-RONDA.md: cambiar la
  acción de la tarea es cosa tuya, está fuera de esta carpeta).

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

## Motores descritos con datos (engines.json esquema 2)

- Cada motor es un **descriptor**: `invocacion` (comando con huecos
  `{prompt} {cwd} {session} {model}`, o HTTP con `ruta` y `cuerpo`, o
  asíncrono crear/sondear/descargar), `formato_salida` (`json_por_lineas` /
  `json_final` / `texto_plano`), `extraer` (dónde están texto, costo, turnos
  y sesión, o `"no_lo_da"`), `reanudar` (`--resume`, plantilla aparte,
  historial local o `"no_soporta"`), `errores` (patrones transitorio /
  definitivo), `timeout_min`, `entorno` (siempre `NO_PROXY=127.0.0.1,localhost`
  y UTF-8), `requisitos`, `base_url`, `credencial_ref`, `capacidades` y
  `fallback` (declarado, sin usar todavía). El detalle está en `_esquema`
  dentro del propio archivo.
- En una plantilla, una sublista es **opcional**: `["--model", "{model}"]`
  solo se pone si la tarea trae modelo. En el formulario se escribe entre
  corchetes: `[--model {model}]`.
- **Credenciales:** `credencial_ref` = `{proveedor, etiqueta}`. El runner lee
  esa clave del Administrador de credenciales de Windows (destino
  `growi-bridge/<proveedor>/<etiqueta>`), nunca por el proveedor solo. Sin
  esa clave, el motor queda «sin credencial» (no disponible). Guardar claves
  es cosa de t-credenciales-keyring.
- **Un descriptor roto no rompe nada:** ese motor sale «no disponible:
  descriptor mal formado: …» y sus tareas fallan en el acto, sin reintentos.
- **Ficha honesta** (Modelos → Motores): estado, qué es, si está verificado
  en vivo, programa encontrado y versión, último healthcheck
  (`motores-salud.json`), base_url, credencial y lo que **no** puede (sin
  streaming no hay consumo en vivo; sin reanudar, las rondas van como sesión
  nueva con resumen; sin costo, «sin dato»; sin herramientas, no se le piden).
- **Nuevo motor** (Modelos): nombre, comando, formato, rutas, cómo continuar
  una sesión, URL base y credencial. **Probar** corre de verdad «Escribe tres
  frutas, una por linea» en un proceso aparte (`growi-bridge.py
  --probar-motor`), comprueba costo/turnos (o «no los da») y si reanuda.
  Solo si pasa se guarda en `engines.json` (copia previa en
  `engines.json.bak`) y aparece en el selector y en «Quién responde».
- Las tareas viejas siguen igual: sin `motor` → el de por defecto (Claude);
  `"model": "ollama:default"` → el motor `ollama`. El resultado es el mismo
  para todos (id, status, started_at, finished_at, duration_s, exit_code,
  result ≤ 20 000, cost_usd, num_turns, session_id, stderr, error); si el
  motor no da costo, `cost_usd` es null y `costo_dato` dice «sin dato».
- **Un motor por tarea (0.5.2, t-motor-generico-052):** `"motor": "claude" | "codex" | "gemini"` (o
  cualquier motor de `engines.json`). También valen `"model": "motor:codex"` (la forma del selector) y
  `"model": "codex:<modelo>"`. Si `motor` y `model` dicen motores distintos, la tarea se **rechaza**
  con el motivo (no se adivina). `"via": "api"` manda la tarea a la API del proveedor del motor
  (gemini → `api:gemini:<modelo>`, gasta con tu clave); sin `via`, gemini va solo por agy con tu sesión
  de Google y nunca cae sola a la clave.
- **Cubos de cuota:** cada motor tiene el suyo (`engines.json → motores.<id>.cuota.cubo`: claude-max,
  chatgpt-plus, google-agy; la API es `api-<proveedor>`). Una tarea cuenta solo en el cubo del motor que
  la corrió (tareas y tokens en 5 h y en la semana). Ningún proveedor publica cuánto queda: el % solo sale
  si pones un límite propio en `settings.json → limites_cubo`, p. ej.
  `{"chatgpt-plus": {"5h": {"tareas": 20}}}`; al pasar el aviso (`cuota_aviso_pct`), antes de lanzar
  se mira solo el cubo de ese motor.
- **Entrar sin clave (`autenticacion.sesion_cli`):** un motor de línea de
  comandos puede declarar cómo comprobar, sin gastar, que su programa tiene su
  propia sesión iniciada (p. ej. `agy models`). Con sesión está disponible
  **sin clave** y se le quitan las variables de clave del entorno; sin sesión
  usa la clave activa de su `credencial_ref`; sin ninguna de las dos queda «no
  disponible» con el motivo y la ficha dice cómo entrar. El token de esa
  sesión lo guarda y renueva el programa, nunca Growi. `errores.auth` marca
  los 401 / sesión caducada: la tarea dice «clave inválida o sesión caducada»,
  es definitiva (no se reintenta) y el acceso se vuelve a comprobar.
  `puede` / `no_puede` / `frase_selector` dan el texto de la ficha y de
  «Quién responde».

### Gemini (Antigravity CLI, `agy`)

- Motor `gemini`: `agy -p "{prompt}" --output-format json` (+ `--mode plan`
  si la tarea no pide permiso; nunca `--dangerously-skip-permissions`;
  `--conversation {session}` para seguir una ronda). **No es Gemini CLI**:
  Gemini CLI está retirado para cuentas personales (HTTP 410); no se instala.
  En corto: versión con `agy --version`; tarea con `agy -p ... --output-format json`.
- **Iniciar sesión en agy:** doble clic a `iniciar-sesion-agy.bat` (sin
  Administrador): abre agy para entrar con Google y luego corre sola la prueba
  real (`share\outbox\capturas-gemini\real\`, y el `.result.json` en `share\inbox\`).
- Entra con la **sesión de agy** (OAuth de Google con tu Google AI Pro; preferida,
  $0 extra) o, si no la hay, con la clave Gemini **activa** de Ajustes → Claves
  (`GEMINI_API_KEY` solo en el entorno del proceso, nunca en archivos ni en el
  registro; si aparece en la salida se tapa con los 4 últimos).
- Lee `response`, `num_turns` y `conversation_id`; **no da costo**
  (`cost_usd` null, «sin dato»); da tokens al terminar.
- Para iniciar la sesión: terminal normal (sin Administrador) → `agy` →
  iniciar sesión con Google → `/quit` → Modelos → Motores → Gemini →
  **Comprobar ahora**. El mapa de disponibilidad (Estado) dice «se usa SIN
  clave API» cuando la sesión vale.

### llama-server en modo router (varios modelos, un solo 127.0.0.1:8080)

- El runner arranca `llama-server --models-dir ..\models --models-max 1
  --models-preset ..\models-preset.ini --host 127.0.0.1 --port 8080` (sin
  `-m`) si el 8080 no responde. Es un proceso padre y un hijo por modelo
  cargado (en otro puerto de 127.0.0.1, nunca 0.0.0.0).
- Cada modelo es un `.gguf` de `models\` y se pide por su nombre sin
  extensión (`"model": "hermes-3-8b-q4_k_m"`). Cambiar de modelo es HTTP:
  `POST /models/load`, `POST /models/unload` y `GET /models` como fuente de
  verdad. **/health OK no es «local listo»**: «local listo» solo cuando
  GET /models dice `loaded`. La ficha (Modelos → Motores → llama) muestra
  «Modelos del router: local listo · … cargado» o «todavía no es local
  listo · … sin cargar / cargando…».
- `--models-max 1`: cuenta modelos, no memoria; en 6 GB no caben dos de 8B.
  Al pedir otro, el router descarga el anterior solo.
- La primera petición a un modelo descargado lo carga desde disco (18–50 s
  medidos con Hermes): el banner dice «cargando modelo... <nombre> (N s)» y se espera hasta
  300 s, no 10.
- `models-preset.ini`: una sección por modelo (`ctx-size`, `parallel`,
  `n-gpu-layers`, `mmproj`, `cache-type-k/v`, `embeddings`). La app añade
  sola las de los `.gguf` nuevos con los datos del catálogo y **no toca las
  que ya existen** (lo editado a mano manda). Hermes: 8192 de contexto,
  1 slot.
- El router solo ve los `.gguf` que había al arrancar. Si lo arrancó la app,
  lo reinicia sola cuando una tarea pide un modelo nuevo. Si no, ciérralo y
  se vuelve a arrancar solo.
- No actualices `llama-server.exe` sin probar el build nuevo: los flags
  cambian de un build a otro. Verificado con el build 11873.

### Ciclo de vida del motor local (arrancar, parar, cambiar de modelo, liberar VRAM)

Pestaña **Modelos → Motor local**. Lo que dice sale del propio servidor
(`GET /models`), de nvidia-smi y de quién escucha en el puerto. Nunca sale
solo de `/health`.

- **Estado**: «local listo: hermes-3-8b-q4_k_m cargado (GET /models:
  loaded)», «cargando modelo... <nombre> (N s)», «Router encendido, ningún
  modelo cargado (VRAM libre)» o «el motor local no responde» (apagado, o
  el proceso del puerto no contesta). Debajo: cada modelo con su estado
  (loaded / unloaded / loading), la VRAM usada según nvidia-smi y el puerto
  con el pid del router.
- **Arrancar**: enciende el router y carga el modelo elegido. Si ya hay un
  router del Bridge vivo en el 8080, lo usa y no lanza otro.
- **Parar**: lo cierra de verdad. Mata el proceso y su árbol (los hijos de
  cada modelo) y espera a que el 8080 quede libre. Solo toca el
  `llama-server.exe` de la carpeta `llama\` del Bridge que escucha en su
  puerto. El `llama-server.exe` de Ollama (otra carpeta, otro puerto) no lo
  toca nunca.
- **Liberar VRAM**: descarga todos los modelos (`POST /models/unload`). El
  router sigue encendido y la VRAM baja de ~5,7 GB a ~0. Úsalo antes de abrir
  Blender, el navegador con aceleración u otro modelo. Solo pasa cuando lo
  pulsas o cuando la tarea lo pide, nunca a escondidas en mitad de una tarea.
- **Cambiar de modelo**: elige el modelo y pulsa «Cargar este modelo».
  Descarga el que está y carga el elegido, sin matar el proceso. La primera
  carga desde disco tarda de ~1 s a más de un minuto, y se espera hasta 300 s.
- **Al salir de la app**: por defecto, «Salir» para el motor local para que
  la VRAM no quede ocupada. Para dejarlo encendido, elige «Dejarlo encendido
  al salir» (en settings.json: `"motor_local_parar_al_salir": false`).
  Minimizar a la bandeja no lo para.
- **Sin huérfanos ni doble instancia**: al abrir la app se cierran los
  `llama-server.exe` del Bridge que hayan quedado sueltos. Por ejemplo, un
  hijo con un modelo cargado cuyo router ya murió, o un segundo servidor que
  pide el mismo puerto. Si el router del Bridge sigue vivo en el 8080, se
  adopta. Antes de lanzar uno, el runner mira el puerto. Si lo ocupa otro
  programa, no lanza nada y lo dice. Si es el del Bridge pero no contesta, lo
  cierra y lanza uno nuevo.

En el task JSON:

```json
{"id": "t1", "prompt": "…", "modelo_local": "hermes-3-8b-q4_k_m"}
{"id": "t2", "prompt": "Renderiza la escena…", "motor": "claude", "liberar_vram": "antes"}
```

- `modelo_local`: es el `.gguf` de `models\` sin la extensión. Manda sobre
  `modelo`, y sin `motor` la tarea va al motor local de engines.json. El
  runner carga ese modelo antes de ejecutar; si ya está cargado, no lo
  recarga. El resultado guarda `modelo_local` y `modelo_local_carga`, con
  cómo quedó listo: si lo arrancó, cuánto tardó en cargar o si ya estaba
  cargado. Si el modelo no está instalado, la tarea falla en el acto, sin
  arrancar nada, con un error que dice cómo bajarlo: «… no está instalado …
  Bájalo con el descargador (Modelos → Librería → Instalar)».
- `liberar_vram`: `"antes"` (o `true`) suelta la VRAM antes de empezar.
  `"despues"` la suelta al terminar. El resultado guarda lo que se liberó en
  `vram_liberada`.
- `--sleep-idle-seconds` (descargar el modelo tras N s sin uso): **no se
  usa**. Ver ESTADO-CICLO-VIDA-LLAMA.md, donde está medido y explicado. Si
  algún día se activa, el estado `sleeping` ya se entiende: «dormido (VRAM
  libre; despierta al usarlo)».

### Ollama y llama-server: dos motores locales con el mismo Hermes

Decisión de Leandro (26 oct 2026): Bridge usa Hermes local vía Ollama. Ollama
ya estaba instalada y se verificó en vivo; no se reinstaló nada. Así que hay
**dos motores locales** y los dos sirven **el mismo Hermes 3 8B (Q4_K_M)**.
Ninguno es «el obvio». Estas son las diferencias reales, medidas el 26 oct 2026
en este PC (RTX 3060 Laptop, 6 GB):

| | `llama` · «Local Hermes 3 directo $0» | `ollama` · «Ollama · Hermes 3 8B (local $0)» |
|---|---|---|
| Programa | `llama\llama-server.exe` (build 11873), lo arranca el runner | Ollama 0.40.10 (`%LOCALAPPDATA%\Programs\Ollama`), servicio propio |
| Dirección | `127.0.0.1:8080` (`/v1/chat/completions`, modo router) | `127.0.0.1:11434` (`POST /api/chat`, `stream:false`) |
| Modelo | `models\hermes-3-8b-q4_k_m.gguf` | `hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M` (blobs de Ollama) |
| Contexto | 8192 (preset) | 4096 (`/api/ps`: `context_length`) |
| VRAM con Hermes | ~5,5 GB | 4046 MiB |
| De dónde salen los modelos | **catálogo curado del descargador GGUF** (Modelos → Librería) | `ollama pull` (tareas `ollama_action`); no es el catálogo curado |
| Cuándo lo usa el router | primero: lo simple va a `llama` | respaldo: solo si `llama` no está disponible |
| Revisión (juez 1) | primero del `orden` | segundo, si llama no responde |
| Carril B | no | no |
| Costo | $0 marginal (local) | $0 marginal (local) |

- **No corren bien a la vez.** Medido con los dos cargados: quedan 111 MiB
  libres de 6144. llama-server tarda 28,5 s en cargar (15,2 s con la VRAM
  libre) y genera a 34 tok/s (45 tok/s solo). No se rompe, pero se pelean.
  Por eso se usa uno a la vez. Ollama suelta el modelo solo tras 5 min sin uso.
  llama-server se para con «Liberar VRAM» o «Parar» (Modelos → Motor local) o
  al salir de la app. **«Liberar VRAM» no toca a Ollama**: es otro programa.
- **Para elegirlo a mano:** en «Quién responde» sale «Hermes 3 8B · Ollama (en
  tu PC) $0». Desde la VM: `{"motor": "ollama", ...}` o la forma vieja
  `"model": "ollama:<modelo>"`. La ficha está en Modelos → Motores → «Ollama ·
  Hermes 3 8B». Su fila «Convive con» explica todo esto.
- **Si Ollama no responde**, la ficha dice «no disponible» con el motivo
  exacto. Su fila desaparece de «Quién responde» (si el último healthcheck,
  de menos de 10 min, falló). Las tareas con motor `ollama` fallan en el acto
  con `error_tipo: definitivo`, 0 reintentos y el motivo, por ejemplo
  «motor ollama no disponible: no está instalado: no encuentro 'ollama' …».
- No hay 32k ni 128k en local: el contexto es el de la tabla.

## Si algo falla

- **Puerto 8787 ocupado:** sigue corriendo el `pc-server.py` viejo (u otro
  programa). Ciérralo y reinicia la app. Desde el gateway unificado nadie más
  puede escuchar en ese puerto mientras la app vive (bind exclusivo).
- **«Growi Bridge ya está corriendo»:** ya hay una copia viva (mira la bandeja).
  La segunda copia sale sola sin tocar nada.
- **Falta el token:** el puente no arranca. `python growi-bridge.py
  --generar-token` lo crea (si hay un `secret.txt` viejo, usa ese mismo valor).
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

## Gateway unificado: un solo proceso

- **Un solo proceso Python** (la app) hace de puente, runner, cola y ventana:
  el runner es un hilo de dentro, no un script aparte (`share\inbox\runner\runner.py`
  es el viejo y ya no se usa). Arranque único: la tarea `GrowiBridgeApp` →
  `iniciar-growi-bridge.bat` → `pythonw growi-bridge.py`.
- **Instancia única:** mutex con nombre de Windows + `gateway.lock` (pid) junto
  al programa. Una segunda copia dice «Growi Bridge ya está corriendo» (ventana
  que se cierra sola a los 15 s y registro) y sale sin abrir ventana, sin
  icono, sin tocar el puerto, la cola, llama-server ni el vigilante. Vale
  también si la primera corre elevada y la segunda no (antes esa se colaba).
- **Plano de control:** solo `127.0.0.1:8787` y, para la VM, la IP de Tailscale
  de este PC (`100.x.y.z:8787`, solo esa IP; nunca `0.0.0.0` ni la red de casa).
  `settings.json` → `"tunel_remoto": "ninguno"` lo deja solo en loopback (la VM
  no llegaría). Cada petición lleva el token (`X-Shared-Secret` como siempre, o
  `Authorization: Bearer`); una con `Origin` de una web, `Sec-Fetch-Site` de
  otro sitio, un `Host` ajeno o que pide WebSocket se rechaza aunque traiga el
  token. Ninguna web puede hablar con el gateway (`gateway_origenes_permitidos`
  vacío por defecto).
- **Token:** cifrado con DPAPI en `%LOCALAPPDATA%\GrowiBridge\plano-control-a.dpapi`
  (fuera de esta carpeta y de `settings.json`; solo tu usuario de Windows lo
  descifra). La primera vez toma el valor de `secret.txt` para no cortar a la
  VM; después la app ya no lo lee, pero el servidor del navegador
  (`browserrowser-server.py`) sí: **no borres `secret.txt`** hasta que ese también
  lea el token. El
  instalador corre `growi-bridge.py --generar-token`; `--mostrar-token` lo
  enseña en la consola para pasárselo al asistente.
- **Cola:** la misma `cola.db` (WAL + `synchronous=FULL`). Además, lo que llega
  a `runner-tasks\` mientras un motor trabaja se apunta en la cola en ~2 s
  (antes esperaba a que el runner diera la vuelta). Al arrancar, lo que quedó
  en curso vuelve a la cola y se avisa en Estado («Al arrancar: se re-encoló…»)
  y con un aviso de la bandeja (no sale si Windows está en «No molestar»). Una tarea que espera tu aprobación no frena la
  cola.
- **Estado = panel del gateway:** proceso único (pid, puertos), cola, skills,
  modelos y cadena de respaldo, canales y cada motor con su credencial
  (proveedor, clave activa y sus 4 últimos caracteres) y su URL base, leído
  en vivo del plano de control cada 3 s. Estados: cargando, vacío (sin
  motores), error, contenido y sin conexión (con Reintentar).
- **Ajustes → Claves:** qué clave guardada del mismo proveedor usa cada
  `credencial_ref` («Usar esta»). Vale desde la siguiente tarea, sin tocar
  `engines.json`; en `settings.json` → `credenciales_activas` solo van nombres.
- **Recarga en caliente:** cambiar `settings.json`, `engines.json`,
  `rules.json`, `folders.json` o las skills se aplica sin reiniciar (cada
  ~1,5 s, por secciones; queda en el registro y en Estado). La tarea que está
  corriendo termina con la configuración con la que empezó (su resultado
  trae `config_al_empezar`); `bridge_port`, `lane`, `apariencia` y
  `piloto_ctk` se aplican al volver a abrir. Un `engines.json` a medio guardar
  no deja a la app sin motores: sigue la última versión buena.
- Detalles y pruebas: `share\outbox\ESTADO-GATEWAY.md`.

## Skills nativas (skills\ propia, sin marketplace)

- **Dónde:** `skills\` junto a growi-bridge.py (o `GROWI_BRIDGE_SKILLS`, solo
  para pruebas). Cada skill es una carpeta con su `SKILL.md` y sus scripts al
  lado. Tres orígenes, con esta precedencia cuando dos se llaman igual:
  `skills\<nombre>\` **propia** (del proyecto) > `skills\_equipo\<nombre>\`
  **del equipo** (las que copias a mano de una fuente que revisaste) >
  `skills\_incluidas\<nombre>\` **incluida** (vienen con Bridge). La que pierde
  sale como «tapada». `skills\_borradores\` nunca se carga.
- **Solo dos vías de entrada:** escritas por ti o por Growi, o copiadas a mano
  por ti. No hay marketplace, no se descarga nada de internet y nada se
  instala solo. OpenClaw no se usa (se puede desinstalar sin que Bridge pierda
  nada).
- **SKILL.md:** frontmatter YAML con `name`, `description`, `version` y
  `requires` (`env`: variables que deben existir; `bins`: programas en el PATH;
  `primaryEnv`: la credencial principal, solo su nombre). Se lee con un YAML
  mínimo propio (sin dependencias nuevas). Guía:
  `skills\_incluidas\escribir-skills\SKILL.md`.
- **Límites:** 6 niveles de carpetas, 200 skills, 256 KB por SKILL.md. Nada de
  enlaces simbólicos ni uniones de carpetas, nada fuera de `skills\`. Una skill
  mala se reporta con su motivo exacto y se salta; las demás siguen.
- **Secretos literales:** `sk-…`, `ghp_…`/`gho_…`, `github_pat_…`, `xox[baprs]-…`,
  `AIza…`, `tsk_…` y bloques `-----BEGIN … PRIVATE KEY-----`, en el SKILL.md y en
  sus scripts. Si aparece uno, la skill queda **sospechosa**, no se carga y la
  evidencia sale como `[REDACTED CREDENTIAL]` (en la ventana, el registro y el
  informe; el secreto no se copia a ningún sitio).
- **Índice en memoria:** nombre + descripción + requisitos de cada skill, al
  arrancar (en un hilo) y otra vez cuando cambia algo en `skills\` (recarga en
  caliente, ~1,5 s). El cuerpo no se guarda: se relee (y se vuelve a validar)
  al activarla.
- **Activación por tarea:** el runner compara el encargo con la
  **descripción** de cada skill (no con su nombre): palabras en común, pesadas
  por lo raras que son; hacen falta 2 o más, y la 2.ª y la 3.ª necesitan al
  menos el 40 % de la puntuación de la mejor. Máximo 3. Solo esas van al motor,
  con su cuerpo recortado a 6000 caracteres cada una, como texto al principio
  del prompt (después de tus reglas), igual para todos los motores (es el hueco
  `{prompt}` del descriptor de `engines.json`). Nada de `always: true`.
  Ajustes opcionales en `settings.json`: `skills_max_activas`,
  `skills_min_coincidencias`, `skills_corte_relativo`, `skills_max_caracteres`,
  `skills_workshop`. Un task con `"skills": false` no lleva ninguna.
- **Queda registrado:** cada `.result.json` trae `skills_activadas` (los
  nombres; `[]` si ninguna) y `skills` (puntuación, palabras que coincidieron,
  caracteres que fueron al prompt, si se recortó, requisitos que faltan). El
  registro dice «skills [id]: activadas por descripción: …».
- **Pestaña Skills:** una fila por skill con nombre, versión, origen (propia /
  del equipo / incluida), descripción y requisitos **comprobados en vivo**
  («Programa «blender»: falta: no está en el PATH» en rojo; «está (ruta)» en
  verde; las variables nunca enseñan su valor). Debajo, las que no se cargaron
  con el motivo. Estados: leyendo, vacía, error, sin conexión con la carpeta y
  contenido. **Validar skills** recorre todo `skills\` y dice cuáles pasan y
  cuáles no, con el motivo exacto (también en `share\outbox\skills-validacion.json`).
  En consola: `python growi-bridge.py --validar-skills`, `--skills-indice` y
  `--skills-activar "encargo"` (en seco: qué skills se activarían).
- **Skills semilla (las curadas de tu trabajo real):** Growi las redacta en la
  VM y las deja en `share\inbox\skills-semilla\<nombre>\` (blender, tripo,
  canva, meta-ads, documentos-humanos, aqualine, summit-maker).
  `python growi-bridge.py --sembrar-skills [carpeta] [--en-seco]` hace, por cada
  una y por separado: **recibir** (la carpeta y su SKILL.md llegaron; si no,
  FALTA con quién la aporta, y aquí no se escribe nada), **validar** (el mismo
  lector del índice: frontmatter con `requires`, carpeta = `name`, 256 KB,
  secretos, enlaces, y que los scripts citados con ruta relativa estén junto a
  la skill; los citados también con ruta absoluta de la VM o de otra carpeta
  salen como «referencia externa») e **instalar** en `skills\<nombre>\`
  (propia: manda). Si ya hay una igual, no se toca; si hay una distinta (quizá
  la editaste tú), la vieja se guarda en `skills\_respaldos\<nombre>.bak-<fecha>\`
  (no se carga: empieza por `_`) y se avisa. Informe en
  `share\outbox\skills-semilla-informe.json`. Nada se descarga de internet.
- **Workshop siempre en modo propose:** cuando no se activó ninguna skill y el
  encargo no es trivial (5 o más palabras con contenido;
  `skills_workshop_min_palabras`), el prompt le pide al motor que, si le faltó
  una guía, escriba al final `SKILL_QUE_FALTA: nombre | para qué serviría`. Si
  lo escribe sin que se le pregunte (ya tenía skills, o era «tres frutas»), se
  ignora: con Hermes 8B, preguntarlo siempre hacía que lo contestara de relleno.
  El runner guarda un **borrador** en `skills\_borradores\<nombre>-<fecha>\`
  (`SKILL.md` con `borrador: true` + `BORRADOR.json`), te avisa (bandeja,
  pestaña Skills, `share\outbox\skills-borradores.jsonl`) y el resultado trae
  `skill_propuesta`. **Nunca lo activa.** En Skills → Borradores: «Editar» (Bloc
  de notas) y «Aprobar» (pide confirmación, valida y COPIA a
  `skills\<nombre>\`; el borrador queda marcado «aprobado», no se borra).
- **Autoprueba:** `python growi-bridge.py --probar-skills` monta en una carpeta
  temporal propia (nunca la `skills\` real) una skill válida, una sin
  description, una con el secreto falso `sk-ant-falso123` y una con un programa
  que no existe, más el workshop, y dice PASA/FALLA por punto: la del secreto
  sale sospechosa, no se carga y su evidencia es
  `ANTHROPIC_API_KEY=[REDACTED CREDENTIAL]`.
- Estado → Gateway → Skills: fila «De Bridge» con las cargadas, las que no y los
  borradores pendientes. Detalles y pruebas: `share\outbox\ESTADO-SKILLS.md`.

## Memoria en el PC (memory\, Markdown que puedes abrir)

- **Dónde:** `memory\` junto a growi-bridge.py. `MEMORY.md` (hechos curados,
  decisiones, preferencias; cada sección con fecha: `## AAAA-MM-DD — tema`) y
  una nota por día, `memory\AAAA-MM-DD.md` (registro del día: solo se añade,
  nunca se reescribe ni se borra). Se abren y se editan con el Bloc de notas.
  Nada de base de datos, ni búsqueda vectorial, ni captura automática.
- **Al arrancar** se crea lo que falte: si Growi dejó
  `share\inbox\memoria-semilla\MEMORY.md`, la primera sync la trae; si no, una
  MEMORY.md mínima con solo lo que la app sabe de verdad (tus reglas, el puerto,
  el motor local) y la semilla entra después, sola, en cuanto llegue.
- **Cada tarea** recibe al empezar MEMORY.md + la nota de hoy + la de ayer
  (nunca más viejas; si no hay nota de ayer, solo la de hoy y se dice). Hasta
  12.000 caracteres o el 25 % del contexto que declara el descriptor del motor,
  lo que sea menor. Queda en el `.result.json` (`memoria_cargada`: qué archivos
  y cuántos caracteres) y en el registro («memoria [id]: inyectados …»). Un task
  con `"memoria": false` no lleva memoria; el carril B nunca.
- **Flush antes de compactar:** al terminar la tarea y ANTES de encolar la
  ronda o fase siguiente, si la tarea se acerca al límite de contexto, si el
  historial local se va a compactar o si terminó una fase, un turno silencioso
  le pide al modelo los hechos duraderos y se **añaden** a la nota de hoy
  («flush (id): … — lo destiló <motor>, sin verificar»). Umbrales: reserva
  20.000 tokens y flush suave a 4.000 del límite para una ventana de 200.000,
  escalados a la ventana que declara el descriptor (con 8.192: 819 + 163). El
  turno silencioso solo usa motores de $0 salvo que pongas uno a mano en
  `memoria.flush_motor`. Queda en el resultado como `memoria_flush`.
- **/nuevo** (paleta Ctrl+K, chat de Tareas o mascota): resume la sesión en
  `memory\snapshot-AAAA-MM-DD-<tema>.md` (nunca pisa otro: `-2`, `-3`…),
  archiva la sesión en `memory\sesiones\` y empieza otra. Resume un motor de $0
  (`memoria.motor_resumen` para otro); si no hay, los encargos tal cual.
- **«recuerda esto: …»** (chat, paleta o mascota): si es duradero (prefiero,
  siempre, nunca, decidí, regla…) va a MEMORY.md, sección «<hoy> — Recordado por
  el usuario»; si es de un día (fecha, hoy, ayer…) a la nota de hoy. «recuerda
  esto para siempre: …» / «recuerda esto hoy: …» fuerzan el sitio. Una ventana
  confirma dónde quedó, con «Abrir el archivo»; se comprueba leyendo el archivo.
- **Sync con la VM por diferencia:** la VM deja sus archivos en
  `share\inbox\memoria-vm\` (y la semilla en `share\inbox\memoria-semilla\`);
  cada 20 s, si cambiaron, se comparan por secciones `## `: lo nuevo se añade
  al final, lo igual no se toca, lo que solo cambió la VM se toma (la versión
  del PC queda en `memory\sync\anteriores\`) y si los dos lados editaron la
  misma sección es un **conflicto**: el PC no se pisa, las dos versiones van a
  `memory\conflictos\`, una línea a `memory\CONFLICTOS.md` y aviso (bandeja,
  registro, `share\outbox\memoria-conflictos.jsonl`). Lo nuevo del PC para la VM
  sale en `share\outbox\memoria-pc\diferencia.json` (solo secciones, nunca el
  archivo entero). La cabecera que pone Bridge (lo de antes del primer `## `)
  no cuenta como edición tuya: una cabecera distinta en la VM no da conflicto.
- **Paleta:** «Abrir la memoria (MEMORY.md)», «Abrir la nota de hoy…»,
  «Abrir la carpeta de la memoria», «Sesión nueva (/nuevo)» y «Sincronizar la
  memoria con la VM».
- **Registro:** `share\outbox\memoria-registro.jsonl`, una línea por carga,
  escritura, flush, snapshot y sync.
- **Ajustes** (`settings.json` → `memoria`, todo opcional): `activa`,
  `max_caracteres`, `reserva_tokens`, `flush_suave_tokens`,
  `contexto_referencia_tokens`, `contexto_tokens`, `flush_fin_de_fase`,
  `flush_motor`, `motor_resumen`, `vm_carpeta`.
- **Consola** (sin ventana): `--memoria-iniciar`, `--memoria-carga "encargo"
  [motor]` (en seco: qué se inyectaría), `--recuerda "recuerda esto: …"`,
  `--nuevo`, `--sync-memoria [carpeta]`, `--buscar-memoria "texto"` (búsqueda
  por texto en los Markdown). Detalles y pruebas: `share\outbox\ESTADO-MEMORIA.md`.


## Claves (BYOK): varias por proveedor, con URL base, en el almacén de Windows

Ajustes → **Claves** (y la página **APIs**, que es la misma superficie) tiene
**una fila por clave**, agrupadas por proveedor (Anthropic, OpenAI, Gemini,
Groq, OpenRouter, Grok, Tripo, Meshy). Cada clave tiene: proveedor, etiqueta
tuya («personal», «trabajo», «respaldo»…), **URL base** editable, la clave (solo
se ven los 4 últimos), activa o no, gasto del mes y su tope, **Probar sin
gastar** y **Borrar**.

- **Dónde se guarda la clave:** una entrada por clave en el Administrador de
  credenciales de Windows con `keyring` (destino `growi-bridge/<proveedor>-<etiqueta>`,
  p. ej. `growi-bridge/anthropic-personal`). Si keyring no está o no puede
  escribir en esa sesión, la app usa sola el **respaldo DPAPI** (cifrado con tu
  sesión de Windows, archivo `credenciales.dpapi.json`, en `.gitignore`). La
  pantalla dice cuál se usa y por qué. En `settings.json` solo quedan proveedor,
  etiqueta, base_url, últimos 4 y cuál está activa: **nunca la clave**.
- **URL base:** se rellena sola con la oficial al elegir el proveedor; cámbiala
  para un endpoint propio, un compatible con OpenAI, un proxy o un servidor
  local. Debe ser `https://` (`http://` solo para 127.0.0.1 o localhost), sin
  `usuario:clave@`, sin `?parámetros`; se quita la barra final.
- **Una activa por proveedor:** «Usar esta» la cambia al instante, sin volver a
  pegar nada. Los motores (por `credencial_ref` en engines.json) y las tareas
  `api:<proveedor>:<modelo>` usan siempre la activa, a su URL base; el
  registro y el `.result.json` dicen qué etiqueta se usó. Sin ninguna activa,
  sus motores salen «no disponible» con el motivo.
- **Probar sin gastar:** pide la lista de modelos (o el saldo / los datos de la
  clave) a la URL base de ESA clave; nunca inferencia. Dice el error exacto
  (401 clave incorrecta, 429 límite, error de red → revisa el proxy).
- **Gasto y tope por clave:** gasto del mes desde los `.result.json` (`gasto_clave`
  con la etiqueta; el costo del motor o tokens × precio de lista de engines.json;
  si no hay precio, «sin precio», no se inventa). Aviso al 75 % y al 90 %; al
  100 % se bloquea SOLO esa clave. Sin tope: aviso antes de cada uso con gasto.
  La sesión Max (motor claude) se muestra como «$ equivalente de Max».
- **Borrar** quita solo esa clave (almacén + settings.json). Borrarla aquí **no
  la invalida en el servidor**: la app te lo dice y te ofrece abrir el panel del
  proveedor para revocarla.
- **Lo que no protege:** DPAPI no protege contra un programa que corre con tu
  sesión. Lo mitigan el guardrail y que cada clave solo se envía a la API de su
  proveedor, a su URL base.
- **Desde la 0.2.0:** las claves de `apis.json` (una por servicio, en texto
  plano) se pasan solas al almacén como «principal» con su URL base por defecto.
  `apis.json` no se borra solo: Ajustes → Claves → «Borrar apis.json…».
  Detalles y pruebas: `share\outbox\ESTADO-CREDENCIALES.md`.

## Saldo Tripo: créditos, generaciones que quedan y costo antes de generar

Arriba de la pestaña **Modelos** están **Saldo Tripo** y **Generar con Tripo**
(CustomTkinter; con `"piloto_ctk": false` o `GROWI_BRIDGE_CTK=0`, la versión
clásica).

- **Saldo real:** `GET /v3/account/balance` (solo lectura, no gasta) con la
  clave Tripo **activa** de Ajustes → Claves (`growi-bridge/tripo-<etiqueta>`),
  a su URL base. La clave se lee del almacén en el momento y solo va a un
  subproceso (`growi-bridge.py --tripo-saldo`) por `TRIPO_API_KEY`; en el
  Registro sale `tsk_…` + los 4 últimos.
- **Sin clave guardada:** «saldo no disponible — falta guardar la clave en
  Ajustes → APIs» y el último saldo verificado (370 créditos, 25 oct 2026)
  marcado **no en vivo**. Si una lectura falla, el último saldo leído con su
  fecha, también **no en vivo**.
- **401:** «clave inválida o revocada». No se reintenta sola; solo con «Volver
  a leer» o al cambiar la clave.
- **Generaciones estimadas:** siempre las dos cifras con su calidad (estándar
  ~10 créditos, alta ~55). Con 370 → ~37 y ~7.
- **Aviso al 25 %** (`tripo_aviso_pct` en settings.json): fila con borde naranja
  en Saldo Tripo, en Generar y en la confirmación. Avisa, pero no bloquea.
- **Costo antes de cada generación:** «Generar…» lee el saldo en vivo y abre una
  confirmación («Esta generación cuesta ~10 créditos…, te quedan 360…»). Sin
  pulsar «Generar y gastar ~N créditos» no se lanza nada. Las tareas del runner
  cuyo encargo habla de Tripo muestran el mismo costo en «Esperan tu
  aprobación».
- **Registro:** `share\outbox\tripo-gasto.jsonl`, una línea al lanzar y otra al
  terminar (manda la última de cada `id`): fecha, tipo, calidad, créditos
  estimados y reales (`credits_consumed`), saldo antes y después, etiqueta de la
  clave, `task_id` de Tripo y estado. Las fallidas cuentan 0 si Tripo no cobró.
  Las de un servidor local salen `"simulada": true` y no cuentan ni calibran.
  En cuanto hay gastos reales de una calidad, el costo estimado pasa a ser su
  media real (las 5 últimas).
  Detalles y pruebas: `share\outbox\ESTADO-SALDO-TRIPO.md`.

## Exportar mis conversaciones (defensa contra el baneo)

- **Estado → Tus conversaciones → «Exportar mis conversaciones»**: explica la
  ruta oficial (claude.ai web o Claude Desktop → Ajustes → Privacidad →
  Exportar datos; en el móvil no está), avisa que el enlace del correo caduca
  a las 24 horas y que el ZIP NO se puede importar a otra cuenta (y no trae la
  memoria ni los archivos subidos). Bridge no exporta por ti: «Ya la pedí»
  apunta la fecha en `settings.json` → `ultima_exportacion`.
- **Recordatorio**: una línea arriba en Estado, «¿Exportaste tus chats esta
  semana?», los domingos si pasaron más de 7 días desde la última exportación
  (o al cerrar un proyecto grande). Máximo 1 por semana
  (`ultimo_recordatorio_exportacion`). Nunca un pop-up.
- **ZIP**: déjalo en `share\inbox\export-claude\` (o en la carpeta que elijas
  con «Carpeta vigilada…», p. ej. Descargas: ahí solo cuentan los `data-…zip`
  o los que llevan «claude» en el nombre). Bridge lo abre, comprueba el CRC,
  lee `conversations.json` entero y cuenta conversaciones y mensajes. Si está
  roto: «El archivo exportado no se pudo leer: vuelve a pedir la exportación».
  El bueno se copia a `share\outbox\export-claude\` (para la VM).
- **Historial de Claude Code** (`C:\Users\forte\.claude\projects`): en cada
  sync (sync de memoria con la VM, al arrancar y cada `copia_claude_cada_min`
  minutos, 30 por defecto) se copia a `share\outbox\claude-projects-backup\`
  (`projects\` + `manifiesto.json` con sha256 + `sincronizaciones.jsonl` con
  la fecha de cada sync). Solo lee los originales. Una copia cortada queda como
  `.parcial` y la siguiente sigue desde ahí. Después se leen los JSONL línea
  por línea y se cuentan; los corruptos se listan por nombre en la tarjeta y
  en el Registro. Apagar: `"copia_claude": false` en settings.json.
- Consola: `--copia-claude [completa]`, `--verificar-export <zip>`,
  `--recordatorio-export [proyecto]`.
  Detalles y pruebas: `share\outbox\ESTADO-EXPORTAR-CHATS.md`.

## Atajos de teclado (Ajustes → Atajos)

- **Cambiar un atajo**: Ajustes → Atajos (o Ctrl+K → «Cambiar los atajos de
  teclado»). Clic en el campo de la acción y **se pulsa** la combinación (no se
  escribe). Esc cancela sin guardar. Se comprueba, se guarda en
  `settings.json` y funciona al momento, sin reiniciar. «Quitar» la deja sin
  atajo.
- **Dos listas**: «Dentro de Bridge» (con la ventana o la paleta delante; no
  ocupan nada en Windows) y «En cualquier aplicación» (globales, con
  `RegisterHotKey`). Acciones: abrir la paleta, mostrar u ocultar la ventana,
  preguntar rápido y parar la tarea en curso. Por defecto: Ctrl+K (paleta,
  dentro de Bridge) y Ctrl+Alt+G (ventana, global), como antes.
- **Lo que se rechaza, con el motivo**: (a) la que ya usa otra acción de Bridge
  (o las fijas: Ctrl+0…9, Alt+1…9 de la paleta, Ctrl+C/V/X/A/Z/Y); (b) las de
  Windows (Ctrl+Alt+Supr, Alt+Tab, Alt+F4, Win+L, Win+D y casi todas las de la
  tecla Windows, F12 sola), las que pisan a todas las apps como global (Ctrl+K,
  Ctrl+Espacio, Ctrl+Mayús+letra, cualquier tecla con un solo modificador) y
  las Ctrl+Alt+letra que en este teclado escriben algo con AltGr (aquí
  Ctrl+Alt+Q = «@»); (c) la que **otra aplicación ya tiene**: lo dice en el acto
  («esa combinación ya la usa otra aplicación… Bridge no se la quita») y ofrece
  «Usar …» con la libre más cercana, comprobada en vivo. Nunca se la quita.
- **Mientras capturas** (máx. 30 s, o hasta que el campo pierde el foco) Bridge
  pone un gancho de teclado de bajo nivel para que la combinación llegue al
  campo aunque otra app la tenga como atajo; se quita en cuanto termina.
- **settings.json** → `"atajos": {"abrir_paleta": {"paleta": "Ctrl + K",
  "global": "Ctrl + Alt + T"}, ...}`. Sin entrada = el de fábrica; `""` = sin
  atajo. Editarlo a mano también vale: la recarga en caliente lo valida igual y
  lo que no valga se queda como estaba y lo dice en su fila. Si settings.json
  está dañado, Atajos lo dice arriba (línea y columna) y no guarda ni borra nada.
- **Al salir** se sueltan todos los globales (`UnregisterHotKey`; en el
  Registro: «atajos: N atajo(s) global(es) soltado(s) al salir»). Si la app
  muere (cuelgue, watchdog), Windows los suelta al terminar el proceso.
  Solo el carril A registra globales; una segunda copia sale por el mutex y una
  copia de prueba con otro mutex no puede quitárselos (lo dice en sus filas).
- **Comandos guardados** (otro spec): `atajo_registrar_accion("comando:<id>",
  nombre, fn, grupo="comando")` + `atajo_guardar(aid, ambito, combinacion)`;
  misma validación, salen en las dos listas.
  Detalles y pruebas: `share\outbox\ESTADO-ATAJOS.md`.

## Comandos de IA guardados (Ctrl+K)

Un prompt que usas a menudo se guarda una vez y se lanza desde la paleta sobre
el texto seleccionado (el mecanismo de los AI Commands de Raycast).

- **Crear**: Ctrl+K → «Nuevo comando de IA». Cinco campos: **título**,
  **prompt** (`{seleccion}` = el texto seleccionado; `{argumento
  nombre="idioma"}` = un dato que se pide al ejecutar), **icono** (un símbolo
  de texto: ≡ ✎ ⇄ ¶ ✉ ★ ✓ ? ◆ ∑), **modelo** (el id de un motor de
  engines.json) y **creatividad** («fiel», «equilibrado», «creativo»). Y qué
  hacer al terminar: «Mostrar para revisar» o «Reemplazar el texto».
- **Integrados**: «Resumir en 3 viñetas», «Mejorar texto» y «Traducir» (pide
  el idioma). Usan Ollama (local, $0) y muestran el resultado. No se editan: en
  la paleta, Ctrl+K sobre la fila → «Duplicar para adaptarlo» (cambias el
  prompt y le añades tus reglas de estilo). Los tuyos: «Editar el comando».
- **Ejecutar**: selecciona texto en Bridge (p. ej. en Tareas), Ctrl+K, busca
  el comando, Enter. Se abre su ventana con el texto, los datos que pida y
  «Ejecutar». También vale pegar el texto en la ventana o «Pegar lo copiado».
  Sin texto, si el comando lo necesita, lo dice y no llama a nada. Sin un dato,
  lo pide («Falta «Idioma»…») y no llama a nada.
- **Mostrar**: el resultado sale abajo para revisarlo (se puede retocar) y
  «Copiar». **Reemplazar**: sustituye el texto seleccionado; es una escritura,
  así que pasa por tus permisos: con «Preguntarme siempre» sale una ventana con
  el texto nuevo **completo** y el que se sustituye, y no cambia nada hasta
  «Reemplazar». Con los otros niveles se hace y se dice («sin preguntar…»), con
  «Deshacer el reemplazo». Si el texto de origen cambió entretanto, no
  reemplaza a ciegas.
- **Motor**: el comando corre con el motor que declara, leyendo solo su
  descriptor (no se crean motores aquí). Si no existe o no responde, sale
  «motor no disponible» (también en la paleta) y no hay resultado inventado.
  La creatividad va como temperatura en los motores HTTP (fiel 0,2,
  equilibrado 0,7, creativo 1,0); en los de consola solo va escrita en el
  prompt.
- **Atajo propio** (opcional): en el formulario, tras guardar, se pulsa la
  combinación («En cualquier aplicación» o «Con Bridge delante»); el mismo
  mecanismo y la misma validación de Ajustes → Atajos (donde también salen).
  Desde otra aplicación, el comando toma lo que tengas copiado (Ctrl + C) y lo
  dice; el reemplazo, en ese caso, deja el resultado en el portapapeles.
- **Archivo**: `comandos-ia.json` junto a growi-bridge.py, una lista
  `"comandos"`; lo escribe la app (Ctrl+K → «Abrir el archivo de comandos de
  IA» para verlo). Sin claves. Los atajos van en settings.json →
  `atajos` → `"comando:<id>"`. Si el archivo está dañado, la paleta lo avisa
  («Comandos de IA: el archivo está dañado (ver por qué)», con línea y columna),
  los integrados siguen y no se guarda nada encima. Un comando mal escrito no
  aparece y se dice por qué.
  Detalles y pruebas: `share\outbox\ESTADO-COMANDOS-IA.md`.

## Asistentes personalizados (perfiles): Ctrl+K y la bandeja

- **Qué es:** un asistente es una forma de trabajar, no un modelo nuevo:
  nombre, foto, para qué sirve, instrucciones en palabras normales, modelo por
  defecto (un motor de engines.json), modelo de revisión, tono (formal,
  cercano, directo o guaro), dónde sale (paleta, bandeja; WhatsApp solo si el
  canal existe), skills, carpetas que ve (con «solo leer» o «leer y
  escribir») y permisos.
- **Dónde vive:** `asistentes\<id>.md` junto a growi-bridge.py: arriba el
  frontmatter YAML, abajo las instrucciones en Markdown. Se abre con el Bloc de
  notas y se respalda copiando la carpeta. Vienen tres: **Growi** (principal,
  Claude, «Preguntarme siempre», todas tus carpetas), **Guionista Summit**
  (brandbook de Summit Maker, Claude, carpeta OneDrive\Proyectos\Summit Maker,
  tono guaro, skills summit-maker, documentos-humanos y canva, «solo lo
  delicado») y **Contable** (Ollama local $0, revisa Claude, solo la carpeta
  `finanzas\`, tono directo y con números, «Preguntarme siempre»).
- **Crear o editar:** Ctrl+K → «Nuevo asistente» (o Ctrl+K sobre un perfil →
  «Editar el asistente»). Editar el archivo a mano también vale (Ctrl+K →
  «Abrir la carpeta de asistentes»).
- **Cambiar:** Ctrl+K → «Usar Guionista Summit» (o «Cambiar» en la fila de
  arriba), o la bandeja → «Asistente: …». Sin reiniciar: desde la siguiente
  tarea el runner usa sus instrucciones, su modelo (si la tarea no dice otro),
  sus carpetas (una tarea fuera de ellas se rechaza con el motivo), su
  revisión, sus skills y sus notas propias; los permisos pasan a los del
  perfil. El cambio queda en el Registro y en settings.json →
  `asistente_activo` (sobrevive al reinicio). Una tarea puede fijar el suyo con
  `"asistente": "<id>"`; las rondas y fases siguen con el mismo.
- **Memoria:** MEMORY.md es la de todos. Cada perfil suma sus notas propias en
  `memory\asistentes\<id>.md` (Ctrl+K: «recuerda esto: …» → «Recordar solo
  para <perfil>»).
- **Permisos:** un perfil nunca baja a «Hazlo sin preguntar» sin escribir SIN
  PREGUNTAR en el formulario (en el archivo: `confirmacion_guardrail: 'SIN
  PREGUNTAR'`); al activarlo se pide otro sí. Un perfil recorta carpetas, nunca
  amplía las de la página Carpetas.
- **Si algo está mal:** ese perfil no aparece y Ctrl+K dice «Asistentes: N no se
  cargaron (ver por qué)» con el motivo exacto; los demás siguen y la app no se
  rompe. Sin perfiles, todo funciona como antes. Un solo usuario en un solo PC:
  no hay cuentas ni login.
  Detalles y pruebas: `share\outbox\ESTADO-ASISTENTES.md`.

## Temas: claro, oscuro Raycast o según Windows (Ajustes → Apariencia)

- **Elegir**: Ajustes → Apariencia → «Claro», «Oscuro» o «Según el sistema»
  (como VS Code). Se guarda en `settings.json` (`"apariencia": "claro" |
  "oscuro" | "sistema"`) y vale también al volver a abrir Bridge. Por defecto,
  el claro de siempre.
- **Según el sistema**: lee `HKCU\Software\Microsoft\Windows\CurrentVersion\
  Themes\Personalize\AppsUseLightTheme` (1 = claro, 0 = oscuro) al arrancar,
  al elegir la opción y cada vez que vuelves a abrir Ajustes.
- **Los temas son archivos** en `temas\` (junto a growi-bridge.py):
  `claro.json` y `oscuro-raycast.json`. «Tema por nombre» lista los que hay y
  «Abrir la carpeta de temas» la abre. Si un archivo está roto, le falta un
  token o no llega a 4,5:1 de contraste, ese tema no aparece y Apariencia dice
  por qué (también en el Registro). Sin la carpeta, queda solo el claro.
- **Cambia al momento**, sin reiniciar (una tapa «Cambiando a …» cubre la
  ventana unos segundos mientras se re-pinta). Si algo no se pudiera re-pintar
  (por ejemplo, un tema con otra fuente), no cambia nada a medias: lo guarda y
  te avisa de que se verá al volver a abrir Bridge.
- **No cambia con el tema**: el tamaño y la colocación de las cosas, los
  bordes de la ventana, el icono de la bandeja y la mascota (son imágenes).
  Alto contraste de Windows: queda fuera por ahora.
  Detalles y pruebas: `share\outbox\ESTADO-TEMAS.md`.
