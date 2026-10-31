# ESTADO — t-oficina-skins-050 (Oficina 0.5.0, spec 10 de 18)

**Fecha:** 30 oct 2026. **Veredicto:** el SISTEMA está LISTO y verificado: paper doll, `skin.json`, `validate_skins.py`, recoloreado al cargar, edición por JSON. Las skins de los 4 líderes y la de Runa existen con todas sus animaciones, pero el arte es **BORRADOR de script (IA)**. Faltan el retoque humano píxel a píxel (regla de licencia) y la paleta §1 (no está en el PC). Mismo bloqueo que el spec 9.

## Dónde está
- `oficina/arte/paperdoll.py`: compositor y recoloreado.
- `oficina/arte/validate_skins.py`: validador, con `--autoprueba`.
- `oficina/arte/generar_skins.py`: plantillas y skins (borrador).
- `oficina/arte/vista_skins.py`: capturas y prueba de edición.
- `assets/office/characters/base/`:
  - plantillas comunes: cuerpo, pantalón, ropa, brazos, corbata, cara, 4 estilos de pelo (delante y detrás)
  - juego de Runa (`*_runa.png`)
  - `efectos/` (z, duda, aviso)
- `assets/office/characters/skins/{clau,cody,luma,gemi,runa}/skin.json` + `accesorio.png`.
- `assets/office/palettes/`: `global.json` y una por departamento.

## LISTO (evidencia en `pruebas/evidencia/oficina-skins-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Paper doll | `paperdoll.py`, `hoja-*-x4.png` | Orden de capas: pelo_atrás, cuerpo (piel), pantalón, ropa, brazos, cara, pelo_frente, corbata, accesorio, efectos. Piel, ropa, brazos, pelo y corbata son **PNG modo P** con índices de plantilla (1 base, 2 oscuro, 3 claro); se recolorean con `putpalette` **una vez al cargar** y se cachean por (ruta, mtime). Cara y accesorios son RGBA. La «Z», el «?» y el «!» son efectos compartidos en `base/efectos/`. |
| 2 / b | `skin.json` | `skins/*/skin.json` | Campos: id, nombre, departamento, plataforma, rol, paleta, capas, colores {pelo, ropa, piel, corbata}, animaciones [{nombre, frames, fps, bucle}], efectos_compartidos, notas, estado_arte. Estructura de carpetas: `palettes/`, `characters/base/`, `characters/skins/<id>/`. El validador acepta los 5. |
| 3 / c | `validate_skins.py` | salida de `--autoprueba` | Comprueba: archivos que existen, dimensiones de hoja, frames con contenido por animación, modo P e índices 0–3 en las capas que se recolorean, colores RGBA dentro de la paleta, corbata solo en líderes, animaciones de líder completas, efectos compartidos. Detecta los 6 fallos inyectados (archivo que falta, dimensiones distintas, frames desiguales, campo que falta, líder sin corbata, JSON roto) con mensaje claro. **También encontró un fallo real del generador:** un azul de jeans suelto (`#254065`) que no era el tono oscuro de la paleta. Corregido. |
| 4 / d | 4 líderes con sus 8 animaciones | `hoja-{clau,cody,luma,gemi}-x4.png` | idle, escribir, caminar, café, teléfono, vagancia, celebrar y dormir (24 frames por líder). Clau: camisa y corbata naranjas, lápiz amarillo de 7 px en la oreja, pelo castaño a un lado. Cody: verde oscuro y corbata verde, auriculares al cuello. Luma: morado, pelo negro recogido, taza en **una** mano con la corbata a la vista. Gemi: azul, corbata `#2B5CB8`, casco amarillo. |
| 5 / e | Jerarquía: corbata de líder | `lideres-y-runa-idle-x4.png` | La corbata se ve en los 4 a 32×48. Lleva contorno de 1 px en el tono oscuro: sin él, la de Clau desaparecía sobre la camisa naranja (lo vi en la primera captura y lo corregí). Runa sin corbata. |
| 6 | Ojos unificados y expresiones | `expresiones-x4.png` | Óvalos negros de 1×3 con 1 px de brillo. normal, feliz, triste, sorprendido y concentrado cambiando solo ojos y boca sobre la misma cara. |
| 7 / f | Editar el JSON y recargar | `editar-json-antes-despues-x4.png`, `vista-skins.json` | Cambiar `colores.ropa` a `#007AFF` y quitar `capas.accesorio` en una copia del `skin.json` de Clau, y recargar: 221 píxeles distintos, la ropa sale azul y el lápiz desaparece. No se tocó Python. |
| 8 / g | Runa | `hoja-runa-x4.png`, `skins/runa/skin.json` | id `runa`, despacho, subgerente. Moño alto `#232323`, blazer negro, pin ámbar con «1», smartwatch y **tableta** (marco oscuro, pantalla crema con líneas: la única con tableta). Animaciones propias: idle, caminar, entregar, esperar (cronómetro), recoger, celebrar y dormir. Sin corbata. |

## FALTA
1. **Retoque humano del arte** (licencia §7.4) y **paleta §1**: el morado de Local (`#8C52C8`) es PROVISIONAL, y los colores de pelo y piel de cada líder los elegí yo (no hay fuente). Están en el `skin.json` para cambiarlos sin código.
2. **Defectos de arte vistos en las capturas:**
   - en «celebrar», los brazos levantados pisan el borde de la cabeza
   - Clau no es «más alta» (el esqueleto común no varía la estatura)
   - la blusa crema de Runa no se ve bajo el blazer
   - la pose de dormir de Runa no está apoyada en la mesa (eso lo pinta el motor con el plano)
   - el cartel «EN OBRAS» de Gemi va en su mesa: es del plano y del arte de decoración, no del sprite
3. **Tinte de pensamiento (§15):** Runa en azul `#007AFF` contra el blazer negro de §10. No lo decido: está anotado en su `skin.json`.
4. El compositor está probado con Pillow. Llevarlo al motor (Pygame-ce o Godot) es el mismo proceso (capas → recolor al cargar → caché) y queda para cuando el arte sea definitivo.

## COMO PROBARLO
```
python oficina\arte\generar_skins.py                  # regenera plantillas y skins (borrador)
python oficina\arte\validate_skins.py --autoprueba    # 5 skins OK + 6 fallos inyectados detectados
python oficina\arte\vista_skins.py salida\            # capturas x4 + prueba de editar el JSON
```
