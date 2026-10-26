# Growi Bridge

Un solo programa para Windows que conecta tu PC con tu asistente Muse: puente de archivos, corredor de tareas de Claude Code, biblioteca de modelos locales, proxy, pantalla compartida, mascota y paleta de comandos. Todo en una ventana y en la bandeja del sistema.

Es una fusión de Ollama y OpenClaw sin tecnicismos: Ollama pone los modelos que viven en tu PC y OpenClaw pone la forma de trabajar del agente (usa herramientas, tiene habilidades y te habla por varios canales). Tú solo ves interruptores, nombres normales y frases simples.

> Versión: **0.1.0-alpha**. Es una alpha: funciona, pero cambia rápido y algunas cosas todavía se pulen a mano.

![Growi Bridge](growi.png)

## Qué hace

- **Puente**: tu Muse manda archivos a tu PC (y recibe los que tu PC produce) por una carpeta compartida, sin nubes de por medio. El indicador de sincronización muestra qué se descarga o envía en cada momento.
- **Runner**: tu Muse le manda tareas a Claude Code en tu PC (sin ventana) y recibe el resultado. Una tarea a la vez, con modelo, herramientas y tiempo límite elegibles. Con sesiones continuas.
- **Modelos**: instala modelos gratis en tu PC con Ollama (Hermes, Qwen, Llama, Mistral, Gemma, DeepSeek, Phi…) y conecta APIs (Anthropic, OpenAI, Gemini, Groq, OpenRouter). El botón **Comprobar mi PC** detecta tu tarjeta de video, memoria y disco, y cada modelo lleva un semáforo: verde si cabe holgado, naranja si va justo, rojo si no cabe (y entonces no se ofrece instalarlo). Tu Muse también puede instalar, borrar y listar modelos desde el chat.
- **Cómo trabaja tu asistente** (dentro de Modelos): quién responde (Claude, un modelo de tu PC o una API), qué puede hacer (habilidades con interruptor), dónde te habla (canales) y tus reglas (frases simples que el agente cumple siempre, como «Pregúntame antes de gastar dinero»).
- **Proxy**: un interruptor para que Claude Code salga por tu proxy (o por uno alquilado) sin tocar la VPN.
- **Pantalla**: comparte fotogramas de tu pantalla con tu Muse solo cuando tú lo activas.
- **Mascota**: vive en tu escritorio. Arrastra un archivo sobre ella y llega a tu Muse; haz clic y escríbele.
- **Paleta de comandos (Ctrl+K)**: escribe la acción y se ejecuta al instante.
- **Tareas**: historial de lo que se hizo, con su duración y su costo, y una cajita para pedir algo eligiendo quién responde.
- **Recursos (Ctrl+0)**: cuánta CPU, RAM, GPU (VRAM por `nvidia-smi`) y disco se usa, y qué proceso lo usa. Primero salen los de Growi (la app, lo que lanzó el runner, claude, ollama, llama-server, codex, meshy, browser-server); la lista completa del sistema es opcional. Puedes cerrar un proceso (siempre con confirmación); los procesos críticos de Windows (explorer, svchost, csrss…) no se pueden cerrar desde la app.
- **No suspender**: la PC no se duerme mientras Claude trabaja.
- **Atajo global (Ctrl+Alt+G)**: muestra u oculta la ventana desde cualquier parte.
- **Carpetas**: eliges qué carpetas puede ver Claude Code (por defecto, el Inbox del puente y tu carpeta de usuario).
- **Actualizaciones**: busca versiones nuevas en GitHub y se actualiza sola (si lo activas).

## Requisitos

- Windows 10 u 11.
- Python 3.12 (python.org; marca la casilla «Add Python to PATH» y deja Tcl/Tk marcado).
- Claude Code instalado y con sesión iniciada con **tu** suscripción (o tu clave). El runner solo necesita que el comando `claude` funcione en una terminal.
- Opcional: [Ollama](https://ollama.com) (gratis) para los modelos de tu PC. Sin Ollama la app funciona igual; solo la parte de modelos locales queda vacía.
- Opcional: [Tailscale](https://tailscale.com) si tu Muse vive en otra máquina y quieres llegar a tu PC sin abrir puertos.

## Instalar

1. Descarga este repositorio (botón Code → Download ZIP) y descomprímelo, o clónalo con git.
2. Doble clic en `instalar-growi-bridge.bat` (pide permisos de administrador; acéptalos).
   - Instala las dependencias (`pystray`, `pillow`, `tkinterdnd2`, `keyboard`).
   - Copia la app a `%USERPROFILE%\growi-bridge\` (tu carpeta de usuario).
   - Crea la tarea programada `GrowiBridgeApp` para que arranque sola al iniciar sesión.
   - Arranca la app: busca la foto en la bandeja del sistema (abajo a la derecha).
3. Si no existe `secret.txt`, la app crea uno al arrancar. Ese es el secreto que tu Muse necesita para conectarse al puente: pásaselo por un canal privado y no lo publiques.
4. Opcional: en **Estado → Proxy** pon los datos de tu proxy (ver más abajo). En **Modelos**, pulsa **Comprobar mi PC** y elige qué modelos instalar.
5. Opcional: en `settings.json` puedes poner `"user_name": "TuNombre"` para que las reglas lleguen como «Reglas de TuNombre».

Para probarla en una ventana visible (ves lo que hace): `probar-growi-bridge.bat`. Para quitarla: `schtasks /delete /tn GrowiBridgeApp /f` y borra la carpeta.

## Cómo se conecta tu Muse

Tu Muse no toca tu PC directamente: te manda archivos y tareas por el puente. Nada de esto depende de un asistente en concreto; cualquier asistente que sepa hablar con el puente sirve.

- **El puente** escucha en el puerto **8787**. Cada petición lleva la cabecera `X-Shared-Secret` con el contenido de `secret.txt`. Rutas: `GET /ping`, `GET /list?box=inbox|outbox`, `GET /get?box=…&name=…`, `POST /put?box=…&name=…`. Lo que tu Muse sube va a `share\inbox`; lo que tu PC produce sale por `share\outbox`.
- **El runner** vigila `share\inbox\runner-tasks\`. Tu Muse sube un archivo `<id>.task.json` (tiene que terminar en `.task.json` o se ignora) y el resultado aparece en `share\outbox\runner-results\<id>.result.json`. Ejemplo:

  ```json
  {"id": "t-20261025-01", "prompt": "Resume el archivo notas.txt",
   "model": "sonnet", "allowed_tools": "Read,Write",
   "permission_mode": "acceptEdits", "timeout_min": 30}
  ```

  `model` puede ser `sonnet`, `opus`, `haiku`, `ollama:<modelo>` (o `ollama:` para el modelo de tu PC elegido en Modelos) o `api:<proveedor>:<modelo>` (por ejemplo `api:openai:gpt-4o-mini`, `api:groq:llama-3.1-8b-instant`; proveedores: `anthropic`, `openai`, `gemini`, `groq`, `openrouter`). Para las APIs hace falta la clave guardada en la pestaña APIs.
- **Motores (`engines.json`)**: un corredor, muchos motores. El campo `motor` elige cuál corre la tarea (por defecto `claude`, como siempre): `claude` (Claude Code, tu sesión), `llama` (llama-server de llama.cpp con Hermes 3 en tu GPU, $0; si el puerto 8080 no responde, el runner lo arranca solo), `ollama` (la API de Ollama, $0), `codex` (si está instalado) y `meshy` (3D: crea, espera y descarga el `.glb`; gasta créditos, así que siempre pide aprobación). `engines.json` dice cómo se lanza cada uno, cómo se le pasa el modelo, cómo se reanuda la sesión y cómo se lee el resultado; el resultado es el mismo para todos. Ningún motor usa `bypassPermissions` ni `--yolo` por defecto: los permisos los pide cada tarea. Si el motor no existe o no está disponible, la tarea falla con el motivo.
- **Orquestación (bucle cerrado)**: al terminar, cada tarea se revisa sola con un motor barato (llama si responde, si no Ollama, si no Claude Haiku) y la revisión queda en `runner-results\<id>.revision.json` (`aprobado`, `que_falta`, `evidencia`). Campos nuevos del task, todos opcionales:

  ```json
  {"id": "t-02", "motor": "claude", "prompt": "Crea informe.md con el resumen de notas.txt",
   "criterios": ["el archivo informe.md existe y tiene más de 20 líneas",
                 "los marcadores \"Resumen\" y \"Pendientes\" están presentes"],
   "fase": "fase 1 de 2", "siguiente_fase": "Ahora tradúcelo al inglés en informe-en.md"}
  ```

  Lo que se puede comprobar en los archivos (que existe, cuántas líneas tiene, marcadores entre comillas) se comprueba de verdad; lo demás lo juzga la revisión. Sin `criterios`, solo se comprueba que el resultado no esté vacío ni traiga error. Si no aprueba, el runner crea una ronda de corrección (`ronda` 1, 2 o 3, `tarea_padre` = la original, mismo `session_id` y motor, y un prompt que es solo la lista de lo que falta). Tras 3 rondas sin aprobar queda en «necesita decisión» con un reporte honesto. Si se aprueba y trae `siguiente_fase`, se encola la fase siguiente con un resumen de lo hecho. El estado de cada tarea está en `runner-results\<id>.orquestacion.json`.
- **Aprobación en lo sensible**: si una tarea pide borrar, publicar, gastar o enviar algo, queda «esperando aprobación» (en `runner-tasks\esperando\`) hasta que la apruebes en la pestaña Tareas; nadie más la puede aprobar (ni tu Muse ni otra tarea). El nivel está en Ajustes → Permisos (`guardrail` en `settings.json`): «Preguntarme siempre» (por defecto), «Preguntarme solo lo delicado» o «Hazlo sin preguntar» (pide doble confirmación).
- **Modelos desde el chat**: tu Muse puede instalar, borrar y listar modelos sin tocar la ventana:

  ```json
  {"id": "m-01", "ollama_action": "pull", "model": "qwen2.5:7b", "timeout_min": 60}
  {"id": "m-02", "ollama_action": "rm",   "model": "qwen2.5:7b"}
  {"id": "m-03", "ollama_action": "list"}
  ```

  El nombre del modelo solo puede tener letras, números, `-`, `_`, `.`, `/` y `:`; cualquier otra cosa se rechaza. Solo se instala desde el registro de Ollama con `ollama pull`, nunca desde una URL. Estas acciones van por su propio carril (no esperan detrás de una tarea larga de Claude) y su progreso se ve en `runner-results\<id>.progress.json`. La pestaña Modelos usa exactamente las mismas acciones.
- **Carpetas permitidas**: Claude Code solo trabaja dentro de las carpetas de la pestaña Carpetas.
- **Reglas y habilidades**: lo que actives en Modelos (reglas en `rules.json`, habilidades apagadas en `settings.json`) se aplica a todas las tareas, vengan de la ventana o de tu Muse.

## El proxy y el VPS (opcional)

**El proxy es opcional.** Sin él la app funciona igual; solo que Claude Code necesita su propia salida a internet. Hace falta cuando usas una VPN que rompe el túnel con tu Muse: en vez de la VPN, Claude Code manda su tráfico por `HTTPS_PROXY` a un servidor con IP fija y la VPN se queda apagada.

Tienes dos vías:

### 1. Tu propio VPS

Un VPS barato sobra: para un tinyproxy basta **1 vCPU y 1 GB de RAM**. Precios orientativos (octubre 2026; revísalos antes de comprar):

| Proveedor | Plan de entrada | Precio/mes |
| --- | --- | --- |
| Vultr | Cloud Compute 1 GB | ~$5 |
| Hetzner | Cloud CX22 | ~€4,50 |
| Contabo | Cloud VPS S | ~$5 |
| DigitalOcean | Basic Droplet 1 GB | ~$5 |

Si el repositorio trae un script de instalación de tinyproxy, úsalo. Si no, en un VPS con Ubuntu son cinco minutos:

```bash
sudo apt update && sudo apt install -y tinyproxy
sudo nano /etc/tinyproxy/tinyproxy.conf
#   Port 18080
#   BasicAuth TU_USUARIO TU_CLAVE_LARGA
#   comenta las líneas "Allow 127.0.0.1" para aceptar conexiones de fuera
sudo systemctl restart tinyproxy
sudo ufw allow 18080/tcp
```

Después pon en la app (Estado → Proxy) la IP del VPS, el puerto, el usuario y la clave, pulsa Guardar y enciende el interruptor del proxy. La clave del proxy viaja sin cifrar hasta el VPS (el contenido de Claude sí va cifrado): usa una clave larga que no uses en otro sitio y cámbiala si sospechas algo.

### 2. Alquilar el acceso al proxy de Growi Bridge ($2,50/mes, opcional)

Si no quieres comprar ni mantener un VPS, puedes alquilar el acceso al proxy de Growi Bridge por **$2,50 al mes**. Cada usuario tiene su propio usuario y clave, y el acceso se puede revocar en cualquier momento. Para contratarlo, escribe a quien te pasó esta app.

## Archivos locales (no se suben a GitHub)

- `secret.txt`: secreto del puente.
- `proxy.json`: host, puerto, usuario y clave de tu proxy.
- `folders.json`: carpetas permitidas para Claude Code.
- `settings.json`: mascota, no suspender, nivel de permisos (`guardrail`), actualización automática, modelo local por defecto (`ollama_model`), quién responde (`default_engine`), tu nombre para las reglas (`user_name`), habilidades apagadas y demás ajustes.
- `apis.json`: claves de API (solo en tu PC; enmascaradas en la ventana y nunca en el registro).
- `rules.json`: tus reglas.
- `sesiones/`: el historial de las conversaciones con los motores locales (llama, Ollama), para que las rondas de corrección continúen la misma conversación.
- `pc-specs.json`: lo que detectó «Comprobar mi PC».
- `growi-bridge.log`: el registro.

El `.gitignore` del repositorio ya los deja fuera. `engines.json` y `models-catalog.json` sí van en el repositorio (`engines.json` es la lista de motores y se amplía sin tocar el código). `models-catalog.json`: es la librería de modelos y se amplía añadiendo entradas (nombre exacto de Ollama, tamaño en disco, VRAM necesaria y una línea de para qué sirve), sin tocar el código.

## Seguridad

- El secreto del puente vive solo en tu PC. Sin él, nadie se conecta.
- Las claves de API se guardan solo en tu PC, enmascaradas en la ventana y nunca en el registro. El botón Probar hace una consulta gratis (listar modelos), no gasta.
- El runner solo ejecuta los motores de `engines.json` (`claude -p`, `codex exec`, `llama-server`), `ollama pull|rm|list` y llamadas HTTP (Ollama y llama-server en 127.0.0.1, siempre sin proxy; las APIs con tus claves). Nunca ejecuta una orden de shell con lo que llega en un task: el prompt va como argumento o por la entrada estándar, nunca por `cmd.exe`.
- Antes de borrar, publicar, gastar o enviar algo, la tarea espera tu aprobación (Ajustes → Permisos).
- Ningún resultado dice que algo funcionó si no está comprobado contra archivos reales: si no se pudo confirmar, el reporte dice «Lo intenté pero no pude confirmar que funcionara».
- Claude Code solo trabaja dentro de tus carpetas permitidas. Borrar algo fuera de ellas requiere tu autorización cada vez.
- Todo queda registrado en `growi-bridge.log`.

## Licencia

Uso personal. Si la mejoras, comparte la mejora: el repo es público para eso.
