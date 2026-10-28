# ESTADO — «Ver el mapa» baja hasta el mapa y lo resalta (t-estado-mapa-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_estado_mapa.py 100` y `… 150`. La de 150 usa DPI 144 y la ventana a su tamaño mínimo.
  Arranca la app real desde una copia, en el puerto de prueba 8797, y **pulsa el botón de verdad** con
  `invoke()`.
- Evidencia: `pruebas/evidencia/estado-mapa/` (`evidencia-100.json`, `evidencia-150.json` y las capturas
  `<dpi>-a-antes`, `-a-despues-resaltado`, `-c-tras-3s` y `-b-desde-tareas`).

## LISTO
1. **Bajar hasta el mapa** (`ver_mapa`): cambia a Estado, espera a que la página esté dibujada y mueve el scroll
   a la **posición real de la tarjeta en ese momento** (`_scroll_a`, que mide `winfo_rooty`). No hay un ancla
   fija: si la página crece, sigue cayendo bien.
2. **Resaltarla** (`_mapa_resaltar`):
   - Borde de 2 px (escalado) en el token «en curso» (`#0A84FF` en el tema oscuro, `#0066CC` en el claro).
   - Fondo un punto más elevado: un 6 % hacia blanco en oscuro y hacia el azul en claro.
   - Dura **3 s** o hasta el **siguiente clic o tecla**, sin contar el mismo clic que lo abrió.
   - Después **vuelve exactamente** a lo que había: se guardan y se restauran el borde y el fondo de cada pieza.
3. **Desde cualquier página**: desde Tareas, el botón lleva a Estado y baja y resalta en la misma acción.
4. **A 100 % y 150 % y a ventana mínima**:
   - La tarjeta queda con su parte de arriba a 12 px del borde visible.
   - A ventana mínima, la primera captura mostró **cortes**, que ya existían antes de este spec:
     - el botón «Ver el mapa» del banner, aplastado;
     - la explicación de la tarjeta, cortada por la izquierda;
     - los botones de las filas («Usa», «Pone»).
   - Arreglo:
     - los botones se reservan antes que el texto;
     - el texto corta al ancho real del contenedor (`_wrap_al_ancho`, que también usan `_card` y el banner).
   - Con eso, **nada se corta**: captura `150-b-desde-tareas`.
5. **Sin tocar el mapa**: los textos de las filas son idénticos antes y después (`e_filas_iguales: true`). Solo
   cambió el orden de empaquetado (el botón primero) y el ancho de corte.

## Evidencia
| Criterio | 100 % | 150 %, ventana mínima |
|---|---|---|
| antes: la tarjeta estaba a… | 1572 px por debajo de lo visible | 2566 px |
| (a) tras «Ver el mapa» en Estado | arriba a **12 px**, visible; borde `[2, #0066CC]`; fondo `#E6ECF4` | arriba a 12 px; borde `[3, #0066CC]` (2 px × 1,5); fondo elevado |
| (b) desde Tareas | página `estado`, arriba a 12 px, resaltada | igual |
| (c) a los 3 s | borde `[1, #E5E5EA]`, fondos `#F5F5F7` de antes | igual |
| (c) con un clic | vuelve a lo normal al instante | igual |
| (e) filas del mapa | iguales | iguales |
| Tracebacks | 0 | 0 |

La tarjeta del mapa mide 2146 px a 100 % (7 filas con su explicación), así que **nunca cabe entera** en la
ventana. «Visible» significa aquí que su cabecera y las primeras filas quedan a la vista.

## FALTA
- **El 150 % es simulado** (`GROWI_BRIDGE_DPI=144`), no el 150 % real de Windows. A DPI 144, el tamaño mínimo
  de la ventana es más alto que la pantalla de este PC: la franja negra de abajo en la captura de 150 es lo que
  queda fuera del monitor, no un fallo de dibujo.

## CÓMO PROBARLO
- `python pruebas/prueba_estado_mapa.py 100` y `python pruebas/prueba_estado_mapa.py 150`.
- En la app: cuando sale el banner de la nube, pulsa «Ver el mapa».
