# ESTADO t-motor-generico-052 (componente 1 de 5 de la 0.5.2: multimotor)

Rama `Claude`, 30 oct 2026. **LISTO en el repo y verificado en una instancia aislada con Codex y Gemini de verdad.**
**FALTA aplicarlo a la app instalada**: el parche está comprobado sobre una copia, pero no lo apliqué a la
app real ni la reinicié sin tu permiso.

Spec: `specs/opus-tasks-052/t-motor-generico-052.task.json`.
Prueba: `pruebas/prueba_motor_generico_052.py`.
Evidencia: `pruebas/evidencia/motor-generico-052/resultado.json` y `growi-bridge-aislada.log`.

## Lo que había (investigado antes de tocar nada)
- El runner de la app (`growi-bridge.py`) ya era genérico: `engines.json` esquema 2, y `run_engine` lee solo
  el descriptor. Sin embargo, en el `cola.db` de la app instalada **nunca corrió una tarea de codex ni de
  gemini**: 100 de claude, 35 de modelos, 1 de ollama y 77 sin motor.
- **Rechazo real:** `t-lote-estados-030-r2` (28 oct, 11:54) llegó con `"model": "motor:codex"`, que es el
  formato del selector. «Pedirle algo» lo traducía, pero `validate_task` no: leía `motor` como si fuera un
  motor, no lo encontraba, caía en claude y claude lo rechazaba con «model no permitido: motor:codex».
- La app instalada es otra versión (36 014 líneas frente a 45 361 en el repo) y su `engines.json` no trae gemini.
- `runner/runner.py` (el runner suelto) solo lanza claude.
- La única cuota que existía era la de Claude, y nunca se activaba (`max_quota()` siempre devuelve
  «no disponible»).
- **Hallazgo durante la prueba:** la ficha de gemini decía `herramientas: false`. Con eso, el runner
  descartaba el `permission_mode` de la tarea y lanzaba `agy --mode plan`. agy planificaba unos 3 min
  (220 000 tokens), pedía «Proceed» y no tocaba nada; en el siguiente intento fallaba con «plan model not
  specified». Con `--mode accept-edits` (agy 1.4.10) crea el archivo en unos 8 s.

## Decisiones (las que recomendé en el diseño; al aprobarlo no elegiste otras)
1. Gemini va **solo** por agy, con tu sesión de Google ($0). La API de Gemini se usa solo si el task pide
   `"via": "api"`. Antes, la ficha caía sola a la clave si no había sesión; ya no.
2. La app instalada se arregla con un script de parche (`parches/parche_motor_generico_052.py`), no con
   una actualización completa.
3. `runner/runner.py` rechaza los motores distintos de claude con «lo corre el runner de la app».

## Cambios
| Archivo | Qué |
|---|---|
| `growi-bridge.py` | `normalizar_motor(motor, model, via)` es la única puerta, y `validate_task` la llama (sirve a la ventana, la VM y las rondas). Acepta `motor`, `"model": "motor:<id>"` y `"<motor>:<modelo>"`. Rechaza si `motor` y `model` dicen motores distintos (claude, codex, ollama...). `via: "api"` se convierte en `motor: api, api:<proveedor>:<modelo>`, con el proveedor sacado de `credencial_ref`. El bloque «forma vieja» queda en `default_motor()` |
| `growi-bridge.py` | Cubos de cuota: `cubo_de_motor()`, `cubos_cuota()` (tareas y tokens en 5 h y en la semana, leídos de los `result.json`; el % solo sale con `settings.json → limites_cubo`) y `cubo_motivo()`. `router_antes` mira **solo el cubo del motor de la tarea**. Si el motor no está en la cadena de respaldo, se registra en el log y la tarea sigue. `spend_summary()["cubos"]` |
| `growi-bridge.py` | `_parse_jsonl`: regla `extraer.uso` que suma los tokens de un evento (codex: `turn.completed`) para su cubo |
| `engines.json` | `cuota.cubo` en claude (`claude-max`), codex (`chatgpt-plus`) y gemini (`google-agy`). En codex, `extraer.uso`. En gemini, `autenticacion.preferencia = ["sesion_cli"]` y `capacidades.herramientas = true` (con el porqué). En el fallback, el coste de gemini pasa a «$0 (sesión de agy...)» |
| `runner/runner.py` | `motor` ≠ claude, o `model: motor:<x>`, se rechaza con «lo corre el runner de la app Growi Bridge» |
| `parches/parche_motor_generico_052.py` | Para la app instalada: añade `normalizar_motor` (la misma función del repo, más `_motor_de_modelo` si falta) y la ficha de gemini del repo. Solo aplica si encuentra el texto original exacto, conserva los CRLF y deja un `.pre-motor-generico-052.bak`. Sin `--aplicar` solo comprueba |
| `LEEME-growi-bridge.md`, `runner/LEEME-runner.md` | Campos `motor` y `via`, y cubos de cuota |

## Verificación (instancia aislada `C:\Users\forte\growi-bridge\_prueba-motor-generico-052\app`: el código del repo, la config de la app instalada solo leída, share, cola.db y log propios; runner_loop real; motores lanzados ocultos con CREATE_NO_WINDOW + SW_HIDE; ninguna ventana)
| | Prueba | Resultado |
|---|---|---|
| a | Task con `"motor": "codex"` por la cola | **OK**: status ok, `motor: codex`, `acceso: sesion_cli` (ChatGPT Plus), session_id = thread_id, 28,9 s, archivo «listo codex», uso 34 198 / 238 tokens. cola.db: `terminada, codex` |
| b | El task real del 28 oct (`"model": "motor:codex"`) | **OK**: `validate_task` lo acepta como motor codex |
| c | Task con `"motor": "gemini"` por la cola | **OK**, tras arreglar `herramientas`: status ok, `motor: gemini`, `acceso: sesion_cli` (agy, Google), 33,2 s, archivo «listo gemini», uso 16 882 / 834. El primer intento, con `herramientas: false`, quedó en cuarentena con «plan model not specified» |
| d | Contradicciones | **OK**: codex+sonnet, gemini+motor:codex y claude+ollama:qwen3 se rechazan con «motor y modelo no coinciden...»; un motor inexistente y `via: "fax"` también. Las formas válidas (`motor:gemini`, `sonnet`, `ollama:default`, `claude+opus`, `codex:gpt-6.1-sol`) dan el motor y el modelo correctos |
| e | Cubos separados | **OK**: chatgpt-plus 0→1 tarea (34 436 tokens), google-agy 0→1 (17 716), claude-max 0→0. Con un límite de prueba de 1 tarea en chatgpt-plus: `cubo_motivo("codex")` = «al 100 %», y claude y gemini = None |
| f | `runner.py` suelto | **OK**: codex y `motor:gemini` se rechazan con «lo corre el runner de la app»; claude se acepta |
| g | `via: "api"` | **OK**: gemini + via api → `motor: api`, `api:gemini:gemini-2.5-flash` (no se ejecutó: gastaría con la clave) |
| — | Parche sobre una **copia** de la app instalada (`_prueba-motor-generico-052\instalada`) | **OK**: aplica, deja .bak y compila; la copia acepta el task del 28 oct como codex, rechaza codex+sonnet, ve gemini disponible («sesión de agy (Google) iniciada») |
| — | Gate de calidad | **PASA** (py_compile, ruff, mypy, pytest 9/1 skip, smoke). Un intento anterior falló solo en el smoke por «puerto 8797 ocupado» (algo pasajero; repetido, pasa) |

Costo: $0 extra. Dos tareas de codex (ChatGPT Plus) y tres de agy (Google AI Pro), contando la que falló. La depuración manual de agy usó 4 llamadas más, también con Google AI Pro. (Corregido el 30 oct: la cuenta de agy es Google AI Pro, plan pago, no free tier; el cubo se llama ahora «Google AI Pro (agy)».)

## FALTA / notas
- **App instalada: parche APLICADO (30 oct, con tu «procede»).** Respaldos `growi-bridge.py.pre-motor-generico-052.bak`
  y `engines.json.pre-motor-generico-052.bak`. Compila, y su `validate_task` acepta `model: motor:codex` y
  `motor: gemini` y rechaza codex+sonnet. La app no estaba abierta (solo `browser-server.py`), así que no
  hubo que reiniciarla: toma el cambio la próxima vez que la abras. No la abrí yo para no sacar ventanas.
  Los cubos y `router_antes` no van en el parche, porque esa versión no tiene cadena de respaldo; llegan con
  la actualización completa.
- **gemini con `acceptEdits` puede correr comandos:** la config propia de agy en este PC tiene
  `toolPermission always-proceed`. Es el mismo nivel que codex con permisos, pero conviene saberlo.
- Ningún proveedor publica cuánto queda de cuota. Los cubos dicen lo medido aquí y solo dan un % si pones
  `limites_cubo`. Codex `exec --json` no trae límites de uso (visto en la salida real).
- `_send_ask` sigue con su propia traducción de `motor:<id>` (también recorta permisos según la ficha). Es
  compatible con la puerta nueva, pero no la reemplacé.
- La reanudación de gemini (`--conversation`) sigue sin verificar en vivo, como ya decía su ficha.
