# ESTADO — t-oficina-arte-base-050 (Oficina 0.5.0, spec 9 de 18: Fase A de arte)

**Fecha:** 30 oct 2026. **Veredicto:** el PIPELINE está LISTO y verificado; el ARTE es un BORRADOR. Hay dos bloqueos que no puedo resolver yo:
1. **`PALETA-Y-SKINS.md` §1 (los 24 colores) no está en este PC.** Solo está §15 (tintes).
2. **La licencia exige retoque humano píxel a píxel.** Lo que dibuja un script escrito por una IA no puede ser arte final.

Por eso Growi existe como borrador, rotulado así en su JSON, para validar formato, capas, hojas y render. El trazo final es de Leandro en Pixelorama.

## LISTO
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Paleta como archivo | `assets/office/paleta.json`, `assets/office/paleta.gpl` | **Parcial: 14 de 24 colores.** Cada uno sale con 3 tonos (oscuro: −28 % de valor; base; claro: 35 % hacia el blanco) y su fuente al lado. `.gpl` es formato GIMP, que Pixelorama importa (Paletas → Importar). Los hex de marca Claude, Codex y Gemini van «de memoria, no verificados (duda 24)». |
| 2 / b | Esqueleto común 32×48 | `assets/office/esqueleto/` | Chibi, cabeza de ~22 px y cuerpo de ~20 px, ancla [16, 47]. Una PNG por capa (cuerpo_ropa, cara, pelo, accesorio, efectos) más la compuesta y su JSON. Growi se construye sobre él (`generar_base.growi()` llama a `esqueleto()`). |
| 3 / c | Growi con 3 animaciones + dormir | `assets/office/personajes/growi.png`, `growi.json`, `capas/growi_*.png`, `growi-x4-8fps.png` | 4 filas en una hoja: idle 4 frames a 8 FPS, escribir 4 a 8 FPS, celebrar 4 a 8 FPS (sin bucle), dormir 2 a 2 FPS. RGBA con fondo transparente. JSON con nombre, fila, frames, FPS, bucle, ancla, capas y licencia. Peluche crema (`#E8D8C0`, color muestreado de la mascota), capucha, suéter negro de cuello alto, jeans, ojos ovalados con brillo de 1 px, rubor de 2 px, sin nariz, corbata ámbar y teléfono. Dormir: cabeza ladeada 2 px, ojos de rayita, cuerpo 3 px más encogido, respiración de 1 px. |
| 4 / d | Pipeline de punta a punta | `render.json`, `growi-x4-8fps.png` | PNG + JSON → Pygame-ce con NEAREST ×4: 14 frames **precalculados al cargar** (1,3 ms), 0 escalados en el bucle, 29,9 FPS de pantalla con animaciones a 8 FPS. **Sin difuminar:** 15 colores en la hoja y 15 en el render ×4, 0 colores nuevos. La «Z» compartida va encima de dormir. |
| 4 / d | Duda 22 | docs oficiales (pixelorama.org/user_manual/cli) | El CLI de Pixelorama 1.x tiene `--export --spritesheet` y `--json` («Export the JSON data of the project»), además de `--scale`, `--frames` y `--split-layers`. Es el JSON del proyecto, no un atlas por animación: por eso el JSON de metadatos lo escribe nuestro script (`growi.json`). **No verificado de primera mano:** Pixelorama no está instalado. |
| 6 / f | Pillow | `python -c "import PIL"` | **Pillow 13.0.0** instalado. |
| 7 / g | SOURCES.md | `assets/office/SOURCES.md` | Con la regla de licencias. 0 assets de terceros. Los propios están marcados como borrador o parcial. |
| 8 / h | Referencia de Runa | `assets/office/personajes/RUNA-REFERENCIA.md` | Moño alto `#232323`, blazer negro, blusa `#FFF6DC`, jeans `#33598C`, pin ámbar «1», smartwatch, la única con tableta, sin silla, duerme apoyada en la mesa de despacho. Sobre el esqueleto común. Anota el tinte azul de §15. |
| 6 | Reglas de arte | `generar_base.py` | Contorno con el tono oscuro de la base (crema oscuro en la cabeza). Negro puro solo en el suéter (identidad de marca). Sombra dura de 1 tono, sin gradientes. Una sola luz, arriba a la izquierda (brillo en la cabeza y borde izquierdo del suéter). |

## FALTA
1. **Paleta completa de 24:** traer `PALETA-Y-SKINS.md` (§1) al PC. Faltan, entre otros, el morado de Local y el azul Summit. El frambuesa `#C2185B` del depto de Diseño solo está propuesto.
2. **Retoque humano de Growi, del esqueleto y de la «Z» en Pixelorama:** bloqueo de licencia. Hoy son borradores (`estado_arte` en cada JSON).
3. **`.pxo` (el negativo editable):** solo se crea desde Pixelorama. Paso para Leandro: abrir las capas `capas/growi_*.png` como capas de un proyecto 32×48, guardar `growi.pxo` en `assets/office/personajes/` y exportar con `Pixelorama.exe --headless -- growi.pxo --export --spritesheet --output growi.png`.
4. **Pixelorama no está instalado:** duda 22 sin confirmar de primera mano (ver arriba).
5. **Las 5 sprites de prueba** (`oficina-sprites-prueba/`: gerente-growi, lider-claude, lider-codex, lider-gemini, lider-local) **no están en este PC.** Se trabajó desde la descripción escrita. Correcciones de §7 que quedan para los specs 10–11: lápiz de Clau de 6–8 px, ojos unificados (óvalo negro con 1 px de brillo, ya aplicado en Growi), corbata de Gemi `#2B5CB8` (está en la paleta), corbata de Luma visible por encima de la taza, rubor `#F2A0A8` de 1–2 px (aplicado), canvas y proporción unificados (esqueleto común).

## COMO PROBARLO
```
python oficina\arte\generar_base.py                      # regenera paleta, esqueleto, growi y z
set PYTHONPATH=oficina\mediciones\.venv\Lib\site-packages
python oficina\arte\render_prueba.py --captura growi.png # x4 NEAREST, 8 FPS, comprueba 0 colores nuevos
```
