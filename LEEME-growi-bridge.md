# Growi Bridge v2.0 — puente + runner + proxy + pantalla + mascota en uno

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
- **Proxy** — botón para encender/apagar el proxy (host, puerto, usuario y
  clave configurables en la ventana; cada quien usa los suyos). Encendido,
  Claude sale por el proxy; apagado, deja de usarlo.
- **Carpetas** — pestaña para elegir qué carpetas puede ver Claude Code.
  Por defecto: el Inbox del puente + tu carpeta principal. Growi también
  puede modificar esta lista pidiéndole a Claude que edite `folders.json`.
- **Skills** — pestaña con las skills instaladas de Claude Code
  (`~/.claude/skills/`).
- **Pantalla** — compartir pantalla con Growi: fotogramas comprimidos (JPEG,
  máx. 1280px) cada pocos segundos, solo cuando tú lo activas. Growi mira
  un fotograma cuando se lo pides o cuando hace falta; no es video en vivo.
- **Mascota** — Growi en la esquina inferior derecha. Clic para saludar
  (animación) y escribirle un mensaje rápido; el mensaje llega a Growi por
  el puente y la respuesta llega en el chat.
- **Botón grande** — enciende/apaga puente + runner juntos, con animación.
- **Actualizaciones** — busca nuevas versiones en GitHub y se actualiza
  sola (descarga el `growi-bridge.py` nuevo y se reinicia).
- **Administrador** — la app detecta si corre elevada; el instalador la
  deja en arranque automático con privilegios máximos para no tener
  problemas de permisos.

## Seguridad (acotada, pero sin amarrar las manos)

- Solo ejecuta `claude -p`, nunca shell directo con nada que venga de un
  task. Las tareas solo llegan por el puente (secreto compartido).
- Claude Code solo trabaja dentro de las carpetas de la pestaña Carpetas.
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
  proxy, indicador de sincronización, configuración del proxy, casilla de
  la mascota, botones (Inbox, Outbox, actualizaciones, salir) y registro.
- **Carpetas:** añadir/quitar/restablecer las carpetas permitidas.
- **Skills:** lista de skills instaladas de Claude Code.
- **Pantalla:** compartir/dejar de compartir, cada cuántos segundos.

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
- **Falta configurar el proxy:** el botón de encender te lo pide; pon host,
  puerto, usuario y clave y guarda.
- **Sin icono en la bandeja:** falta `pystray` (`pip install pystray
  pillow`); la ventana sigue funcionando.
- **Registro completo:** `growi-bridge.log` junto al programa.
