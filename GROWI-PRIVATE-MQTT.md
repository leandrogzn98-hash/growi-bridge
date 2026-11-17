# Growi Private MQTT 0.1 — bifurcación solo MQTT

Rama `growi-private-mqtt`, nacida de la punta de `reforma-cuentas`
(Fases 0–6 + correcciones + reforma de cuentas). Es el mismo programa
con otra identidad y otra conexión: **solo MQTT con brokers** para
hablar con las cuentas Muse. El harness y todo lo nuevo de esta
bifurcación es para esa conexión.

Las ramas de solo diseño de la tarde (`diseno-mqtt`, `diseno-equipo`)
quedan descartadas por decisión del dueño: su dictado de esta
bifurcación las reemplaza. No se borra código probado.

## Fases

- **P0 · Bifurcación y poda** — hecha (este documento).
- **P1 · MQTT de verdad** — hecha (detalle abajo).
- **P2 · Cuentas con broker** — hecha (detalle abajo).
- **P3 · La sala** — el Chat pasa a chat general estilo globitos:
  dueño y cuentas en el mismo hilo, reparto conversado conectado al
  encargo real, notificaciones y fallos con su extracto.
- **P4 · Skills-plus** — skills por cuenta, compartibles y conocidas
  por ambas, como criterio vivo del reparto.
- **P5 · Modelos unificado** — Modelos absorbe APIs (añadir/reemplazar
  clave), el CLI de Gemini, el MCP y la Librería de modelos locales.
  Las APIs de Claude/ChatGPT/Llama las usa cada Muse directo en su
  espacio; Growi solo guarda claves de modelos cuando aplica.
- **P6 · Recursos con sliders y Tareas vivas** — Recursos resumido
  (consumo actual arriba, lectura de disco arreglada, sliders de
  núcleos/GB RAM/GB GPU sobre los topes absolutos existentes) y
  Tareas como lista real por cuenta con % de avance.
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
