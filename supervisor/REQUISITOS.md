# Qué necesitas para el supervisor local ("subgerente")

Esta lista cubre todo lo que hace falta para que el supervisor revise tu Growi Bridge y te avise por correo. Va en el
orden en que lo vas a necesitar.

## 1. Tu equipo

| | Windows | Linux | macOS |
|---|---|---|---|
| Sistema | Windows 10 o 11 | cualquiera con systemd de usuario o cron | macOS 12 o más nuevo |
| Python | 3.10 o más nuevo, de [python.org](https://www.python.org/downloads/windows/) (marca «Add python.exe to PATH») | 3.10 o más nuevo, con el paquete `python3-venv` (`sudo apt install python3-venv` en Debian/Ubuntu) | 3.10 o más nuevo, de [python.org](https://www.python.org/downloads/macos/) |
| Dónde guarda las claves | Administrador de credenciales de Windows | Secret Service (GNOME Keyring o KWallet) | Llavero (Keychain) |
| Cómo se programa | Programador de tareas | temporizador de systemd de usuario (o cron) | launchd |
| Probado en su sistema real | **sí** (0.4.6) | no todavía (previsto en la 0.4.7) | no todavía |

No hace falta ser administrador. El instalador crea un entorno de Python propio (la carpeta `.venv` junto al script)
con lo único que el supervisor usa además de Python: `keyring`, `pyyaml` y `requests`.

También necesitas **Growi Bridge instalado** en el mismo equipo (por defecto en `~/growi-bridge`; si está en otro
sitio, cambia `bridge.carpeta` y `bridge.share` en el YAML).

## 2. Una cuenta del modelo que va a juzgar (elige una)

| Proveedor | Dónde se consigue la clave | Nombre de la clave por defecto |
|---|---|---|
| DeepSeek (el de la instalación de referencia) | [platform.deepseek.com](https://platform.deepseek.com/api_keys); hay que cargar saldo | `DEEPSEEK_API_KEY` |
| OpenAI | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | `OPENAI_API_KEY` |
| Anthropic | [console.anthropic.com](https://console.anthropic.com/settings/keys) (cuenta de API, no la de Claude Code) | `ANTHROPIC_API_KEY` |
| Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | `GEMINI_API_KEY` |
| Ollama ($0, en tu equipo) | no hay clave: instala [Ollama](https://ollama.com/download) y descarga un modelo (`ollama pull hermes3:8b`) | — |

## 3. Una cuenta de Resend para los correos

1. Crea la cuenta en [resend.com](https://resend.com/signup).
2. Añade y **verifica tu dominio** en [resend.com/domains](https://resend.com/domains): Resend te da unos registros DNS
   que pones donde compraste el dominio. El correo «desde» del supervisor tiene que ser de ese dominio (por ejemplo
   `growi@tudominio.com`).
3. Crea una clave en [resend.com/api-keys](https://resend.com/api-keys). Para que `--verificar` pueda comprobar el
   dominio, la clave necesita permiso completo («Full access»); con una clave «Sending access» los correos salen igual,
   pero esa comprobación saldrá FAIL.
4. Su nombre por defecto es `RESEND_API_KEY`.

## 4. Dónde poner cada clave (nunca en el YAML)

Las claves van en **uno** de estos dos sitios. El YAML solo dice cuál:

- **Llavero del sistema** (recomendado): el asistente `--configurar` te la pide sin mostrarla y la guarda ahí, en la
  entrada `growi-supervisor` / `<nombre de la clave>`.
- **Variable de entorno**:
  - Windows: `setx DEEPSEEK_API_KEY "tu-clave"` (y abre una ventana nueva).
  - Linux / macOS: `export DEEPSEEK_API_KEY="tu-clave"` en `~/.profile` o `~/.zshrc`. Ojo: una tarea de cron o de
    launchd no lee tu perfil; ahí usa el llavero.

## 5. El orden del montaje

1. **Instala** con el script de tu sistema (crea el entorno de Python y la tarea programada):
   - Windows: `powershell -ExecutionPolicy Bypass -File supervisor\instalar-supervisor.ps1`
   - Linux: `sh supervisor/instalar-supervisor.sh`
   - macOS: `sh supervisor/instalar-supervisor-macos.sh`
2. **Configura**: `python supervisor.py --configurar`, con el Python de `.venv` (`supervisor\.venv\Scripts\python.exe` en
   Windows, `supervisor/.venv/bin/python` en Linux y macOS). Te pregunta, en este orden y con un valor por defecto:
   1. el proveedor del subgerente (de la lista de arriba);
   2. el modelo (propone el habitual de ese proveedor);
   3. dónde guardar la clave (llavero o variable de entorno) y, si eliges llavero, la clave, sin mostrarla;
   4. el correo que envía los avisos (de tu dominio verificado en Resend);
   5. el correo que los recibe;
   6. cada cuántos minutos revisar (60 por defecto).

   Si cambias el intervalo, vuelve a correr el instalador para que la tarea programada lo tome.
3. **Comprueba**: `python supervisor.py --verificar` dice OK o FAIL en cada punto (YAML, clave, proveedor, Resend,
   tarea programada) y por qué.
4. **Mira sin gastar**: `python supervisor.py --dry-run` enseña qué diría y qué correo mandaría, sin enviar nada ni
   llamar a ninguna API de pago.

Para quitarlo: el mismo instalador con `-Desinstalar` (Windows) o `--desinstalar` (Linux, macOS).
