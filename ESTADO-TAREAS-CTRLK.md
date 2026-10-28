# ESTADO — «Buscar o pedirle algo (Ctrl K)» en el encabezado de Tareas (t-tareas-ctrlk-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_tareas_ctrlk.py <dpi>`. Es **oculta** y el runner es inerte.
  - Siembra 4 tareas con su encargo: dos de «facturas», una de Blender y una de notas de reunión para Obsidian.
- Evidencia: `pruebas/evidencia/tareas-ctrlk/evidencia-*.json`.

## LISTO
1. **Campo en el encabezado.** «Buscar o pedirle algo (Ctrl K)» a la derecha del título «Tareas».
   - Es Tkinter clásico (`ttk.Entry` con su texto gris): la paleta no se convierte.
2. **Buscar en vivo.** Al escribir, la lista se filtra por **id** o por **título** (el encargo), sin distinguir
   mayúsculas.
   - Vacío, no hay filtro.
   - Se suma a la píldora de estado (#4) y al proyecto activo. Va en la huella de la tabla, así que repinta al
     momento.
3. **Pedir.** Intro sin coincidencias manda el texto como **encargo nuevo** por `_send_ask`, el camino del
   compositor (#11) y de la paleta, con «**Automático (recomendado)**»: decide el router.
   - El motor del compositor y los criterios que tuvieras a medias no se tocan: se guardan y se reponen.
   - La tarea sale en la lista y el campo se limpia.
   - Intro **con** coincidencias elige la primera y abre su detalle.
4. **Atajos.**
   - **Ctrl+K** con Tareas a la vista pone el foco en el campo.
   - Si el campo ya tiene el foco, o estás en la paleta, Ctrl+K hace lo de siempre (abrir la paleta, o sus
     acciones secundarias).
   - **Esc** en el campo lo limpia y devuelve el foco a la lista.
5. **La paleta sin tocar.** Su aspecto, sus resultados y sus atajos son los mismos. El único cambio es que el atajo
   «dentro de Bridge», con Tareas a la vista, va primero al campo. Fuera de Tareas, y desde otra app (atajo global),
   abre la paleta como antes.

## Evidencia (100 % y 150 % dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) filtra en vivo | «factura-0» → `t-factura-01`, `t-factura-02` (id); «BLENDER» → `t-blender-07`; «obsidian» y «reunión» → `t-notas-11` (título) |
| (b) borrar quita el filtro | vuelven las 4, igual que al inicio |
| (c) pedir sin coincidencias | «Hazme una lista de la compra para la semana» → la lista queda vacía; Intro → `t-20261028-142401.task.json` con `motor: "auto"`, sin `model`, el prompt escrito, en la lista, campo limpio; el selector del compositor sigue en «Claude Haiku» |
| Intro con coincidencias | «notas» → elige `t-notas-11` y el detalle muestra `t-notas-11` |
| (d) Ctrl+K desde la lista | `focus_set` del campo (registrado; oculta, Tk no da foco real), y **no** se abrió la paleta |
| (e) Esc | campo `""`, `focus_set` de la lista, sin filtro |
| (f) la paleta igual | en Estado, Ctrl+K → la paleta (`Toplevel`) abierta; «ajustes» → sección «Resultados» con 2 resultados |
| DPI, ventana al mínimo | el encabezado (título + campo) pide 382 px (100 %) y 604 px (150 %), con 534 y 801 de contenido → cabe |
| arranque (`build_gui`, 100 %) | antes 11,2 / 11,7 s; después 11,5 / 11,4 s, igual |
| Tracebacks | 0 |

## FALTA
- **(g) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_tareas_ctrlk.py 100` (y `150`).
- Oculta, el foco de Ctrl+K y de Esc se comprobó por la llamada a `focus_set`, no con la ventana activa.

## CÓMO PROBARLO
- `python pruebas/prueba_tareas_ctrlk.py 100` (y `150`).
- En la app: Tareas, Ctrl+K y escribe. Filtra; Intro sin coincidencias lo encarga.
