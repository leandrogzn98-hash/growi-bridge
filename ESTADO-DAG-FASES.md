# Estado: planes con grafo de fases (t-dag-fases-030)

Rama `Claude`, 28 oct 2026. **LISTO.**

DAG mínimo, **sin motor de grafos**: el grafo es un campo del plan y la verdad
del plan es una tabla en `cola.db`. Las fases corren de una en una por la cola
de siempre (el paralelo es t-paralelo-seguro-030). La cadena lineal de antes
(`siguiente_fase`, tablas `planes` y `plan_fases`) sigue igual.

## Formato del plan
Un `.task.json` con `fases`:
```json
{"id": "p-ejemplo", "cwd": "C:\...", "motor": "claude", "revisar": true,
 "fases": [
   {"id": "A", "prompt": "…", "criterios": [{"tipo": "existe", "archivo": "a.txt"}]},
   {"id": "B", "prompt": "…"},
   {"id": "C", "prompt": "…", "depende_de": ["A", "B"], "al_fallar": "pedir_decision"}]}
```
`al_fallar` puede ser:
- `reintentar_una_vez`: si vuelve a fallar, pasa a pedir decisión;
- `saltar_con_aviso`: la fase queda «saltada» con aviso, y cuenta como hecha;
- `abortar_plan`: lo pendiente queda cancelado;
- `pedir_decision`: es el valor por defecto; el plan queda en
  `necesita_decision` y el resto intacto.

## Código (`growi-bridge.py`, bloque antes de `_process_one_impl`)
| Pieza | Qué hace |
|---|---|
| `dag_init()` (desde `cola_init`) | Tablas **`dag_planes`** (id, estado, orden resuelto, cwd, motor, revisar) y **`dag_fases`** (id, n, prompt, depende_de, al_fallar, criterios, estado, task_id, reintentos, motivo) |
| `dag_validar()` | **Antes de ejecutar:** ids, prompt, `al_fallar` válido, dependencias que existen, auto-dependencia y **ciclos** (orden topológico de Kahn). El motivo se da en palabras normales |
| `dag_ingestar()` (`_process_one_impl` lo llama si el JSON trae `fases`) | Valida → **registra el plan en SQLite** con su orden → encola las fases sin dependencias. Si el grafo está mal, el plan se rechaza y no corre nada |
| `dag_avanzar()` | Encola lo que ya puede empezar. **Fan-in:** una fase con dependencias solo arranca si **todas** están en ok **y** sus criterios tipados pasan **ahora** (`_check_tipado`, $0); si no, se aplica su `al_fallar`. Lo que depende de algo roto queda bloqueado. Cierra el plan |
| `dag_fallo()` | Aplica `al_fallar` |
| `dag_fase_terminada()` (al final de `_after_run`) | La tarea de una fase termina: si quedó aprobada o sin revisión, la fase queda terminada; si no, se aplica `al_fallar` |
| `dag_supervisor()` (al arrancar el runner, tras `supervisor_arranque`) | Recompone los planes a medias: las fases **hechas** no se repiten. Las que estaban en cola siguen con su checkpoint o, si su archivo se perdió, **vuelven a la cola sin duplicarse**. Si una fase ya tenía resultado final que el plan no llegó a apuntar, se apunta ahora. Las que no arrancaron se encolan cuando les toca |
| `dag_txt()` / `dag_reflejar()` | La **fila del plan en Tareas** (resultado + familia): «Plan X (necesita tu decisión). Lo bloquea la Fase 2 (B). Fase 1 (A): terminada; Fase 2 (B): necesita decisión (…); Fase 3 (C): sin arrancar — espera a Fase 2.» |
| `validate_task` | Deja pasar `dag` (a qué plan y fase pertenece la tarea) |

## Verificación (runner real, motor falso; evidencia en `pruebas/evidencia/dag/evidencia.json`)
`pruebas/prueba_dag.py` usa una copia aislada y `cola.db` propia. Los planes
pasan por `_process_one_impl` → cola → motor → `_after_run`. El motor falso
apunta cada fase que corre: así se cuentan las repeticiones.

| | Prueba | Resultado |
|---|---|---|
| a | A, B y C←{A,B} | Al registrar: A y B en cola, «Fase 3 (C): sin arrancar — espera a Fase 1 y Fase 2». Orden real: A, B, C. Final: las 3 terminadas, plan terminado |
| b | B falla con `pedir_decision` | Plan `necesita_decision`, «Lo bloquea la Fase 2 (B)»; A terminada; **C intacta** (pendiente, «espera a Fase 2») |
| c | Fan-in con B fallida | C **no corrió** (`C_corrio: false`) |
| c' | Fan-in con A y B en ok, pero el hecho que B garantizaba (`b2.txt` contiene «dato») cambió antes de C | C no arranca: «sus dependencias no pasan la validación: «B»: falta el marcador «dato»…». Su `al_fallar` (`abortar_plan`) deja el plan **abortado** |
| d | **Matar la app** (proceso aparte con `os._exit`) tras la fase A; además se borra el archivo de B (peor caso); rearranque (módulo nuevo, misma `cola.db`) | Supervisor: «plan p-corte: hechas A; a medias B (vuelta a la cola); sin arrancar C». Corridas del motor en todo el plan: **A, B, C, una vez cada una** (A no se repitió) |
| e | Ciclo A↔B y dependencia a «Z» | «El plan no se ejecutó: el plan tiene un ciclo: A ↔ B dependen unas de otras y ninguna podría empezar nunca…» y «…la fase «A» depende de «Z», que no existe en el plan». **No se ejecutó nada** y el plan con ciclo no llegó a registrarse |
| f | Lo que se ve | La fila de cada plan en Tareas lleva el texto de arriba: fases, estados, de quién depende cada una y qué lo bloquea |

## FALTA / notas
- **Decidir** en un plan que `necesita_decision` (reintentar la fase, saltarla
  o abortar desde la app): hoy el plan queda parado con el motivo a la vista,
  pero falta el botón. Queda para la vista de detalle de Tareas.
- Las fases de un plan corren **en serie** a propósito (sin paralelo).
