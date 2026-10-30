---
name: carruseles
description: "Carruseles de Instagram automáticos en el PC (4:5, 1080x1350): láminas HTML/CSS con el brandbook de la marca renderizadas a PNG con Chrome headless. Tipo 1 HTML puro, tipo 2 con imágenes generadas (solo motores sin costo extra; los de pago se reportan, no se activan), tipo 3 con fotos propias sin deformar. QC automático de cada lámina (dimensiones, texto cortado o fuera de pantalla, contraste medido, una sola acción), lotes sin supervisión, memoria de marca que aprende de las correcciones y caption sugerido."
version: 0.6.0
requires:
  env: []
  bins:
    - python
---

# Carruseles automáticos (Growi Bridge)

Convierte un brief (copy por lámina + marca) en un carrusel listo para subir: un PNG de 1080x1350 por lámina, el
caption y un reporte. Claude no dibuja: compone elementos web (tipografías, bloques, formas) y Chrome los fotografía.
Es la taxonomía de Andrea Vega: **tipo 1** HTML puro, **tipo 2** HTML + imágenes de un motor, **tipo 3** HTML + fotos
propias. Lo opera el Departamento de Diseño y Audiovisuales, junto a la skill `edicion-video`.

**Reglas que no se negocian**
1. El copy se aprueba antes de generar (GATE del brief de `summit-maker`). La skill no reescribe el copy: si una
   lámina no cabe o se pasa de palabras, el QC la rechaza y **tú** reescribes el brief.
2. Nada de cifras, testimonios ni datos inventados. Lo que falte es `[PENDIENTE: dato]`. Un brandbook con
   `[PENDIENTE]` en colores o fuentes **no se diseña** (sale «bloqueado»), y un dato que la marca pide (el RIF) y
   está pendiente hace rechazar la pieza.
3. Ningún gasto sin el OK de Leandro. El tipo 2 usa solo motores locales o de suscripción ya pagada; las APIs de
   pago se reportan y la skill no tiene código para llamarlas.
4. Sin gradientes ni plantillas genéricas: bloques de color sólido, asimetría, una idea por lámina (el QC rechaza
   cualquier gradiente).

## Requisitos (una vez por PC)

- Python con Pillow (`pip install pillow`).
- **Chrome Headless Shell**: lo deja `skills\edicion-video\instalar.ps1` en `%LOCALAPPDATA%\growi-video\remotion\...`.
  En este PC el Chrome y el Edge normales con `--headless=new` salen sin hacer nada; otra ruta se pone en
  `GROWI_CARRUSELES_CHROME`.
- Las fuentes del brandbook instaladas en Windows (Summit: Space Grotesk + Inter). Se copian a la carpeta del
  carrusel; si faltan, el QC rechaza porque se vería una sustituta.

## El brief (JSON)

```json
{
 "id": "c1-tareas",
 "marca": "summit-maker",
 "tipo": 1,
 "contexto": "Lo que añade el pie de foto (no repite las láminas).",
 "cifras_con_fuente": {"1.219": "CRM LearnU, conversaciones de Ads"},
 "laminas": [
  {"titulo": "Tu asistente no necesita **más prompts**", "texto": "Necesita saber qué haces cada lunes."},
  {"titulo": "Escribe tu semana en una hoja", "texto": "..."},
  {"titulo": "Antes del taller, ten esto a mano", "items": ["...", "..."]},
  {"titulo": "Lo único que necesitas es ejecución", "accion": "Comenta ASISTENTE"}
 ]
}
```

- `**palabra**` la resalta en el color de acento.
- `rol` es opcional: la 1.ª es `gancho`, la que trae `accion` es `cierre`, la que trae `items` es `lista`, y las demás
  alternan `punto` (numeral grande + franja) y `contraste` (mitad oscura). Con foto: `foto` y `foto-gancho`.
- Tipo 3: `"fotos": "C:\\fotos\\taller"`; cada lámina puede nombrar `"foto": "x.jpg"` y `"encuadre": "center 30%"`
  (CSS `object-position`). Las que no la nombran (gancho, punto, contraste) toman las siguientes en orden de nombre.
- Tipo 2: la lámina lleva `"imagen": "descripción de la imagen"`. Opcional `"motor": "codex"`.
- `caption` fija el pie de foto; si no, se sugiere `contexto` + el CTA de la marca.

## Uso

```
python skills\carruseles\scripts\carrusel.py --brief C:\briefs\c1.json --salida C:\carruseles\c1
python skills\carruseles\scripts\carrusel.py --brief C:\briefs\c2.json --salida C:\carruseles\c2 --tipo 3 --fotos C:\fotos\taller
python skills\carruseles\scripts\lote.py --briefs C:\briefs\semana\ --salida C:\carruseles\semana
python skills\carruseles\scripts\qc.py C:\carruseles\c1                 (vuelve a revisar una carpeta)
python skills\carruseles\scripts\motores.py                             (qué motores de imagen hay, $0)
python skills\carruseles\scripts\marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"
python skills\carruseles\scripts\marca.py lista
```

Salida en la carpeta: `lamina-NN.png` (o `lamina-NN.RECHAZADA.png`), `lamina-NN.html` (editable),
`lamina-NN.medidas.json`, `caption.txt`, `copy.md` (el copy con palabras por lámina), `reporte.md`, `reporte.json`,
`qc.json`, `carrusel.json`, `fuentes\`, y `fotos\` o `imagenes\` si hay. Código: 0 listo · 1 rechazado o error ·
3 bloqueado (sin motor gratis o brandbook incompleto). Una lámina tarda ~3 s (3 pasadas de Chrome).

## QC automático (`qc.py`)

Mira cada PNG de verdad y rechaza con diagnóstico:

| Check | Cómo |
|---|---|
| Dimensiones | PNG y viewport exactamente 1080x1350 |
| Fuentes | las del brandbook en estado `loaded` (no una sustituta) |
| Texto sin cortes | cada caja: alto y ancho de contenido contra su caja; el ajuste baja la letra hasta un mínimo legible (cuerpo 34 px, títulos 50) y si ni así cabe, rechaza diciendo cuántos px faltan |
| Dentro de pantalla | ningún texto recortado por su contenedor, fuera del lienzo ni a menos de 40 px del borde |
| Contraste | captura con texto contra captura con el texto transparente: contraste WCAG del color del texto contra el fondo real píxel a píxel (vale sobre fotos). Mínimo 4,5:1, o 3:1 desde 60 px |
| Una sola acción | exactamente una lámina con `accion` y un solo tipo de pedido en todo el copy (comentar, guardar, compartir, seguir, link en bio…) |
| Marca | palabras por lámina (regla de marca o corrección), palabras prohibidas, datos que la marca pide en la última |
| Fotos | `object-fit` cover/contain con escala uniforme (si no, «foto deformada»); aviso si se amplía más de ×1,6 |
| Sin gradientes | ningún `background-image` con gradiente |

Avisos (no rechazan): cifras sin fuente declarada en `cifras_con_fuente`, citas que parecen testimonios, vocabulario
de la guía anti-olor-a-IA (`documentos-humanos`), número de láminas fuera de lo que pide la anatomía de la marca,
última lámina sin checklist.

## Memoria de marca

- Brandbooks semilla en `skills\carruseles\marcas\`: `summit-maker` (completo, del brandbook v1.0),
  `violet-agency` y `salpro` (esqueletos con `[PENDIENTE]`: hasta completarlos, salen «bloqueado»).
- Correcciones en `%LOCALAPPDATA%\growi-carruseles\marcas\<marca>.json`, con historial; cada carrusel siguiente las
  aplica y el reporte dice cuáles. **Cuando Leandro corrija un carrusel, guarda la corrección con `marca.py` antes de
  rehacerlo.**
- Entiende: «máximo N palabras», «menos texto» (−25 %), «siempre el RIF en la última», «entre N y M láminas»,
  colores `#hex` (principal, acento, fondo), «fuente de titulares X», «nunca uses la palabra «x»», «el CTA es «…»».
  Lo que no entiende queda como nota y lo avisa; para fijar algo exacto: `--clave datos.rif --valor "J-..."`.

## Motores de imagen (tipo 2)

`motores.py` detecta sin gastar (PATH, nombres de variables, archivos de sesión, `codex features list` y puertos de
127.0.0.1; nada sale a internet). Orden: local ($0) > suscripción ya pagada > nada.

| Motor | Tipo | Estado en la skill |
|---|---|---|
| Stable Diffusion WebUI / Forge (`:7860 --api`) | local | adaptador escrito, sin probar (no hay WebUI en este PC) |
| ComfyUI, Ollama con modelos de imagen, diffusers | local | solo se detectan |
| Codex CLI (`image_gen` integrado) | ChatGPT Plus ya pagado | probado: ~2 min por imagen, sin `OPENAI_API_KEY` |
| Gemini CLI | sesión Google | solo texto: la imagen pide `GEMINI_API_KEY` (de pago) |
| APIs de Gemini, OpenAI, fal, Replicate, Stability, BFL, Ideogram, Leonardo, Higgsfield; conectores de claude.ai | pago | solo se reportan |

Sin motor gratis, el tipo 2 sale «bloqueado» con el reporte de motores. Con Summit Maker avisa que el brandbook pide
«fotos propias o ninguna»: una imagen generada puede leerse como stock.

## Modo Bridge (tarea del runner, motor `claude`)

```json
{
 "id": "t-carrusel-c1",
 "motor": "claude",
 "modelo": "sonnet",
 "cwd": "C:\\Users\\forte\\carruseles",
 "timeout_min": 20,
 "prompt": "Usa la skill carruseles. brief: C:\\briefs\\c1.json; marca: summit-maker; tipo: 1; salida: C:\\carruseles\\c1. Si el QC rechaza por texto, reescribe solo esa lámina respetando las reglas de la marca, guarda el brief corregido como c1.v2.json y repite una vez. Devuelve el resultado en JSON."
}
```

Entradas: `brief` (ruta o el copy por lámina en el prompt, que el agente guarda como JSON), `marca`, `tipo` (1/2/3),
`fotos` (carpeta, tipo 3), `motor` (tipo 2, opcional), `salida`; para lote, `briefs` (carpeta o lista).
Resultado (el agente lo devuelve y queda en `<salida>\reporte.json`):

```json
{"estado": "listo | rechazado por QC | bloqueado | error",
 "laminas": ["C:\\carruseles\\c1\\lamina-01.png", "…"],
 "caption": {"texto": "…", "origen": "del brief | sugerido"},
 "qc": {"ok": true, "laminas_ok": 5, "total": 5, "laminas": [{"lamina": 1, "ok": true, "checks": ["…"], "rechazos": []}]},
 "avisos": ["5 láminas; la anatomía de la marca recomienda 7-8"],
 "marca_aplicada": ["reglas.max_palabras_lamina = 12"],
 "motor_imagen": "codex", "imagenes": [{"lamina": 1, "segundos": 116.1, "costo": "suscripción ChatGPT Plus: $0 extra"}],
 "segundos": 15.3}
```

El agente **no** publica: entrega PNG + caption + reporte. Publicar (Instagram) es otra decisión de Leandro.

## Límites honestos

- El QC mide lo que se puede medir (cortes, contraste, palabras, una acción). El gusto, el hook y si el copy mueve
  a Jesús, Andreína o Don Ramón los juzga una persona.
- Las láminas salen de 7 composiciones fijas. Variar más es añadir un rol en `plantilla.py`.
- «Cifra sin fuente» es un aviso, no un rechazo: el script no sabe si un número es real.
- El tipo 2 con codex tarda ~2 min por imagen y gasta cuota del plan Plus.
