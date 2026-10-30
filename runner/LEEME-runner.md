# Growi Runner — el webhook de Claude Code en tu PC

Un programita que vigila una carpeta y corre Claude Code sin ventana con los
prompts que Growi le manda por el puente. Growi dispara, Claude trabaja, el
resultado vuelve solo.

## El flujo (webhook por archivos)

1. Growi sube `<id>.task.json` a `share\inbox\runner-tasks\` con un `put`
   directo del puente. **Ese `put` ES el disparo**: llega en segundos.
2. El runner lo detecta (sondea cada 5 s) y corre, sin ventana:
   `claude -p "<prompt>" --output-format json` en la carpeta indicada.
   "Sin ventana" de verdad: se lanza con `CREATE_NO_WINDOW (0x08000000)` +
   `STARTUPINFO SW_HIDE`, así que ninguna consola negra aparece ni parpadea
   (`runner.log` dice «claude lanzado oculto» en cada lanzamiento). Si el
   lanzamiento falla, el error va al resultado; nunca se reintenta visible.
3. Escribe `<id>.result.json` en `share\outbox\runner-results\` y el puente
   lo devuelve a la VM en el siguiente sync (máx 2 min).

No se abrió ningún puerto nuevo ni se expuso nada a internet: todo pasa por
el puente, que ya exige el secreto compartido.

## Arrancar

- **Probar (ventana visible):** doble clic a `iniciar-runner.bat`. Se ve lo
  que hace en vivo; se para con Ctrl+C.
- **Arranque automático al iniciar sesión:** doble clic a
  `instalar-runner.bat` (crea la tarea programada `GrowiRunner` y la arranca
  en el momento). Para quitarla: `schtasks /delete /tn GrowiRunner /f`.

El runner escribe `runner.log` en esta misma carpeta y un
`runner-status.json` en el outbox (para que Growi vea si está vivo).

## Qué puede y qué no puede

- Solo ejecuta `claude -p ...`. Un task con otro motor (`"motor": "codex"`,
  `"model": "motor:gemini"`...) se rechaza con «lo corre el runner de la app»: los
  demás motores los corre Growi Bridge con `engines.json` (t-motor-generico-052).
  **Nunca** ejecuta shell directo con nada
  del task. Claude Code hace su trabajo con sus propias herramientas, como
  cuando lo corres tú en la terminal.
- La carpeta de trabajo (`cwd`) tiene que existir y estar dentro de
  `share\inbox`. Fuera de ahí, la tarea se rechaza y queda registrado.
- Una tarea a la vez, con timeout (por defecto 30 min, máx 120).
- Las tareas solo llegan por el puente (secreto compartido). Si el secreto
  se filtra, alguien podría mandar tareas: mismo nivel de confianza que el
  puente que ya existe.

## Formato del task (`<id>.task.json`)

```json
{
  "id": "t-20261024-prueba",
  "prompt": "Escribe el archivo prueba.txt en esta carpeta con el texto 'ok'",
  "cwd": "C:\\Users\\forte\\growi-bridge\\share\\inbox\\runner-tasks",
  "model": "sonnet",
  "timeout_min": 30
}
```

- `id`: obligatorio, solo letras, números, `- _ .`
- `prompt`: obligatorio, el prompt para Claude Code.
- `cwd`: opcional (por defecto el inbox). Debe estar dentro de `share\inbox`.
- `model`: opcional (`sonnet`, `opus`, `haiku` o `claude-...`).
- `timeout_min`: opcional (1–120, por defecto 30).
- `allowed_tools`: opcional, se pasa como `--allowedTools` si Claude pide
  permisos y se los niegan (ej. `"Read,Write,Edit,Bash"`).
- `permission_mode`: opcional (`acceptEdits`, `plan`, `default`).
- `session_id`: opcional (v1.1), id de una sesión anterior; la tarea continúa
  esa conversación en vez de empezar de cero (ver "Sesiones continuas").

## Sesiones continuas (v1.1)

Cada resultado trae un `session_id`. Si la siguiente tarea incluye ese
`session_id`, el runner corre `claude -p --resume <id>`: Claude retoma la
conversación anterior con su contexto (archivos leídos, decisiones, etc.).
Así se encadenan tareas como en una sesión interactiva, sin que Leandro
tenga que pegar nada. Si la sesión ya no existe, Claude lo reporta como
error en el resultado y la tarea se manda de nuevo sin `session_id`.

## Formato del resultado (`<id>.result.json`)

```json
{
  "id": "t-20261024-prueba",
  "status": "ok",
  "started_at": "...",
  "finished_at": "...",
  "duration_s": 42.3,
  "exit_code": 0,
  "result": "texto de respuesta de Claude",
  "cost_usd": 0.12,
  "num_turns": 3,
  "session_id": "uuid-de-la-sesion",
  "stderr": "",
  "error": null
}
```

`status` puede ser `ok`, `error` o `timeout`. Si `claude` no está en el
PATH, la tarea falla con error y queda registrado, no se queda colgada.

## Si algo falla

1. Mira `runner.log` en esta carpeta.
2. Revisa que `claude` funcione en una terminal normal (`claude --version`).
3. Recuerda: el runner hereda las variables del usuario, incluido
   `HTTPS_PROXY` (sale por el proxy del VPS, sin Avast).
4. Si Claude pide permisos y se los niegan en modo headless, Growi manda
   la tarea con `allowed_tools` o se configuran los permisos del proyecto.

## Consumo en vivo (v1.2)

- Claude se lanza con `--output-format stream-json --verbose
  --include-partial-messages` y un hilo lee cada mensaje según llega. El
  resultado final es **el mismo de siempre** (mismos campos; el costo es el
  `total_cost_usd` que da Claude al terminar).
- Mientras corre se escribe `share\outbox\runner-live.json` cada ~5 s
  (tarea, modelo, tiempo, tokens de entrada / salida, costo estimado a
  precio de lista y, al terminar, el costo final real).
- Si `claude` no entiende stream-json, se repite con `--output-format json`
  como antes y el vivo dice «sin vivo».
- `runner-status.json` sigue latiendo cada 60 s aunque haya una tarea
  corriendo, y `current` trae `{id, motor, modelo}`. Un `last_poll` viejo ya
  no significa «Claude trabajando»: significa problema.
- Nota: Growi Bridge (la app) ya trae su propio runner; este programa
  suelto es el de antes y no debe correr a la vez que la app.
