# Estado: pronóstico e historial de gasto (t-gasto-pronostico)

Rama `Claude`, 28 oct 2026. **LISTO**, con la P2 (ahorro por local) como FALTA.

Construido **sobre** t-consumo-vivo (los tres dineros de `spend_summary`) y
t-estimado-gasto-030 (el tope), sin duplicarlos. **Nunca** se muestra cuenta
atrás de cuota ni «te quedan X»: Anthropic no publica la cuota restante de
Max. El pronóstico es siempre sobre lo **acumulado**, y lo dice.

## Código (`growi-bridge.py`, bloque antes de `spend_lines`)
| Pieza | Qué hace |
|---|---|
| Campo **`proyecto`** | Cada resultado (`_base_result`) lleva `proyecto`: el declarado en el `.task.json` (`"proyecto": "Aqualine"`) o el nombre de la carpeta de trabajo (`cwd`). Si es `share\inbox`, «general». Para resultados viejos sin el campo, sale de su `.task.json` archivado |
| `gasto_7dias()` / `gasto_por_proyecto_7d()` | Últimos 7 días de `.result.json` reales: día, proyecto, modelo, dinero y costo; agrupados por proyecto con $ real, $ equivalente Max, tareas locales, días y modelos |
| `pronostico_semana()` | Acumulado desde el lunes ÷ días transcurridos × 7. Con un límite propio (`aviso_cuota_semanal_usd`): **«vas bien»** (≤ 80 %), **«vas justo»**, o **«te vas a quedar sin semana el <día>»**. Sin límite: «a este ritmo acabarías la semana en $X; sin un límite tuyo no puedo decir si te alcanza». Siempre con su base: «sobre tu acumulado de $X en N días de 7 (desde el lunes)» |
| `pico_de_gasto()` / `_pronostico_avisar()` | Hoy ≥ **2 ×** el promedio diario de los 7 días anteriores (y > $0.05) → aviso en la bandeja **una vez al día** y línea naranja en la tarjeta Gasto |
| **Freno** | Usa el `presupuesto_max_usd` de t-estimado-gasto-030 (no se duplica) y **además** lo lee del encargo: «no gastes más de $X en esto» → `presupuesto_max_usd = X`. El runner corta por acumulado y, con claude, con `--max-budget-usd` |
| Tarjeta **Gasto** (Tareas) | Tres líneas nuevas: pronóstico, pico (si lo hay) y «Últimos 7 días por proyecto» con cada cifra etiquetada (`$ real` · `$ equivalente Max` · `local`) |

## Verificación (`pruebas/prueba_gasto_pronostico.py` → `pruebas/evidencia/gasto-pronostico/evidencia.json`)
La historia de 6 días son `.result.json` **de prueba**, cada uno con su
`.task.json` archivado (carpetas `Aqualine` y `Summit Maker`) y con fechas de
días anteriores. Hoy hay **una tarea real** por el runner en la carpeta
`HAYAI`. La tarjeta Gasto se dibujó de verdad (Tk).

| | Prueba | Resultado |
|---|---|---|
| a | Pronóstico con su base | Sin límite: «a este ritmo acabarías la semana en $5.16; sin un límite tuyo… no puedo decir si te alcanza — sobre tu acumulado de $1.50 en 2.0 días de 7 (desde el lunes)». Con $50: **«vas bien…»**. Con $2: **«te vas a quedar sin semana el miércoles (a este ritmo, $5.16 frente a tus $2.00)»**. Siempre termina con «Es sobre lo acumulado: Anthropic no publica cuánto te queda de Max» |
| b | 7 días por proyecto | Aqualine $1.20 equiv. (6 tareas, 6 días, sonnet) · Summit Maker $0.60 equiv. + 6 locales (hermes, sonnet) · **HAYAI $0.90** (la tarea real de hoy; su resultado lleva `"proyecto": "HAYAI"`) |
| c | Pico | Hoy $0.90 frente a un promedio de $0.26 → **3.5 veces** → aviso «Gasto de hoy: 3.5x tu promedio», una sola vez aunque se compruebe dos veces |
| d | Freno del encargo | «No gastes más de $0.50 en esto» → `presupuesto_max_usd 0.5`. El motor gastó $0.90 → **`necesita_decision`**: «Parada por el tope de gasto: lleva $0.90 de $0.50…» |
| e | Etiquetas | La tarjeta: «$ real · $ equivalente Max · tareas $0 local…»; el pronóstico lleva «($ equivalente Max, no dinero real)» |

## FALTA
- **P2: «esta semana el local te ahorró $X equivalentes»**: no se añadió.
  Las tareas locales no traen los tokens en todos los casos, y calcular su
  equivalente sería inventar un precio. Queda explícito como FALTA.
- La «ventana semanal» se toma **desde el lunes**: es la semana del
  calendario, no la de Max (que no es pública).
