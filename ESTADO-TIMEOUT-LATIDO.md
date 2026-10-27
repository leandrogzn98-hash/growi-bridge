# Estado: timeout de inactividad y latido con actividad

Rama `Claude`, 27 oct 2026. Origen: un spec se quedó 70 min en «lanzando» sin
que Claude produjera nada ($0 gastado): no había límite de inactividad ni forma
de ver si el motor trabajaba o estaba colgado.

## Qué se hizo

### 1. Runner con progreso (`runner/runner.py`)
- `run_task()` ya no usa `subprocess.run` bloqueante en ningún camino:
  - `_run_stream` (stream-json, el normal) y `_run_plain` (json, el respaldo
    para un claude sin stream-json) lanzan con `subprocess.Popen`, con
    stdout y stderr en `PIPE`, y cada uno tiene **dos hilos lectores**:
    stdout y stderr.
  - Cada línea que llega (de stdout o de stderr) llama a `touch()`, que guarda
    el `last_activity`.
- El parseo no cambió: `result`, `total_cost_usd → cost_usd`, `num_turns`,
  `session_id`, `is_error` y `exit_code` salen de `_fill_from_final()`, igual
  que antes.

### 2. Timeout de inactividad de 5 min (runner)
- Constantes arriba en `runner.py`:
  - `NO_PROGRESS_TIMEOUT_S = 300`
  - `NO_PROGRESS_TXT = "lanzamiento sin progreso en 5 min"`
- `no_progress_s()` permite acortar el umbral **solo** con la variable de
  entorno `GROWI_NO_PROGRESS_S`; sin ella valen los 300 s.
- `_wait_watch()` espera al proceso con dos límites:
  - **inactividad**: `no_progress_s()` sin ninguna línea;
  - **total**: `timeout_min`, que no cambia (30 por defecto, máximo 120).
- Si se pasa la inactividad, `_kill_tree()` mata el intento entero:
  - con psutil, primero los hijos (recursivo) y después el padre, más
    `wait_procs`;
  - sin psutil, `taskkill /PID <pid> /T /F`.
- El resultado de ese intento queda así:
  - `status = "error"`;
  - `error = "lanzamiento sin progreso en 5 min"`, el texto exacto, también
    en el log;
  - `duration_s` es el tiempo real;
  - `cost_usd = null`.
- El `.result.json` se escribe igual y el task se archiva en `done/`.
- Un intento matado por inactividad **no** se repite con `--output-format json`
  (se colgaría otros 5 min).
- El timeout total ahora también mata el árbol completo. Antes solo hacía
  `proc.kill()` del padre, y quedaban hijos `node`.

### 3. Lo mismo en el gateway (`growi-bridge.py`)
- Constantes junto a `MAX_TIMEOUT_MIN`: `NO_PROGRESS_TIMEOUT_S = 300` y
  `NO_PROGRESS_TXT`, más `no_progress_s()` con la misma variable de entorno.
- `_ACT` / `_act_touch()` guardan la última actividad de la tarea en curso:
  - se marca al empezar la tarea y al lanzar el motor;
  - y luego en **cada evento stream-json** que lee el hilo lector de
    `_run_cli_stream()`.
- `_run_cli_stream()` vigila igual: si pasan 300 s sin eventos:
  - `_kill_tree(proc)`;
  - `error = "lanzamiento sin progreso en 5 min"`;
  - `error_tipo = "definitivo"`, para que `_es_transitorio()` diga que no y
    **no se reintente en bucle**.
  - Tampoco se repite «sin vivo».
- Con eso el checkpoint pasa de `lanzando` a `fallida`
  (`siguiente_paso = terminada`), y la cola a `fallida`.
- `_kill_tree()` del gateway: con psutil, hijos primero y después el padre; sin
  psutil, `taskkill /T /F` como antes. Lo usa también el botón Parar.
- **Motor de revisión**: la revisión corre por `_run_cli_engine(...,
  rol="revision")` → `_run_cli_stream()`, así que tiene el mismo límite sin
  código aparte.
- **`_run_http_engine` en streaming** (llama-server/Ollama):
  - el socket usa `min(timeout_total, 300)` como espera máxima sin recibir
    nada;
  - cada línea recibida marca actividad;
  - al vencer da el error exacto, con `error_tipo = "definitivo"`.

### 4. Latido con actividad
- **Runner** (`runner-status.json`):
  - mientras corre, `"current"` es
    `{"id", "motor", "modelo", "started_at", "last_activity", "idle_s"}`;
    se mantienen los campos que ya había (`id`, `motor`, `modelo`) y se
    añaden los otros tres;
  - al terminar vuelve a `null`;
  - el latido sigue cada 60 s (`HEARTBEAT_SECONDS = 60`, sin cambios).
- **Gateway**:
  - el `current` de `runner-status.json` añade `started_at`,
    `last_activity` e `idle_s` a lo que ya tenía;
  - el vivo (`runner-live.json`, cada ~5 s) añade `ultima_actividad` e
    `idle_s`;
  - en la ventana, la línea «En vivo» añade «Última actividad del motor hace
    m:ss» cuando el motor lleva 30 s o más callado.

### 5. Lo que no se rompió
- `DEFAULT_TIMEOUT_MIN` sigue en 30 y `MAX_TIMEOUT_MIN` en 120: el timeout total
  por spec no cambió y sigue cortando con `status = "timeout"`.
- Se corta solo por **inactividad**: un spec que produce salida y tarda más de
  5 min no se corta (prueba c).
- El formato de `.result.json` no cambió. En el gateway se añade
  `error_tipo`, que ya existía para otros errores.
- No se tocaron el carril B, `VERSION`, el secreto ni la revisión por
  criterios.

## Evidencia de las pruebas

Todo se probó con `pruebas/prueba_timeout_latido.py`, que corre el runner y el
gateway **de este repo** contra un claude falso (`pruebas/fake_claude.py`) en
una carpeta temporal propia (`%TEMP%\growi-prueba-*`). No toca `share/`,
`cola.db` ni ningún carril instalado.
- El claude falso «colgado» no escribe nada y lanza un hijo python que también
  duerme, para comprobar que se mata el árbol completo.
- El «lento» emite un evento stream-json cada 2 s y termina con el mensaje
  final.
- Los JSON completos están en `pruebas/evidencia/`.

### (a) Colgado → muere solo con el error exacto
**Runner, `GROWI_NO_PROGRESS_S=20`** (`runner-colgado-20s.json`):
```
16:45:36 [prueba-runner-colgado] claude lanzado oculto (...), pid 10408
16:45:56 [prueba-runner-colgado] lanzamiento sin progreso en 5 min: 20 s sin una linea de salida (limite 20 s); se mato el arbol de procesos del pid 10408
16:45:56 [prueba-runner-colgado] terminado: status=error duracion=20.2s costo=None error=lanzamiento sin progreso en 5 min
```
`.result.json`: `"status": "error"`, `"error": "lanzamiento sin progreso en 5 min"`,
`"duration_s": 20.2`, `"cost_usd": null`. El task quedó en `done/`.

**Runner, valor real de 300 s** (sin la variable; `runner-colgado-300s.json`):
```
16:50:38 [prueba-runner-colgado] claude lanzado oculto (...), pid 15044
16:55:38 [prueba-runner-colgado] lanzamiento sin progreso en 5 min: 301 s sin una linea de salida (limite 300 s); se mato el arbol de procesos del pid 15044
16:55:38 [prueba-runner-colgado] terminado: status=error duracion=300.8s costo=None error=lanzamiento sin progreso en 5 min
```

### (b) Latido durante el colgado (runner, 300 s reales, latido real de 60 s)
| t (s) | last_poll | current |
|---|---|---|
| 3 | 16:50:33 | `null` (libre) |
| 6 | 16:50:38 | `id=prueba-runner-colgado, started_at=16:50:38, last_activity=16:50:38, idle_s=0` |
| 68 | 16:51:38 | `last_activity=16:50:38, idle_s=60` |
| 127 | 16:52:38 | `last_activity=16:50:38, idle_s=120` |
| 188 | 16:53:38 | `last_activity=16:50:38, idle_s=180` |
| 247 | 16:54:38 | `last_activity=16:50:38, idle_s=240` |
| 306 | 16:55:38 | `null` (terminó) |

`idle_s` crece de 60 en 60, `last_activity` se queda quieto, y al terminar
`current` vuelve a `null`. Con el umbral de 20 s solo da tiempo a un latido
(`idle_s=0`) antes de morir. Por eso la prueba de (b) se hizo con los 300 s
reales: el latido sigue en 60 s y no se acortó para la prueba.

### (c) Un task con salida continua no se corta
`GROWI_NO_PROGRESS_S=20` y un claude falso que emite un evento cada 2 s durante
45 s (`runner-lento-20s.json`):
`status=ok`, `duration_s=46.1` (más del doble del umbral), `result="hecho tras
23 eventos"`, `cost_usd=0`, `num_turns=1`, `session_id=fake-sesion`, `exit_code=0`.

### (d) Gateway: el checkpoint no se queda en «lanzando»
Camino real `_process_one_impl()` (cola → checkpoint → motor `claude` de
`engines.json` → resultado). Solo se cambiaron dos cosas:
- el binario, por el claude falso colgado;
- la aprobación humana, que se anuló porque sin `riesgos.json` en la carpeta
  temporal todo sería R3 y la tarea quedaría aparcada.

Con `GROWI_NO_PROGRESS_S=20` (`gateway-colgado-20s.json`):
```
16:49:43 runner [prueba-gw-colgado]: claude lanzado oculto (...), pid ...
16:50:03 runner [prueba-gw-colgado]: lanzamiento sin progreso en 5 min: claude lleva 20 s sin un evento (límite 20 s); se mató el árbol de procesos del pid ...
16:50:03 runner [prueba-gw-colgado]: fallida: Lo intenté pero no pude confirmar que funcionara. lanzamiento sin progreso en 5 min.
```
- **resultado**: `status=error`, `error="lanzamiento sin progreso en 5 min"`,
  `error_tipo=definitivo`, `duration_s=20.2`, `cost_usd=null`,
  `estado=fallida`, `reintentos=0`;
- **checkpoint**: `estado=fallida`, `paso=motor`, `siguiente_paso=terminada`.
  Historial: `lanzando → fallida (resultado del motor: error) → fallida`;
- **cola**: `estado=fallida`, `motivo="lanzamiento sin progreso en 5 min"`,
  `reintentos=0`; `_es_transitorio(result) = False`;
- **vivo** (`runner-live.json`): `ultima_actividad` se queda en la hora del
  lanzamiento y `idle_s` sube 5 → 10 → 15 → 20 hasta que muere.

**Gateway, valor real de 300 s** (`gateway-colgado-300s.json`):
```
17:01:17 runner [prueba-gw-colgado]: lanzamiento sin progreso en 5 min: claude lleva 301 s sin un evento (límite 300 s); se mató el árbol de procesos del pid 17276
17:01:17 runner [prueba-gw-colgado]: terminado: error duracion=300.8s costo=None
17:01:17 runner [prueba-gw-colgado]: fallida: Lo intenté pero no pude confirmar que funcionara. lanzamiento sin progreso en 5 min.
```
Igual que con 20 s: `error_tipo=definitivo`, checkpoint `fallida` (`siguiente_paso=terminada`),
cola `fallida`, `reintentos=0`, `_es_transitorio = False`. Latido del gateway (real, cada 60 s):

| last_poll | current |
|---|---|
| 16:56:10 | `started_at=16:56:10, last_activity=16:56:10, idle_s=0` |
| 16:57:10 | `last_activity=16:56:16, idle_s=54` |
| 16:58:11 | `last_activity=16:56:16, idle_s=114` |
| 16:59:11 | `last_activity=16:56:16, idle_s=175` |
| 17:00:11 | `last_activity=16:56:16, idle_s=235` |
| 17:01:12 | `last_activity=16:56:16, idle_s=296` |
| 17:01:17 | `null` (terminó) |

(16:56:10 es el inicio de la tarea; 16:56:16 es el lanzamiento del motor, tras preparar
memoria y checkpoint: desde ahí no hubo ni un evento.)

**HTTP en streaming** (`_http_local_stream`, `gateway-http-colgado-10s.json`):
contra un servidor local que acepta la conexión y no manda nada, con
`timeout_total=1800` y `GROWI_NO_PROGRESS_S=10`, se cortó a los 10,0 s con
`LocalCallError("lanzamiento sin progreso en 5 min")`.

### (e) Sin huérfanos
En todas las pruebas de colgado el arnés vio dos procesos durante la prueba:
- el claude falso;
- su hijo `python -c ... # growi-fake-hijo`.

Después de matar el intento, la búsqueda con psutil por esos marcadores da
**0 procesos vivos**. `tasklist /FI "IMAGENAME eq claude.exe"` da el mismo
número antes y después (2/2: son las sesiones de Claude Code que ya estaban
abiertas en el PC, no son de la prueba).
- **Lectores**: los hilos lectores terminan porque al morir el árbol se
  cierran los pipes (`join(15)`). Además son `daemon`, así que no frenan el
  proceso.

## Cómo repetir las pruebas
Desde la raíz del repo, en PowerShell (necesita Python 3 y psutil):
```powershell
$env:GROWI_NO_PROGRESS_S = '20'
python pruebas/prueba_timeout_latido.py runner-colgado     # (a), (e)
python pruebas/prueba_timeout_latido.py runner-lento 45    # (c)
python pruebas/prueba_timeout_latido.py gateway-colgado    # (d), (e)
$env:GROWI_NO_PROGRESS_S = '10'
python pruebas/prueba_timeout_latido.py gateway-http-colgado
$env:GROWI_NO_PROGRESS_S = $null                           # valor real: 300 s
python pruebas/prueba_timeout_latido.py runner-colgado     # (a) real y (b): ~5,5 min
python pruebas/prueba_timeout_latido.py gateway-colgado    # (d) real: ~5,5 min
```
- **Salida**: cada corrida imprime y guarda su JSON en
  `pruebas/evidencia/<modo>-<umbral>s.json`.
- **Comprobar huérfanos a mano**: después de la prueba, `tasklist | findstr
  python` no debe mostrar ningún `fake_claude.py`.

## Lo que NO se verificó o queda como riesgo
- **No se colgó un `claude` real**. Las pruebas usan un claude falso: provocar
  a propósito un cuelgue real de Claude Code no es reproducible. El mecanismo
  (Popen, lectores, vigilante, matar el árbol) es el mismo que corre con el
  binario real, que solo cambia en `_build_cmd`/`_build_cli_cmd`.
- **Herramientas largas y calladas**:
  - el límite es «sin ninguna línea». Si Claude corre una herramienta (p. ej.
    un `Bash` de más de 5 min) que no emite nada mientras tanto, stream-json
    tampoco emite eventos y el intento se cortaría;
  - con `--include-partial-messages` el texto del modelo emite eventos
    constantemente, así que el riesgo se limita a herramientas silenciosas
    de más de 5 min;
  - si pasa, se ve claro en el log y en el `.result.json`.
- **Runner `_run_plain`** (respaldo `--output-format json`):
  - claude escribe todo al final, así que en ese modo cualquier tarea de más
    de 5 min se cortaría;
  - es solo el respaldo para un claude que no entienda stream-json (el
    instalado sí lo entiende), y se dejó con el límite porque el pedido era
    que `run_task()` no tuviera un camino bloqueante sin vigilancia.
- **Gateway `_run_cli_plain`** (motores sin streaming, p. ej. codex sin vivo)
  y **`_run_http_engine` sin streaming** (`stream: false`):
  - **no** tienen el límite de inactividad: no emiten nada hasta terminar, y
    un corte a los 5 min mataría tareas largas legítimas;
  - siguen con el timeout total por spec.
- **HTTP en streaming**: el límite de 300 s también cubre la espera hasta el
  primer trozo. Un servidor local que tarde más de 5 min en cargar el modelo o
  en procesar el prompt antes del primer token se cortaría.
- **Pruebas con la app abierta**:
  - no se probó con la ventana de la app abierta ni en un carril instalado; el
    gateway se probó importando `growi-bridge.py` en una carpeta temporal y
    llamando a `_process_one_impl()`;
  - la línea «Última actividad del motor hace …» de la ventana no se vio en
    pantalla: se verificó solo que el vivo trae `ultima_actividad`/`idle_s`.
