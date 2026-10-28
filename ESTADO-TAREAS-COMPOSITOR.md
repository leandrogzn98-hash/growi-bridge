# ESTADO — Compositor «Pedirle algo a Growi…» (t-tareas-compositor-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_tareas_compositor.py <dpi> [variante]`. Es **oculta**.
  - En la copia, el runner se sustituye por uno **inerte**: las tareas se encolan de verdad (el `.task.json` en la
    cola), pero nadie las ejecuta, así que no se gasta nada.
- Evidencia: `pruebas/evidencia/tareas-compositor/evidencia-*.json`.

## LISTO
1. **Compositor debajo del detalle**, en CTk:
   - un campo `CTkTextbox` con el texto gris **«Pedirle algo a Growi…»**, que se ve solo con el campo vacío y sin
     foco;
   - el campo de criterios (opcional), como antes;
   - el **selector de motor**, con «**Automático (recomendado)**» por defecto (o el modelo que elegiste para el
     chat en Modelos por superficie);
   - **Enviar**, en acento `#FF6363`.
   - El selector es un `CTkButton` que abre un menú con los mismos valores y cabeceras de siempre
     (`engine_choices`), con ✓ en el elegido. Un `CTkOptionMenu` costaba ~0,7 s de arranque. Se usa como el
     Combobox (`get`, `set`, `config(values)`, `cget`, `<<ComboboxSelected>>`), así que el resto de la app
     (Modelos, perfiles, paleta) no cambia.
2. **Envío real por el camino que ya existe.** Enviar es `_send_ask`, el **mismo** que usa la paleta Ctrl+K
   (`_palette_ask_ai`): ni camino nuevo ni motor nuevo.
   - Automático deja la tarea con `motor: auto` (decide el router). Un motor elegido deja su `model` o `motor`.
3. **Vacío no envía.** Ni con el campo vacío ni con solo espacios: ni tarea ni error.
4. **Después de enviar.** El campo se limpia, vuelve el texto gris y la tarea nueva sale en la lista («● pendiente»).
   Debajo, «En cola: <id>, esperando a que empiece» (el seguimiento de siempre). Si empieza a correr, la zona
   fijada (#4) la toma de `runner-live.json`.
5. **Respaldo y foco.**
   - Sin CTk, con `piloto_ctk: false` o con `GROWI_BRIDGE_CTK=0` sale el compositor clásico (Text + Combobox +
     Enviar ttk).
   - Tab llega al campo (foco nativo de Text), al selector y a Enviar.
   - **Intro en el campo envía**, en las dos versiones; Mayús+Intro mete un salto de línea.

## Evidencia (100 % CTk; 150 % y las 3 de respaldo dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) encargo con el motor elegido | selector «Claude Haiku», Intro en el campo → `t-20261028-141033.task.json` con `model: "haiku"` (= `_ASK_ENGINES["Claude Haiku"]`), campo limpio |
| (b) Automático | por defecto «Automático (recomendado)» → `t-20261028-141032.task.json` con `motor: "auto"`, sin `model`, y el prompt escrito |
| (c) vacío | vacío y «solo espacios»: la cola sigue igual (`[]` → `[]`), 0 errores |
| (d) después | campo `""`, texto gris visible otra vez, la tarea en la lista con «● pendiente», «⠧ En cola: t-20261028-141032, esperando a que empiece» |
| (e) respaldo | `clasica`, `sinctk` y `flag`: `Text`, `Combobox` y `Button` ttk; (a) a (d) igual; **0 tracebacks** |
| foco | campo nativo; selector y Enviar `takefocus 1`; Intro enlazado |
| DPI, ventana al mínimo | la fila del selector y Enviar pide 328 px (100 %) y 498 px (150 %), con 502 y 753 de contenido → cabe |
| arranque (`build_gui`, 100 %) | antes 11,6 / 11,6 s; después 11,7 / 11,6 s, igual. El compositor CTk solo: 790-823 ms (el `CTkTextbox`); el total no se movió |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_tareas_compositor.py 100` (y `150`).
- No se dejó correr la tarea encolada, para no gastar. Que el runner la toma y la ejecuta es el camino de siempre:
  el mismo `.task.json` que escribía el compositor anterior.

## CÓMO PROBARLO
- `python pruebas/prueba_tareas_compositor.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Tareas → «Pedirle algo». Escribe y pulsa Intro.
