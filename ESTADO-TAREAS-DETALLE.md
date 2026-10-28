# ESTADO — Detalle debajo de la tabla de Tareas (t-tareas-detalle-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_tareas_detalle.py <dpi> [variante]`. Es **oculta**: «Abrir resultados» se registra y no
  abre nada.
  - Siembra `t-detalle-a`: revisada, con 2 checks de código (uno pasa y otro falla), un juez que aprueba, su hora
    y su `.result.json`.
  - Siembra `t-detalle-b`: sin revisión y sin resultados.
- Evidencia: `pruebas/evidencia/tareas-detalle/evidencia-*.json`.

## LISTO
1. **Detalle debajo de la tabla.** Panel fijo, ni modal ni ventana nueva, en CTk (`CTkFrame`, esquinas 10).
   - Campos: Tarea (id en **Consolas**), Estado (punto + texto en su color), Motor, Ronda, Tiempo, Tokens, Coste
     y Revisión. Salen de la cola real: las mismas funciones que pintan la fila.
   - Debajo sigue todo lo demás de la revisión: encargo, criterios, jueces, reintentos, aprobación…
   - Al elegir otra fila, el detalle cambia. Sin selección dice «Elige una tarea…».
2. **Línea de tiempo de verificación.** Un renglón por paso **real**, sacado del `.revision.json` de la última
   revisión: los checks de código y los jueces.
   - Cada renglón lleva **hora** (`revisado_at`), **✓ verde o ✗ rojo** y el texto.
   - Encima, el resumen «N pasaron, M fallaron».
   - Si la tarea no tiene revisión: «Sin datos: esta tarea no tiene pasos de verificación registrados». Nunca
     inventa pasos. Si la revisión no guardó la hora, lo dice.
3. **Botones.**
   - «**Abrir resultados**» (acento `#FF6363` en oscuro) abre el `.result.json` **real** de la última ronda de la
     tarea. Antes abría la carpeta general. Sin resultados, lo dice en el panel y no abre un vacío.
   - «**Volver a la cola**» devuelve el foco a la lista, en la fila elegida, como pide el spec.
   - Volver a encolar la tarea (lo que hacía antes ese botón) sigue igual, como «**Volver a encolar**», y en
     Ctrl+K. No se pierde nada.
4. **Cerrar ✕ siempre alcanzable.** Va en la cabecera del panel, a la derecha y en su propio hueco, empaquetado
   antes que el título: el texto no lo puede empujar fuera. Cierra el detalle, quita la selección y deja el foco en
   la lista.
5. **Respaldo y foco.** Sin CTk, con `piloto_ctk: false` o con `GROWI_BRIDGE_CTK=0` sale el mismo panel con
   `_KitTk` (botones ttk, «Abrir resultados» en `Accent.TButton`). Los 4 botones son paradas de Tab.
6. **La tabla ya no se sale de la ventana a 150 %** (lo que dejó pendiente el #4).
   - Las columnas se adaptan al ancho (`tareas_columnas_para`). Primero esconden las que el detalle ya enseña, en
     este orden: tokens, tiempo, ronda, revisión y motor.
   - Tarea, estado y costo no se esconden nunca. Con sitio, salen las 8.
   - La columna Estado se mide con la fuente monoespaciada a ese DPI: «● necesita decisión» cabe entero.

## Evidencia (100 % CTk; 150 % y las 3 de respaldo dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) 2 tareas distintas | A: `t-detalle-a`, «● necesita decisión», Claude, 2/3, 1:35, 12.0 k / 3.4 k, $0.42 eq., «No: falta el archivo plan.md». B: `t-detalle-b`, «● pendiente», Ollama, 0/3, —, —, $0 local, — |
| (b) línea de tiempo | A: «2 pasaron, 1 fallaron»: `10:42 ✓ el comando pytest sale con 0…`, `10:42 ✗ existe plan.md (plan.md no existe)`, `10:42 ✓ Juez claude: aprueba (4/5)`. B: «Sin datos: …», 0 renglones |
| (c) Abrir resultados | A → `os.startfile(…\t-detalle-a-r2.result.json)` = el esperado. B → no abre nada y avisa «todavía no tiene resultados». Acento `#ff6363` |
| (d) Volver a la cola | `focus_set` de la lista llamado 1 vez, fila con foco `t-detalle-a` |
| (e) cerrar | «✕» en la cabecera, a la derecha; al pulsarlo: selección vacía, cuerpo oculto y foco a la lista |
| tabla a ventana mínima | 100 %: contenido 534 px → tarea, estado y costo (390 px) → cabe. 150 %: 801 px → las mismas (593 px) → cabe. Estado: 150 ≥ 145 px (100 %) y 233 ≥ 227 (150 %). A 1200 px salen las 8 |
| arranque (`build_gui`, 100 %) | antes 11,3 / 11,3 s; después 11,7 / 11,7 s. El panel solo: **40-43 ms** |
| Tracebacks | 0 en las 5 variantes |

## FALTA
- **(e) con la mascota y con scroll real**: oculta no hay pantalla. El ✕ tiene su hueco en la cabecera, y el solape
  con la mascota en cada posición de scroll lo verifica el #17, `t-mascota-solape-045`.
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_tareas_detalle.py 100` (y `150`).
- La hora de cada paso es la de la revisión (`revisado_at`): la revisión no guarda una hora por paso.

## CÓMO PROBARLO
- `python pruebas/prueba_tareas_detalle.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Tareas, clic en una fila; el detalle sale debajo de la tabla.
