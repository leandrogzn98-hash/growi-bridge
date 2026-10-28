# ESTADO — Proyectos (t-proyectos)

Rama `Claude`. Prueba: `pruebas/prueba_proyectos.py`. Usa una copia aislada y el runner real; el motor es
falso y apunta el prompt que recibe. La búsqueda de carpetas de los proyectos iniciales es **real, en este
PC**. Evidencia: `pruebas/evidencia/proyectos/evidencia.json`.

## LISTO
1. **Proyecto = tareas + chats + instrucciones + carpeta + guardrail** (+ modelo y asistente). Cada uno es un
   archivo `proyectos\<id>.json` (git lo ignora). Se crea con la ventana «Proyectos» (Ctrl+K): nombre,
   cliente, carpeta (con «Elegir carpeta…»), instrucciones y permisos, en palabras.
   - Las tareas que mandas desde la app llevan su proyecto.
   - Sus instrucciones y su memoria se le dan al asistente en cada tarea de ese proyecto.
2. **Cambio en un gesto** (`proyecto_activar`): permisos, modelo del chat, asistente y carpeta de las tareas
   nuevas, a la vez. El activo se ve en la **paleta** (primera sección: «Proyecto activo: X (cambiar)»), en
   la **bandeja** («Proyecto: X») y en **Tareas**, que solo enseña las del proyecto activo.
3. **Memoria por proyecto**: `memory\proyectos\<id>\MEMORY.md`, aparte de la general.
   - El runner usa la del proyecto **de la tarea** + la general, sin mezclarlas.
   - Buscar en la memoria desde otro proyecto marca el hallazgo: «de OTRO proyecto (Aqualine)».
4. **Iniciales reales**: Aqualine, Summit Maker y HAYAI.
   - La carpeta se busca **de verdad** (OneDrive, Documentos, Escritorio, perfil); si no está, la deja
     como **FALTA**, sin inventar una.
   - Las instrucciones son las líneas de MEMORY.md que nombran el proyecto; si no hay, «sin instrucciones
     todavía».
5. **Sin mezclar**: una tarea es de su proyecto (campo `proyecto`), y cambiar el activo después no la
   mueve. El **gasto por proyecto** (t-gasto-pronostico) agrupa por ese campo.

## Evidencia
| Criterio | Resultado |
|---|---|
| iniciales | Aqualine, Summit Maker y HAYAI creados. **En este PC no encontré ninguna de sus carpetas** → los tres con «FALTA: no encontré la carpeta…». Instrucciones sacadas de la MEMORY.md (de prueba): Summit «talleres hands-on», HAYAI «implementación de IA y automatización»; Aqualine «MEMORY.md no dice nada» |
| (a) agrupa | `Aqualine: t-aq-1, t-aq-2`; `Summit Maker: t-sm-1`. El prompt de una tarea de Aqualine trae «PROYECTO Aqualine… Escribe en tono comercial… Memoria del proyecto Aqualine…» |
| (b) un gesto | antes: permisos delicado, sin modelo, carpeta inbox → **Aqualine**: siempre, haiku, `clientes\Aqualine`, bandeja «Proyecto: Aqualine» → **Summit**: nunca, sonnet, `clientes\Summit Maker` |
| (c) memoria | el prompt de Summit NO trae «filtro X»; el de Aqualine sí. Buscar «filtro» en Summit → «de OTRO proyecto (Aqualine)»; en Aqualine, sin marca |
| (d) gasto | `Aqualine: 2 tareas, $0.04 equiv.`; `Summit Maker: 1 tarea, $0.02 equiv.` |
| paleta | primera sección «Proyecto» |
| Tracebacks | 0 |

## FALTA
- **Las carpetas reales** de Aqualine, Summit Maker y HAYAI: no están en este PC (o no con esos nombres). Se
  ponen en la ventana «Proyectos» → «Elegir carpeta…». Además, la carpeta tiene que estar en Carpetas para que
  las tareas la usen; si no, se avisa y se usa la de siempre.
- Las instrucciones iniciales salen de la MEMORY.md **de la app instalada**, que esta prueba no lee (usó
  líneas de prueba). En la app real se rellenan solas la primera vez que se abre «Proyectos».

## COMO PROBARLO
`python pruebas/prueba_proyectos.py` → `pruebas/evidencia/proyectos/`. En la app: Ctrl+K → «Proyectos».
