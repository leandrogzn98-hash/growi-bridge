# Growi Private MQTT 0.1 — la versión solo MQTT

Se trabaja **en la misma rama `reforma-cuentas`** (Fase 6 +
correcciones + reforma de cuentas): corrección 2 del dueño el
2026-11-17 — tampoco hay rama nueva; «Growi Private MQTT 0.1» es la
identidad y la versión de la app, no una bifurcación de código. (Las
fases P0–P2 se hicieron primero en una rama `growi-private-mqtt` y
sus commits se pasaron tal cual a `reforma-cuentas`, que es donde
vive y sigue todo el trabajo.) Es el mismo programa con otra
identidad y otra conexión: **solo MQTT con brokers** para hablar
con las cuentas Muse. El harness y todo lo nuevo de esta etapa es
para esa conexión.

Las ramas de diseño de la tarde (`diseno-mqtt` y `diseno-equipo`)
**se quedan como referencia** — corrección del dueño el 2026-11-17:
«olvídate lo de borrar», no se borra nada; con «borrar» se refería a
los ajustes del principio, que no sirvieron por no tener conexión.
De hecho los dos diseños alimentan esta bifurcación: el de MQTT es
la base de P1 y el de equipo lo es de P3 y P4.

## Fases

- **P0 · Bifurcación y poda** — hecha (este documento).
- **P1 · MQTT de verdad** — hecha (detalle abajo).
- **P2 · Cuentas con broker** — hecha (detalle abajo).
- **P3 · La sala** — hecha (detalle abajo).
- **P4 · Skills-plus** — hecha (detalle abajo).
- **P5 · Modelos unificado** — hecha (detalle abajo).
- **P6 · Recursos con sliders y Tareas vivas** — hecha (detalle abajo).
- **P7 · Pruebas físicas completas** — el programa en Rust pedido en
  la sala y probado en el PC vía MQTT midiendo consumo; el flujo
  «revisa las actualizaciones y actualiza» con el ayudante de root
  de la Fase 6 (la contraseña de root no se guarda en ningún sitio);
  reparto en la sala entre dos cuentas reales de prueba.

## P0 · Lo hecho

- **Identidad**: `VERSION` = `0.1`; el título de la ventana, la
  cabecera y la línea de versión de la barra lateral y el texto de
  Ajustes dicen «Growi Private MQTT». Los nombres internos (carpetas
  de datos, servicio de la bóveda) no cambian: renombrarlos rompería
  los datos existentes sin aportar nada.
- **Fuera la página Estado**: sin entrada en el menú ni en la paleta
  de comandos; la página inicial pasa a ser Cuentas; el chip de
  conexión y el botón del banner apuntan a Cuentas; los comandos de
  paleta propios de esa superficie (mapa de disponibilidad, probar
  el proxy, ir a la configuración del proxy) se retiran. Nada de
  puertos/router/proxy/Tailscale se usa en esta bifurcación.
- **Fuera la página «Ventana»**: la página de pantalla compartida
  (en el código, «Pantalla») sale del menú y de la paleta. Mostrar
  un error se hace pasándolo por la app nativa de una Muse, que se
  lo describe a la otra — como dictó el dueño.
- **Carpetas baja** en el menú: el orden nuevo es Cuentas, Chat,
  Modelos, APIs, Skills, Tareas, Recursos, Ajustes, Carpetas.
- **Registro oculto y reactivable**: no aparece en el menú; se
  reactiva con el comando de paleta «Mostrar u ocultar el Registro»
  (ajuste `mostrar_registro`, se aplica al reabrir la app).
- **Ajustes deja de duplicar las APIs**: la sección de claves sale
  de Ajustes; las claves viven solo en la página APIs hasta que P5
  las unifique dentro de Modelos.
- **Cómo se poda**: las páginas Estado y Pantalla no se borran del
  código; quedan construidas pero inalcanzables desde la UI — la
  misma disciplina que el código dormido de otros canales en este
  proyecto (poda visible y reversible, sin desestabilizar la
  maquinaria interna: puente, runner y cola siguen funcionando).

### Verificación P0

- Suite completa: **443 pruebas en verde** (las mismas de la rama
  madre; la poda no rompe ninguna).
- Arranque real en el entorno de pruebas (Xvfb): puente arriba
  (401 sin clave), título de ventana «Growi Private MQTT 0.1»
  leído por X11, barra lateral con la identidad nueva y el menú
  podado en el orden dictado, página inicial = Cuentas.
- **Fallo real cazado por la prueba física**: la paleta reventaba
  con `KeyError: 'cuentas'` porque su diccionario de alias no tenía
  las páginas Cuentas/Chat (nunca estuvieron en la paleta). Se
  agregaron los dos alias. Sin arranque real, este fallo no se ve.

## P1 · Lo hecho

- **`mqtt_enlace.py`** (módulo nuevo): el cliente MQTT del programa.
  Temas `growi/<id-pc>/<cuenta>/…` (tareas, resultados, avisos,
  presencia) y `programa/presencia` + `programa/tablero` retenidos;
  QoS 1 con sesión persistente e **idempotencia por id** (los
  duplicados de QoS 1 se descartan); **tope de 64 KB** por mensaje
  sin trocear; **TLS obligatorio** (texto plano o no verificar el
  certificado solo hacia hosts locales: el túnel CONNECT de los
  espacios Muse); presencia con LWT. Sin paho-mqtt instalado, el
  módulo carga igual y el enlace falla con motivo claro, sin tumbar
  la app.
- **`ayudante-mqtt.py`** (nuevo): el lado Muse, un solo archivo sin
  dependencias del proyecto. Recibe un JSON con el paquete de 4
  datos (broker, su credencial, raíz de temas, su clave Growi);
  verifica la clave dentro de cada sobre antes de aceptarlo; deja
  las tareas como archivos en `entrada/` y publica lo que la Muse
  deje en `salida/`; presencia retenida + LWT. Si el entorno sale
  por proxy CONNECT (los espacios Muse), levanta su propio túnel
  local — el patrón verificado en la prueba de viabilidad.
- **Modo `mqtt` por cuenta**: `cuentas.py` acepta la conexión
  `mqtt` (la opción visible en el alta llega con la UI de P2). A
  efectos del vigilante dual, una cuenta mqtt no arranca el modo
  dual: es una pata única, como «servidor».
- **Cableado en el monolito** (`_fpm_*`): al arrancar, si hay broker
  configurado en ajustes (`mqtt_broker`, `mqtt_usuario`, contraseña
  en la bóveda como `mqtt:programa`, id de PC persistente) y alguna
  cuenta habilitada en modo mqtt, el enlace conecta. Lo que llega
  se autentica con la clave Growi de la cuenta (comparación segura;
  si no coincide, se descarta y se anota) y cae en la carpeta
  compartida `mqtt-resultados/`; la presencia alimenta
  `mqtt-estado.json`. `_mqtt_enviar_tarea(cuenta, datos)` es la
  puerta de salida para las fases siguientes.

### Verificación P1

- **458 pruebas unitarias en verde** (443 de antes + 15 nuevas:
  URL/TLS, sobres y tope, idempotencia, el enlace con un cliente
  falso, y el modo mqtt en el registro de cuentas).
- **Prueba en vivo contra el broker público de EMQX** (WSS, por el
  proxy del entorno): el programa conecta; el ayudante conecta con
  su propio túnel; la presencia de la cuenta se ve; una tarea llega
  al ayudante como archivo; el resultado vuelve al programa con la
  clave correcta dentro; al matar el ayudante sin despedirse, el
  LWT anuncia «sin_conexion» solo. 6/6.
- **Arranque real de la app** con el cableado: puente arriba y ni
  una línea MQTT en el registro (sin broker configurado ni cuentas
  mqtt, el enlace duerme, como debe ser).

## P2 · Lo hecho

- **El alta ofrece «mqtt»** en «Cómo se conecta», con su línea en
  lenguaje llano: «por internet con punto de encuentro (un broker):
  nadie entra a tu PC».
- **Sección «Broker MQTT» en Cuentas**, tras el bloque de cuentas:
  dirección del broker y usuario del programa (a ajustes), su
  contraseña (a la bóveda como `mqtt:programa`, solo escritura);
  credencial del broker por cuenta (usuario a ajustes, contraseña a
  la bóveda como `mqtt:<cuenta>`); botón **«Paquete para su Muse»**
  que muestra los datos a pasar (broker, usuario, raíz de temas y
  cuenta, con la nota honesta de qué no se vuelve a mostrar y cómo
  recuperarlo). Guardar el broker valida la dirección y reconecta
  el enlace en caliente (`_fpm_reiniciar`).
- **Uso resumido**: una línea por cuenta mqtt con su presencia
  (del estado del enlace) y su % de tokens libres (del tablero):
  nada de pared de datos.

### Verificación P2

- Suite completa en verde (458) y arranque real: la sección se ve
  completa y la línea resumida de la cuenta mqtt aparece («Rayo:
  sin datos · —% de tokens libres» en el entorno, sin enlace).
- Con los ajustes que escribe esta pantalla, la app real intentó
  el enlace al arrancar: sin paho instalado lo dijo tal cual en el
  registro, y con paho llegó al saludo TLS (en esta VM falla la
  verificación porque el extremo es el túnel local 127.0.0.1 y el
  certificado es del broker — el camino vivo completo ya quedó
  probado en P1; en un PC normal la dirección real del broker
  verifica sin problema).
- **Fallo real cazado y corregido**: la conexión MQTT corría en el
  hilo de arranque y un broker lento podía dejar la app sin
  arrancar (el puente no subió en una prueba). `_fpm_iniciar` ahora
  conecta en su propio hilo: un broker caído o lento jamás bloquea
  la app.
- Límite de método: el robot de pruebas no logró teclear en el
  campo del broker (la página va desplazada y el tecleo X11 del
  entorno falla con ciertos caracteres); el guardado se verificó
  por el formato exacto de ajustes que la pantalla escribe,
  alimentado a mano en el arranque real de arriba.

## P3 · Lo hecho

- **`sala.py`** (nuevo): el registro de la sala (`sala.jsonl`) con
  un solo punto de escritura y **redacción obligatoria** (patrones
  de secreto + los valores de la bóveda que el monolito le pasa:
  ningún secreto entra en la sala), y el estado del reparto
  conversado (`sala-reparto.json`: fases, asignada, aceptada, peso).
  La autoridad del encargo sigue en `encargos.json` (relevo.py);
  esto es su cara conversada.
- **La página Chat es ahora la Sala**: globitos (el dueño a la
  derecha, las cuentas a la izquierda, el sistema en el centro),
  panel del reparto en curso con sus fases y botones (Empezar,
  Reasignar a la otra, Marcar aceptada), y entrada con «Crear
  encargo». La página de chat 1:1 queda en el código, dormida.
- **El reparto conversado manda**: un encargo nacido en la sala
  (`"sala": true`) se divide como siempre, pero **no se entrega
  nada** hasta que el reparto se arranca desde la sala. Al dividir,
  la propuesta cae en la sala con cada fase y su asignada.
- **Los fallos caen en la sala** con su extracto acotado y
  redactado (gancho en `_f4_resultado_a_buzon`), y el cierre del
  encargo también, con su resumen. Por MQTT, una cuenta puede
  aceptar o reclamar una fase y mandar el resultado de su subtarea
  al buzón del relevo (`_fpm_sala_ruta`): el autor lo pone el
  programa desde el sobre autenticado, nunca el texto de la Muse.

### Verificación P3

- Suite completa en verde (469: 458 + 11 de la sala).
- Ciclo físico completo con la app real (dos carriles): encargo de
  sala → división propuesta en la sala → subtarea **retenida** →
  arranque → ejecución → **fallo en la sala con su extracto** →
  resultado en el buzón → encargo cerrado y **cierre en la sala**.
  La página pinta la conversación y el panel del reparto en vivo.
- Fallos reales cazados y corregidos: una clave de tema inexistente
  tumbaba la ventana al arrancar; **el cwd de las subtareas de la
  sala salía rechazado** (la carpeta del programa no es carpeta
  permitida: el encargo de la sala ahora nace con cwd en la casa del
  usuario, que sí lo es); el mismo fallo se escribía dos veces en
  la sala (deduplicado) y el cierre del encargo se etiquetaba como
  fallo de fase (ahora va como cierre).
- Límites honestos: el robot del entorno no logra pulsar los
  botones de las páginas con scroll (le pasa igual en P2; los
  clics reales del dueño en su PC sí funcionan, probados por él en
  rondas anteriores) — el flujo se verificó entregando el encargo
  con el formato exacto que escribe el botón y llamando a las
  mismas funciones que llama «Empezar». La ruta MQTT→sala queda
  probada por piezas (transporte en P1, módulos aquí) y su prueba
  viva completa es parte de P7. El reparto con varias fases reales
  depende del planificador con motor real; con el plan de reserva
  es una sola fase.

## P4 · Lo hecho

- **Campo `fuertes` por cuenta** (`cuentas.py`): lista opcional de
  nombres de skill en `accounts.json`; los registros sin el campo
  (v1) cargan igual. Aquí solo se valida la forma del nombre; que el
  skill exista lo valida la app al guardar (el registro no conoce el
  catálogo) y, si un fuerte deja de existir, al repartir cuenta 0 y
  la fila de la cuenta lo marca «(ya no existe)». Ayudante
  `cuentas.fuertes_de()` (sin duplicados, en orden declarado).
- **Editor en Cuentas**: sección «Skills fuertes» con la explicación
  en llano, la línea de fuertes de TODAS las cuentas (compartidos y
  conocidos por ambas: también van en la fila de cada cuenta de la
  lista), el campo de la cuenta elegida con la lista de skills que
  existen y «Guardar fuertes», que rechaza con el motivo en llano
  cualquier nombre que no esté en el catálogo.
- **El reparto por puntos** (`relevo._elegir_por_puntos`): cuando
  alguna cuenta tiene fuertes válidos, `relevo.asignar` elige con la
  fórmula del diseño de equipo — 0,4·fuerte + 0,3·peso + 0,2·tokens
  libres + 0,1·(1 − carga) — sobre las mismas candidatas de siempre
  (habilitada, con carril, activa). El factor fuerte lo calcula el
  monolito (`_f4_fuertes_fn`) cruzando la descripción de cada skill
  fuerte con el texto de la subtarea con el tokenizado de siempre
  (≥2 palabras en común = 1,0; 1 = 0,5). El peso declarado de la
  subtarea (`spec["pesos"]`) entra topado por el propio factor
  fuerte — nadie se autoasigna más peso del que su fuerte justifica
  — y sin peso declarado el factor hace de peso. Cada subtarea
  guarda `fuerte`, `skill_fuerte` y `puntos`: el reparto es
  explicable, y la propuesta de la sala lo dice («→ segunda
  (fuerte: ahorro-tokens)»). Sin fuertes declarados, `fuertes_fn`
  es None y el reparto es exactamente el de antes.
- **Prioridad al ejecutar** (`_skills_con_fuertes`): al montar el
  prompt de una tarea, los skills fuertes de SU cuenta entran como
  candidatas prioritarias si encajan con el texto (≥1 palabra en
  común con su descripción; la selección normal pide ≥2). La
  elección sigue siendo por descripción — un fuerte sin relación
  con la tarea no entra — y el tope de candidatas no cambia.
- **Fallo real cazado por la prueba física**: la primera versión
  leía la cuenta del dict de la tarea, pero `validate_task` la
  descarta a propósito (la autoridad es la fila de la cola, §12.4
  de la Fase 4) y la cuenta vive en `_ENV_TAREA`, que compone
  `_f4_fijar_entorno_tarea` antes de ejecutar. Corregido: la cuenta
  sale de `_ENV_TAREA` (con el dict y el entorno como respaldo) y
  hay prueba de regresión.
- **El motor por cuenta del diseño de equipo (§5: fichas de
  DeepSeek/Kimi como motores de texto con su clave por cuenta) pasa
  a P5**, que es la fase de Modelos: ahí se toca `engines.json` y
  las claves, y encaja mejor que aquí.
- **Pruebas**: 490 en verde (21 nuevas: forma y carga de `fuertes`,
  la fórmula — el fuerte gana al %, el peso se topa, las cuentas no
  activas no entran, sin `fuertes_fn` nada cambia — y el monolito
  contra un catálogo real de juguete). Pruebas físicas con la app
  real y dos skills de juguete (`revision-profunda` para principal,
  `ahorro-tokens` para segunda): el encargo de sala «ahorra tokens
  en cada tarea y revisa el consumo» se lo quedó segunda con
  fuerte 1,0 y la propuesta de la sala lo anotó; una tarea de
  principal con una sola palabra en común («revisa este archivo»)
  activó su skill fuerte, cosa que la selección normal no hace; la
  sección de Cuentas se ve entera con los fuertes de las dos
  cuentas y la lista de skills existentes. Límite de método: el
  botón «Guardar fuertes» no se pudo pulsar con el robot del
  entorno (el límite ya conocido de los botones en páginas con
  desplazamiento); el guardado queda probado por la misma vía de
  registro que usan los demás botones de la página y por las
  pruebas del módulo.

## P5 · Lo hecho

- **La página «APIs» ya no existe**: fuera del menú, de la paleta y
  de los atajos (la lista de páginas y sus alias quedan consistentes,
  que fue el fallo de la P0). Su contenido — las claves — se dibuja
  ahora dentro de **Modelos** («Claves de API», la misma superficie
  de siempre con su dibujo al abrir la página), y todos los textos
  que mandaban a «Ajustes → Claves» o «Ajustes → APIs» dicen ahora
  «Modelos → Claves de API». Los saltos internos que abrían la
  página APIs (disponibilidad, «Usar» un motor) abren Modelos.
- **CLI de Gemini en Modelos**: sección con el estado real del
  programa de Gemini del PC (Antigravity, `agy`) — instalado o no y
  si puede entrar — comprobado sin gastar con `engine_status`, y
  botón para recomprobar. La Librería de modelos locales ya vivía
  en Modelos y se queda donde estaba.
- **MCP en Modelos, honesto**: Growi no guarda servidores MCP (cada
  programa — Claude Code, el CLI de Gemini — guarda los suyos); la
  sección lo dice en llano y muestra los detectados en el PC
  leyendo SOLO los nombres de `~/.claude.json` (raíz y proyectos) y
  de un `mcp_servers.json` junto a la app (`_mcp_detectados`: esos
  archivos pueden guardar claves dentro de cada servidor y no se
  tocan).
- **Motor por cuenta** (lo que la P4 dejó aquí del diseño de
  equipo §5): campo opcional `motor` en `cuentas.py` (forma
  validada; la existencia la valida la app al guardar) y sección
  «Motor de cada cuenta» en Cuentas: la línea de cada cuenta con su
  motor y si tiene clave propia, el selector de la cuenta elegida
  y su clave a la bóveda como `motor:<cuenta>:<motor>`.
- **Orden de motores al validar una tarea**: el de la tarea > el
  router Automático > **el propio de la cuenta** > el del asistente
  > el del programa. La cuenta solo manda si la tarea declara esa
  cuenta y es la de este carril (la misma regla que cierra las
  tareas de otra cuenta).
- **Fichas nuevas en `engines.json`: DeepSeek y Kimi**, APIs
  compatibles con OpenAI marcadas `solo_texto: true`. El ejecutor
  HTTP aprendió el camino de internet (`_http_api_remota`): con
  `credencial_ref`, la llamada sale con su cabecera `Authorization`
  y la base de la clave activa si trae otra; los motores locales
  siguen por `_http_local` sin tocar. `engine_status` acepta la
  API remota con la credencial válida como disponibilidad.
- **Clave por cuenta de verdad**: `resolver_credencial_motor` —
  primero la clave propia de la cuenta en curso
  (`motor:<cuenta>:<motor>`, con la cuenta de `_ENV_TAREA`, nunca
  del payload); si no hay, la general de siempre. Lo usan
  `acceso_motor`, el entorno del motor y el limpiado de resultados
  (una clave propia que el motor repita en su salida también se
  tapa).
- **Veto en el reparto**: `relevo.asignar` acepta `motor_fn` y
  `motores_texto`; una fase de código (con git o archivos) nunca va
  a una cuenta cuyo motor efectivo sea solo de texto — ni por
  puntos ni por la vía clásica — y si el veto deja la fase sin
  nadie, el motivo lo dice tal cual.
- **Dos fallos reales cazados por las pruebas físicas** (la
  primera versión pasaba las unitarias y fallaba en vivo):
  `validate_task` siempre estampa un motor concreto, así que el de
  la cuenta no llegaba nunca; y el motor del asistente activo se
  imponía también. Corregidos con el orden de arriba y pruebas de
  regresión sobre `validate_task`.
- **Pruebas**: 512 en verde (22 nuevas). Físicas con la app real:
  el menú ya no trae «APIs»; Modelos se ve con sus secciones (las
  claves dibujadas dentro, el CLI de Gemini con su estado honesto
  «no instalado» en el entorno); Cuentas muestra «Segunda:
  deepseek · clave propia: no (usa la general)»; y una tarea real
  de la segunda cuenta corrió con SU motor y se cerró sin clave
  con el motivo nuevo: «motor deepseek no disponible: sin
  credencial: no hay ninguna clave de deepseek guardada (Modelos →
  Claves de API)». Límites: DeepSeek/Kimi no se verifican en vivo
  (hace falta la clave del dueño, como Telegram); la página
  Modelos no se dejó desplazar por el robot del entorno (pesada en
  CustomTkinter), así que sus secciones nuevas se verificaron
  además en una ventana aislada con el mismo código.


## P6 · Lo hecho

- **La lectura de disco, arreglada**: la tarjeta «Disco libre» de
  Recursos pedía la unidad de Windows (`C:\`) tal cual, así que en
  Linux fallaba siempre y decía «No pude leer el disco.». Ahora en
  POSIX lee el disco donde vive el programa y la tarjeta dice los
  GB libres y «en /»; en Windows sigue como estaba.
- **Recursos resumido y en el orden pedido**: arriba las cuatro
  tarjetas de consumo (CPU, RAM, GPU y disco libre), debajo la
  sección Multi-Muse con la presencia, los % por modo y los topes,
  y «Mis procesos» baja al final de la página (sigue funcionando
  igual: buscar, ver todos y cerrar procesos).
- **Deslizadores para los topes**: los tres campos de texto de los
  topes absolutos (núcleos de CPU, GB de RAM, GB de GPU) son ahora
  deslizadores por modo (ausente y presente), con el máximo del
  hardware detectado y la etiqueta al lado («sin tope» en 0, o el
   valor). Escriben en las mismas variables que lee el botón
  «Guardar porcentajes y topes», así que el guardado y la regla de
  «manda el tope más bajo entre el % y el absoluto» no cambian.
- **Tareas por cuenta**: tarjeta nueva en la página Tareas con una
  lista por cuenta Muse — su carril, sus encargos vivos con el
  avance hecho/total y el % (del registro compartido de encargos),
  sus fases sin terminar y lo que tiene en su cola en cada carril
  (su `cola.db` leída en solo lectura). Se refresca cuando cambia
  cualquiera de esas fuentes; si una cola no se puede leer, esa
  parte se salta y el resto se muestra.
- **Pruebas**: 515 en verde (3 nuevas). Las unitarias cazaron un
  fallo real antes de salir: la vista iteraba el registro de
  encargos como lista cuando es un diccionario por raíz — en la
  app habría quedado la tarjeta muda para siempre. Físicas con la
  app real: la tarjeta de disco marca «148.5 GB libres de 150 GB
  en /», el orden nuevo se ve tal cual, un deslizador se movió y
  su etiqueta pasó a «0.5 GB», y la tarjeta de Tareas muestra las
  dos cuentas con su carril y «sin trabajo ahora». Límite: el
  botón Guardar de la página no se pudo pulsar con el robot del
  entorno (el límite conocido de los botones sobre lienzo); el
  guardado es el mismo código que ya funcionaba con los campos de
  texto y los deslizadores solo escriben sus variables.
