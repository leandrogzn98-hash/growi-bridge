# Estado: automatizaciones (t-automations)

Rama `Claude`, 28 oct 2026. **LISTO**, con las FALTA de abajo.

Programador persistente dentro de la app. Un trabajo tiene horario
estructurado, encargo, motor y entrega. Vive en `cola.db`, en dos tablas
nuevas: `automatizaciones` y `automatizaciones_runs`. Se crea en lenguaje
natural, se ve en palabras normales, se edita, se borra y se apaga en un clic.
Todo corre con código local ($0); ningún trabajo usa un modelo.

## Código (`growi-bridge.py`, bloque «automatizaciones» antes de `build_gui`)
| Pieza | Qué hace |
|---|---|
| `automations_init()` (desde `cola_init`) | Crea las tablas y siembra los 5 iniciales (`INSERT OR IGNORE`: no pisa lo que hayas cambiado) |
| `auto_interpretar(texto)` | Reglas fijas en español, sin modelo: «en N minutos/horas/días …», «mañana a las 9 …», «a las 18:30 …», «cada lunes a las 9 …», «cada día a las 21 …». Lo que no entiende lo dice con ejemplos |
| `auto_crear` / `auto_borrar` / `auto_activar` | Guardan el **horario como JSON** (`{"tipo":"una_vez","ts":…}`, `{"tipo":"semanal","dia":0,"hora":"09:00"}`…). El texto original queda solo para «Editar» |
| `auto_describir(h)` | El horario en palabras («cada lunes a las 09:00», «una vez, el 27/10 a las 23:41 (se borra al hacerlo)») |
| `auto_tick` / `_auto_loop` | Hilo del carril A: chequeo de arranque a los 20 s y luego cada 30 s. Los de «una vez» se **borran tras ejecutarse**; el historial queda |
| `auto_ejecutar` | Corre el trabajo y escribe una fila en `automatizaciones_runs`: cuándo, resultado, detalle, motor y **costo** ($0) |
| `_auto_aviso_ok` | **Máximo 1 aviso proactivo al día.** Lo que pediste tú (recordatorios) siempre avisa |
| `automations_ui()` | Ventana «Automatizaciones» (CustomTkinter con respaldo clásico): crear, lista con Apagar/Encender, Editar y Borrar, e historial con costo. Se abre desde Ajustes → Notificaciones y atajos → Automatizaciones |

## Los 5 iniciales
1. **Chequeo de salud al arrancar** (`salud`). Lee proxy, llama-server, disco,
   Tailscale y cola pendiente. Avisa solo si algo está mal.
2. **Aviso de cuota Max al 75 %** (`cuota`, cada 30 min). Suma `cost_usd` de
   los `*.result.json` de los últimos 7 días (logs locales) y lo compara con
   `aviso_cuota_semanal_usd` de `settings.json`.
   - Sin ese límite el resultado es «sin dato»: Anthropic no publica la cuota de
     Max y **no se inventa** (como dice `max_quota()`).
   - Nunca llama a un modelo.
3. **Recordatorios de una vez**, que se borran tras ejecutarse.
4. **Vigía de la cola** (cada 5 min). Avisa de una tarea `en_curso` sin
   moverse más de 30 min, o de las tareas re-encoladas tras un corte
   (`GATEWAY["recuperadas"]`).
5. **Resumen 21:00** (`resumen`). En este código no había ningún resumen de
   las 21:00 (el mensaje de las 21:00 lo manda Growi desde fuera). Para **no
   duplicarlo**, el trabajo solo escribe `share\outbox\resumen-<fecha>.md` con
   las tareas del día, sin avisar. Es un trabajo más del programador.

El **brief pre-reunión** queda como hueco: fila apagada y sin horario
(«Hueco preparado para t-brief-reunion»). No se construyó.

## Verificación (con evidencia real)
`pruebas/prueba_automations.py` arranca **la app real** (copia en `%TEMP%`,
puerto 8797, `cola.db` propia) con su programador corriendo, y usa la ventana
con ratón y teclado de verdad. Evidencia en `pruebas/evidencia/automations/`.

| | Prueba | Resultado |
|---|---|---|
| a | Escribir «recuérdame en 1 minuto probar el gate de calidad» + Intro en la ventana | Guardado como `{"tipo":"una_vez","ts":…}`, encargo «probar el gate de calidad», motor local, entrega «aviso en la bandeja». La ventana dice «una vez, el 27/10 a las 23:41 (se borra al hacerlo)». **El bucle real lo ejecutó a su hora** (23:41:48, aviso «Recuerda: probar el gate de calidad») y lo borró de la lista; quedó en el historial |
| b | Chequeo de salud al arrancar (datos reales) | «proxy: ● Conectado — sales por EEUU; llama-server: sin respuesta de 127.0.0.1:8080 en 2 s; disco: 83.9 GB libres en C:; Tailscale: activo; cola: 0 pendiente(s)» |
| c | Cuota contra logs, no modelo | Sin límite: `sin_dato` («Anthropic no publica la cuota… no se inventa»). Con límite $10 y un `result.json` de $8: `aviso`, 80 %. **Llamadas a motores en toda la prueba: 0** (`_run_cli_engine`/`_run_http_engine` contados) |
| d | Trabajo apagado no corre | Vigía apagado y forzado a «le toca» → corridas antes/después **0 / 0** |
| e | Historial con costo | Filas con hora, nombre, resultado, detalle, motor «local (código, $0)» y `costo_usd 0.0` |
| — | 1 aviso al día | La segunda cuota del mismo día no avisa: «aviso no mostrado: ya hubo el aviso proactivo de hoy» |
| — | Sobrevive a reinicios | Tras cerrar la app, `cola.db` en disco sigue con los 5 trabajos y 4 corridas (`persistencia-tras-cerrar.json`) |

Capturas: `1-ventana-con-recordatorio.png`, `2-historial.png`. Log de la
prueba sin tracebacks.

## FALTA
- **Gemini Flash** como motor de un automation: ninguno lo necesita (todos
  son código). Si un trabajo futuro necesitara texto generado, el campo
  `motor` ya está; no se conectó a ningún motor.
- **Un aviso real de cuota de Max:** la cuota no es pública. El aviso
  funciona contra el límite que pongas en `aviso_cuota_semanal_usd`; no hay
  campo en Ajustes para ponerlo (no se añadió un ajuste nuevo).
- **El brief pre-reunión** es solo el hueco (t-brief-reunion).
- **Editar** un recordatorio es «cambiar el texto y Guardar», que lo
  reemplaza. No hay editor por campos.
