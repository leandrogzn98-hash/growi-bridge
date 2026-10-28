# ESTADO — Paralelo seguro (t-paralelo-seguro-030)

Rama `Claude`. Prueba: `pruebas/prueba_paralelo.py`, en una copia aislada con share, cola, mutex y memoria
propios.
- La 1.ª tarea corre por el runner real.
- El vigía del 2.º hueco (`slot_vigia`) lanza la 2.ª en un **proceso aparte de verdad**
  (`growi-bridge.py --slot2`).
- Los motores son falsos en los dos procesos: un hook que solo se acepta en una instancia aislada.
- El repo git del caso del worktree se crea en la prueba, con una suite **pytest real**.

Evidencia: `pruebas/evidencia/paralelo/evidencia.json`.

## LISTO
1. **Máximo 2, solo si no se solapan.** `settings.paralelo_max` (por defecto 2; 1 = todo en serie).
   - El 2.º hueco es **otro proceso**: no mezcla el estado de la tarea que ya corre.
   - Reglas (`paralelo_decidir`): nunca dos Claudes (sesión Max única), nunca dos locales (VRAM), nunca el
     mismo motor dos veces.
   - Si las carpetas o archivos objetivo declarados se solapan → **en serie**, con el motivo en el registro.
2. **Worktree por tarea de código**: si las dos tareas son del mismo repo git (sin solaparse), la 2.ª trabaja
   en `git worktree add ../<repo>-<id> -b agent/<id>`. El registro `worktrees-agentes.json` (ignorado por git)
   deja ese worktree como carpeta permitida, porque su repo sí lo está. Al fusionar se quita
   (`git worktree remove` + `branch -d`).
3. **Merge explícito con test gate.** Nada se fusiona solo:
   - al terminar se corre la suite en el worktree (`settings.paralelo_tests`, o `pytest` si hay `tests/`);
   - se escribe `<tarea>.merge.md` con la rama, la base, qué va primero y qué tests corrió, con su salida;
   - «Fusionar» (Ctrl+K → «Fusionar la rama del agente», o `paralelo_fusionar`) **vuelve a correr los tests**
     y solo con exit 0 hace `merge --no-ff`; con un conflicto, `merge --abort` y no cambia nada;
   - con los tests en rojo, el agente **recibe el fallo y reintenta** (hasta 2 veces) en su worktree; después
     se para y decides tú.
4. **Detección de solapamiento antes de lanzar**: carpetas y archivos objetivo (`archivos`, `acciones.ruta`, o
   la carpeta de trabajo).
5. **La espera libera el hueco**: una tarea que pide aprobación en el 2.º hueco se aparca y el hueco pasa a la
   siguiente, con el paralelo activo.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) paralelo | Claude 05:19:22-05:19:36 y local 05:19:26-05:19:29: **el local corrió entero dentro del de Claude**; los dos ok |
| (b) en serie | Claude + Claude → «nunca dos Claudes a la vez (sesión Max única)»; local en `libre1\dentro` con Claude en `libre1` → «se solapan…: en serie»; ninguno se lanzó en el 2.º hueco |
| (c) worktree | la 2.ª trabajó en `repo-t-par-c2\subB` (rama `agent/t-par-c2`, base `main`); en `main` no aparece hasta fusionar; nota de merge escrita; «Fusionar» → tests exit 0 → `Merge agent/t-par-c2 (tarea t-par-c2, tests en verde)`; worktree quitado |
| (d) test en rojo | el agente rompe un test → `pytest` exit 1 → **no se fusiona** («los tests fallan (exit 1)»); el agente recibe el fallo (`-test1`, `-test2`, con la salida de pytest en el encargo) |
| (e) espera | con Claude corriendo, `t-par-e2` (borrar, R2) queda **esperando_aprobacion** y `t-par-e3` corre en el hueco y termina **mientras Claude sigue** |
| Tracebacks | 0 |

## FALTA
- **Solapamiento descubierto a mitad**: se decide antes de lanzar y el worktree aísla el código. Si una tarea
  escribe a mitad en la carpeta de la otra, **no se detecta**: Bridge no sabe qué proceso escribió cada
  archivo, y para eso haría falta rastrear las escrituras por proceso. Queda en el registro como limitación.
- El worktree aísla archivos, no la máquina (puertos, bases de datos, un `cp` hacia el checkout principal).
- El 2.º hueco solo se llena mientras corre una tarea en el 1.º; el bucle principal sigue siendo el de
  siempre.

## COMO PROBARLO
`python pruebas/prueba_paralelo.py` → `pruebas/evidencia/paralelo/`.
