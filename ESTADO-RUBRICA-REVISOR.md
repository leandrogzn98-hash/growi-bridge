# ESTADO — Rúbrica, doble juez y calibración del revisor (t-rubrica-revisor-030)

Rama `Claude`. Prueba: `pruebas/prueba_rubrica_revisor.py`. Usa la app real en una copia (puerto 8797) y
tareas por el runner real `_process_one_impl`. El ejecutor es falso.
- Juez de (a): **real**, la cadena del revisor (llama-server no está, así que va al **Ollama local**, $0).
- Jueces «claude» de (b) y (c): falsos (`--juez <modelo>`), sin gasto.

Evidencia: `pruebas/evidencia/rubrica-revisor/` (`evidencia.json` + captura).

Buena parte del revisor ya venía de la Fase A: rúbrica, esquema, segundo juez y registro de calibración. Este
spec lo comprobó punto por punto y añadió lo que faltaba:
- la vista en la app (rúbrica, calibración con propuesta, costo y tiempo medidos por juez);
- el `veredicto` en tres palabras;
- el motor por revisión (`cadena_revisor`, de t-router-fallbacks).

## LISTO
1. **Rúbrica fija en el prompt** (`_armar_prompt_juez`): completitud, corrección, no-regresión y evidencia,
   de 1 a 5, con el umbral de `revision.rubrica.umbral_min`. Es la misma para todas las revisiones.
2. **JSON con esquema validado** (`RUBRICA_ESQUEMA` + `parse_veredicto`): 4 puntuaciones, `aprobado`, y
   `que_falta` con su `arreglo` concreto por debilidad. Si no valida, la revisión queda «sin revisión»,
   nunca aprobada. El registro trae `veredicto`: aprobado / rechazado / necesita_decision / sin_revision.
   El juez corre en solo lectura y sin herramientas que cambien nada: evalúa, el sistema decide.
3. **Doble juez solo en desacuerdo o riesgo alto**: el primero de la cadena siempre. El segundo (Haiku) solo
   si un check determinista falla o la tarea es R2/R3, **nunca en R0**. Si no coinciden →
   `necesita_decision` con los dos veredictos. El juez ve **la obra** (archivos tocados y su contenido), no
   solo el parte del motor.
4. **Calibración contra Leandro**: cada revisión se guarda (tabla `revisiones`). «Corregir la revisión: yo
   la apruebo / la rechazo» (Ctrl+K) deja la etiqueta. `calibracion-revisor.json` y la vista nueva (Ctrl+K
   → «Revisor») muestran la tasa de acuerdo y una **propuesta en palabras** («subir el umbral de 3 a 4…»).
   Nada se ajusta solo.
5. **Costo y tiempo medidos por juez**: la vista «Revisor» saca de cada `*.revision.json` lo que cada juez
   costó y tardó de verdad (`costo_usd`, `segundos`, tokens). Sin dato dice «sin medir»; no se inventa.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) revisión real | Ollama (Hermes 3 8B local): JSON válido con las 4 dimensiones (5/5/5/5) → `veredicto: aprobado`; 17-22 s, ~700 tokens, $0; `cadena_revisor` «llama: no_disponible → ollama: valido» |
| (b) JSON malformado | juez «roto» → `sin_revision` con la lista de lo que no cumple el esquema («completitud … llegó 9»); nunca aprobado |
| (c) R2 + check fallido | primer juez aprueba, `informe.txt` no existe → **segundo juez llamado** («un check determinista falló») → rechaza → `necesita_decision` («los dos jueces no coinciden») con los dos veredictos |
| (c) R0 | «tarea R0: nunca se gasta el segundo juez» |
| (d) el juez ve la obra | el prompt real incluye «LA OBRA (archivos tocados y su contenido…)» con `notas.txt` y sus 3 líneas |
| (e) calibración | 1 corrección etiquetada → acuerdo 0 % (1) y la propuesta «subir el umbral de 3 a 4 o pedir más evidencia… No se cambia solo» |
| (f) costo | Ollama medido ($0, tiempo y tokens reales). **Haiku: sin medir** (ver FALTA) |
| Tracebacks | 0 |

## FALTA
- **(f) Costo y tiempo reales de una revisión con Haiku**: no se corrió Haiku en vivo porque gasta cuota de
  Claude. La vista lo deja como «sin medir». En la prueba el «haiku» es un juez falso: su tiempo (0,1 s) no
  es una medida real, y en la app real no habrá juez falso. Para medirlo: una tarea R1/R2 con criterios y un
  check que falle (eso llama a Haiku), y mirar Ctrl+K → «Revisor».
- La calibración tiene 1 caso de prueba (en una copia); con el uso real se llenará sola cada vez que se
  corrija una revisión.

## COMO PROBARLO
`python pruebas/prueba_rubrica_revisor.py` → `pruebas/evidencia/rubrica-revisor/`. En la app: Ctrl+K → «Revisor».
