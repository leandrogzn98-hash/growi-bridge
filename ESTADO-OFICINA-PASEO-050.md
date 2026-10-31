# ESTADO — t-oficina-paseo-050 (Oficina 0.5.0, spec 14 de 18)

**Fecha:** 30 oct 2026. **Veredicto:** LISTO las 7 subfunciones:
- la lógica, verificada con pruebas;
- las tareas reales (Sonnet, Hermes Ollama y «después de esto»), verificadas con el runner del repo en una instancia aislada;
- un visor del plano con cámara, avatar y ficha.

Lleva **un cambio en el runner** (`despues_de`), con parche reproducible. La app instalada no se tocó.

## Dónde está
- `oficina/paseo/paseo.py`:
  - `Rejilla` (A* sobre `plano.json`), `Duenio` (paseo y WASD), `Camara`
  - `Proximidad`, `ficha()`, `decidir()` (tabla por estado), `Frases`, `respuesta_bocadillo()`
  - `Hablar` (crea la tarea con ESE motor), `recordatorios()`
- `oficina/paseo/paseo_vista.py`: visor del paseo (plano real, cámara, los 14 en sus sillas y Leandro).
- Skin de Leandro: `assets/office/characters/skins/leandro/` (camisa azul Summit `#052048`, zapatillas blancas, pelo corto oscuro, sin corbata).
- Runner: `parches/parche_despues_de_050.py`: `encolar_tarea(despues_de=)`. El runner no recoge esa tarea mientras la otra espere aprobación o, si se aprobó, mientras siga en cola o en curso. Comprobado que, aplicado al commit anterior, reproduce `growi-bridge.py` y `encolar.py` exactos.
- Pruebas: `pruebas/oficina_paseo_050/prueba_paseo.py`.

## LISTO (evidencia en `pruebas/evidencia/oficina-paseo-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Movimiento | `resultado.json` (`a_movimiento`), `a-inicio.png`, `a-andando.png` | De la entrada a la silla de Dex: camino A* de 4 vecinos que rodea las mesas, 0 saltos, 0 baldosas de obstáculo pisadas. Velocidad fija de 3 baldosas/s, sin sprint: tarda exactamente pasos/3 s. WASD contra una pared no se mueve. La cámara sigue con suavizado y nunca sale del plano (600 fotogramas comprobados). En el visor: WASD y clic en el suelo. |
| 2 / b | Proximidad, solo postura | `resultado.json` (`b_proximidad`), `b-proximidad.png` | Al acercarse reaccionan los 5 casos: sin_tarea (mira la pantalla vacía), en_cola (hojea papeles), trabajando (teclea más rápido), esperando_aprobacion (levanta la mano y te mira) y gerente (levanta la vista del tablón y asiente). sin_senal y en_revision no reaccionan (dormir tampoco). A los 11 s ya no hay postura (máximo 10 s). Solo se re-dispara tras alejarse más de 1 s. No escribe nada. |
| 3 / c | Clic: dos modos explícitos | `c-clic-ficha.png`, `c-preguntar.png` | Ficha «Sonnet (Depto. Claude) — trabajando · Tarea: t-… · ronda 0/3» con [Preguntar] y [Pedir tarea]. El dueño elige; no se adivina. |
| 4 / d | Pregunta real | `resultado.json` (`d_pregunta_sonnet`) | Tarea real con `model: sonnet` y **sin criterios**. Bocadillo: «Sonnet dice: La capital de Francia es París. · $0.1307». El costo es el equivalente Max que da el runner (con la suscripción, el gasto real es $0). Más de 280 caracteres se cortan con «...» y queda `ver_completo` con el detalle del `.result.json` (result, costo, turnos, session_id). |
| 5 / e | Tarea real con ese motor | `resultado.json` (`e_tarea_ollama`) | A Hermes Ollama: el `.task.json` lleva `motor: ollama`. La frase («Me pongo en ello.» / «Voy con eso.» / …) es **None** antes de que la tarea exista y sale cuando está en la cola. Las frases nunca se repiten dos veces seguidas (40 muestras). |
| 6 / f | Tabla por estado | `resultado.json` (`f_tabla`, `g_despues_de_esto.rechazo`) | sin_tarea, terminado y fallido crean la tarea. Dormir despierta primero. trabajando, en_cola, en_revision, en_ronda y en_pausa van detrás «(posición N de M)». esperando_aprobacion **rechaza sin encolar nada** (real: `id: None`). sin_senal: «Sin señal: no sé si este agente está.», sin encolar. |
| 7 / g | «Después de esto» | `resultado.json` (`g_despues_de_esto`) | Real: Hermes Ollama con una tarea R2 retenida. «Después de esto» la encola marcada («Queda en cola para después de la revisión.»). **Sigue en cola 10 s** con la aprobación pendiente. Al aprobar, el runner corre primero la aprobada y después la marcada. **Corregido en la prueba:** la aprobada vuelve a la cola con mtime nuevo y la marcada se le colaba; ahora espera también a que termine. |
| 7 | Pegajoso | `resultado.json` (`recordatorios`) | Bocadillo «Te espero en revisión.» una vez por tramo de 5 min. Toast único a los 30 min. |

## FALTA
1. **El paseo no está dentro de la ventana de la oficina:** es un visor aparte con estados de escenario (rotulado DEMO). La lógica (`paseo.py`) es la que usará la escena final. Unirlo a la derivación real del spec 8 y al teléfono es del ciclo de vida (spec 18) y del motor Godot.
2. **Corrección como tarea prioritaria** (cuando el dueño corrige en vez de aprobar): el runner ya tiene `urgente` (spec 13), pero `Hablar` no tiene un modo «corregir» que la use. Queda para cuando haya UI de corrección.
3. **El toast de los 30 min y el punto de «tienes respuesta»** los genera `recordatorios()` y el bocadillo. Mostrarlos como toast es del spec 16.
4. La skin de Leandro es borrador (licencia: retoque humano). Los rasgos son neutros, sin intento de parecido.
5. El cambio `despues_de` del runner solo está en el repo; la app instalada lo recibe al instalar el `growi-bridge.py` del repo.

## COMO PROBARLO
```
python pruebas\oficina_paseo_050\prueba_paseo.py      # lógica + real (Sonnet de suscripción, ollama $0; ~3 min)
set PYTHONPATH=oficina\mediciones\.venv\Lib\site-packages
python oficina\paseo\paseo_vista.py                    # pasear con WASD / clic; clic en un agente
python oficina\paseo\paseo_vista.py --demo --salir-a 18
```
