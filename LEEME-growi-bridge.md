# Growi Bridge v2.2 — puente + runner + proxy + pantalla + mascota + APIs en uno

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
  segundos por el puente.
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

La X minimiza (la ventana queda minimizada y la mascota sigue en su
esquina). Salir de verdad es con el botón Salir o desde el menú de la
bandeja (clic derecho al icono).

## El menú de la bandeja

Clic derecho a mi foto: Mostrar ventana, Puente, Runner, Proxy (✓ cuando
está encendido), Mascota (✓), Compartir pantalla (✓), Salir. Doble clic
muestra la ventana.

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
