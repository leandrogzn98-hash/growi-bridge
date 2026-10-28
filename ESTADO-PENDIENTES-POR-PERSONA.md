# ESTADO — Qué falta por responder, por persona (t-pendientes-por-persona)

Rama `Claude`. Prueba: `pruebas/prueba_pendientes.py`. Usa una copia aislada y encargos **de prueba** (los
nombres son los del spec). Corre el mismo resumen de las 21:00 (automatización `resumen-2100` →
`_auto_resumen`). Evidencia: `pruebas/evidencia/pendientes/` (`evidencia.json` + `resumen-seccion.md`).

## LISTO
1. **Sección «Qué falta por responder» en el resumen de las 21:00** (`share\outbox\resumen-<fecha>.md`): una
   entrada por persona con lo que quedó pendiente y **desde cuándo**. Solo salen personas con pendientes
   reales; si no hay ninguno, dice **«nada pendiente»**. También está en Ctrl+K → «Qué falta por responder».
2. **Solo fuentes del Bridge**: las tareas del runner (sus encargos) y los encargos en la cola, que incluyen los
   mensajes que reenvías al asistente.
   - Un pendiente es un encargo con un verbo de respuesta (responder, contestar, enviar, mandar, escribir,
     llamar, confirmar, avisar) dirigido a una persona con nombre.
   - **Cada uno lleva su origen**: qué tarea o encargo y de qué fecha.
   - **No se leen chats ni el calendario**: esas fuentes no existen en este código.
3. **Marcar como hecho**: en la ventana, «Hecho» por pendiente. Se guarda en `pendientes-hechos.json` (git lo
   ignora) y **no vuelve** en el resumen siguiente. Cada línea del resumen lleva su id.
4. **Sin ruido**: como mucho **5 por persona**, los más recientes, y «y N más». El resumen cabe en una pantalla.

## Evidencia
| Criterio | Resultado |
|---|---|
| (d) cero | sin encargos con persona → «## Qué falta por responder — nada pendiente» |
| (a) por persona | Angelis (encargo en cola), William, Vero (`envíaselo a Vero`), Luis Galban: cada línea con «tarea t-… (fecha)» o «encargo en cola … (fecha)» |
| sin ruido | Luis Galban tiene 7 → se ven los 5 más recientes + «y 2 más» |
| (b) solo Bridge | las personas salen solo de familias del runner y encargos en la cola; lo que no pasó por Bridge no aparece |
| (c) hecho | marcado el de William → en el resumen siguiente **ya no está** |
| Tracebacks | 0 |

## FALTA
- **Con encargos reales**: esta prueba usa encargos de prueba. En la app, el resumen de las 21:00 (si está
  activo en Automatizaciones) ya lleva la sección.
- La detección es por frase («Responde a William…», «envíaselo a Vero»). Un encargo que no nombra a la persona
  con un verbo de respuesta no cuenta como pendiente: es a propósito, para no inventar.

## COMO PROBARLO
`python pruebas/prueba_pendientes.py` → `pruebas/evidencia/pendientes/`. En la app: Ctrl+K → «Qué falta por responder».
