# Growi Bridge

Un solo programa para Windows que conecta tu PC con tu asistente Muse: puente de archivos, corredor de tareas de Claude Code, biblioteca de modelos locales, proxy, pantalla compartida, mascota y paleta de comandos. Todo en una ventana, todo en la bandeja del sistema.

> Versión: **0.1.0-alpha**. Es una alpha: funciona, pero cambia rápido y algunas cosas todavía se pulen a mano.

![Growi Bridge](growi.png)

## Qué hace

- **Puente**: tu Muse manda archivos a tu PC (y recibe los que tu PC produce) por una carpeta compartida, sin nubes de por medio. El indicador de sincronización muestra qué se descarga o envía en cada momento.
- **Runner**: tu Muse le manda tareas a Claude Code en tu PC (sin ventana) y recibe el resultado. Una tarea a la vez, con modelo, herramientas y tiempo límite elegibles. Con sesiones continuas.
- **Modelos**: instala modelos open-source en local con Ollama (Hermes, Qwen, Llama, Mistral…) y conecta APIs (Anthropic, OpenAI, Gemini, Groq, OpenRouter). Tu Muse también puede instalar y gestionar modelos desde el chat.
- **Proxy**: un interruptor para que Claude Code salga por tu proxy (o por uno alquilado) sin tocar la VPN.
- **Pantalla**: comparte fotogramas de tu pantalla con tu Muse solo cuando tú lo activas.
- **Mascota**: Growi vive en tu escritorio. Arrastra un archivo sobre él y llega a tu Muse; haz clic y escríbele.
- **Paleta de comandos (Ctrl+K)**: escribe la acción y se ejecuta al instante, estilo Raycast.
- **Tareas**: historial de lo que Claude hizo, con su duración y su costo.
- **No suspender**: la PC no se duerme mientras Claude trabaja.
- **Atajo global (Ctrl+Alt+G)**: muestra u oculta la ventana desde cualquier parte.
- **Carpetas**: elige qué carpetas puede ver Claude Code (por defecto, el Inbox del puente + tu carpeta principal).
- **Skills**: lista las skills instaladas de Claude Code (`~/.claude/skills/`).
- **Botón grande**: enciende/apaga puente + runner juntos, con animación.
- **Actualizaciones**: busca nuevas versiones aquí mismo en GitHub y se actualiza sola.

## Requisitos

- Windows 10 u 11.
- Python 3.12 (python.org, marca la casilla "Add Python to PATH").
- Claude Code instalado y con sesión iniciada (tu suscripción Max o tu API key).
- Opcional: Ollama (para modelos locales), Tailscale (si tu Muse vive en otra máquina).

## Instalar

1. Descarga este repositorio (o clónalo con git).
2. Haz clic derecho en `instalar-growi-bridge.bat` → **Ejecutar como administrador**.
   - Instala las dependencias (`pystray`, `pillow`, `tkinterdnd2`, `keyboard`).
   - Copia todo a `C:\Users\<tu-usuario>\growi-bridge\`.
   - Crea la tarea programada `GrowiBridgeApp` para que arranque sola al iniciar sesión.
   - Arranca la app.
3. La primera vez, la app te pide lo que necesita: la carpeta de trabajo y, si usas proxy, sus datos.
4. Tu Muse se conecta al puente por el puerto 8787 con el secreto de `secret.txt` (se genera solo; no lo compartas). El puente solo acepta conexiones con ese secreto.

También puedes probarla en ventana visible con `probar-growi-bridge.bat`.

## Cómo trabaja tu Muse con la app

Tu Muse no toca tu PC directamente: te manda archivos y tareas por el puente.

- **Archivos**: lo que tu Muse te manda aparece en la carpeta de trabajo (`share\inbox`). Lo que tu PC produce vuelve por `share\outbox`.
- **Tareas**: tu Muse escribe un archivo `<id>.task.json` en `runner-tasks/` con el prompt, el modelo (`sonnet`, `opus`, `haiku`, `ollama:<modelo>` o `api:<proveedor>:<modelo>`), las herramientas permitidas y el tiempo límite. El runner lo recoge, corre Claude Code (u Ollama, o la API) y deja el resultado en `runner-results/<id>.result.json`. El archivo **tiene** que llamarse `*.task.json` o el runner lo ignora.
- **Modelos locales**: tu Muse puede pedirle al runner que instale, borre o liste modelos de Ollama con el campo `ollama_action` (`pull`, `rm`, `list`) en el task. La pestaña Modelos de la app usa las mismas acciones.
- **Carpetas permitidas**: Claude Code solo trabaja dentro de las carpetas que tú añadas en la pestaña Carpetas. Nada fuera de ahí sin tu permiso.

## El proxy y el VPS (opcional)

Claude Code necesita salir a internet. Si usas una VPN que rompe el túnel con tu Muse, la solución es un proxy: Claude Code manda su tráfico por `HTTPS_PROXY` a un servidor con IP dedicada, y la VPN se apaga para siempre.

Tienes dos vías:

### 1. Tu propio VPS (recomendado)

Un VPS barato sobra: para un tinyproxy basta 1 vCPU y 1 GB de RAM. Precios orientativos (oct 2026, revísalos antes de comprar):

| Proveedor | Plan de entrada | Precio/mes |
| --- | --- | --- |
| Vultr | Cloud Compute 1 GB | ~$5 |
| Hetzner | Cloud CX11/CX22 | ~€4,50 |
| Contabo | Cloud VPS S (2 vCPU / 4 GB) | ~$5 |
| DigitalOcean | Basic Droplet 1 GB | ~$5 |
| InterServer | 1 vCPU / 2 GB | ~$3 |
| Hostinger | KVM 1 (1 vCPU / 4 GB) | ~$6,49 (renueva ~$12) |

En el VPS instalas tinyproxy con autenticación y pones sus datos en la pestaña Proxy de la app. La clave viaja sin cifrar hasta el VPS; el contenido de Claude va cifrado con TLS. Es una credencial de bajo valor: rotable en un minuto.

### 2. Alquilar el acceso al proxy ($2,50/mes, opcional)

Si no quieres comprar ni mantener un VPS, puedes alquilar el acceso al proxy de Growi Bridge por **$2,50 al mes**. Cada usuario tiene su propio usuario y clave, y el acceso se puede revocar en cualquier momento. Es opcional: sin proxy la app funciona igual, solo que Claude Code necesita su propia salida a internet.

Para contratarlo, escribe a quien te pasó esta app.

## Configuración local (no va a GitHub)

- `secret.txt`: secreto compartido del puente (lo genera el asistente).
- `proxy.json`: host, puerto, usuario y clave de tu proxy.
- `folders.json`: carpetas permitidas para Claude Code.
- `settings.json`: mascota, no suspender, actualización automática y demás ajustes.
- `apis.json`: claves de API (solo en tu PC, enmascaradas en la ventana).

## Seguridad

- El secreto del puente (`secret.txt`) vive solo en tu PC. Sin él, nadie se conecta.
- Las claves de API se guardan solo en tu PC (`apis.json`), enmascaradas en la ventana y nunca en el registro.
- El runner solo ejecuta `claude -p`, `ollama` y llamadas a APIs con tus claves. Nunca ejecuta shell directo con lo que llega en un task.
- Claude Code solo trabaja dentro de tus carpetas permitidas. Borrar algo fuera de ellas requiere tu autorización cada vez.
- Todo queda registrado en `growi-bridge.log`.

## Licencia

Uso personal. Si la mejoras, comparte la mejora: el repo es público para eso.
