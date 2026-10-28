# ESTADO — Historial de gasto por día (t-historial-gasto-045)

Rama `Claude`, 28-oct-2026. Pedido de Leandro del 27 oct: ayer mostraba ~$424, hoy ~$118, y no había ni suma ni
historial.

- Prueba: `pruebas/prueba_historial_gasto.py 100` y luego `… 100 reinicio`. Es **oculta**.
- Verificación de las cifras de referencia: `… 100 real`, sobre una **copia de solo lectura** de los registros de
  la app instalada. La instalada no se tocó.
- Evidencia: `pruebas/evidencia/historial-gasto/evidencia-100-ctk.json`, `-reinicio.json` y `-real.json`.

## LISTO
1. **Persistencia diaria**: `share\gasto-historial.json`, en la carpeta de datos de la app (`SHARE`), con una fila
   por día.
   - Cada fila lleva real, equivalente Max, local (tareas en tu PC, $0), tareas, sin precio, la fuente (cuántos
     archivos) y cuándo se actualizó.
   - La fecha es la de los propios registros: `finished_at` / `revisado_at`, hora de Caracas.
   - Las cifras salen de los **mismos registros y con las mismas reglas** que los «hoy» (`spend_summary`):
     `.result.json` y `.revision.json`, con `_money_kind`.
   - Se actualiza al arrancar (todos los días verificables), cuando entra un resultado nuevo (la fila de hoy, en
     segundo plano) y al cerrar la app.
   - **Nunca se reescribe borrando días**: solo se pone o se sube la fila de cada día. Si los registros de un día
     desaparecen, el día se queda como estaba. Si el archivo está dañado, no se pisa y se avisa en el log.
2. **Total acumulado** en la tarjeta Gasto, debajo de los «hoy»: «Total acumulado desde DD/MM/AAAA (N días): real …
   · equivalente Max … (no se cobra aparte: va en tu Max) · local N tareas ($0)». Es la suma de las filas del
   historial.
3. **Historial por día**: `ttk.Treeview` clásico con Día, Real, Equivalente Max, Local ($0) y Tareas, lo más
   reciente primero.
   - Los días sin registro no aparecen.
   - Sin ningún día, la tabla dice «sin datos» (y el total también), nunca un cero.
4. **Semilla con datos verificados**: al arrancar se siembran los días que tienen registros. Ver la tabla de
   referencias abajo.
5. **Los «hoy» no cambian**: misma función, mismos números y mismo sitio. El historial va añadido debajo.

## Evidencia
| Criterio | Resultado |
|---|---|
| siembra (prueba) | resultados sembrados de 3 días → `gasto-historial.json` con 26/10 (equiv. $0.65, 2 tareas), 27/10 ($1.10, 1 local, 2 tareas) y 28/10 ($0.05, 1 tarea); cada cifra = `gasto_por_dia()` → `d_verificado` todo `true` |
| (b) total = suma | «Total acumulado desde 26/10/2026 (3 días): real $0.00 · equivalente Max $1.80 (no se cobra aparte…) · local 1 tareas ($0)»; suma de las filas: real 0, equiv 1.80, local 1, tareas 5 → **cuadra** |
| (c) tabla | `28/10/2026 $0.00 $0.05 0 1` → `27/10/2026 $0.00 $1.10 1 2` → `26/10/2026 $0.00 $0.65 0 2`: la más reciente primero, sin días inventados |
| el día crece | resultado nuevo de hoy ($0.30) → la fila de hoy pasa de **$0.05 a $0.35** (y 2 tareas), en vivo |
| (a) sobrevive al reinicio | otra instancia con ese `gasto-historial.json` y **solo** un registro de hoy (los de días anteriores ya no están): el historial sigue con 26/10, 27/10 y 28/10 (`anteriores_siguen: true`), total $2.10 = suma de las filas |
| (e) los «hoy» | pantalla «Real hoy» $0.00 y «Equivalente Max hoy» $0.05 = `spend_summary()["hoy"]`, y la fila de hoy del historial da lo mismo → cuadra |
| Tracebacks | 0 |

**(d) Cifras de referencia** contra los registros reales de la app instalada (298 archivos copiados para leer):
| Día | Referencia de Leandro | Registros de la app | Veredicto |
|---|---|---|---|
| 26/10/2026 | $424.63 equivalente Max | Día entero: **$455.38**, 63 tareas. Acumulado a las **17:15: $424.80** | La referencia era una foto a media tarde (17:15, $0.17 de diferencia). Se siembra el día entero, **$455.38**, que es lo que dicen los registros |
| 27/10/2026 | $118.88 a las 07:09 (día parcial) | Acumulado hasta las 07:09: **$118.88 exactos** (el último registro antes de esa hora es de las 03:42). Día entero: **$190.75**, 38 tareas | **Verificada**. Se siembra el día entero, $190.75 |
| otros | — | 24/10 $0.59 · 25/10 $81.43 · 28/10 $18.27 (hasta ahora) | De los registros |

En este repo no se escribió nada en la app instalada. Al abrir la app real con esta rama, el arranque siembra esos
días de sus propios registros.

## FALTA
- La siembra solo cubre los días cuyos registros siguen en `runner-results`. Si se archivaron o borraron
  resultados viejos, esos días no se pueden verificar y no se siembran: quedan «sin datos», sin inventar nada.
- Capturas de la tarjeta: no se tomaron, a pedido de Leandro (no abrir ventanas).

## CÓMO PROBARLO
- `python pruebas/prueba_historial_gasto.py 100`, luego `python pruebas/prueba_historial_gasto.py 100 reinicio`
  (usa el historial que deja la primera), y `python pruebas/prueba_historial_gasto.py 100 real`.
- Para ver crecer el día: termina una tarea; la fila de hoy sube sola. Al reabrir la app, los días siguen.
- En la app: Tareas → tarjeta Gasto → «Total acumulado» y la tabla «Por día».
