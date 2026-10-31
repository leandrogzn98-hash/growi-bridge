---
name: redactar-propuesta
description: "Redacta propuestas comerciales en borrador, una por prospecto de prospectos.csv: mensaje corto y una propuesta en Markdown con la oferta que dé el usuario, sin precios ni casos inventados. Nunca envía: solo deja archivos para revisar."
version: 0.1.0
entradas:
  - "oferta | ¿Qué ofrecemos? (servicio y para quién) | [PENDIENTE: oferta]"
  - "cuantas | ¿Para cuántos prospectos (los de mayor prioridad)? | 3"
salidas:
  - propuestas.md
---

# Redactar propuesta (agente de Ventas, Growi Bridge)

Lee `prospectos.csv` de la carpeta de la tarea y, para los `cuantas` de mayor prioridad, escribe en `propuestas.md` una
sección por prospecto con:
1. **Mensaje de primer contacto** (máximo 60 palabras): una idea, una pregunta, sin presión, tuteo cercano.
2. **Propuesta breve**: el problema que probablemente tiene (solo si lo dice la lista), qué ofrecemos (la entrada
   `oferta`), el siguiente paso propuesto (una llamada corta).

**Reglas**
- **BORRADOR.** Arriba de `propuestas.md` va la línea «BORRADOR — no enviado. Enviar es decisión de Leandro, uno por uno.»
- **Sin precios** salvo que la entrada `oferta` los traiga. **Sin casos de éxito, cifras ni testimonios inventados.**
  Si la oferta es `[PENDIENTE: oferta]`, escribe los mensajes con ese marcador donde iría la oferta.
- **No envíes nada** ni prepares envíos automáticos (nada de scripts de correo ni enlaces de WhatsApp con el mensaje).
- Si `prospectos.csv` no existe, escribe `propuestas.md` con «[PENDIENTE: prospectos]» y termina.

Responde con una línea: cuántas propuestas dejaste en borrador.
