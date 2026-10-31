# Diseño 0.5.2: #4 skills como unidades y #5 agente de ventas

**Fecha:** 31 oct 2026. **Estado:** propuesta de Claude, sin aprobar todavía por Leandro. Los componentes 1–3 tuvieron diseño aprobado antes de implementarse; estos dos no tenían ninguno escrito. Se implementa lo que no tiene riesgo y lo que exige su decisión queda marcado **[DECIDE LEANDRO]**.

## Punto de partida (lo que hay hoy, medido en el código)
- Una skill es una carpeta con `SKILL.md`: frontmatter (name, description, version, requires) más el cuerpo.
- El runner la **inyecta como texto al principio del prompt** cuando su *descripción* coincide con el encargo (máximo 3, `skills_para_texto`). Una tarea no puede pedir una skill concreta. La skill no declara entradas ni salidas. El resultado anota `skills_activadas` (nombres), pero no hay estadísticas por skill.
- Los workflows (#3) encadenan pasos con motor, criterios, acciones y revisión, pero no pueden decir «este paso usa la skill X».
- Los asistentes (`asistentes/*.md`) ya tienen perfil, tono, carpetas, guardrail y una lista de `skills`.

## #4 Skills como unidades
Que una skill sea una **pieza que se pide por su nombre y rinde cuentas**, no solo texto que el runner a veces añade.

1. **Pedirla por nombre.** El `.task.json`, un paso de workflow o `encolar_tarea()` llevan `"skill": "carruseles"` (o una lista).
   - La skill pedida se activa **siempre**, primero y sin depender de la descripción.
   - Si no existe o su `SKILL.md` no es válido, la tarea **no se encola**: `validate_task` la rechaza con el motivo.
   - Si le falta un requisito en este PC (programa o variable), se activa con el aviso «falta en este PC», igual que hoy.
2. **Contrato de la unidad** (frontmatter opcional, compatible con las skills de ahora):
   - `entradas: [{nombre, pregunta, por_defecto}]`: los valores van en el task (`"entradas": {...}`) y llegan al motor en un bloque «Entradas de la skill». Si falta una sin valor por defecto, la tarea no se encola, como pasa con los parámetros de workflow.
   - `salidas: ["*.png", "reporte.md"]`: se convierten en criterios tipados `existe` (la revisión comprueba que salieron), salvo que el task ya traiga los suyos.
3. **Estadísticas por skill:** `skills_estadisticas()` sobre los `.result.json`: usos (pedida o elegida por descripción), terminadas bien, costo mediano y última vez. Sin base nueva: sale de lo que ya se escribe.
4. **Verla:** `skills_vista()` (cada skill con contrato, requisitos en este PC, estadísticas y validez) y `/gateway/skills` con el token de siempre.
5. **No cambia:** la elección por descripción sigue igual para lo que no se pide; el tope de 3; las propuestas `SKILL_QUE_FALTA` en borrador.

## #5 Agente de ventas
Un asistente más, hecho de piezas que ya existen: **perfil + skills + workflows**, con la regla de oro de no enviar nada sin el sí de Leandro.

1. **Perfil `asistentes/ventas.md`:** tono comercial cercano; carpeta propia `ventas/`; guardrail «Preguntarme siempre»; skills `prospectar`, `redactar-propuesta` y `seguimiento`.
2. **Skills (unidades del #4) con contrato:**
   - `prospectar` (entradas: nicho, ciudad, fuente; salida: `prospectos.csv`): **solo fuentes que Leandro autorice** [DECIDE LEANDRO: ¿qué fuentes? Firecrawl y Apify son de pago. Hoy: solo una lista que Leandro deja en la carpeta].
   - `redactar-propuesta` (entradas: prospecto, oferta; salida: `propuesta-<prospecto>.md`): borrador, nunca enviado.
   - `seguimiento` (entrada: `pipeline.csv`; salida: `seguimiento.md`): quién toca hoy y qué decirle, en borrador.
3. **Workflow `ventas-semana`:** prospectar → redactar las propuestas de los N mejores → seguimiento. Cada paso es una tarea normal, con guardrail, revisión y costo estimado antes de lanzarla (#3).
4. **Envío: NO se implementa.** Mandar un correo o un WhatsApp a un prospecto es publicar hacia fuera: el runner ya lo trata como R2/R3 («enviar», «escribir a otras personas»). [DECIDE LEANDRO: canal (Resend o WhatsApp), remitente, plantilla legal y si alguna vez se envía sin aprobar una por una.]
5. **Qué negocio vende** [DECIDE LEANDRO]: HAYAI, Summit, SalPro… El perfil queda genérico, con `[PENDIENTE: oferta]`. No se inventan precios ni casos de éxito; la skill lo prohíbe igual que `carruseles`.

## Cómo se verifica
- #4: una tarea con `"skill"` activa esa skill aunque la descripción no coincida; una skill que no existe → no se encola; las `salidas` se convierten en criterios `existe`; las estadísticas cuadran con los `.result.json`; `/gateway/skills` responde 200 con token y 401 sin él. Todo en instancia aislada.
- #5: perfil y skills válidos (`skills_validar_todo`); el workflow `ventas-semana` pasa `wf_validar` y da costo estimado; una corrida real con una lista de prueba **inventada y rotulada** produce los borradores; ninguna acción de envío existe (búsqueda en el código y en el `.task.json`).
