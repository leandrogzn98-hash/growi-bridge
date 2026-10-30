# ESTADO — Skill de carruseles automáticos (0.6.0, t-skill-carruseles-060)

Rama `Claude`, 29 oct 2026. La skill está en `skills/carruseles/`: `SKILL.md`, los brandbooks de `marcas/` y
`scripts/` (`carrusel.py`, `lote.py`, `qc.py`, `motores.py`, `marca.py`, `plantilla.py`, `render.py`, `comun.py`).
Pasa `python growi-bridge.py --validar-skills` con «frontmatter válido, sin secretos», y `ruff` sin errores. No toqué
`VERSION`.

## Antes de leer: qué copy usé

Todo el copy de las pruebas lo escribí yo para verificar la skill (`pruebas/carruseles/briefs/`). **Ninguno pasó
por tu aprobación**, así que no son piezas para publicar. No tienen cifras ni testimonios. La fecha y el precio del
taller van como `[PENDIENTE: dato]`.

Las fotos del tipo 3 son **sintéticas**: las generé en el PC, son un fondo con un círculo verde y el rótulo «FOTO DE
PRUEBA SINTETICA». Con el círculo se puede medir si la composición deforma la foto.

## LISTO (verificado en este PC)

Se corre con `python pruebas\carruseles\prueba_carruseles.py --con-imagen`. La evidencia queda en
`pruebas/evidencia/carruseles/`: un JSON por punto, los PNG, los reportes y `resumen-abcdefg.md`.

- **(a) Tipo 1, 5 láminas con Summit Maker: OK.**
  - Salen 5 PNG de exactamente 1080x1350, en 12-15 s (unos 3 s por lámina).
  - Usa Azul Summit #052048, Naranja Guaro #FA5102 y fondo #F7F8FA, con Space Grotesk + Inter de verdad cargadas
    (el QC mira el estado `loaded` de la fuente).
  - Lleva 5 composiciones distintas: gancho, numeral con franja, mitad oscura, checklist y cierre naranja con el
    CTA «Comenta ASISTENTE».
  - Todo el texto queda dentro de la zona segura y el contraste más bajo es 3,17:1, en el numeral naranja de
    230 px (el mínimo para texto grande es 3:1). El resto pasa de 4,7:1.
  - Ver `a-tira.png` y `a-reporte.md`.
- **(b) El QC rechaza láminas saboteadas: OK.** Saboteé una copia del carrusel (a):
  - **Lámina 3**, caja de texto forzada a 40 px: «texto cortado: … necesita N px de alto y su caja tiene 40 px
    (letra ya en el mínimo legible, 34 px)».
  - **Lámina 2**, título movido 700 px a la derecha: «texto recortado por su contenedor», «texto fuera de pantalla
    … x=700..1560» y contraste 1,0:1.
  - Las láminas 1, 4 y 5 siguen OK. Las rechazadas se renombran a `.RECHAZADA.png`.
  - El control (el mismo carrusel sin sabotaje) da OK.
  - Ojo: mi primer sabotaje (caja de 90 px) **no** cortaba nada, porque el texto cabía en 2 líneas. El QC acertó y
    la prueba estaba mal.
- **(c) Lote de 3 carruseles sin intervención: OK.** Salieron 3 de 3 listos (5, 6 y 5 láminas) en 38 s, con un
  `reporte.md` por carrusel y `lote.md`, que lista láminas OK, advertencias y tiempo de cada uno. Un carrusel que
  falla no para el lote.
- **(d) Tipo 3 con 3 fotos sin deformar: OK.**
  - Usé fotos de 3000x4000 (vertical), 4000x2250 (horizontal) y 2000x2000 (cuadrada).
  - En el PNG final, el círculo verde mide ancho/alto = **1,00** en las tres, así que no hay deformación. El QC lo
    confirma con «escala uniforme».
  - El texto va sobre una placa sólida, sin gradiente.
  - Control: forzar `object-fit:fill` da «foto deformada: escala 0,270 x 0,351».
- **(e) Una corrección guardada se aplica en el siguiente carrusel: OK.**
  - Antes de la corrección, el brief con una lámina de 18 palabras sale **listo**.
  - Guardé `marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"`.
  - Con el mismo brief, el siguiente carrusel sale **rechazado**: «18 palabras en la lámina; máximo 12 (regla de
    marca: máximo 12 palabras por lámina)».
  - Reescrito a 10 palabras, sale **listo** y el reporte dice «Correcciones de marca aplicadas:
    reglas.max_palabras_lamina = 12».
  - Extra: con «siempre el RIF en la última», la pieza se **rechaza**, porque el RIF de Summit Maker está
    `[PENDIENTE]` y no se inventa.
  - La prueba usó una carpeta de memoria temporal. La real (`%LOCALAPPDATA%\growi-carruseles`) ni existe todavía.
- **(f) Reporte de motores de imagen sin gastar nada: OK** (`f-motores.txt`, 14 s, $0).
  - La detección no generó imágenes ni salió a internet.
  - Locales (ComfyUI, SD WebUI/Forge, modelos de imagen de Ollama, diffusers): no hay ninguno.
  - De suscripción: **Codex CLI sí**. Tiene sesión de ChatGPT e `image_generation=true`, y usa la herramienta
    integrada, que no pide `OPENAI_API_KEY`.
  - Gemini CLI tiene sesión, pero solo da texto: la imagen pediría `GEMINI_API_KEY`, que es de pago.
  - De pago: no hay ninguna clave en el entorno (Gemini, OpenAI, fal, Replicate, Stability, BFL, Ideogram, Leonardo,
    Higgsfield). Los conectores de claude.ai se reportan y no se usan.
  - Pedir un motor de pago da error («la skill no lo activa»).
  - Un tipo 2 con un motor que no está sale «bloqueado», con el reporte de motores.
- **(g) Tipo 2 de verdad: OK.** Codex generó la foto de la lámina 1 (una mesa con laptop) en 116 s (12 933 tokens de
  Codex). Gastó cuota del plan Plus, **$0 extra**. El carrusel pasó el QC (`g-tira.png`). El reporte avisa que tu
  brandbook pide «fotos propias o ninguna» y que una imagen generada puede leerse como stock.
- **Memoria de marca**:
  - Summit Maker está completo, tomado del brandbook v1.0 de la skill `summit-maker`.
  - Violet Agency y SalPro tienen todo en `[PENDIENTE]`: en el PC no hay colores, fuentes ni RIF de ninguno de los
    dos. Hasta completarlos salen «bloqueado». No inventé paletas.
- **Modo Bridge**: el formato de la tarea y el del resultado están en `SKILL.md`, sección «Modo Bridge».

## Gasto

$0 en dinero. Lo único que se consumió es cuota de ChatGPT Plus: 2 imágenes de Codex, una en la prueba manual del
motor y otra en (g).

## FALTA

- **Brandbooks de Violet Agency y SalPro**: colores, fuentes, CTA, usuario de IG y el RIF de SalPro. Mientras
  falten, esas marcas no se pueden diseñar.
- **El RIF de Summit Maker**, si quieres usar «siempre el RIF en la última».
- **Probarlo como tarea real del runner**: el formato está documentado, pero no mandé ninguna tarea a la cola. Lo
  probado es la ejecución directa de los scripts.
- **Probarlo con copy aprobado y fotos reales del taller.** Con fotos reales, el QC de contraste mide sobre la foto
  (texto sobre placa sólida), pero no lo vi con fotos de gente.
- **Motores locales**:
  - El adaptador de SD WebUI/Forge está escrito y **no probado** (en el PC no hay WebUI).
  - ComfyUI y Ollama con imagen solo se detectan.
  - La RTX 3060 de 6 GB daría para un SD local. Instalarlo es decisión tuya.
- **Hook y gusto**: el QC no juzga si el copy mueve a Jesús, Andreína o Don Ramón.
- **Composiciones**: hay 7 fijas (gancho, punto, contraste, lista, cierre, foto y foto-gancho). Variar más es añadir
  roles.
- **Chrome**: en este PC, Chrome y Edge normales en modo headless salen sin hacer nada. La skill usa el Chrome
  Headless Shell que instaló la skill `edicion-video`. En otro PC hay que correr su `instalar.ps1` o poner
  `GROWI_CARRUSELES_CHROME`.
- **Los briefs de prueba tienen 3-6 láminas**, y tu anatomía pide 7-8: el reporte lo avisa en cada uno.

## Revisión del contenido de la evidencia (corrección del 29 oct 2026)

Abrí los reportes y medí los PNG, no solo comprobé que existan. El informe vive en
`share\outbox\ESTADO-SKILL-CARRUSELES-060.md`, con copias en la raíz del repo y en `share\inbox\`.

- `a-reporte.md`: LISTO, 5/5 láminas OK, cada una con «1080x1350, fuentes cargadas, texto dentro de pantalla y sin
  cortes».
  - `a-lamina-01/02/05.png` miden 1080x1350 con PIL.
  - El píxel (500, 1340) de esas láminas es #052048 (Azul Summit), #F7F8FA (fondo) y #FA5102 (Naranja Guaro): los
    colores del brandbook.
  - Las medidas de Chrome dicen `Tit 300 700: loaded`, `Cue 400: loaded` y `Cue 700: loaded`: el texto usa Space
    Grotesk (titulares) e Inter (cuerpo), no fuentes sustitutas.
- `b.json`: el sabotaje no tiene `reporte.md` propio, porque se corre con `qc.py` sobre una copia del carrusel (a).
  - Lámina 3: «texto cortado: … necesita 90 px de alto y su caja tiene 40 px (letra ya en el mínimo legible,
    34 px)».
  - Lámina 2: «texto recortado por su contenedor» y «texto fuera de pantalla … x=700..1560».
  - El control sin sabotaje da OK.
- `c-lote.md`: 3/3 listos (5/5, 6/6 y 5/5 láminas) en 38 s, con advertencias y tiempo por carrusel.
- `d-reporte.md`: LISTO, 4/4.
  - Las láminas 1-3 dicen «foto sin deformar (cover, escala uniforme 0.36 / 0.35 / 0.54)».
  - `d-lamina-01/02.png` miden 1080x1350 y el círculo verde mide ancho/alto 1,00.
  - En `d.json`, forzar `object-fit:fill` da «foto deformada: escala 0.270 x 0.351».
- `e-2-despues-reporte.md`: RECHAZADO. La lámina 2 da «18 palabras en la lámina; máximo 12 (regla de marca: máximo
  12 palabras por lámina)», y arriba dice «Correcciones de marca aplicadas: reglas.max_palabras_lamina = 12».
- `f-bloqueado-reporte.md`: BLOQUEADO, con la lista de motores. No hay ningún motor de pago activo, y la detección no
  generó imágenes ni salió a internet.

## Decisión pendiente de Leandro

La corrección «máximo 12 palabras por lámina» solo se probó en una carpeta temporal y **no está aplicada** a los
carruseles reales de Summit Maker. No la apliqué porque cambia tu regla de marca. Si la quieres, corre esto (queda
guardada en `%LOCALAPPDATA%\growi-carruseles\marcas\summit-maker.json`):

```
python skills\carruseles\scripts\marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"
```

Estado: **pendiente de tu confirmación.**

## COMO PROBARLO

Todo se corre desde la raíz del repo (`C:\Users\forte\source\growi-bridge`). Las pruebas guardan la memoria de marca
en una carpeta temporal, no en la real.

Batería completa (a-f, ~3 min, $0):

```
python pruebas\carruseles\prueba_carruseles.py
```

Uno por uno:

```
REM (a) carrusel tipo 1 de 5 láminas con Summit Maker
python skills\carruseles\scripts\carrusel.py --brief pruebas\carruseles\briefs\a-summit-5.json --salida C:\carruseles\prueba-a

REM (b) sabotaje del QC (automático: python pruebas\carruseles\prueba_carruseles.py a b)
REM     a mano: en C:\carruseles\prueba-a\lamina-03.html pon antes de </style>:  .cue{height:40px!important}
python skills\carruseles\scripts\qc.py C:\carruseles\prueba-a
REM     -> «lámina 03 RECHAZADA: texto cortado …» y queda lamina-03.RECHAZADA.png

REM (c) lote de 3 carruseles sin intervención
python skills\carruseles\scripts\lote.py --briefs pruebas\carruseles\briefs\lote --salida C:\carruseles\lote

REM (d) tipo 3 con fotos propias: 3 fotos en C:\fotos\prueba con los nombres del brief
REM     (1-vertical.png, 2-horizontal.png, 3-cuadrada.png); con las sintéticas: prueba_carruseles.py d
python skills\carruseles\scripts\carrusel.py --brief pruebas\carruseles\briefs\d-fotos.json --salida C:\carruseles\prueba-d --fotos C:\fotos\prueba

REM (e) corrección guardada. OJO: esto cambia tu memoria real de Summit Maker
REM     (la prueba aislada es: python pruebas\carruseles\prueba_carruseles.py e)
python skills\carruseles\scripts\marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"
python skills\carruseles\scripts\carrusel.py --brief pruebas\carruseles\briefs\e-largo.json --salida C:\carruseles\prueba-e
REM     -> rechazado: «18 palabras en la lámina; máximo 12»

REM (f) motores de imagen disponibles, sin gastar
python skills\carruseles\scripts\motores.py

REM (g, opcional) tipo 2 real: 1 imagen con Codex, ~2 min, gasta cuota de ChatGPT Plus ($0 extra)
python pruebas\carruseles\prueba_carruseles.py --con-imagen
```
