# ESTADO — Estadísticas, píldoras de filtro y tarea en curso fijada (t-tareas-estadisticas-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_tareas_estadisticas.py 100` y `… 150`.
  - Arranca la app real desde una copia, en el puerto de prueba 8797 y en tema oscuro.
  - Siembra **54 tareas** en 8 estados, 3 resultados de hoy con costo y una tarea corriendo en
    `runner-live.json`.
- Evidencia: `pruebas/evidencia/tareas-estadisticas/` (`evidencia-100.json`, `evidencia-150.json` y 4 capturas
  por DPI).

## LISTO
1. **Fila de 3 estadísticas** (CustomTkinter, con la clásica de respaldo), arriba de la página, bajo el resumen:
   - **En curso**: familias en `en_curso`/`revisando` más la que corre en `runner-live.json`.
   - **Aprobadas hoy**: familias `aprobada` actualizadas hoy.
   - **Gasto de hoy**: de `day_by_model()`, la **misma fuente** que el consumo vivo y la tarjeta Gasto: real ·
     equivalente Max · local $0. Si no se puede leer: «sin dato».
2. **Píldoras de filtro** sobre la tabla: Todos, En curso, Aprobadas, Necesita decisión, **Sin revisión** y
   Fallidas.
   - Cada una con su **contador real**, filtra la tabla al pulsarla.
   - Tinte por estado: verde aprobadas, azul en curso, naranja necesita decisión. La activa lleva borde de 2 px.
   - Si no caben, pasan a otra fila (a 150 % lo hacen).
   - Debajo hay una **explicación en línea** de «Necesita decisión» y «Sin revisión», los estados heredados.
     No se esconden.
   - La tabla ahora enseña hasta 300 filas (antes 40), para que el contador cuadre con lo que se ve.
3. **Tarea en curso fijada** sobre la tabla, **fuera de ella**: al desplazar las 54 filas sigue a la vista.
   - Muestra «● Trabajando ahora: <id>» con motor, tiempo y coste vivo (de `runner-live.json`, repintado cada
     ~5 s).
   - Al terminar, se fija la siguiente en curso de la cola.
   - Si no queda ninguna: «Ninguna tarea corriendo ahora», sin esconderse y sin un cero falso.
4. **Tabla sin cambios de fondo**:
   - sigue siendo `ttk.Treeview` con las mismas 8 columnas;
   - la fila seleccionada va en **`#222224`** en el tema oscuro (en claro, el azul claro de siempre);
   - el estado se muestra como punto + etiqueta (spec #1).
5. **En vivo**: estadísticas, contadores y fijada se repintan cuando cambia la cola. La fijada además cada ~5 s
   para el tiempo y el coste. No hay que reiniciar y la ventana no se congela (`_refresh_tasks_ui` solo repinta
   si cambió algo).

Arreglos de paso:
- **La fila viva «Trabajando…» ya no se cuela** en la tabla con una píldora que no incluye «en curso». Antes
  descuadraba el contador.
- **«Esperan tu aprobación»** se dibuja encima de la fijada, no entre las píldoras y la tabla.
- **`start_availability`** pintaba el mapa desde su hilo. Tk solo admite llamadas desde el hilo de la ventana:
  era el `TclError: bad window path name` al cerrar. Ahora pinta con `_ui_call`.

## Evidencia (100 % y 150 % dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) fijada | «● Trabajando ahora: t-corriendo-01 / Claude Opus 5.5 · lleva 1:15 · ~$0.12 eq. (en vivo)». Con la tabla bajada hasta la **última de las 54 filas**: `ultima_fila_visible: true`, `fijada_visible: true` |
| (b) al terminar | `runner-live` en `terminado` y la familia `aprobada` → «Trabajando ahora: t-corriendo-02 (cola)», En curso 2. Al aprobar las demás → «Ninguna tarea corriendo ahora.», En curso **0** |
| (c) estadísticas | pantalla `3` / `11` / `$0.00 real · $0.40 equivalente Max`. Esperado de los datos: 3 / 11 / `day_by_model` real 0, equiv 0.40 → **cuadra** |
| (d) píldoras (contador = filas en la tabla) | Todos 54=54 · En curso 3=3 · Aprobadas 21=21 · Necesita decisión 5=5 · Sin revisión 5=5 · Fallidas 10=10. Cada filtro solo enseña su estado |
| (e) explicación | «Necesita decisión: tras 3 rondas no quedó bien, o su aprobación venció o se denegó; decides tú… Sin revisión: terminó pero el revisor no pudo revisarla; no cuenta como aprobada.» |
| fila seleccionada | `Style().map("Tareas.Treeview","background")` → `[("selected", "#222224")]` |
| Tracebacks | 0 en el log y 0 en la salida |

(f) Capturas en `pruebas/evidencia/tareas-estadisticas/`: `<dpi>-a-fijada-y-54-filas`,
`-d-filtro-necesita-decision`, `-b-se-fija-la-siguiente` y `-b-ninguna-corriendo`. El 150 % es simulado
(`GROWI_BRIDGE_DPI=144`).

## FALTA
- **A 150 % la tabla es más ancha que la ventana**: las 8 columnas suman 880 px a 100 %. En Consolas,
  «necesita decisión» se corta en la columna Estado. Rehacer el detalle y la tabla es t-tareas-detalle-045 (#10).
- **«Gasto de hoy»** solo cuenta lo **terminado** (como `day_by_model`). El coste de la que corre se ve en la
  fijada, marcado como estimado (`~`).

## CÓMO PROBARLO
- `python pruebas/prueba_tareas_estadisticas.py 100` (y `150`).
- En la app: Tareas. Las píldoras filtran, y la tarea que corre se ve arriba de la tabla.
