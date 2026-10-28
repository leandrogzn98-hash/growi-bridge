# ESTADO — Agentes en paralelo (t-agentes-paralelos-030)

Rama `Claude`. Prueba: `pruebas/prueba_agentes.py`, en una copia aislada.
- El agente 1 corre por el runner real.
- El vigía lanza el agente 2 en un **proceso aparte de verdad** (`--slot2`).
- Los motores son falsos en los dos procesos (hook de instancia aislada). Si el encargo dice MUERE, el
  proceso del agente se mata una vez a mitad (`os._exit(3)`).

Evidencia: `pruebas/evidencia/agentes/evidencia.json`.

Encima del paralelo seguro (t-paralelo-seguro-030): el 2.º hueco es un agente, el orquestador reparte, vigila
y fusiona, y la fusión es la de ese spec (tests en el worktree, merge explícito).

## LISTO
1. **Orquestador**: cada agente = motor + su tarea (+ su worktree `agent/<id>` si es código del mismo repo).
   - El vigía reparte, vigila el proceso de cada agente y, al terminar, pasa el test gate y deja la nota de
     merge.
   - La fusión la decide Leandro: nunca automática ni silenciosa.
   - La revisión automática de cada agente es la de siempre, en su propio proceso.
2. **Topes reales**: `paralelo_max` (por defecto 2 en total).
   - Nunca dos Claudes (Max) ni dos locales (VRAM: un modelo grande a la vez).
   - Nunca más agentes que huecos: el 2.º trabaja en su worktree si toca el mismo repo.
   - Lo que no cabe **se queda en la cola con el motivo a la vista** («espera hueco: los 2 huecos están
     ocupados», «espera hueco: nunca dos Claudes…»), en la vista y en `cola.db`.
3. **Contexto mínimo por agente**: el agente del 2.º hueco recibe reglas + encargo + archivos de su tarea +
   perfil, **sin la memoria larga**. Lo que recibió cada uno queda en su resultado (`contexto_recibido`:
   caracteres por pieza y modo).
4. **Deduplicación por task_id**: si el id ya corre en un hueco, o consta en curso en la cola, no se asigna
   otro agente («ya tiene un agente activo: no se asigna otro»). Su fila de la cola no se toca.
5. **Fallo y reasignación**: si el proceso del agente muere a mitad, su tarea vuelve a la cola (corte +1),
   se reasigna con el **mismo task_id** y **sigue desde su checkpoint**. El otro agente sigue como si nada.
   El motivo queda en la cola, en el registro y en el resultado.
6. **Vista por agente** (Tareas → «Agentes», cada 3 s): hueco, tarea, motor, rama del worktree, estado, costo
   (o «sin dato»), tokens, progreso, y lo que espera en la cola con su motivo. El 2.º hueco escribe su propio
   estado y su vivo (`runner-status-slot2.json`, `runner-live-slot2.json`) para no pisar los del 1.º.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) dos agentes | Claude (`t-ag-1`, `repo\subA`) 05:29:18-05:29:43 y Hermes local (`t-ag-2`, en `repo-t-ag-2\subB`, rama `agent/t-ag-2`) 05:29:23-05:29:31, a la vez |
| (b) tope | con los 2 huecos ocupados, `t-ag-3` (codex) **no se lanza** y queda «espera hueco: los 2 huecos están ocupados»; entra cuando se libera uno |
| (c) dedup | un 2.º archivo con el mismo `task_id` que el agente 1 → «ya tiene un agente activo: no se asigna otro (deduplicación)»; no se lanzó |
| (d) reasignación | el agente de `t-ag-5` muere (salida 3) → «vuelve a la cola (corte 1) y sigue desde su checkpoint; el resto sigue» → reasignado → ok, «se reanudó desde el checkpoint (ronda 0)», **mientras el agente 1 seguía** (y el 1 terminó ok) |
| (e) vista | 2 filas (hueco, tarea, motor, rama, estado, costo, progreso) + la cola con su motivo |
| contexto | agente 2: `memoria: 0`, modo «agente del 2.º hueco (contexto mínimo)»; agente 1: memoria 1.963 car. |
| Tracebacks | 0 |

## FALTA
- La «contabilidad de VRAM» es la regla de clase («nunca dos locales a la vez»), no un cálculo con el semáforo
  de t-semaforo-vram-v2 por tamaño de modelo. Un local pequeño en CPU junto a otro en GPU no se permite
  todavía.
- El costo del agente 2 sale del vivo de su proceso; en esta prueba los motores son falsos, así que «sin dato»
  o $0.

## COMO PROBARLO
`python pruebas/prueba_agentes.py` → `pruebas/evidencia/agentes/`. En la app: Tareas → «Agentes».
