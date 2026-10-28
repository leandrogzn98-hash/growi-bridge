# ESTADO — Recursos con gráficos, rango y tarjetas con sparkline (t-recursos-graficos-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_recursos_graficos.py <dpi> [variante]`. Es **oculta**.
  - Junta ~75 s de muestras **reales** de este PC: el contador de la barra lateral (cada 2 s, CPU y RAM) y lecturas
    completas de `_res_sample`, la misma de la página.
  - Las lecturas completas las pide la prueba a mano, porque con la ventana oculta la lectura automática se pausa:
    así está hecha.
- Evidencia: `pruebas/evidencia/recursos-graficos/evidencia-*.json`.

## LISTO
1. **Selector de rango** (`CTkSegmentedButton`): 1 min, 5 min, 15 min y 1 h.
   - La app no guardaba ningún histórico, así que ahora junta en memoria (`_RESH`, hasta 1 h) las muestras que
     ya mide: la lectura completa con la página a la vista y, sin ella, la CPU y la RAM del contador de la barra
     lateral.
   - El selector **lo dice**: «Solo hay datos desde que abriste la app (hace N min): no se guarda un histórico
     entre sesiones». Si el rango todavía no está completo, también lo dice. No finge un histórico.
2. **Gráficos de línea** de CPU y Memoria en Canvas: 0-100 % con rejilla en 25, 50 y 75 y etiquetas. Cada muestra
   va en su hora dentro de la ventana elegida, y el punto de ahora queda marcado.
3. **Tarjetas de métrica** CTk (`CTkFrame`) con número grande y **sparkline** de los últimos 5 min:
   - CPU, RAM, GPU (nvidia-smi) y Disco libre: lo que la app mide de verdad.
   - **Red no**, porque la app no la mide y no se inventa.
   - Los números y textos son los de siempre (`_res_card_set`). La barra fina se convirtió en sparkline.
   - Los textos van en `tk.Label` sobre la tarjeta CTk y se parten al ancho real de la tarjeta.
4. **Lista de procesos sin cambios**: la misma `ttk.Treeview`, columnas, buscador, «Ver todos», ordenar,
   Supr / «Cerrar proceso» y F5. No se añadió ni se quitó ningún poder.
5. **Respaldo, foco, arranque y DPI.**
   - Sin CTk, con `piloto_ctk: false` o con `GROWI_BRIDGE_CTK=0`: tarjetas `tk.Frame` y selector con radios.
   - Cada botón del segmentado es parada de Tab con Espacio.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) gráficos con datos reales | 62-63 muestras en ~130 s; CPU real `[12.5, 10.0, 10.6, 13.8, 6.2, 7.9, 11.1, 8.5, 8.6, 15.7, 18.6, 11.2]` %, RAM `[81.0, 80.9, 80.9, 81.0, …]` %; los dos gráficos con 62 puntos y su rejilla (12 elementos en el Canvas) |
| (b) el rango cambia la ventana | muestras de CPU en la ventana: **1 min → 29**, 5 min → 62, 15 min → 62, 1 h → 63 (todas las que hay). Nota: «Solo hay datos desde que abriste la app (hace 2 min): no se guarda un histórico entre sesiones. Este rango todavía no está completo.» |
| (c) tarjetas = fuente | pantalla CPU «22 %», RAM «12.5 GB» («de 15.4 GB (81 %)»), GPU «0 %» («VRAM 0 de 6 GB»), Disco «75.9 GB libres de 435.5 GB en C:» = la última `_res_sample` → `c_cuadra: true`. Sparklines: CPU y RAM con 63 muestras, GPU y disco con 5 (solo las lecturas completas) |
| (d) procesos igual | columnas `name, pid, cpu, ram, origin` = `_RES_COLS`; 18 filas; `<<TreeviewSelect>>`, `<Delete>` y `<F5>` enlazados; «Cerrar proceso»; buscador `Entry` |
| (e) respaldo | `clasica`, `sinctk` y `flag`: tarjetas `Frame` y selector de radios; (a) a (d) igual; **0 tracebacks** |
| DPI, ventana al mínimo | cada tarjeta a 1/4 del contenido (127 px a 100 %, 191 px a 150 %): su texto cabe; el selector pide 196 / 293 px → cabe |
| arranque | ver abajo |

**Arranque** (`build_gui`, 100 %, alternado): antes 13,4 / 12,9 s; después 13,4 / 14,5 s, dentro del ruido de la
máquina. Las tarjetas y los gráficos solos: **41-58 ms**.

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_recursos_graficos.py 100` (y `150`).
- El histórico es **en memoria**: se pierde al cerrar la app. Un histórico entre sesiones sería otra función, y el
  spec no la pide.
- La GPU y el disco solo se leen con la página a la vista (la lectura completa), así que sus sparklines tienen
  menos puntos.

## CÓMO PROBARLO
- `python pruebas/prueba_recursos_graficos.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Recursos. Las tarjetas llevan su sparkline; debajo, «Uso en el tiempo» con el rango.
