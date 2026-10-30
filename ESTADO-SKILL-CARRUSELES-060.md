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

## CÓMO PROBARLO

```
python pruebas\carruseles\prueba_carruseles.py                 (a-f, ~3 min, $0)
python pruebas\carruseles\prueba_carruseles.py --con-imagen    (+ g: 1 imagen con Codex, ~2 min, cuota de Plus)
python skills\carruseles\scripts\motores.py                    (motores de imagen, $0)
python skills\carruseles\scripts\carrusel.py --brief pruebas\carruseles\briefs\a-summit-5.json --salida C:\carruseles\prueba
python skills\carruseles\scripts\lote.py --briefs pruebas\carruseles\briefs\lote --salida C:\carruseles\lote
python skills\carruseles\scripts\marca.py corregir --marca summit-maker "máximo 12 palabras por lámina"
```

Para la memoria real hay un detalle: la corrección de (e) se guardó solo en la carpeta temporal. Si quieres que el
máximo de 12 palabras valga para todos los carruseles de Summit, corre tú la última línea.
