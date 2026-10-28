# ESTADO — Perfil «Sobre mí» (t-perfil-sobre-mi)

Rama `Claude`. Pruebas: `pruebas/prueba_perfil_gui.py` (app real en una copia, puerto 8797) y
`pruebas/prueba_perfil_runner.py` (runner real `_process_one_impl`; motor falso que guarda su prompt, y una
tarea real con Hermes 3 8B local, $0). Evidencia: `pruebas/evidencia/perfil-sobre-mi/`
(`evidencia.json`, `runner.json`, 3 capturas).

## LISTO
1. **Página «Sobre mí»**: cinco campos en palabras (Quién soy, Qué vendo / qué hago, Cómo escribo, A quién le
   hablo, Qué NO hago), CustomTkinter con respaldo clásico. Se guarda sola 0,7 s después de la última tecla en
   `memory\PERFIL.md`, junto a la memoria, en Markdown (sin JSON a mano). Se llega desde **Ajustes → General →
   «Editar mi perfil»** y desde la paleta («Editar mi perfil (Sobre mí)»). No tiene botón propio en la barra
   lateral, que ya no cabe a 700 px de alto.
2. **El perfil alimenta el prompt del runner**: `perfil_bloque_prompt` lo inyecta en cada tarea (cada campo
   recortado a 400 caracteres), justo antes del encargo. Se lee en cada tarea: un cambio vale para la
   siguiente, sin reiniciar. El log dice qué se inyectó y qué estaba vacío. No entra en contextos de grupo
   ni en el carril B (como MEMORY.md).
3. **Vacío = sin invención**: cada campo vacío va como «DESCONOCIDO… responde que no lo sabes y pregúntaselo;
   no lo deduzcas de nada (ni de las reglas, ni de la memoria, ni de internet)». Si el encargo pregunta por
   un campo vacío (pistas: «tono», «cómo escribo», «a quién le hablo»…), se añade un recordatorio detrás del
   encargo. Nada autocompleta el perfil: no hay ningún camino que lo rellene con datos de fuera.
4. **Visible, exportable y borrable**: «Exportar» (.md), «Abrir mi memoria» y «Borrar mi perfil», con
   confirmación que avisa de que el asistente se queda sin perfil. El aviso queda en la página, en un toast y
   en el log. Sin perfil, la siguiente tarea va sin él y el log lo dice.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) página | desde Ajustes → «Editar mi perfil» → página `sobremi`; escrito con el teclado real → `PERFIL.md` guardado solo («Guardado a las…; Vacío (no se inventa): …») |
| (a) paleta | «Editar mi perfil (Sobre mí)» → página `sobremi` |
| (b) cambio → siguiente tarea | tarea 1 recibe «Cómo escribo: DESCONOCIDO…»; tras escribir el tono, la tarea 2 recibe «Cómo escribo: Directo y cercano, tuteo, sin emojis.» (`b_cambio_visto: true`, prompts reales del runner) |
| grupo | una tarea de canal de grupo NO recibe el perfil |
| (c) tarea real, campos vacíos | Hermes 3 8B local: **parcial** (ver FALTA) |
| (d) exportar / borrar | exportado `.md` con el perfil; borrar pregunta, borra `PERFIL.md`, avisa, y la siguiente tarea va sin perfil |
| Tracebacks | 0 en las dos pruebas |

## FALTA
- **(c) con un modelo real solo se cumple a medias.** Con «Cómo escribo» y «A quién le hablo» vacíos, Hermes 3
  8B (local) contesta que «no se especifica en tu perfil a quién le hablas… lo mejor es preguntar», pero
  igual describe el tono como «cálido y claro, sin forzar el tío ni el pana». Eso lo saca de las reglas de
  estilo del asistente (la cabecera de la app), no del perfil. Se probaron tres redacciones (vacío → «sin
  dato», «DESCONOCIDO», el perfil al final y el recordatorio detrás del encargo); mejoró, pero el modelo
  pequeño sigue rellenando. La app no inventa nada ni lo autocompleta; lo que falla es la obediencia de
  un modelo de 8B. **Falta probarlo con Claude**, que gasta cuota de la suscripción: no se hizo.
- Prellenar el perfil desde MEMORY.md: no se hace a propósito, porque el spec pide que nunca se
  autocomplete. El botón «Abrir mi memoria» deja copiar a mano.

## COMO PROBARLO
`python pruebas/prueba_perfil_gui.py` y `python pruebas/prueba_perfil_runner.py` → `pruebas/evidencia/perfil-sobre-mi/`.
En la app: Ajustes → General → «Editar mi perfil», o Ctrl+K → «Editar mi perfil».
