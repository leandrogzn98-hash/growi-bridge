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
- **P1 · MQTT de verdad** — transporte del diseño verificado (WSS,
  temas `growi/<id-pc>/<cuenta>/…`, QoS 1 + idempotencia por id,
  presencia retenida + LWT, tope 64 KB, clave Growi dentro de la
  carga; el broker es transporte, no autoridad) y modo de conexión
  `mqtt` por cuenta.
- **P2 · Cuentas con broker** — entrada del broker en Cuentas
  (dirección, usuario, contraseña a la bóveda como `mqtt:<cuenta>`)
  y uso resumido por cuenta.
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
