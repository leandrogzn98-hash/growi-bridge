# ESTADO — Panel de Estado del gateway (t-panel-estado-gateway)

Rama `Claude`. Prueba: `pruebas/prueba_panel_estado.py` (app real en una copia, puerto 8797).
Evidencia: `pruebas/evidencia/panel-estado/` (`evidencia.json` + 5 capturas).

## LISTO
1. **Un solo panel con secciones, en palabras normales** (sobre el panel del gateway que ya existía, ahora
   reordenado): Gateway (vivo desde, una sola instancia, acceso remoto, runner, «ahora mismo» desde
   `runner-live.json`), Canales, Skills, Cadena de modelos y respaldo (modelo activo, orden de la cadena,
   **último cambio de motor con su motivo**, revisión, respaldo por motor, modelos del PC), Motores, Cola
   (pendientes / en ejecución / fallidas / esperando aprobación o decisión).
   - Puertos, pid, mutex, lockfile, token y base URL viven en **«Detalle técnico» plegable** (Mostrar / Ocultar).
     En la vista principal las direcciones se dicen en palabras («sin respuesta del servidor local»), y un
     motor instalado dice «programa instalado» en vez de la ruta del binario.
   - Nuevo `motor_cambio(de, a, motivo)` + `_CAMBIOS_MOTOR`: lo registran la caída de la nube al modelo local
     (`local_fallback_model`), una superficie cuyo modelo dejó de estar (`superficie_modelo`) y un cambio de
     motor entre rondas. En memoria: si no hubo ninguno dice «ninguno desde que arrancó».
2. **Datos reales, nunca inventados**: cada sección lee su fuente (plano de control → cola.db, engines.json,
   ~/.claude/skills y skills/ de Bridge, runner-live.json). Fuente que no responde → «sin datos: …» en rojo
   con el motivo y lo que no se perdió («Las tareas siguen guardadas en la cola»).
3. **Acciones desde el panel**: «Ver la tarea» (lleva a Tareas con la tarea seleccionada y su detalle),
   «Ver tareas», «Ir a Modelos», «Comprobar» en un motor no disponible (relee ya, sin esperar los 10 s),
   «Reintentar» en la cola o en el gateway caído, «Mostrar/Ocultar» el detalle técnico.
4. **Actualización sin congelar**: cada 3 s en un hilo. La comprobación de motores ya no bloquea la
   respuesta: la primera lectura (o tras «Comprobar») va en segundo plano y la sección dice
   «comprobando… (las demás secciones no esperan)». El dibujo es incremental (solo se crean las filas
   nuevas) y «Reintentar» ya no borra lo que se ve mientras comprueba.

## Evidencia (evidencia.json)
| Criterio | Resultado |
|---|---|
| (a) secciones | Gateway, Canales, Skills, Cadena de modelos y respaldo, Motores, Cola (`a_filas` con los textos reales) |
| (a) sin puertos en la vista | `127.0.0.1: false, 8797: false, token: false`; con «Mostrar» salen pid, `127.0.0.1:8797`, túnel y token |
| (b) servicio caído | llama-server no corre: «no disponible: sin respuesta del servidor local en 2 s» en rojo + «Comprobar» |
| (b) fuente que no responde | cola rota (simulada): «sin datos: no se pudo leer (…database is locked…). Las tareas siguen guardadas» + «Reintentar»; al reintentar vuelve |
| Último cambio de motor | «motor:inexistente → Automático, porque Chat de Tareas: ya no está en la lista…» (cambio real de `superficie_modelo`) |
| (c) Ver la tarea | página `tareas`, selección `t-panel-prueba`, detalle con el encargo |
| (c) Ir a Modelos | página `modelos` |
| (c) Comprobar | motores releídos (`releido: true`) |
| (d) comprobando… | con llama tardando 4 s (simulado en hilo de fondo): a los 1,3 s «comprobando…» y Cola/Skills/Canales ya rellenos |
| (d) sin congelar | durante la comprobación: p95 121 ms por vuelta del bucle de Tk, peor 0,67 s (al crear las filas nuevas) |
| Tracebacks en el log | 0 |

## FALTA / notas
- El registro de cambios de motor es en memoria (desde que arrancó); no hay todavía un router con cadena de
  fallbacks que cambie de motor por sí solo: eso es `t-router-fallbacks` (spec 35), que usará `motor_cambio`.
- Nota de la prueba: dentro del arnés en-proceso la primera vuelta de `update()` tarda ~60-120 s (dibujo
  inicial de toda la ventana con la consola de python). Medido DESDE FUERA sobre la app real visible
  (`WM_NULL` con `SendMessageTimeout`), la ventana se cuelga ~14 s mientras se construye (lo ya conocido
  de build_gui) y luego solo tirones de 0,5-2,6 s: el arnés no refleja la app real en ese punto.
- Durante la prueba apareció una copia de prueba vieja mía (`growi-prueba-reinicio-aislado`, pid 24716)
  ocupando 8797; se cerró (no era la app instalada, que usa 8787).

## COMO PROBARLO
`python pruebas/prueba_panel_estado.py` → mira `pruebas/evidencia/panel-estado/`.
En la app: pestaña Estado → tarjeta «Gateway».
