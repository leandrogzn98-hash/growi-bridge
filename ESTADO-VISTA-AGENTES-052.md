# ESTADO t-vista-agentes-052 (componente 2 de 5 de la 0.5.2: Vista de Agentes)

Rama `Claude`, 30 oct 2026. **LISTO en el repo y verificado en una instancia aislada, con una tarea real de
Codex.** **FALTA en la app instalada:** esa versión no tiene las piezas en las que se apoya (los cubos de cuota,
la cadena de respaldo), así que llega con la actualización completa, no con un parche.

Spec: `specs/opus-tasks-052/t-vista-agentes-052.task.json`.
Prueba: `pruebas/prueba_vista_agentes_052.py`.
Evidencia: `pruebas/evidencia/vista-agentes-052/resultado.json`, `datos-reales.json` y
`growi-bridge-aislada.log`.

## Lo que había
- En Tareas, una pila: estadísticas, la tarjeta «Agentes» (solo los 2 huecos corriendo, en texto), el gasto, la
  tarjeta de aprobaciones, filtros y la tabla. Los datos estaban todos, pero repartidos, y ninguno decía el motor
  y el cubo de cada tarea.

## Cambios
| Archivo | Qué |
|---|---|
| `growi-bridge.py` | `vista_agentes()`, sin ventana. Hace una tarjeta por encargo, tomando la fila más reciente de su raíz en `cola.db` (sus rondas van dentro). El estado final sale de la familia y se completa con su `result.json`, los huecos en vivo (`agentes_vista`, que ahora da también `inicio_ts`) y el pedido de aprobación. Ventanas: Terminadas 24 h y 10 como máximo; Te necesitan, las aprobaciones siempre y lo demás de 7 días, 12 como máximo; el resto se cuenta en `mas`. No salen las rechazadas por ti, las archivadas ni las esperas cuyo encargo ya no está en `esperando\`. `en_cola` solo se cuenta. Si `cola.db` no se lee, `error` lo dice y las columnas van vacías (nunca un «nada» falso) |
| `growi-bridge.py` | Tablero `_vista_agentes_build` arriba de Tareas, en lugar de la tarjeta «Agentes» (`_agentes_build` y `_agentes_refrescar` ya no existen). Funciona con CustomTkinter y con Tk clásico de respaldo. «Aprobar» y «Rechazar» van a `_approve_ui` y solo aparecen en lo que se puede aprobar. «Ver» usa `_tarea_ver_en_lista()`, que ahora comparte con «Ver la tarea» del panel de Estado. La lectura va en un hilo cada 3 s y solo se pinta en la ventana; si cambian solo los tiempos, se repintan las etiquetas sin rehacer las tarjetas |
| `growi-bridge.py` | `GET /gateway/agentes`: lo mismo en JSON, en el mismo handler, puerto y token que `/gateway/estado` |
| `growi-bridge.py` | Un costo de 0.0 que nace con la familia no se muestra como «$0.00»: si ningún result trae cifra (codex, agy), sale «costo sin dato». Al motivo se le quita la coletilla «Lo intenté pero no pude confirmar…», para que se vea el porqué |
| `engines.json`, `availability.json`, `LEEME-growi-bridge.md` | **agy es Google AI Pro (plan pago), no free tier.** El cubo `google-agy` se llama ahora «Google AI Pro (agy)». Se quitaron «$0 en el free tier» y «Pro no está en el free tier»; ahora dice «$0 extra por tarea: va con la suscripción». Qué modelos y cuánta cuota incluye no lo dice agy (anotado como no comprobado). `ESTADO-MOTOR-GENERICO-052.md` corregido igual |
| App instalada (`C:\Users\forte\growi-bridge\engines.json`) | Esos mismos textos de la ficha de gemini (7 de 8; la sección de respaldo no existe en esa versión), con respaldo `engines.json.pre-google-ai-pro.bak`. Su `availability.json` no tenía la frase |
| `LEEME-growi-bridge.md` | Sección «Vista de Agentes (arriba de Tareas)» |

## Verificación
Instancia aislada `C:\Users\forte\growi-bridge\_prueba-vista-agentes-052\app`: el código del repo y la config
instalada solo leída. Guardrail «siempre». El tablero se construye en un Tk retirado (`withdraw`), sin
mostrarse ni tomar el foco, y los botones se pulsan con `invoke()`. Codex se lanza oculto.

| | Prueba | Resultado |
|---|---|---|
| a | 27 filas sembradas en `cola.db`, con familia y result | **OK**: t-va-curso y t-va-revisando en Trabajando; decisión, fallida, cuarentena y la de 2 rondas (una sola tarjeta, con la ronda 1) en Te necesitan; 14 terminadas de 24 h → 10 en Terminadas y `mas` = 4, la más reciente primero. No salen la rechazada, la fallida de hace 8 días, la terminada de hace 30 h, la archivada ni la espera sin encargo. La de cola, solo contada. El hueco en vivo trae hueco 1, cubo chatgpt-plus, 75 s, paso, 1 200 tokens y $0.0123 |
| b | Tablero con CustomTkinter y con Tk clásico | **OK** con los dos: cabeceras «Trabajando (2)», «Te necesitan (4)», «Terminadas (14)» y «y 4 más». Las fallidas no tienen Aprobar; Trabajando y Terminadas solo tienen «Ver». «Ver» abre Tareas con la tarea seleccionada y su detalle. Pie: «En cola: 1 tarea. t-va-cola: espera hueco…». Cuando cambian solo los tiempos, las mismas tarjetas (no se rehacen) |
| c | `/gateway/agentes` | **OK**: con token, 200 y las mismas columnas que `vista_agentes()`; sin token, 401 |
| d | De verdad, con Codex | **OK**: dos tareas de codex con una acción R1 declarada quedan retenidas en Te necesitan con Aprobar, Rechazar y Ver (pedido R1, vence el sáb 31/10). **Rechazar** en una: sale del tablero y su familia queda «rechazada». **Aprobar** en la otra: vuelve a la cola (sin columna, contada en el pie), a los 4 s está en Trabajando (la tarjeta aparece en el tablero) y a los 50 s en Terminadas: «sin revisión · 33 s · costo sin dato», motor codex, cubo chatgpt-plus, archivo «listo». Ningún diálogo |
| e | Sin congelar | **OK**: leer va en el hilo (~30 ms; la primera, en frío, 100-450 ms). Pintar en la ventana: 160-220 ms cuando hay que rehacer las 16 tarjetas (solo si cambia algo que no sea un tiempo) y casi nada al repintar tiempos |
| — | Datos reales (copia de `cola.db` y resultados de la app instalada, `datos-reales.json`) | Lee en 105 ms (670 ms la primera). **Te necesitan tiene 40 de la última semana** (12 a la vista + 28 «más»): sobre todo decisiones de 3 rondas sin cerrar y fallidas por «claude no está en el PATH». Terminadas: 13 de 24 h (10 a la vista) |
| — | Gate de calidad | **PASA** (py_compile, ruff, mypy, pytest 9/1 skip, smoke /gateway/salud) |

Costo: $0 extra. Tres tareas de Codex con ChatGPT Plus, una por corrida completa; la primera corrida no
retuvo las tareas porque el guardrail solo pregunta por acciones R1 o más, y se corrigió declarando la acción.

## FALTA / notas
- **App instalada:** el tablero llega con la actualización completa. Esa versión no tiene `cubo_de_motor` ni las
  piezas de 0.5.x en las que se apoya, así que un parche suelto sería frágil.
- **Te necesitan se llena con lo viejo:** con tus datos reales salen 40 en una semana. Si las cierras o archivas
  desde Tareas, salen del tablero. Si prefieres otra ventana (p. ej. 3 días), es `VA_NECESITAN_DIAS`.
- Cuando cambia el contenido, pintar las 16 tarjetas en CustomTkinter tarda unos 200 ms en la ventana: se nota
  como un instante, solo cuando entra o sale una tarea, no cada 3 s.
- «Te necesitan» solo tiene «Ver» para decisiones, fallidas y cuarentena: decidir, reintentar o cerrar sigue en
  el detalle de la tarea (el diseño solo pedía botones directos para aprobar y rechazar).
