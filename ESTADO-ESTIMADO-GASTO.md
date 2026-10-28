# Estado: estimado de gasto antes de ejecutar (t-estimado-gasto-030)

Rama `Claude`, 28 oct 2026. **LISTO.**

Los tres dineros siguen separados: **$ real** (API) / **$ equivalente Max**
(sesión de suscripción, no dinero real) / **$0 local**. La cuota que te queda
de Max no tiene API pública: el estimado **dice** que no sabe si la tarea
cabe, y nunca muestra una cuenta atrás inventada.

## Código (`growi-bridge.py`, bloque antes de `_approval_needed`)
| Pieza | Qué hace |
|---|---|
| `estimar_gasto(task)` | **Entrada contada del prompt real** (`prompt_de_tarea`: reglas + encargo + contexto, contado con `_contar_tokens` del motor). **Reserva de salida** por tipo (respuesta corta 800 / código 6000 / documento largo 12000 tokens). Una ronda = entrada + 5 llamadas más leídas de caché + salida, con los **precios de `engines.json`** (los verificados contra 8 tareas reales). **Revisión:** Hermes $0 + posible Haiku. **Peor caso:** 3 rondas. Texto en los tres dineros, con «($ equivalente Max, no dinero real.)» |
| **Calibración** (`_historico_costes`) | Con ≥ 5 `cost_usd` reales del mismo motor (y tipo, si se puede saber) da el rango real p10–p90 de tus tareas. Sin eso: **«Sin histórico: estimado grueso, rango $a–$b»**. Nunca una tabla inventada |
| Umbral (`umbrales_gasto`, `_gasto_pide_aprobacion` dentro de `_approval_needed`) | Por defecto **$1 por tarea y $5 por plan** (`umbral_tarea_usd`, `umbral_plan_usd`). Si el peor caso pasa del umbral, se añade la acción **R2 «gasto estimado alto»**, que pide aprobación aunque el nivel sea «solo lo delicado»; con «Hazlo sin preguntar», no. La tarjeta de aprobación lleva el estimado en el motivo. Se cambia en **Ajustes → Permisos y seguridad → «Pedir permiso si puede costar mucho»** (por tarea $ / por plan $, se guarda al salir del campo) |
| Estimado visible antes de ejecutar | Al recoger la tarea, el estimado va a la familia (`estimado`) y al log, aunque no haga falta aprobación |
| **Tope por tarea** | Campo opcional `presupuesto_max_usd` del `.task.json`. Con claude se añade **`--max-budget-usd`** (nativo, solo con `-p`). Con cualquier motor, `_tope_superado` al principio de `_after_run` corta por **acumulado de la familia** (reintentos, rondas y revisiones): la tarea queda `necesita_decision` y no se abre otra ronda |
| **Circuit breaker** (`breaker_apuntar`, `runner_loop`) | 3 fallos transitorios seguidos → la cola **se pausa** y avisa. Se reanuda **a mano** (paleta: «Reanudar la cola (tras 3 fallos seguidos)»), con un mínimo de 10 min. El resumen de Tareas lo dice |
| **Costo por tarea completada** (`costo_por_tarea_completada`) | Por motor: todo lo gastado (familias, con rondas y revisiones dentro de la tarea padre, también las fallidas) / tareas que terminaron bien. Sale en el resumen de Tareas |

## Verificación (`pruebas/prueba_estimado_gasto.py` → `pruebas/evidencia/estimado-gasto/evidencia.json`)
Copia aislada; tareas por el runner real (`_process_one_impl` y `runner_loop`)
con un claude falso que declara su costo.

| | Prueba | Resultado |
|---|---|---|
| a | Estimado de una tarea corta (sonnet) | 1028 tokens de entrada (contados del prompt real), reserva 800, una ronda $0.01, revisión $0.00, **peor caso a 3 rondas $0.03**, en los tres dineros y con la etiqueta. «No sé si cabe en lo que te queda de Max…». Guardado en la familia **antes** de ejecutar |
| b | Umbral con «solo lo delicado» | La corta corre sin preguntar. La grande (documento largo, opus, 31 150 tokens): **peor caso $1.20 > umbral $1.00** → aparcada esperando aprobación con la acción R2 «gasto estimado alto»; el motivo de la tarjeta lleva el estimado entero |
| c | Tope $0.05, el motor gasta $0.08 | **`necesita_decision`**: «Parada por el tope de gasto: lleva $0.08 de $0.05 (con reintentos, rondas y revisiones)…». Comando de claude con tope: `claude -p hola --output-format json --max-budget-usd 0.50` |
| c | Circuit breaker | Tras 3 fallos de red: `pausado`. Con el **bucle real** del runner, una tarea en cola **no corre** durante la pausa. Reanudar antes de 10 min: «La pausa mínima es de 10 min…». Tras reanudar, **la tarea corre** |
| d | Costo por tarea completada | claude: gastado $0.54 en 5 familias, 2 completadas → **$0.27 por tarea completada** (incluye los $0.30 de una fallida) |
| e | Calibración | Sin histórico: «Sin histórico: estimado grueso, rango $0.01–$0.03». Con 9 resultados de claude (6 de prueba + 3 de la propia corrida): «Rango real de tus tareas parecidas: $0.08–$0.52 (9 resultados)» |

## FALTA / notas
- **Umbral por plan ($5):** se guarda y se muestra, pero no se aplica todavía.
  Haría falta sumar el peor caso de todas las fases de un plan con grafo
  (t-dag-fases-030) al ingresarlo.
- La fila de umbrales en Ajustes se probó compilando y con la app arrancada
  (gate/smoke), pero sin captura.
- El tope de los motores que no son claude corta **al final de cada ronda**
  (por acumulado), no a mitad de una ronda.
