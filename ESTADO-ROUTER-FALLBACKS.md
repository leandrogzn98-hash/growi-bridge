# ESTADO — Cadena de respaldo y router (t-router-fallbacks)

Rama `Claude`. Pruebas:
- `pruebas/prueba_router_runner.py`: runner real `_process_one_impl`. Los motores del ejecutor son
  **falsos dentro del proceso** (429, 401 u ok, sin red ni gasto). La revisión de (e) es **real**
  (cadena del revisor con Ollama local, $0).
- `pruebas/prueba_router_gui.py`: app real en una copia, puerto 8797, pestaña Modelos.

Evidencia en `pruebas/evidencia/router-fallbacks/`: `runner.json`, `evidencia.json` y 2 capturas.

## LISTO
1. **Cadena en engines.json** → sección `fallback`, editable:
   - `ejecutor.cadena` claude → gemini → llama;
   - `revisor.cadena` llama → ollama → claude:haiku, espejo de `revision.orden`, que es lo que usa el runner;
   - `motores` con rol, coste y `cambia_si` de cada uno;
   - `breaker` (3 fallos, 5 min), `cuota_aviso_pct` (90), `degradacion_sin_regla`, `utilidad` y `heartbeat`
     (llama).

   Solo valen motores de `motores` (allowlist). Uno de fuera se rechaza en la cadena y en el editor.
2. **Taxonomía y disparadores**:
   - **Transitorios** (429, 408, 5xx, red, cuota, timeout, sin respuesta): reintento con backoff y, agotados
     los reintentos, el siguiente de la cadena.
   - **Definitivos** (400/401/403, Unauthorized/Forbidden, «invalid api key», configuración): nunca
     reintento ni respaldo.
   - El cambio es **entre intentos**: la tarea vuelve a la cola con el motor nuevo, nunca a mitad de una
     salida. Si el motor nuevo no puede seguir la sesión, el checkpoint le da el resumen (t-checkpoint-ronda).
   - Si la cadena se agota → `necesita_decision` con el motivo y «lo hecho está guardado».
3. **Circuit breaker por motor**: 3 fallos transitorios seguidos → 5 min al respaldo y luego se vuelve a
   probar el primario. Los candidatos en pausa no se reintentan (enfriamiento). Una tarea sin regla
   **espera** a que pase la pausa en vez de quemar intentos. Cada cambio queda en el Registro
   (`motores: cambio de … a …`) y en Estado → «Último cambio».
4. **Hot reload desde Modelos**: tarjeta «Cadena de respaldo» con el modelo activo, las dos cadenas, el
   estado de cada motor y ↑/↓. Guarda en engines.json con `.bak`, la recarga en caliente lo aplica sin
   reiniciar y la tarea en curso termina con el motor con el que empezó.
5. **Lo barato para lo barato**: la revisión va por la cadena local (llama → ollama; Haiku solo desde R1),
   y `utilidad` y `heartbeat` son llama. **Aviso de cuota**: con Claude ≥ 90 %, una tarea que permite
   degradar empieza ya en el respaldo, antes del corte.
6. **Motor por intento y por revisión en el resultado**: `motor_elegido`, `motivo_eleccion`,
   `escalon_previo`, `motivo_escalado` y `ruta_motor.pasos` («claude: 429 → gemini», «gemini: 429 →
   llama»). La revisión trae `cadena_revisor` («llama: no_disponible (…) → ollama: valido»).
7. **Degradación declarada**: solo se cambia de motor si la tarea lo dice (`"degradacion": true`, o
   `{"permitida": true}`) o si `degradacion_sin_regla` es `seguir`. Sin regla, el error no decide: la
   tarea queda `necesita_decision`.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) cadena | `cadena_ejecutor` = claude, gemini, llama; revisor llama, ollama, claude/haiku; legible en Modelos (captura 1) |
| (b) 429 | llamadas claude, claude (reintento), gemini, gemini, llama → **termina con llama**; `ruta_motor.pasos` con los dos saltos |
| (b) 401 | **1 llamada** a claude, fallida, sin reintento ni respaldo |
| (c) breaker | 3 fallos seguidos → `abierto_hasta` +5 min. Con regla → va directo a gemini sin llamar a claude. Sin regla → espera («esperando a Claude (breaker abierto…)») |
| (d) en Modelos | ↓ a Claude → engines.json `gemini, claude, llama` y el runner lo usa ya. Revisor ↑ Ollama → `revision.orden` y `fallback.revisor` cambian juntos. «recarga en caliente: aplicado sin reiniciar» |
| (d) en curso | reordenar MIENTRAS corre una tarea → esa termina con **claude**; la siguiente ve el orden nuevo |
| (e) revisión barata | revisión **real**: llama-server no instalado → **Ollama local** aprueba ($0); `cadena_revisor` registrada |
| cuota | Claude al 95 % (simulado) + regla → empieza en gemini; sin regla → sigue con claude y lo dice |
| (g) sin regla / agotada | `necesita_decision` («…no se cambia de motor: ni la tarea ni engines.json lo declaran…», «lo hecho está guardado») |
| Tracebacks | 0 |

## FALTA
- **(f) Haiku revisando con llama Y ollama caídos, en vivo**: no se corrió, porque gasta cuota de Claude (Max).
  La cadena hasta Ollama sí se probó en vivo. El paso a Haiku es el mismo código (`_llm_review` recorre
  `revision.orden`); falta verlo con dinero de por medio. Cómo probarlo: en una copia, poner la `base_url`
  de ollama a un puerto muerto y correr una tarea R1 con criterios.
- **Gemini/agy en vivo como respaldo**: en el PC de la prueba el motor gemini aparece «no disponible» (sin
  sesión de agy). En la prueba del runner los tres motores eran falsos.
- La cuota real de Claude solo se ve si la app la puede leer (`_quota_pct`); sin dato no hay aviso
  anticipado.

## COMO PROBARLO
`python pruebas/prueba_router_runner.py` y `python pruebas/prueba_router_gui.py` → `pruebas/evidencia/router-fallbacks/`.
En la app: Modelos → «Cadena de respaldo». Una tarea que permite cambiar de motor lleva `"degradacion": true`.
