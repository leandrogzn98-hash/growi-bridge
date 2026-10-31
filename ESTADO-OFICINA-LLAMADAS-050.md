# ESTADO — t-oficina-llamadas-050 (Oficina 0.5.0, spec 13 de 18)

**Fecha:** 30 oct 2026, 23:40. **Veredicto:** LISTO las 7 subfunciones. Una parte se verificó con el runner real en instancias aisladas (Claude Haiku, ollama, motor inexistente, Meshy sin clave, urgente y 3 en cola) y otra con un simulador que usa el formato real de cola-live y runner-live (ocupado con posición, no contesta, necesita revisión, fin). Lleva **dos cambios pequeños en el runner**, con parches reproducibles. La app instalada no se tocó.

## Dónde está
- `oficina/llamadas/llamadas.py`: `fase_llamada()` / `llamada()` (función pura), `posicion()` y `en_cola_de()`.
- `oficina/telefono/telefono.py`: aviso de 3 en cola con su sí/no, y «urgente».
- `growi-bridge.py`:
  - `parches/parche_urgente_050.py`: `encolar_tarea(urgente=)`; orden del runner ronda → urgente → resto; `urgente` en cola-live.
  - `parches/parche_lanzado_at_050.py`: `lanzado_at` en runner-live al arrancar el proceso, escrito al instante.

  Comprobado: aplicados sobre el commit anterior, reproducen el archivo exacto. Lo mismo `encolar.py` (`urgente`).
- Prototipo: `parches/parche_oficina_llamadas_050.py` (línea punteada, temporizador, bocadillos y estado de la llamada), más dos arreglos del protocolo, abajo.
- Pruebas: `pruebas/oficina_llamadas_050/prueba_llamadas.py` y `demo_llamada.py`.

## LISTO (evidencia en `pruebas/evidencia/oficina-llamadas-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | El gerente levanta el teléfono | `resultado.json` (`a_llamada_claude`) | Llamada **real** a Claude Haiku. Fases de la oficina: marcando (3,0 s) → timbre (6,9 s, «¿Sí?») → en línea (7,9 s) → fin (31,3 s, «Listo, Claude se encarga.»). Log del runner: corriendo 23:29:09, lanzado 23:29:11, terminado. «Marcando» dura lo que el lanzamiento real, porque termina con `lanzado_at`. **Corregido:** sin ese campo, la oficina pasaba a «timbre» 2 s antes del `Popen` (runner-live se escribe antes de lanzar). |
| 2 / b | Suena en vacío | `resultado.json` (`b_motor_inexistente`) | `motor:noexiste`: la tarea queda **fallida** con el motivo real («definitivo, sin reintentos: el motor 'noexiste' no existe en engines.json (hay: …)») y la fase es `suena_en_vacio`. |
| 3 / c | Cada motor atiende a su manera | `resultado.json` (`c_*`) | Meshy sin clave (runner-status real: «falta la clave en APIs»): `candado`, el gerente no deja el encargo. Con clave (simulado): `buzon` (el mensajero sale). En ningún caso hay alguien tecleando. llama apagado: `encendiendo` («enciende la luz»), con el motivo «apagado; se arranca solo». |
| 4 | Durante la llamada | `llamada-fin.png` | Línea punteada tenue de Growi a Luma (jefa de Local), temporizador `00:06` y Hermes Ollama «trabajando». A partir de 3 min el temporizador pasa a ámbar y el jefe dice «Sigue en ello...» (simulado: `ambar_ok`). El progreso sale de runner-live; no hay porcentajes. |
| 5 / d | Departamento ocupado | `resultado.json` (`simulado.d_*`) | «Claude está ocupado. Tu tarea queda en cola, es la n.º 3 de 3 (posición calculada como la elige el runner).» La urgente es la n.º 1 y su bocadillo empieza con «!». **Duda 19:** cola-live no trae la posición. Se calcula con el mismo orden que usa el runner: rondas, luego urgentes, luego por antigüedad. La cola del runner es **una sola** (es serie): la posición es global, no por departamento. |
| 5 / e | 3 en cola y urgente | `resultado.json` (`e_*`) | Con 3 tareas de Local en cola: «Local tiene 3 en cola. ¿Lo dejo en espera igual? (sí / no)». «no» → «Vale, no lo encolo.». «sí» → se encola con su id. **Urgente real:** 3 tareas encoladas con el runner parado, la urgente la última. Al arrancar, el runner la ejecuta **primero** y luego las otras dos, sin interrumpir ninguna en curso (solo elige al quedar libre). |
| 6 / f | No contesta | `resultado.json` (`simulado.f_*`) | Fallo pasajero con reintento programado: «Codex no contesta. Lo reintento a las HH:MM (reintento 1 de 3).» Al agotar los reintentos: «necesita revisión» y la tarea queda fallida en la app (lo hace el runner). |
| 7 / g | Fin de la llamada | `resultado.json` (`g_ok`) | «Listo, Claude se encarga.» o «Listo, te lo dejo por aprobar en la app.». La oficina muestra el estado, nunca el resultado. |

## Arreglos del protocolo hechos aquí (los encontró la prueba visual)
- **runner-live se leía cada 10 s hasta que existía:** el prototipo decidía si había «tarea en curso» mirando solo runner-live. Ahora también lo dicen cola-live (`en_curso`) y runner-status (`current`).
- **El hilo de lectura ya dormido no se enteraba:** cuando aparece una tarea nueva en curso, se despierta el lector de runner-live (`ya()`). Medido: la tarea arrancó a las 23:35:29 y la oficina la leyó a las 23:35:30,3.

## Discrepancia con el spec (para que decida Leandro)
- **Política de reintentos:** el spec pide «reintento en 2 minutos, máximo 2». El runner real reintenta a los **30 s, 2 min y 8 min (3 reintentos)**, con `RETRY_BACKOFF_S`. La oficina muestra **la del runner**: no cambié la política global del runner por una visualización. Si se quiere la del spec, se cambia `RETRY_BACKOFF_S = (120, 120)` y la oficina la sigue sola (`MAX_REINTENTOS_RUNNER` en `llamadas.py`).
- **Toast de «no contesta»:** hoy va al log de métricas de la oficina y al bocadillo. Los toasts son del spec 16.

## FALTA
1. Los dos cambios del runner (urgente, `lanzado_at`) solo están en el repo. La app instalada los recibe cuando Leandro instale el `growi-bridge.py` del repo y reinicie.
2. Animación de 2 frames del gerente levantando el auricular: el arte es borrador (specs 9–11). Hoy se ve con la actividad «al teléfono», la línea y los bocadillos.
3. La «posición» se calcula: si el runner cambia su orden, `llamadas.posicion()` tiene que cambiar con él (anotado en el código).

## COMO PROBARLO
```
python pruebas\oficina_llamadas_050\prueba_llamadas.py   # real + simulado (~4 min; Haiku de suscripción, ollama $0)
python pruebas\oficina_llamadas_050\demo_llamada.py      # ventana: llamada real con línea, temporizador y bocadillos
```
