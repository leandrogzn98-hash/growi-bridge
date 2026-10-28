# Estado: gate de calidad local como Stop hook (t-gate-stop-hook-calidad)

Rama `Claude`, 27-28 oct 2026. **LISTO**, con las desviaciones del spec
anotadas abajo.

El gate es un filtro previo y gratis ($0, sin modelo) que corre al terminar
cada `claude -p`. Si encuentra un fallo real en lo que cambió, no deja terminar
y devuelve el fallo al agente, que lo corrige en el mismo loop. La revisión
por criterios sigue igual, pero recibe el log del gate y no vuelve a
comprobar a mano sintaxis, lint, tipos, tests ni arranque.

## Qué se hizo

| Pieza | Dónde |
|---|---|
| El gate | `gate-calidad.py` (raíz del repo; solo biblioteca estándar + `python -m ruff/mypy/pytest`) |
| Stop hook + UserPromptSubmit | `.claude/settings.json` del proyecto (abajo el bloque) |
| Tests del gate | `tests/test_gate_calidad.py` (9 tests, ~4 s) |
| Runner → gate | `growi-bridge.py`: `_engine_env(eng, task, rol)` pone `GROWI_TAREA_ID` y `GROWI_TAREA_ROL` al lanzar `claude -p` (tarea y revisión) |
| Gate → revisión | `growi-bridge.py`: `_gate_para_revision(task)`, llamada desde `_armar_prompt_juez` (la usa `_review_prompt`) |
| Logs | `<raíz>/gate-calidad/gate-calidad-<id>.log` (ignorado por git) + copia en `share/outbox/` si existe |
| Evidencia | `pruebas/evidencia/gate/` |

Instalé `ruff 0.17.3`, `mypy 2.4.0` y `pytest 9.2.0` con `pip`; no estaban.
Si faltan en otro PC, el gate avisa con «FALTA» y no bloquea.

### 1. El script (`gate-calidad.py`)
Corre en orden, solo sobre lo cambiado:
- **(a) py_compile** de cada `.py` tocado.
- **(b) ruff check**: las reglas de error `E9,F63,F7,F82` (sintaxis, comparaciones
  inválidas, errores de sentencia, nombres sin definir) bloquean en líneas
  cambiadas. El resto de reglas por defecto solo salen como aviso.
- **(c) mypy**: uno a uno, con `--follow-imports=silent --ignore-missing-imports`.
- **(d) pytest -q** de los tests afectados: un test cambiado o que nombra al
  archivo cambiado. Si no hay ninguno, corre la suite completa con tope de 120 s.
  Si no hay suite, lo dice y sigue.
- **(e) smoke de Tkinter**, solo si cambió `growi-bridge.py` o algo que la app
  lee al arrancar (`engines.json`, `temas/`…):
  - copia la app a `%TEMP%\gate-calidad-smoke-<pid>`, con share, cola, token y
    mutex propios, en el **primer puerto libre desde 8797** (nunca 8787/8788/8789);
  - la lanza con `pythonw` minimizada y sin foco, y espera **200 en
    `/gateway/salud`** (tope 30 s);
  - mira que el log no tenga `Traceback`;
  - la cierra por la X con `on_close=quit`, o sea por **`quit_app`**;
  - si no sale en 25 s es FALLA y se mata igual;
  - comprueba que no queda el pid y borra la copia si pasó.

**De dónde salen los archivos cambiados:**
1. stdin JSON `archivos`/`files`, o `--archivos`.
2. Si no hay lista: en el hook, los `Edit/Write/MultiEdit/NotebookEdit` del
   `transcript_path`, más `git diff --name-only <base>` y los no rastreados
   nuevos. La `<base>` es el HEAD al empezar la sesión, que guarda
   `--registrar-base` en `UserPromptSubmit`; así un commit del agente no
   esconde su cambio.
3. Sin hook: `git diff HEAD` más los no rastreados.
4. Sin git ni transcript: todos los `.py`.

«Líneas cambiadas» son los hunks de `git diff -U0`; un archivo nuevo cuenta
entero.

**Salida:** un resumen `[PASA]/[FALLA]/[AVISO]/[OMITIDO]` por chequeo. Sale
**0** si pasa y **2** si hay un fallo real; en modo hook, el resumen va
también por stderr.

**Tope anti-bucle:** tras 3 bloqueos seguidos en la sesión deja terminar
(salida 0), y el log dice `GATE: FALLA SIN CORREGIR` para que la revisión lo
vea como fallo.

**Sesión del juez:** con `GROWI_TAREA_ROL=revision` no corre, porque el juez
no cambia nada.

### 2. Stop hook registrado
Archivo: `C:\Users\forte\source\growi-bridge\.claude\settings.json`. Añadí a
`.gitignore` la excepción `!.claude/settings.json`, porque `settings.json` ya
estaba ignorado por ser el de la app.
```json
{
  "hooks": {
    "UserPromptSubmit": [{"hooks": [{"type": "command",
      "command": "python \"C:/Users/forte/source/growi-bridge/gate-calidad.py\" --registrar-base", "timeout": 30}]}],
    "Stop": [{"hooks": [{"type": "command",
      "command": "python \"C:/Users/forte/source/growi-bridge/gate-calidad.py\"", "timeout": 300}]}]
  }
}
```
**Que `claude -p` lo hereda está probado con una corrida real** (abajo, (c)).
Se hereda cuando `claude -p` corre con el cwd en este repo.

**Al integrarlo**, en la app instalada las tareas corren con
`cwd = C:\Users\forte\growi-bridge\share\inbox`. Para que hereden el hook hay
que copiar el bloque a `C:\Users\forte\growi-bridge\.claude\settings.json`
(o a `share\inbox\.claude\`) con la ruta al `gate-calidad.py` integrado. No lo
toqué: es la app instalada.

### 3. Barato y con alcance
Coste en modelo: **$0**. El gate no llama a ningún modelo; solo procesos
locales. El `$0.013` de la prueba (c) es del agente de prueba (haiku), no del
gate.

| Corrida | Tiempo | Evidencia |
|---|---|---|
| Cambio típico: `growi-bridge.py` + `gate-calidad.py` (con smoke) | **34,4 s** (smoke 18,4 s, de los que 9-16 s son el arranque de la app) | `a4-final.txt` |
| Cambio de un `.py` sin smoke (tarea del loop) | **6,7 s** | `c-gate-calidad-prueba-gate-loop-2.txt` |
| Sin `.py` cambiados (árbol limpio) | **0,2 s** (0,5 s de reloj) | `a3-arbol-limpio.txt` |

### 4. Conexión con la revisión
`_gate_para_revision(task)` busca primero `SHARE/outbox/gate-calidad-<id>.log`.
Si no está, busca `<cwd o carpeta de arriba>/gate-calidad/gate-calidad-<id>.log`.
Lo que añade al prompt del juez, entre los criterios y el parte del motor:
- un bloque «GATE DE CALIDAD LOCAL (comprobado por código, $0…) Ya comprobó
  sintaxis, lint, tipos, tests y arranque: NO lo vuelvas a comprobar a mano;
  céntrate en los criterios»;
- el log, hasta 1500 caracteres;
- si el log dice FALLA: «El gate FALLÓ y el agente no lo corrigió: es un HECHO
  que FALLA, la tarea NO se aprueba»;
- si no hay log: «el gate no corrió; compruébalo tú».

La rúbrica y los criterios no se tocaron. `engines.json` no se tocó (no hizo
falta: la tarea pasa su id por entorno).

### 5. Solo bloquean fallos reales
Las reglas están en la cabecera de `gate-calidad.py`.
- **Bloquea:**
  - error de py_compile;
  - ruff `E9/F63/F7/F82` en líneas cambiadas;
  - mypy `error:` en líneas cambiadas (salvo `var-annotated`, `import-untyped`,
    `import-not-found`, `annotation-unchecked` y `no-redef`, que en un código sin
    anotaciones son ruido);
  - test en rojo;
  - smoke con traceback, sin 200 en `/gateway/salud` o sin salida limpia.
- **No bloquea (aviso):**
  - el estilo de ruff (el proyecto no tiene config de ruff ni usa `ruff format`;
    hay 832 hallazgos preexistentes);
  - los 41 errores de mypy preexistentes;
  - cualquier hallazgo en líneas o archivos no tocados;
  - ruff, mypy o pytest ausentes («FALTA»);
  - que no haya suite;
  - que la suite pase de 120 s.

## Verificación (con evidencia real)
| | Prueba | Resultado | Evidencia |
|---|---|---|---|
| a | Gate sobre el cambio del propio gate y sobre el árbol limpio | Salida 0. Con cambio: PASA en py_compile, ruff, mypy, pytest (9 passed) y smoke (200 a los 9,1 s, salida limpia código 0, log sin tracebacks). Árbol limpio: PASA, todo OMITIDO por no haber `.py` cambiados | `a4-final.txt`, `a3-arbol-limpio.txt` |
| a' | La primera corrida del gate sobre su propio cambio | **Salida 2**: encontró 3 errores reales de mypy en `tests/test_gate_calidad.py` (`ModuleSpec \| None`); los corregí y pasó | `a-cambio-tipico.txt` es ya la corrida corregida |
| b | Copia `runner/runner_copia_gate.py` con `return variable_sin_definir + 1` | **Salida 2**, `[FALLA] ruff check: runner_copia_gate.py:762: F821 Undefined name variable_sin_definir`. Sin la copia (gate sobre `runner/runner.py`): **salida 0** | `b1-bloqueo.txt`, `b2-sin-copia.txt` |
| c | `claude -p` real (haiku, cwd = repo, `GROWI_TAREA_ID=prueba-gate-loop-2`): escribe `pruebas/demo_gate_loop.py` con `return x * factor` | 1) el agente escribe y dice «listo»; 2) **Stop hook feedback**: `GATE: FALLA … F821 Undefined name factor`, el stop se bloquea; 3) el agente edita (`factor = 2`); 4) el gate vuelve a correr: **PASA**, la sesión termina (`num_turns 4`). El log dice `historial de esta sesion: 23:08:57 FALLA -> 23:09:09 PASA`. Se repitió dos veces (la primera, `prueba-gate-loop`, sin historial en el log) | `c-loop-claude-p.json`, `c-gate-calidad-prueba-gate-loop-2.txt` |
| c' | Tope anti-bucle: 4 paradas de la misma sesión con un archivo roto | rc 2, 2, 2 y luego **0** con `GATE: FALLA SIN CORREGIR` | `tope-gate-calidad-prueba-tope.txt` |
| d | Tiempo y coste | Ver la tabla del punto 3; $0 | — |
| e | El prompt real del juez (`_armar_prompt_juez`) de una copia aislada de la app para 3 tareas de prueba | `prueba-gate-loop`: el bloque del gate con PASA. `prueba-tope`: el bloque + «la tarea NO se aprueba». `tarea-sin-log`: «el gate no corrió». La rúbrica y los criterios siguen en los 3 | `e-prompt-juez.txt` |

`tests/test_gate_calidad.py` también cubre lo que no debe bloquear: mypy
ausente da AVISO, sin suite da OMITIDO, y la sesión de revisión no corre.

## Desviaciones del spec y por qué
- **Ubicación:** el `.task.json` pide `share\inbox\growi-bridge-app\` y
  `share\outbox\`. La orden de esta sesión fue trabajar en este repo y no tocar
  la app instalada, así que el gate está en la raíz del repo. El log va a
  `gate-calidad/` y, si hay `share/outbox/`, también ahí. La revisión lo busca
  en `SHARE/outbox` primero.
- **Smoke:**
  - usa `/gateway/salud` en un puerto de prueba (8797+), no
    `http://127.0.0.1:8787/health`: `/health` da 404 y 8787 es la app
    instalada;
  - en la **copia** del smoke quito `servidor` (motor local) y
    `autenticacion.sesion_cli` de `engines.json`; el `engines.json` del repo no
    se toca. Motivo, medido: `agy models` (la sesión del motor gemini) tarda
    **~40 s** y `build_gui` la espera de forma síncrona (volcado de pila:
    `build_gui → engine_choices → engine_status → acceso_motor → _sesion_cli`),
    así que la copia tardaba 31 s en responder y el tope de 30 s fallaba
    siempre. Sin esa comprobación la app responde en 9-16 s. **Esto es un
    problema real de arranque de la app, para otro fix:** la comprobación de
    sesión de los CLI no debería bloquear el hilo de la ventana. Quitar el
    servidor del motor local evita además que la copia adopte o cierre el
    `llama-server` de la app instalada.
- **ruff:** en un archivo de 32 000 líneas sin configuración de ruff, «errores»
  son las reglas de error (`E9,F63,F7,F82`), no todo el set por defecto
  (estilo), y solo en líneas cambiadas. Si no, el gate bloquearía siempre por
  lo preexistente.

## FALTA / no verificado
- No se probó con el runner de la app instalada lanzando una tarea real de la
  cola: la prueba (c) es `claude -p` directo con las mismas variables que pone
  el runner. Lo que hace el runner (`_engine_env(eng, task, rol)`) está en el
  código, sin corrida de la cola.
- No se probó el hook con el cwd de la app instalada (`share\inbox`): ver
  «Al integrarlo» arriba.

## Cómo repetir las pruebas
```
python gate-calidad.py                         # (a) sobre lo cambiado segun git
python gate-calidad.py --smoke                 # forzar el smoke
python -m pytest -q tests                      # tests del gate
# (b) copia con error
copy runner\runner.py runner\copia.py & echo x = sin_definir>> runner\copia.py
python gate-calidad.py --archivos runner/copia.py   # -> 2, F821
del runner\copia.py & python gate-calidad.py --archivos runner/runner.py   # -> 0
# (c) loop real (desde la raiz del repo)
set GROWI_TAREA_ID=prueba-gate-loop
claude -p "Crea pruebas/demo_gate_loop.py con: def doble(x): return x * factor (aunque tenga error). Si un hook te reporta un fallo, corrigelo." --model haiku --permission-mode acceptEdits --allowedTools Write,Edit,Read --output-format stream-json --verbose
type gate-calidad\gate-calidad-prueba-gate-loop.log   # historial FALLA -> PASA
```
