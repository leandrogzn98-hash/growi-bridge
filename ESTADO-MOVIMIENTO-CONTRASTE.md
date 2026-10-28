# Estado: reducir movimiento y alto contraste (t-movimiento-contraste)

Rama `Claude`, 28 oct 2026. **LISTO**, con la sesión real en Night Sky como FALTA.

## Qué se hizo (`growi-bridge.py`, bloque antes de `_theme_init`)
| Pieza | Qué hace |
|---|---|
| `animaciones_sistema()` | Lee **`SPI_GETCLIENTAREAANIMATION` (0x1042)**: si Windows tiene los efectos de animación encendidos |
| `movimiento_permitido()` / ajuste **«Reducir movimiento»** (Ajustes → Apariencia) | `settings.json → reducir_movimiento`: **Seguir el sistema** (por defecto) / **Siempre animar** / **Nunca animar** |
| Sin movimiento | `_animate_power` dibuja el estado al momento (sin animación), `_pulse_loop` no hace latir el botón, la mascota no anima (`_mascot_play`, `_mascot_micro` y el tecleo de «trabajando»): **fotograma fijo**. Lo que se sabía por el movimiento sigue escrito (estado del botón, «Trabajando…» en Tareas) |
| `alto_contraste_sistema()` | Lee **`SPI_GETHIGHCONTRAST` (0x0042)**, flag `HCF_HIGHCONTRASTON` |
| `tema_alto_contraste()` (aplicado en `_theme_init`) | Con contraste alto, la app usa un tema hecho con los **colores del sistema** (`GetSysColor`): fondo (`COLOR_WINDOW`), texto (`COLOR_WINDOWTEXT`), botones (`COLOR_BTNFACE`), selección y foco (`COLOR_HIGHLIGHT` / `HIGHLIGHTTEXT`) y enlaces (`COLOR_HOTLIGHT`). Pasa por el mismo filtro de colores que los temas, así que también cubre los colores fijos de marca. Ajustes → Tema lo dice |

## Verificación (app real en 8797; `pruebas/prueba_movimiento_contraste.py` → `pruebas/evidencia/movimiento-contraste/`)
| | Prueba | Resultado |
|---|---|---|
| a | Windows **sin animaciones** (simulado dentro del proceso de la app; no se tocó el ajuste de Windows) | Con «Seguir el sistema», durante los 3 primeros segundos (incluido el saludo de arranque) la mascota **no se animó nunca** y el botón no tuvo animación; al cambiar el botón, sin animación en curso |
| b | Los 3 valores | Con Windows sin animaciones: sistema → no anima, **animar → anima** (la mascota vuelve a moverse), nunca → no anima. Captura del ajuste: `1-ajuste-reducir-movimiento.png` |
| d | Windows en **contraste alto** (detección simulada) | Log «temas: Contraste del sistema ((Windows), …, Windows tiene un tema de contraste)». Tokens de la app = colores del sistema: fondo `#ffffff` = COLOR_WINDOW, texto `#000000` = COLOR_WINDOWTEXT, barra lateral `#f0f0f0` = COLOR_BTNFACE, líneas = texto, enlace = COLOR_HOTLIGHT. Capturas `2-contraste-estado/tareas/ajustes.png`. Como el tema real de Windows no estaba en contraste, `GetSysColor` dio los colores normales del sistema |

Log sin tracebacks.

## FALTA (con procedimiento)
- **(c) La sesión real en Night Sky.** Cambiar el tema de Windows de todo el
  PC no se hizo sin pedirlo. **Procedimiento:**
  1. Configuración → Accesibilidad → Temas de contraste → **Night Sky** →
     Aplicar (o Alt izq + Mayús + Impr Pant).
  2. Arrancar Growi Bridge y abrir **cada página**: Estado, Carpetas, Skills,
     Pantalla, APIs, Modelos, Tareas, Recursos, Ajustes, Registro.
  3. Anotar, por página, lo que no se lee o se rompe.
  4. Sitios a revisar primero:
     - los **lienzos** (el botón grande, la mascota, la barra de recursos) se
       dibujan con colores propios y podrían no seguir la paleta;
     - las **superficies CustomTkinter** (Ajustes) reciben los colores del tema,
       pero sus botones redondeados podrían perder el borde;
     - los **toasts** de la bandeja.
  5. Volver al tema normal.
- Esas mismas zonas (lienzos, mascota, toasts) quedan como posibles FALTA
  hasta hacer la sesión: no se pudieron comprobar con colores de contraste
  reales.

Nota: con esto existe «Reducir movimiento», que t-ajustes-reorg tenía como
FALTA en Apariencia.
