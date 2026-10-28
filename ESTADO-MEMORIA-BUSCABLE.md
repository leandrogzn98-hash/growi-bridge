# Estado: memoria buscable (t-memoria-buscable)

Rama `Claude`, 28 oct 2026. **LISTO.**

Búsqueda **por palabras + fecha** en `MEMORY.md` y las notas diarias, sin
vectores y sin IA generativa encima. La memoria sigue siendo Markdown legible
en el PC.

## Qué había (fase A, t-memoria-pc) y qué se añadió
| Subfunción | Antes | Ahora |
|---|---|---|
| 1. Buscar desde la paleta | `mem_buscar` existía solo para la consola (`--buscar-memoria`), sin orden y cortando a los 40 | **«qué sé de X»** (también «que se de X» o «memoria: X») en la paleta → sección «Memoria: lo que sé de «X»» con hasta 12 resultados y «… y N más». Intro abre el archivo |
| 2. Fecha y origen | — | `mem_buscar_ordenado`: cada resultado dice de dónde sale («nota diaria del AAAA-MM-DD», «MEMORY.md (sección del AAAA-MM-DD)») y su fecha. Lo que no tiene fecha sale **«sin origen registrado»** |
| 3. Decaimiento = orden | — | Puntos = recencia (media vida 30 días) + refuerzo (el mismo hecho en varios sitios). **No se borra nada:** todo resultado sigue en la lista, solo cambia el orden |
| 4. «Recuerda esto» | **Ya existía** (`mem_recuerda`, en la paleta y el chat): escribe en MEMORY.md (duradero) o en la nota del día (episódico), lo comprueba en el archivo y dice dónde y por qué | Solo verificado |
| 5. Sin cargar toda la memoria | La carga en las tareas ya era acotada (MEMORY.md + hoy + ayer) | La búsqueda lee los archivos **en el momento de buscar**, sin caché de todo. **Contexto de grupo** (`canal` con «grupo»/«group» o `grupo: true`): `MEMORY.md` **no** se carga (`_tarea_de_grupo` en `mem_bloque_prompt`) |

## Verificación (`pruebas/prueba_memoria_buscable.py` → `pruebas/evidencia/memoria-buscable/evidencia.json`)
Memoria **de prueba** (temporal) con notas fechadas, una de hace 60 días.
Además, una medida sobre una **copia de la memoria real** del PC, de la que
solo se guardan cifras.

| | Prueba | Resultado |
|---|---|---|
| a | Paleta: «qué sé de Aqualine» | 6 resultados con su texto: «Aqualine paga a 30 días · nota diaria del 2026-10-28», «… · MEMORY.md (sección del 2026-10-18)», «Aqualine pidió el diseño nuevo…», «Aqualine prefiere WhatsApp…», «Reunión con Aqualine: precio viejo 120 $ · nota diaria del 2026-08-29», «Aqualine usa logo azul · MEMORY.md: sin origen registrado (sin fecha)» |
| b | Fecha y origen | Cada resultado lleva origen y fecha; el que no la tiene dice «sin origen registrado» |
| c | Lo viejo sigue, abajo | La nota de hace 60 días aparece (puntos 0.25), debajo de lo reciente; lo que no tiene fecha va al final. El hecho repetido sube por refuerzo |
| d | «recuerda esto: …» | Escribe en MEMORY.md y está en el archivo (comprobado). Con «para siempre», también en MEMORY.md |
| e | Sin cargar todo (memoria real copiada: 7 archivos, 47 KB) | «growi»: 59 resultados en **85 ms**; «claude»: 40 en 22 ms; «proxy»: 4 en 16 ms, leyendo los archivos en el momento. Grupo: con `canal: whatsapp-grupo`, el bloque de memoria **no trae MEMORY.md**; una tarea privada sí |

## FALTA / notas
- En la memoria real casi todo sale «sin origen registrado»: sus secciones de
  `MEMORY.md` no llevan fecha en el título. Es correcto: no se inventa fecha.
- «recuerda esto: … el lunes» lo guarda como duradero: la clasificación de
  la fase A (`mem_clasificar`) no ve «el lunes» como fecha. No se cambió.
- Sin vectores (decisión del spec). A estos tamaños no hacen falta.
