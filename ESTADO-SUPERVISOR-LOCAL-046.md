# ESTADO — Supervisor local, el «subgerente» (0.4.6)

Rama `Claude`, 29-oct-2026. Pedido de Leandro: un supervisor proactivo que viva en el PC, revise cada hora el estado
del Bridge con criterio (un modelo de lenguaje) y escale por correo lo que necesite una decisión humana.
- **Nunca corrige nada**: solo lee, juzga e informa. No reinicia, no borra, no reintenta, no tiene herramientas y no
  usa Tailscale.
- No se tocó `growi-bridge.py`, ni `VERSION`, ni la app instalada (`C:\Users\forte\growi-bridge\`).

## Dónde vive
Todo está en `supervisor/`:

| Archivo | Para qué |
|---|---|
| `supervisor.py` | El núcleo y las órdenes `--dry-run`, `--configurar`, `--verificar`, `--evals`, `--intervalo`, `--programacion` |
| `supervisor-config.yaml` | Toda la configuración. Lleva los valores de la instalación de Leandro y ninguna clave |
| `proveedores/` | Un archivo por proveedor (`deepseek`, `openai`, `anthropic`, `gemini`, `ollama` y `mock` para pruebas), con una sola función `completar(prompt, …) -> texto`. Añadir uno es añadir un archivo; el núcleo lo encuentra por su nombre |
| `evals.py` | Las evals del juez |
| `instalar-supervisor.ps1` | Instalador de Windows |
| `instalar-supervisor.sh` | Instalador de Linux |
| `instalar-supervisor-macos.sh` y `supervisor.plist.plantilla` | Instalador de macOS |
| `requirements.txt` | `keyring`, `pyyaml` y `requests` |
| `REQUISITOS.md` | Lo que necesita un usuario |

- Lo del propio PC queda fuera de git: `supervisor/.venv/` (el entorno de Python que crea el instalador) y
  `supervisor/_prueba/` (la instalación de prueba).
- El log y la memoria de alertas van en `~/.growi-supervisor/`, configurable en `datos`.
- Pruebas: `pruebas/prueba_supervisor.py` (todo lo verificable sin gastar) y `tests/test_supervisor.py` (schema,
  secretos y recorte).
- Evidencia: `pruebas/evidencia/supervisor/evidencia.json` y `tarea-programada.txt`.

## LISTO (con su verificación; todo sin gastar: proveedor mock, sin correo real)

### 1. El script supervisor
Cada pasada lee:
- `/gateway/salud` por 127.0.0.1, sin proxy y sin token;
- si la app «debería estar abierta»: su log tocado hace menos de 15 min o un `gateway.lock`;
- `runner-status.json`: la edad del latido y la tarea en curso;
- los `*.result.json` de las últimas 24 h:
  - en `necesita_decision`;
  - fallidas, con error o con timeout **posteriores a la pasada anterior**;
- los `CADENA-ESTADO*.json` (los patrones están en el YAML), donde `detenido` con texto es una cadena detenida;
- las líneas de error nuevas de los logs de la app y del runner.

Con eso arma «candidatas», cada una con una clave estable y una firma, y se las da al modelo junto con las reglas. Si
el veredicto es NECESITA_DECISION, escribe por Resend; si no, solo deja el log.

Todo texto leído pasa por `sin_secretos()` antes de ir al prompt, al correo o al log. Tapa `token=`, `Bearer …`,
`sk-…`, hex o base64 largos, y similares.

Verificación:
- **(a)** py_compile de los 10 `.py`: ok.
- **(c)** Se metió un secreto falso en el motivo de una tarea. Sale como `[oculto]` en el correo, y
  `secreto_en_evidencia` es `false` en toda la evidencia.

### 2. Configuración agnóstica
- El YAML tiene tres secciones principales:
  - `subgerente`: proveedor, modelo, de dónde sale la clave (`entorno` o `llavero` y su nombre) e intervalo.
  - `gerente_general`: nombre, y el canal con `from`, `to`, prefijo de asunto y de dónde sale la clave de Resend.
  - `bridge`: carpeta, share, puerto, logs y cadenas.
- Además están `juez`, `escalacion`, `programacion` y `datos`.
- Valores por defecto de Leandro: deepseek / deepseek-chat / 60 min, `growi@summitmaker.co` → `duet@summitmaker.co`,
  prefijo `[GROWI-BRIDGE]`.
- El código no tiene ni correos ni rutas fijas.
- Las claves solo se leen de una variable de entorno o de `keyring` (servicio `growi-supervisor`); el YAML no las
  admite.

### 3. Reglas de escalación y anti-spam
- **NECESITA_DECISION**:
  - cadena detenida;
  - tarea en `necesita_decision`;
  - gateway caído con la app que debería estar abierta;
  - errores nuevos del runner.
- **Ruido**:
  - gateway caído con la app cerrada;
  - una línea de error suelta;
  - un latido viejo.
- **Anti-spam** (`supervisor-memoria.json`): la misma clave con la misma firma no se re-envía antes de
  `reaviso_horas` (6). Si cambia el estado (otra firma), se avisa enseguida.

### 4. Instaladores
- **Windows** (verificado):
  - Crea el `.venv`, instala las dependencias, lee el intervalo y el nombre del YAML (`--programacion`) y registra la
    tarea.
  - La tarea corre con `pythonw.exe`, oculta y sin ventana, sin administrador, con `IgnoreNew` y un límite de 30 min.
  - `-Desinstalar` la quita.
  - **(e)** Se instaló la tarea **`GrowiSupervisor-prueba`** contra una instalación de prueba (`supervisor/_prueba/`,
    proveedor mock y Bridge simulado «cerrado»). Se lanzó: `LastRunTime 29/10/2026 4:05:33 PM`,
    `LastTaskResult 0`, y en el log quedó `TURNO estado=14e3bea9acf954f5 veredicto=TODO_BIEN confianza=0.9 …`.
    `--verificar` la detecta.
  - Después se **desactivó** (State `Disabled`), no se borró: así no corre cada hora. Ver `tarea-programada.txt`.
  - Arreglado de paso: Windows PowerShell 5.1 leía el `.ps1` sin BOM como ANSI y «`«$Nombre»`» quedaba vacío. Ahora
    va en UTF-8 con BOM y con `${Nombre}`.
- **Linux** (`instalar-supervisor.sh`): mismo contrato. Usa un temporizador de systemd de usuario
  (`OnUnitActiveSec=<min>`) o, si no lo hay, una línea de cron marcada `# <nombre>`.
- **macOS** (`instalar-supervisor-macos.sh` + plantilla del plist): agente `local.<nombre>` con
  `StartInterval = min × 60`.
- **(l)** Solo se comprobó su sintaxis (`sh -n`: ok; el plist es XML válido). **Sin verificar en su sistema real**: ver
  FALTA.

### 5. Modo `--dry-run`
No llama a ninguna API: el veredicto sale de las reglas locales. No envía nada y no escribe ni log ni memoria.
- **(b)** Estado sano: la primera línea es `TODO_BIEN`, sin correo y sin log escrito.
- **(c)** Con `necesita_decision`: `NECESITA_DECISION` y el correo completo que se enviaría, sin secretos.
- **(k)** Corre en Windows.

### 6. README
Nueva sección **«Roles: gerente general y subgerente»**, en lenguaje llano:
- qué hace cada rol;
- una tabla de plataformas con su coste y lo que necesitas;
- dos ejemplos de cambio de proveedor editando solo el YAML (a Ollama sin clave, y a OpenAI con llavero);
- los comandos `--configurar`, `--verificar` y `--dry-run`.

**(g)** ok.

### 7. `--configurar`
Pregunta, con valores por defecto: proveedor, modelo (el del proveedor), dónde guardar la clave, la clave (con
`getpass`, sin eco; solo si se elige llavero), `from`, `to` e intervalo. Confirma cada valor y valida el YAML que
escribe.
- **(h)** Entradas simuladas (openai, llavero, `avisos@ejemplo.com`, `yo@ejemplo.com`, 30) con un llavero en memoria,
  para no tocar el real:
  - YAML válido;
  - la clave no está ni en el YAML ni en pantalla;
  - sí está en el llavero.

### 8. `--verificar`
Da OK, FAIL u OMITIDO por punto: YAML, clave (sin mostrarla), proveedor alcanzable (una llamada mínima), Resend
(`GET /domains` y que el dominio del `from` esté `verified`) y tarea programada. Sale con 1 si algo falla.
- **(i)** Sin clave: `[FAIL] clave del proveedor: falta la clave de deepseek: no está en la variable de entorno
  DEEPSEEK_API_KEY…`, código 1.
- Con `--sin-llamadas`, lo no probado sale como `[OMITIDO]`, no como OK.

### 9. `REQUISITOS.md`
Cubre:
- equipo por sistema (Windows, Linux, macOS);
- cuentas con enlaces (los 5 proveedores y Resend con dominio verificado);
- dónde va cada clave;
- versiones mínimas (Python 3.10 o superior);
- el orden del montaje, con lo que pregunta el asistente paso a paso.

**(j)** ok.

### 10. Portabilidad
- Usa `pathlib`, `os.path.expanduser`, `platform.system()` (en la consulta de la tarea programada) y `~` en el YAML.
- **(k)** grep de `X:\` en el código, los instaladores y el YAML: 0 resultados.
- Dependencias: stdlib de Python 3.10 o superior más `keyring`, `pyyaml` y `requests`. pytest solo para las pruebas.

### 11. Robustez del juez (addendum)
- **(a) Schema estricto**:
  - El prompt exige JSON con exactamente `{veredicto, evidencia, confianza}`.
  - `validar_veredicto` rechaza: texto libre, claves de más o de menos, veredicto desconocido, evidencia que no es una
    lista de textos y confianza fuera de 0..1 o booleana.
  - Si falla, queda **FALLO_DE_JUICIO** en el log y se reintenta **una vez** con el mismo prompt. Si vuelve a fallar,
    el turno termina en FALLO_DE_JUICIO, sin correo.
  - Las alertas (y su anti-spam) salen de las candidatas locales, nunca del texto del modelo.
  - **(m)** Texto libre, otro schema y confianza 7: los tres registran «intento 1» e «intento 2» y `enviadas=[]`.
- **(b) Debounce**:
  - Ante NECESITA_DECISION con algo nuevo, espera `juez.debounce_s` (300), vuelve a leer el estado y solo escala lo
    que sigue grave.
  - Lo que se resolvió solo queda en el log como `FLAPPING`, no en el correo.
  - **(n)** Gateway intermitente:
    - primera pasada (vuelve durante el debounce): sin correo, con la línea `FLAPPING … ['gateway']`;
    - segunda pasada (persiste): con correo.
  - En las evals el debounce se simula (no se esperan 5 min); en una pasada real se espera de verdad.
- **(c) Evals** (`supervisor.py --evals` o `evals.py [proveedor]`):
  - Son 5 casos sintéticos, con un Bridge falso y un gateway HTTP real en 127.0.0.1 que se enciende y se apaga: sano,
    cadena detenida, gateway intermitente (en dos pasadas) y necesita_decision sin atender.
  - **(o)** Con el proveedor mock: **5/5**.
- **(d) Rastro**: cada turno deja `TURNO estado=<sha256 del estado, 16 hex> veredicto=… confianza=… fuente=…
  proveedor=…`.
  - **(p)** Comprobado en el log de la pasada real con mock.
- **(e) Presupuesto**:
  - **Estado de más de 8000 caracteres**: se recorta (primero las líneas de log) y queda
    `AVISO presupuesto: estado de 10987 caracteres recortado a 7862 (tope 8000)`.
  - **Tope de llamadas al día** (`max_llamadas_dia`, 48, reintentos incluidos): al pasarlo, el turno se abrevia a
    reglas locales y queda el aviso.
  - **Tope de gasto diario en USD**: solo actúa si se pone `precio_usd_por_millon_tokens` en el YAML. No se inventó
    ningún precio, así que por defecto está en `null` y el gasto no se estima.
  - Comprobado en la prueba.
  - Arreglado gracias a `tests/test_supervisor.py`: la marca `recortado` podía volver a pasar el tope.

**Gate** sobre los 12 `.py` nuevos: **PASA** (py_compile, ruff, mypy, pytest).
- El pytest del gate usa el Python del sistema, que no tiene `pyyaml`, así que `tests/test_supervisor.py` se salta
  ahí.
- Con el `.venv`: **10 passed**.

## FALTA
- **DeepSeek real y Resend real, sin probar**: en este PC no hay `DEEPSEEK_API_KEY` ni `RESEND_API_KEY` (ni en el
  entorno ni en el llavero), y no se compró ni creó nada.
  - Lo probado: el camino completo con el proveedor mock, el error claro sin clave y el armado del correo.
  - Sin probar: una respuesta real de DeepSeek, el envío real por Resend y el chequeo de dominio de `--verificar`.
- Para dejarlo funcionando de verdad, Leandro tiene que hacer esto:
  1. Guardar las dos claves con `supervisor\.venv\Scripts\python.exe supervisor\supervisor.py --configurar`
     (llavero).
  2. Si las tareas de Resend van con una clave «Sending access», saber que la comprobación de dominio de
     `--verificar` dará FAIL.
  3. Correr `powershell -ExecutionPolicy Bypass -File supervisor\instalar-supervisor.ps1`.
  4. Comprobar con `--verificar`.
- **Evals con un modelo real**: solo corrieron con el mock. Ollama ($0) no estaba arrancado y no se arrancó, para no
  cargar la GPU de un PC en uso.
  - Para medir un juez real gratis: `supervisor\.venv\Scripts\python.exe supervisor\evals.py ollama hermes3:8b`, con
    Ollama abierto.
  - Ni la calidad del juicio de DeepSeek ni de ningún modelo real está medida.
- **La tarea `GrowiSupervisor-prueba` sigue en el Programador de tareas, desactivada**. No se borró porque el spec
  prohíbe borrar. Para quitarla: `instalar-supervisor.ps1 -Config supervisor\_prueba\config.yaml -Desinstalar`. La
  tarea real `GrowiSupervisor` no se instaló, porque sin claves solo dejaría errores cada hora.
- **Linux y macOS: sin verificar en su sistema real** (solo sintaxis). La 0.4.7 verifica Linux; macOS queda para
  después. `tarea_programada_existe` para Linux y macOS tampoco se ha ejecutado nunca en esos sistemas.
- **Límite conocido de «app debería estar abierta»**: es una heurística (log reciente o `gateway.lock`). Si la app se
  cierra mal y deja `gateway.lock`, el gateway caído se tomará por grave hasta que se borre ese archivo.
- **La «confianza» del modelo se registra pero no decide nada** (no hay umbral). Usarla para decidir sería una
  decisión de diseño sin datos todavía.

## CÓMO PROBARLO
- Todo lo que no gasta:
  `supervisor\.venv\Scripts\python.exe pruebas\prueba_supervisor.py`. Imprime el resumen de (a) a (p) y escribe
  `pruebas/evidencia/supervisor/evidencia.json`.
- Unidad: `supervisor\.venv\Scripts\python.exe -m pytest -q tests\test_supervisor.py`.
- Evals: `supervisor\.venv\Scripts\python.exe supervisor\evals.py mock` (o `ollama hermes3:8b` con Ollama abierto).
- A mano, sobre la instalación real y sin gastar:
  `supervisor\.venv\Scripts\python.exe supervisor\supervisor.py --dry-run` y `… --verificar --sin-llamadas`.
- La tarea programada: `Get-ScheduledTaskInfo -TaskName GrowiSupervisor` tras instalar; el log está en
  `~\.growi-supervisor\supervisor.log`.
