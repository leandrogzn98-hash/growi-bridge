# Estado: regla de los 300 ms (t-carga-300ms)

Rama `Claude`, 28 oct 2026. **LISTO**, con las FALTA de la matriz.

## El mecanismo único (`growi-bridge.py`, antes de `check_updates_ui`)
- **`Carga(nombre, mostrar, detalle, ocultar, texto)`**: toda espera pasa por
  aquí.
  - A los **300 ms** llama a `mostrar()` si la espera sigue (esqueleto o
    spinner). Antes no se muestra nada.
  - A **1 s** llama a `detalle(texto)`, que dice qué está pasando.
  - `fin()` cancela lo pendiente y anota `(nombre, ms, patrón)` en
    `_CARGA_REG` y, si pasó de 300 ms, en el log («carga: X: N ms -> patrón»).
- **`con_carga(nombre, trabajo, al_terminar, …)`**: el trabajo en un hilo y
  el final en la ventana.
- **`boton_largo(btn, …)`**: el botón se desactiva **al momento** (respuesta
  en menos de 200 ms y sin doble clic); a 300 ms gira (`⠋ Buscando…`); a 1 s
  cambia al texto del detalle; al acabar vuelve a su texto.
- **`esqueleto(parent, filas)`**: filas grises con la geometría de la lista
  (título + subtítulo por fila), nunca un spinner a pantalla completa.

## Dónde se aplica
- **Skills:** mientras el índice lee (`_skb_render`), el esqueleto a los
  300 ms y «Leyendo la carpeta de skills…» a 1 s. El repintado no lo borra.
- **Modelos:** mientras no llega la lista de instalados (`_render_models`),
  el esqueleto a los 300 ms y «Leyendo tus modelos (Ollama)…» a 1 s.
  `_apply_models_list` llama a `fin()`.
- **Ajustes → «Buscar actualizaciones»:** `check_updates_boton`, con spinner
  y sin doble clic.
- **Tareas:** la tarea en curso **sin fila** todavía (sin resultado) aparece
  arriba como «Trabajando…» con su motor, tiempo, tokens y costo en vivo. Una
  fila que ya existía dice «Trabajando… (estado)» mientras siga viva
  (`_apply_live_to_tree`).
- **Descargas:** ya tenían el progreso real de t-descargador-gguf
  (`lib_progress_text`). Se comprobó, no se cambió.

## Verificación (app real en 8797; evidencia en `pruebas/evidencia/carga-300ms/`)
`pruebas/prueba_carga_300ms.py` (ratón de verdad).

| | Prueba | Resultado |
|---|---|---|
| a | Una espera de 100 ms y otras de 600 y 1500 ms | 100 ms → **«nada»** (no se llamó a `mostrar`; 222 ms vistos desde la ventana). 600 y 1500 ms → `mostrar` y luego `detalle`. Con la app recién pintada, el primer `update()` tarda ~0,8 s; por eso la prueba calienta la ventana antes de medir |
| b | Lista que tarda (Skills, índice «leyendo» 1,5 s) | A 150 ms **no hay** esqueleto; a 650 ms **sí** (4 filas); sigue tras un repintado; a 1,25 s el estado dice «Leyendo la carpeta de skills…»; al llegar el índice, se quita. `_CARGA_REG`: «lista de skills, 1363 ms, carga+detalle». Captura `1b-skills-esqueleto.png` |
| b' | Modelos | Aquí la lista de instalados llega en **menos de 300 ms** (la app ya la tiene), así que el registro dice «nada» y no se dibujó esqueleto: es lo que pide la regla. El camino del esqueleto es el mismo `Carga` que en Skills; en el primer arranque, con la lista lenta, el log dice «carga: lista de modelos: 21082 ms -> carga+detalle» |
| c | Dos clics reales seguidos en «Buscar actualizaciones» (búsqueda de 2 s) | A 550 ms: «⠼ Buscando…», `disabled`. Al final: «Buscar actualizaciones», `normal`. **Búsquedas lanzadas con 2 clics: 1** |
| d | Progreso de descarga | «126.0 de 609.0 MB (20.7 %) · 10.8 MB/s · faltan 45 s»; sin velocidad todavía: «… · midiendo la velocidad…» (no inventa). La descarga real de un GGUF está en `ESTADO-DESCARGADOR-GGUF` (fase A); no se repitió porque son GB |
| e | Tarea en curso sin fila | Fila `t-prueba-trabajando`: «**Trabajando… (corriendo)**», «claude (sonnet)», 42 s, 1.2k / 300, ~$0.01. Captura `4-tareas-trabajando.png`. El vivo se simuló (`_live_active`), no se lanzó una tarea real |

Log sin tracebacks.

## Matriz página por página
| Página | Qué carga | Patrón |
|---|---|---|
| Skills | índice de `skills\` (hilo) | **esqueleto** a 300 ms + texto a 1 s |
| Modelos | lista de instalados (runner u Ollama) | **esqueleto** a 300 ms + texto a 1 s (si tarda) |
| Modelos → Descargas | GGUF | **barra + % + MB/s + tiempo restante reales** |
| Modelos → «Comprobar mi PC» | detección | botón desactivado + «Comprobando tu PC…» (ya existía) |
| Ajustes → Buscar actualizaciones | GitHub | **spinner en el botón**, sin doble clic |
| Ajustes → Probar (proxy) | proxy + Claude | botón desactivado + «⠋ Probando el proxy…» (ya existía, `proxy_test_ui`) |
| Tareas | tarea en curso | **fila «Trabajando…»** + línea «En vivo» |
| Tareas (lista) | `runner-results\*.json` locales | síncrono → por la regla, nada (FALTA medirlo con cientos de resultados) |
| Carpetas | `folders.json` | síncrono, instantáneo → nada |
| Registro | el log local | síncrono → nada (FALTA esqueleto si un log enorme pasara de 300 ms) |

## FALTA
- Tareas, Carpetas y Registro cargan de forma síncrona (archivos locales). No
  tienen esqueleto porque hoy no esperan. Si con muchos datos pasan de
  300 ms, hay que moverlas a `con_carga`; no se midió con volumen grande.
- Hay otros botones largos que no pasan por `boton_largo`: los que ya tenían
  su propio «⠋ …» (Probar proxy, Comprobar mi PC) siguen igual.
