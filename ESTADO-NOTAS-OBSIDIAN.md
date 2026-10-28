# Estado: notas locales estilo Obsidian (t-notas-obsidian-030)

Rama `Claude`, 28 oct 2026. **LISTO**, con Muse Link como FALTA explícita.

Notas en **Markdown plano** dentro de `notas\`, junto a la app (configurable
con `GROWI_BRIDGE_NOTAS`): un `.md` por nota, que se abre y edita con
cualquier editor. Nada de base opaca. Ventana **«Notas»** (paleta: «Notas»,
«Nota de hoy»).

## Qué hay (`growi-bridge.py`, bloque «notas» antes de `mem_buscar`)
| Subfunción | Cómo |
|---|---|
| 1. Markdown + frontmatter + nota diaria | `nota_escribir` / `nota_leer`: frontmatter `titulo`, `fecha`, `etiquetas`, `proyecto`. `nota_diaria()` crea `AAAA-MM-DD.md` la primera vez que se pide («Hoy» o «Nota de hoy») |
| 2. `[[wikilinks]]` y backlinks | `notas_indice()`: backlinks por nota («Qué enlaza aquí» en el panel) y **enlaces pendientes**: el destino no existe, se marca y **no se crea vacío** |
| 3. Grafo simple | `notas_grafo_ui()`: notas en un círculo agrupadas por proyecto, aristas por enlace, pendientes punteados. Filtro por **etiqueta** y por **proyecto**. Sin física ni 3D |
| 4. El asistente trabaja las notas | En la paleta, en palabras normales: **«nota: Título»**, **«nota de reunión / proyecto / idea: Título»**, **«enlaza A con B»**, **«resume la nota X»** (resumen **extractivo, local, sin IA**, y lo dice). **Captura en un clic:** «Capturar en notas: la tarea elegida» y «… lo escrito en el chat» (a la nota del día, con su origen). **Duplicados:** al crear avisa «ya tienes notas parecidas: …» (difflib). **Nunca fusiona ni borra** |
| 5. Plantillas y búsqueda | Plantillas **reunión** (asistentes, temas, acuerdos, siguiente paso), **proyecto** (objetivo, pendientes, enlaces) e **idea** (chispa, siguiente paso). `notas_buscar`: títulos > etiquetas > contenido, leído en el momento (como la búsqueda de t-memoria-buscable) |
| 6. Nube como espejo | `notas_espejo_sync(carpeta)`: espejo **bidireccional con una carpeta sincronizada** (OneDrive, Google Drive). Copia lo nuevo de cada lado; si una nota cambió **en los dos lados** desde la última sincronización es un **conflicto**: no se toca y se lista para que elijas. El original es `notas\` |

## Verificación (`pruebas/prueba_notas.py` → `pruebas/evidencia/notas/`)
| | Prueba | Resultado |
|---|---|---|
| a | Crear con plantilla | `Kickoff Aqualine.md` con frontmatter (`titulo`, `fecha: 2026-10-28`, `etiquetas: reunion`, `proyecto: Aqualine`) y la estructura de reunión. Nota diaria `2026-10-28.md` |
| b | Backlinks y pendientes | Aqualine ← Idea logo, Kickoff Aqualine (y Summit Maker tras «enlaza»). Panel: «Qué enlaza aquí: Idea logo, Kickoff Aqualine, Summit Maker» (captura 2). `[[Presupuesto 2027]]` → **pendiente**, sin archivo vacío creado |
| c | Grafo | Todos: 6 nodos, 3 aristas y 1 pendiente (captura `1-grafo.png`). Filtro proyecto «Summit Maker»: 1 nodo |
| d | Asistente | En la paleta: «Crear la nota «Revisión semanal» (plantilla reunion)», «Enlazar «Summit Maker» → [[Aqualine]]» (hecho y comprobado), «Resumir la nota… (extractivo, sin IA)». Crear «Aqualin» avisa de la parecida «Aqualine», y Aqualine sigue intacta. Captura del chat: «- (chat de Tareas, 01:51) Llamar a Aqualine el lunes» en la nota del día |
| e | Búsqueda | «aqualine»: 2 por título, 3 por contenido; «diseño»: por etiqueta; «arranque»: por contenido |
| f | Espejo | Primera vez: 6 subidas. Cambio en el espejo: 1 bajada. Cambio **en los dos lados**: **1 conflicto**, y cada lado conserva su versión (nada sobrescrito) |

## FALTA
- **Muse Link** como backend del espejo: hace falta su endpoint y su
  credencial, que no están en este PC. El espejo funciona con una carpeta
  sincronizada; el adaptador para Muse Link queda pendiente. **No hay nube
  configurada por defecto: local funciona solo y completo.**
- **Configuración guiada** del espejo en palabras normales (elegir carpeta,
  GitHub…): hoy es la función `notas_espejo_sync(carpeta)`, sin pantalla de
  configuración.
- **Resumir con IA:** el resumen es extractivo y local. Un resumen con modelo
  gastaría y no se pidió; si se quiere, va por el router.
- La ventana Notas es tkinter clásico (no CustomTkinter): la regla CTk de las
  superficies nuevas queda pendiente para esta ventana.
