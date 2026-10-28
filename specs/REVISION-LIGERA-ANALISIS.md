# Revisión ligera — cómo funciona hoy la revisión en el gateway

Análisis de solo lectura sobre `~/workspace/shared-bridge/growi-bridge-raiz.py`
(28.087 líneas, copia en la VM del gateway instalado en el PC) y
`~/workspace/shared-bridge/runner/runner.py` (357 líneas).
No se editó nada. Las líneas citan el gateway salvo que se diga lo contrario.

## 1. Cómo funciona hoy la revisión y qué modelo usa

### El flujo completo (gateway)

1. Corre el motor con el prompt ensamblado (`prompt_de_tarea`, línea 10183).
2. Al terminar, `_after_run` (12340) decide: si el resultado no es `ok` → fallida;
   si el task trae `"revisar": false` → `sin_revision` (12349); si no,
   llama a `review_task(task, result)` (12358) y guarda el veredicto en
   `<id>.revision.json`.
3. `review_task` (10015) hace, en este orden:
   - **(1) Checks deterministas ($0), puerta dura.** `checks_deterministas`
     (9619) comprueba los criterios tipados contra archivos reales.
     Los tipos son `existe`, `lineas`, `contiene`, `compila`, `comando`
     (`CRIT_TIPOS`, 9295). El comentario de cabecera lo dice literal:
     «EL JUEZ OPINA; LOS HECHOS MANDAN: si un check tipado falla no hay
     aprobación, diga lo que diga el juez» (9291-9294).
   - **(2) Primer juez (LLM).** `_llm_review` (9947) recorre la cadena del
     descriptor y usa el primero que responda. Un juez que responde JSON
     inválido **no** se salta: es «sin revisión» (9952-9958).
   - **(3) Segundo juez, solo si hace falta.** `_motivo_segundo_juez`
     (9994): nunca en R0; solo si un check falló o la tarea es R2/R3.
   - **(4) Decisión.** Dos jueces que no coinciden, o jueces que aprueban
     contra un hecho, → `necesita_decision` (decide Leandro, sin otra ronda).
4. **Rondas de corrección.** Si no se aprueba y `ronda < MAX_ROUNDS` (3,
   línea 4510), `_after_run` (12399) encola `_enqueue_round` (12281): una
   tarea nueva con el mismo motor y modelo (`_task_core`, 12265-12279),
   prompt «Revisé tu trabajo y faltan estas cosas…» + el encargo original.
   Cada ronda es **motor completo + revisión completa**: el multiplicador
   de coste real del pipeline.

### Qué modelo usa el juez: NO es el del spec

El juez no se elige desde el task JSON. Se elige desde **`engines.json`
(sección `revision.orden`)**, leída por `_rev_cfg()` (9329-9331) vía
`load_engines()` (4861), que lee `APP_DIR / "engines.json"` (4507, en el PC).

`_llamar_juez` (9890) toma `mid = spec.get("motor")` y construye la tarea
de revisión con `"modelo": spec.get("modelo")` (9918-9920), donde `spec`
es **la entrada de `revision.orden`, no el task**. El `model`/`modelo`
del spec de la tarea nunca llega al juez. Tampoco hay ningún campo
`revisor_model` ni similar en todo el gateway (grep `revisor`: solo
calibración y logs).

Valores reales en la copia del repo en la VM
(`~/workspace/growi-bridge-repo/engines.json`, sección `revision`):

```json
"orden": [
  {"motor": "llama"},
  {"motor": "ollama"},
  {"motor": "claude", "modelo": "haiku", "allowed_tools": "Read,Glob,Grep"}
],
"max_rondas": 3
```

Es decir: **locales $0 primero (llama → ollama), Haiku solo si ningún
local responde**. Si falta `engines.json` o está roto, el fallback
(`_FALLBACK_ENGINES`, 4517) es solo `claude/haiku`.

Resolución del modelo del juez:

- HTTP local (`_run_http_engine`, 7374; `_local_model`, 7360): modelo del
  spec de revisión o `modelo.por_defecto` del descriptor → llama
  `hermes-3-8b-q4_k_m`; ollama `@ollama_por_defecto` (de `settings.json`).
  Con `for_review=True` no arranca el servidor solo para revisar ni reusa
  la sesión de la tarea (7379, 7394).
- CLI (`_build_cli_cmd`, 6933): `task.get("modelo")` de la tarea de
  revisión o `por_defecto` del descriptor → `--model haiku` para el juez
  de Claude (el descriptor de `claude` declara `por_defecto: null` y
  `permitidos: [sonnet, opus, haiku, claude-*]`).

**Segundo juez:** en la copia de `engines.json` de la VM **no existe
`revision.segundo_juez`**, así que `spec2` es `None` y el segundo juez
nunca se llama (10068-10076: «engines.json no declara
revision.segundo_juez»). La propuesta habla de Haiku como segundo juez;
hoy el código lo prevé pero la config no lo declara. (Caveat: el
`engines.json` del PC podría diferir de la copia del repo; verificar allí
la sección `revision` antes de afirmar el coste real.)

### El prompt del juez ya es ligero (no lleva memoria ni reglas)

`_armar_prompt_juez` (9769): encargo (≤3000 car.), criterios en frases,
hechos de los checks, parte del motor recortada y obra (archivos tocados,
≤6 archivos × 2500 car. por defecto). `prompt_juez_que_quepa` (9861)
recorta por niveles (`_NIVELES_RECORTE`, 9855) si no cabe en el contexto
del juez. No incluye memoria ni reglas: ahí no hay nada que recortar.

## 2. ¿Re-etiquetar el `model` del spec abarata la revisión? No

- El modelo de la revisión sale de `revision.orden` en `engines.json`
  (PC), no del campo `model`/`modelo` del spec. La validación del task
  (4275) acepta `modelo` o `model` y lo guarda en el task normalizado
  (4430-4431), pero `review_task` y `_llamar_juez` no lo leen.
- Cambiar `model: sonnet → haiku` en el spec **solo** abarata la pasada
  del motor (y sus rondas de corrección, que heredan motor y modelo vía
  `_task_core`, 12265-12279). La revisión cuesta exactamente lo mismo
  antes y después del re-etiquetado.
- Matiz: si el motor de la tarea es local (llama/ollama), la revisión
  también tiende a ser $0 porque el juez local es el primero del orden;
  pero eso depende del **motor** elegido, no del campo `model`.
- El camino del runner simple (`runner.py`) ni siquiera tiene revisión:
  una sola llamada `claude -p` (líneas 218-224), con `model` restringido
  a `sonnet | opus | haiku | claude-*` (`ALLOWED_MODELS`, 60). Ahí el
  re-etiquetado sí es el único coste que hay, porque no hay revisión
  que abaratar.

## 3. Palancas que existen desde la VM y cambios que harían falta en el gateway

### Palancas que ya existen hoy (campos del spec, sin tocar el gateway)

| Palanca | Efecto | Dónde |
|---|---|---|
| `"revisar": false` | Salta la revisión entera (`sin_revision`) | 4436, 12349 |
| Criterios **tipados** (`existe`/`lineas`/`contiene`/`compila`/`comando`) en vez de frases | La decisión la toman los hechos ($0); el juez solo confirma. Las frases solo las juzga el juez | 9295, 9440 (`separar_criterios`) |
| `"memoria": false` | Apaga la memoria del prompt del motor (no afecta al juez, que no la lleva) | 4436, `mem_activa` 10241 |
| Motor local (`llama`/`ollama`) | Juez local $0 si responde; si no, cae a Haiku | `engines.json`, orden |
| Criterios precisos y pocos | Evita rondas de corrección (cada una = motor + revisión otra vez) | 12399, 12281 |

Lo que **no** existe: ningún campo del task JSON controla el modelo de
revisión ni el prompt del juez. La validación (4381-4448) solo propaga
`revisar` y `memoria` como controles de la revisión. Tampoco hay campo
por task para `max_rondas` (fijo en 3, línea 4510).

### Cómo se construye hoy el prompt del motor (para la palanca de memoria)

`prompt_de_tarea` (10183-10199), en este orden:

1. `rules_prefix()` (2805): reglas activas de `rules.json` —
   `DEFAULT_RULES` (2054): «Pregúntame antes de gastar dinero» y
   «No borres nada sin pedirme permiso» — más las skills apagadas.
2. `mem_bloque_prompt(task)` (10395): **MEMORY.md (cuota 50%) + nota de
   hoy (30%) + nota de ayer (20%)**, nunca notas más viejas.
   Presupuesto: `max_caracteres` de `settings.json → memoria` (defecto
   **12000**, `_MEM_DEF`, 10213) o 25% del contexto del motor si es menor
   (10413-10418). Una sola carga por tarea (caché `_MEM_CARGA`).
3. `skills_bloque_prompt(task)` (1224): skills activadas por descripción,
   máximo 3.
4. El `prompt` del task.
5. `autocritica_txt(task)` (10160): solo en tareas de código; reflexión
   de auto-comprobación contra los criterios tipados.

### Cambios necesarios en el gateway (para un spec futuro)

1. **Revisión sin juez (cambio mínimo, una sola edición):** aceptar
   `"revisar": "solo_checks"` (además de `true`/`false`) en la validación
   (4436) y en `_after_run`/`review_task` (12349, 10015): con criterios
   tipados decide solo el código; sin tipados, o si alguno falla, el
   resultado es `necesita_decision`/`sin_revision` en vez de pagar un
   juez. Es la palanca «revisión barata» que hoy falta.
2. **Override del juez por task (opcional, más invasivo):** aceptar un
   campo `"juez": {"motor": ..., "modelo": ...}` en la validación
   (4381-4448), guardarlo en el task normalizado y que `_llm_review`
   (9947) lo anteponga a `_rev_cfg().orden`. Hoy no hace falta: el orden
   fijo ya pone Haiku al final y los locales $0 primero.
3. **Memoria por spec (para reducir el prompt del motor):** hoy solo hay
   on/off (`"memoria": false`). Hacen falta una de estas, en
   `mem_bloque_prompt` (10395):
   - `"memoria_max_caracteres": N` — baja el presupuesto de 12000 por task;
   - `"memoria_texto": "..."` — la VM inyecta el fragmento relevante ya
     recortado (la VM conoce el spec y puede extraerlo de MEMORY.md) y el
     gateway lo usa en vez de cargar los tres archivos;
   - `"memoria_secciones": [...]` — filtrar MEMORY.md por encabezados.
   La opción 2 es la más precisa y la que menos código toca en el gateway
   (un `if` al inicio de `mem_bloque_prompt`).

## 4. Recomendación

1. **No re-etiquetar el motor esperando abaratar la revisión: no
   funciona.** El re-etiquetado (`sonnet → haiku`) abarata motor y
   rondas, que es donde está el grueso del coste; la revisión ya es
   barata por diseño (locales $0 primero, Haiku como último recurso,
   checks $0 como puerta, segundo juez no declarado en la config actual).
2. **Palancas inmediatas desde la VM, sin tocar el gateway:** criterios
   tipados siempre que algo sea comprobable por código; `"revisar": false`
   en tareas triviales/R0; motor local cuando el trabajo lo permite; y
   sobre todo criterios precisos, porque cada ronda de corrección
   re-cobra motor + revisión (máx. 3).
3. **Un solo cambio en el gateway para el próximo spec:** `"revisar":
   "solo_checks"` — revisión sin juez LLM, solo checks deterministas.
   Es el único hueco real entre «revisión completa» y «sin revisión».
   El campo `revisor_model` por task no se recomienda: añade complejidad
   sin ahorro, porque el juez ya es el más barato disponible en cada
   momento (local $0, si no Haiku).
4. **Verificar en el PC** la sección `revision` de su `engines.json`
   (la copia del repo en la VM puede diferir): confirmar el orden de
   jueces y si existe `segundo_juez`, porque eso fija el coste real de
   la revisión hoy.
