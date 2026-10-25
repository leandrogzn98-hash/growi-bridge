# Growi Bridge

Puente + runner + proxy + pantalla + mascota en un solo programa para
Windows. Conecta tu PC con tu asistente de IA (Muse) para orquestar
Claude Code desde el chat, sin abrir la terminal.

![Growi Bridge](growi.png)

## Qué hace

- **Puente**: servidor de archivos PC ↔ asistente (puerto 8787, secreto
  compartido). El indicador de sincronización muestra qué se descarga o
  envía en cada momento.
- **Runner**: ejecuta `claude -p` sin ventana con las tareas que llegan por
  el puente, con sesiones continuas.
- **Proxy**: botón para encender/apagar tu proxy (host, puerto, usuario y
  clave configurables; cada quien usa los suyos).
- **Carpetas**: elige qué carpetas puede ver Claude Code (por defecto, el
  Inbox del puente + tu carpeta principal).
- **Skills**: lista las skills instaladas de Claude Code
  (`~/.claude/skills/`).
- **Pantalla**: compartir pantalla con fotogramas comprimidos, solo cuando
  tú lo activas.
- **Mascota**: tu asistente en la esquina inferior derecha; clic para
  saludar y escribirle un mensaje rápido.
- **Botón grande**: enciende/apaga puente + runner juntos, con animación.
- **Actualizaciones**: busca nuevas versiones aquí mismo en GitHub y se
  actualiza sola.

## Instalar

1. Python 3 con tkinter (el instalador oficial de python.org lo trae).
2. Doble clic a `instalar-growi-bridge.bat`. Instala `pystray` y `pillow`,
   copia todo a `C:\Users\<tu-usuario>\growi-bridge\` y crea el arranque
   automático al iniciar sesión (con privilegios máximos).
3. Abre la ventana desde el icono de la bandeja y configura el proxy si
   usas uno.

También puedes probarla en ventana visible con `probar-growi-bridge.bat`.

## Configuración local (no va a GitHub)

- `secret.txt`: secreto compartido del puente (lo genera el asistente).
- `proxy.json`: host, puerto, usuario y clave de tu proxy.
- `folders.json`: carpetas permitidas para Claude Code.
- `settings.json`: mascota activada o no.

## Seguridad

- El runner solo ejecuta `claude -p`, nunca shell directo con nada que
  venga de un task. Las tareas solo llegan por el puente (secreto
  compartido).
- Claude Code solo trabaja dentro de las carpetas permitidas.
- Todo queda registrado en `growi-bridge.log`.

## Licencia

Uso personal. Haz un fork y pon tus propios valores.
