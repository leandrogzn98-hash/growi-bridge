# Estado: revisión «solo_checks» (t-revision-solo-checks)

Rama `Claude`, 28 oct 2026. **LISTO.**

`"revisar": "solo_checks"` es un modo nuevo entre la revisión completa y no
revisar. Corre solo los checks deterministas ($0) y nunca llama a un juez LLM:

| Situación | Resultado |
|---|---|
| Hay criterios tipados y todos los checks en verde | **aprobado** |
| Algún check en rojo | **necesita_decision** (nunca aprobado contra un hecho) |
| No hay criterios tipados (solo frases, o nada) | **necesita_decision** (nunca aprobado en silencio) |

`"revisar": true` y `"revisar": false` siguen igual.

## Líneas exactas cambiadas (`growi-bridge.py`)

| Línea(s) nuevas | Función | Cambio |
|---|---|---|
| 4460-4463 | `validate_task` | `"revisar"` acepta `"solo_checks"` (también `"solo-checks"`, sin mayúsculas) y lo deja normalizado como `"solo_checks"`. Cualquier otro valor sigue como antes: `data.get("revisar", True) is not False` |
| 10159 | `review_task` | `solo = task.get("revisar") == "solo_checks"` |
| 10168-10170 | `review_task` | el `.revision.json` lleva `"modo_revision": "solo_checks"` o `"completa"`. La regla «sin criterios: aprueba si el resultado no está vacío» ya no se aplica con `solo_checks` |
| 10191-10192 | `review_task` | tras los checks deterministas (y el «parado»), con `solo` → `return _decision_solo_checks(...)`, **antes** de `_llm_review` y del segundo juez |
| 10281-10307 | nueva `_decision_solo_checks` | la decisión de la tabla de arriba; `cost_usd 0.0`, `jueces_intentados []`, `segundo_juez.llamado false`, y una línea en el registro |

`_after_run` no cambió: `"solo_checks"` es verdadero, así que entra en la rama
de revisión. Con `necesita_decision` el flujo existente decide sin otra ronda.

**Sin tocar:** `engines.json`, `CRIT_TIPOS`, `MAX_ROUNDS`, el segundo juez, la
rama de `"revisar": true` y la de `false`.

**Por qué `necesita_decision` y no `no_aprobado` con check en rojo:** el
criterio del spec pide «necesita_decision o sin_revision». Además, sin juez no
hay quien guíe otra ronda, así que decide Leandro con el `que_falta` de los
checks.

## Verificación con tareas reales
`pruebas/prueba_solo_checks.py` carga una **copia** de `growi-bridge.py` en
una carpeta temporal y pasa cada tarea por el camino real:
`_process_one_impl` → `validate_task` → cola → motor → `_after_run` →
`review_task` → `<id>.revision.json`.
- El motor y el juez son un `claude -p` falso: el motor contesta «hecho» y el
  juez contesta un veredicto JSON válido.
- Se cuentan las llamadas a `_llm_review` y `_llamar_juez`.
- Evidencia: `pruebas/evidencia/solo-checks.json`, y la misma batería con el
  código **anterior** en `pruebas/evidencia/solo-checks-codigo-anterior.json`.

| Caso | Ahora | Con el código anterior |
|---|---|---|
| (a) `solo_checks` + 2 tipados que pasan (`existe`, `contiene «hola»`) | **aprobada**, `modo_revision: solo_checks`, juez llamado **0** veces, `cost_usd 0.0`, `veredictos []` | sin_revision; llamaba a la cadena de jueces |
| (b) igual + `contiene «adios»` (falla) | **necesita_decision**, `que_falta`: «falta el marcador «adios» en …hola.txt», juez **0** veces | no_aprobado y otra ronda; juez llamado |
| (c) `solo_checks` + solo una frase | **necesita_decision**: «la tarea no trae criterios_tipados…», juez **0** veces | sin_revision; juez llamado |
| (d1) `revisar: true`, R0 | sin_revision, `modo_revision: completa`; cadena de jueces llamada (locales no disponibles, Haiku omitido en R0) | **igual** |
| (d3) `revisar: true`, R1 | **aprobada** con el veredicto del juez `claude` (`valido`, aprobado), `modo_revision: completa` | **igual** |
| (d2) `revisar: false` | sin_revision, sin juez, **sin `.revision.json`** | **igual** |

**(e) Modo en el `.revision.json`:** a, b y c dicen `"modo_revision":
"solo_checks"` y `"motor_revision": "checks deterministas (revisar:
solo_checks, sin juez, $0)"`; d1 y d3 dicen `"completa"`. Con `revisar:
false` no hay `.revision.json` (como antes; no se cambió), así que ahí no
queda modo escrito. Su `result.json` y la familia quedan en `sin_revision`.

**FALTA:** el juez de (d3) es el `claude -p` falso, no Haiku de verdad. Se
quiso así para no gastar: lo que se prueba es que el camino `true` llama a la
cadena de jueces y usa su veredicto igual que antes.

## Cómo usar `solo_checks` desde un spec
Campo `"revisar": "solo_checks"` en el `.task.json`. Los criterios tipados van
en `criterios` como objetos (`existe`, `lineas`, `contiene`, `compila`,
`comando`):
```json
{
  "id": "t-ejemplo-rutina",
  "prompt": "Añade la funcion saludar() a util.py y que compile.",
  "motor": "claude",
  "cwd": "C:\\Users\\forte\\growi-bridge\\share\\inbox",
  "revisar": "solo_checks",
  "criterios": [
    {"tipo": "contiene", "archivo": "util.py", "texto": "def saludar("},
    {"tipo": "compila", "archivo": "util.py"},
    {"tipo": "comando", "comando": "python -m pytest -q tests/test_util.py", "exit": 0}
  ]
}
```

**Conviene:** specs rutinarios donde los criterios tipados lo cubren todo
(existe, contiene, compila, un comando de tests). Ahí el juez no aporta nada y
se ahorra su pasada.

**No conviene:**
- specs sin criterios tipados (quedarán en `necesita_decision`);
- specs donde hace falta juicio que el código no comprueba: calidad de un
  texto, diseño, «que no rompa nada», UX;
- specs R2/R3, donde el segundo juez es parte de la seguridad.

Ahí, `"revisar": true`.

## Cómo repetir
```
python pruebas/prueba_solo_checks.py
# contra otra version: PRUEBA_GB_ORIGEN=<ruta growi-bridge.py> PRUEBA_SALIDA=otra.json python pruebas/prueba_solo_checks.py
```
