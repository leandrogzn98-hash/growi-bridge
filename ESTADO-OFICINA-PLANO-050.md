# ESTADO — t-oficina-plano-050 (Oficina 0.5.0, spec 7 de 18)

**Fecha:** 30 oct 2026. **Veredicto:** LISTO. El plano son solo datos (`oficina/plano/plano.json`) y tiene su validador (`oficina/plano/validate_plano.py`); vale para Godot y para Pygame-ce. Sin arte, sin escenas.

## LISTO (evidencia en `pruebas/evidencia/oficina-plano-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Departamentos, mesas, sillas | `plano.json`, `plano.png` | Los 5 departamentos que pide el spec (Claude, Local, Taller 3D, Codex, Gemini), más Gerencia, Despacho y Sala de espera. Los 14 personajes tienen silla y mesa, cada mesa con su empleado (id de skin), su departamento y su rectángulo. Haiku tiene un escritorio pequeño en la esquina de Claude. Gemini tiene 2 sillas vacías con cartel («Flash — por instalar», «Pro — por instalar»). Local tiene 2 sillas «en obras» (Qwen y Gemma). La mesa de despacho de Runa queda entre la bandeja de entrada y los puestos, con el tablero de la cola encima. Runa no tiene silla. |
| 2 / b | Tablón y teléfono | `validacion.json` | El tablón (en curso, pendientes, esperando aprobación) está a 0 baldosas de la Gerencia. El teléfono, en [6,2], cae dentro de `mesa_growi`. La entrada está abajo en el centro, [24,29]. |
| 3 / c | Puntos de interés | `plano.json` | Café (cap. 2), ventana (2), baño (1, tras su pared con puerta), planta (1) y mesa del pasillo (3). La capacidad es igual al número de baldosas de acceso. `puntos_que_no_hay` está vacío: hoy están los 5. |
| 4 / d | Rejilla de pathfinding | `validacion.json` | Rejilla de 48×30 baldosas de 32 px, 4 vecinos, `teletransporte: false`, con 36 obstáculos rectangulares en el JSON. Un BFS desde la entrada alcanza 1267 baldosas, todas las sillas, todos los accesos, el frente del tablón, la silla del gerente (44 pasos) y la mesa de Runa. Pasos entrada → bandeja / mesa de Runa / puesto mediano: 9 / 15 / 32. |
| 5 / e | Taller 3D honesto | `plano.json` | El Taller 3D está tras su pared con puerta. Tiene buzón de Meshy, buzón de Tripo y un mensajero con mostrador de buzón y banco (`tecleo: false`). La ruta del mensajero va de los buzones al despacho. Gemini es un local en obras, con cartel y polvo. Ninguna mesa de los dos teclea. |
| 6 / f | Validador | `validacion.json` | `validate_plano.py` pasa. Con `--autoprueba` rompe copias del plano: detecta los 10 fallos inyectados (solape, silla encerrada, sin silla, capacidad, tecleo en el taller, teléfono fuera, tablón lejos, Runa con silla, JSON sin rejilla, una silla de Gemini menos) y da un mensaje claro en cada uno. |

## Decisiones tomadas (sin fuente a mano)
- El mensajero (taller) y los especialistas (Blender, Tripo) cuentan entre los 14 y el validador les exige silla y mesa. Para que nadie teclee donde no hay trabajo, su «mesa» no es un escritorio: el mensajero tiene un **mostrador de buzón** y los especialistas una **mesita de sala de espera** compartida.
- Gemi (líder de Gemini) tiene mesa, pero `tecleo: false`: el departamento está en obras. Su estado visible lo decide el spec 8.
- El vigilante tiene un taburete junto a la entrada. Está fuera de los 14.

## FALTA
- `INVESTIGACION-0.5.0-oficina.md` (§2.5 plano orientativo, §4.4 puntos de interés) no está en este PC. El plano sale del texto del spec, no del dibujo de la investigación. Cuando aparezca, contrastar la distribución.
- El departamento de Diseño y Audiovisuales (ficha `oficina/departamentos/diseno-audiovisuales.json`, t-oficina-depto-diseno-050) **no se añadió**: no está entre los 5 que pide este spec ni entre los 14. Hueco libre para él: x 30–36, y 9–17 (pasillo este). Su validador (`validar_departamento.py`) puede comprobarlo ya contra este `plano.json`.
- Los colores de `plano.png` son provisionales (PALETA-Y-SKINS no está en el PC). Es una imagen de revisión, no arte.

## COMO PROBARLO
```
python oficina\plano\validate_plano.py                       # PASA / FALLA con la lista
python oficina\plano\validate_plano.py --autoprueba --json   # + los 10 fallos inyectados
python oficina\plano\validate_plano.py --png plano.png       # dibujo de revisión
```
