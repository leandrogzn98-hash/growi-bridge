# ESTADO — Página Carpetas en CustomTkinter (t-carpetas-ctk-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_carpetas_ctk.py <dpi> [variante]`. Es **oculta**: no abre ventanas, ni icono de
  bandeja, ni el Explorador. Usa el arnés común nuevo, `pruebas/arnes_oculto.py`.
  - Siembra `folders.json` con 3 rutas reales de la copia: 2 que existen, una de ellas con un nombre largo con
    espacios, y 1 que no existe.
  - Variantes: `ctk` a 100 % y 150 %; `clasica` (`GROWI_BRIDGE_CTK=0`), `sinctk` (import roto), `rota` (CTk
    falla al dibujar) y `flag` (`piloto_ctk: false`).
- Evidencia: `pruebas/evidencia/carpetas-ctk/evidencia-*.json`.

## LISTO
1. **Carpetas en CTk.** Una tarjeta `CTkFrame` (esquinas 10, borde de 1 px `line`) con **una fila por carpeta**:
   - la ruta real de `folders.json`;
   - «Abrir» (`open_folder`, la abre en el Explorador) y «Quitar»;
   - debajo, «Añadir carpeta» y «Restablecer».
   Los botones son `CTkButton` del kit del piloto (esquinas 8, colores de THEME). Sin carpetas, la tarjeta lo
   dice y explica qué hacer.
2. **Mismo comportamiento.** Los mismos manejadores: `add_folder_ui`, `reset_folders_ui` y `refresh_folders_ui`.
   «Quitar» llama a `quitar_carpeta(ruta)`, que ahora usa también el «Quitar seleccionada» clásico.
   - Lo nuevo es «Abrir» por fila: es lo que pide el spec («cada botón abre su carpeta real»).
   - Si una ruta **no existe en este PC**, la fila lo dice en naranja y «Abrir» queda desactivado y fuera del Tab.
     No se inventa nada.
3. **Respaldo y foco.**
   - Si CTk no se puede importar, falla al dibujar, `piloto_ctk` es false o `GROWI_BRIDGE_CTK=0`, sale la lista
     clásica de siempre (Listbox + 3 botones). El log dice por qué.
   - Foco: `_teclado_ctk_patch` hace cada `CTkButton` parada de Tab con Espacio e Intro. El anillo azul `#4DA3FF`
     lo pinta el foco global de t-teclado-foco.
4. **Arranque medido.**
5. **DPI.** La ruta se parte al ancho real de su caja (`<Configure>`), así que con la ventana al mínimo no pisa
   los botones ni se sale.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) CTk con todas las filas | `ctk: true`; tarjeta `CTkFrame` con esquinas 10; 3 filas con «Abrir» y «Quitar» `CTkButton` (esquinas 8); pie `CTkButton` ×2; rutas = `folders.json` = las sembradas → `true`. Log: «carpetas: página con CustomTkinter 6.0.0 (11 ms)» |
| (b) cada botón abre su carpeta | Espacio en cada «Abrir» activo → `os.startfile` (registrado, sin abrir el Explorador) con las 2 rutas que existen, en orden → `b_cuadra: true`. La que no existe: «Abrir» `disabled`. «Quitar» en la 3.ª → `folders.json` con 2 y la tarjeta con 2 filas |
| (c) respaldo | `clasica`, `sinctk` («ModuleNotFoundError … se usa la versión clásica»), `rota` («RuntimeError: CTk roto a propósito … clásica») y `flag`: `ctk: false`, Listbox = `folders.json`, «Quitar seleccionada» quita, **0 tracebacks** |
| (d) foco | los 7 botones activos: `takefocus 1`, Espacio e Intro enlazados; «Abrir» desactivado: `takefocus 0`; foco global enlazado, color `#4DA3FF` |
| (e) arranque (`build_gui`, 100 %, tandas alternadas) | antes 12,8 / 12,8 / 13,4 / 13,8 s; después 16,0 / 14,0 / 13,4 / 13,9 s. La página sola: **11 ms** en CTk y 4 ms en clásica. La diferencia total está dentro del ruido |
| DPI, ventana al mínimo | 100 %: contenido 502 px; ruta partida a 374 px + botones 120 → cabe. 150 %: contenido 753 px; ruta 562 + botones 178 → cabe. Con la ventana del tamaño de prueba, la ruta no pisa los botones y los botones quedan dentro de la fila (100 % y 150 %) |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron.** Leandro pidió no abrir ventanas mientras usa el PC. Para
  tomarlas cuando él quiera: `PRUEBA_VER=1 python pruebas/prueba_carpetas_ctk.py 100` (y `150`).
- Oculta, Tk no recorre el orden de Tab: se comprobó cada parada (`takefocus` y teclas enlazadas), no el
  recorrido completo con la ventana visible.
- 150 % real de Windows: sigue simulado (`GROWI_BRIDGE_DPI=144`).

## CÓMO PROBARLO
- `python pruebas/prueba_carpetas_ctk.py 100`, y `150`, `100 clasica`, `100 sinctk`, `100 rota` y `100 flag`.
- En la app: Carpetas, una fila por carpeta. «Abrir» la abre en el Explorador.
