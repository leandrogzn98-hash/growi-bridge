---
name: seguimiento
description: "Plan de seguimiento comercial en borrador: a partir de prospectos.csv y propuestas.md, escribe seguimiento.md con a quién tocar, cuándo y qué decirle en un recordatorio corto. Nunca envía mensajes ni agenda nada."
version: 0.1.0
entradas:
  - "dias | ¿Cada cuántos días se hace seguimiento? | 3"
salidas:
  - seguimiento.md
---

# Seguimiento (agente de Ventas, Growi Bridge)

Con `prospectos.csv` y `propuestas.md` de la carpeta de la tarea, escribe `seguimiento.md`: una tabla con prospecto,
fecha sugerida del siguiente contacto (hoy + `dias`, luego + `dias` × 2) y un recordatorio de máximo 30 palabras para
cada uno, más una sección «Qué falta para poder enviar» con los `[PENDIENTE: …]` que haya.

**Reglas**
- **BORRADOR**: arriba, «BORRADOR — nada se envía ni se agenda solo.»
- No envíes, no agendes, no crees eventos de calendario ni recordatorios en otras apps.
- No inventes respuestas de los prospectos ni estados («ya respondió»): si no lo dice un archivo, no lo sabes.

Responde con una línea: cuántos seguimientos dejaste planificados.
