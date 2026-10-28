# ESTADO — Idempotencia, cuarentena y compensación (t-idempotencia-cuarentena-030)

Rama `Claude`. Prueba: `pruebas/prueba_idempotencia.py`. Usa una copia aislada y el runner real
`_process_one_impl`. El ejecutor es falso (dentro del proceso) y el juez «claude» es falso: rechaza la
primera vez y aprueba la segunda. La «muerte» entre hacer y apuntar se simula cortando la función justo
después del efecto. No gasta ni llama afuera. Evidencia: `pruebas/evidencia/idempotencia/evidencia.json`.

## LISTO
1. **run_id único por encargo**: el id del encargo original, la raíz. Va en el encargo, en cada ronda
   (`-r1.task.json`), en cada resultado, revisión, checkpoint de ronda y familia (`.orquestacion.json`), y en
   cada línea del registro de aprobaciones. El runner lo apunta también en el encargo original al tomarlo.
2. **idempotencia_key por efecto externo** (`efecto_ejecutar`): clave `run_id:paso`, y para dinero
   `run_id:paso:<fingerprint del payload>`. Se **registra en `cola.db` (tabla `efectos`) ANTES** de hacer el
   efecto.
   - Al repetir: si consta **hecho**, no se repite.
   - Si consta solo **registrado** (murió entre hacer y apuntar), primero **se comprueba** si se hizo; si sí,
     se marca hecho sin repetir.
   - Si no se puede comprobar → **cuarentena** (no se repite a ciegas).
   - El envío del pedido de cosecha a la VM (t-pedir-cosecha) ya pasa por esta puerta.
   - La aprobación va **antes** del efecto: es el pedido por paso de t-politicas-persistentes, que se aprueba
     antes de lanzar la tarea, no en el mismo paso.
3. **Estado `en_cuarentena`**: un fallo que no encaja en ninguna respuesta conocida (ni pasajero ni
   definitivo) no se reintenta solo ni se da por fallido. Queda en cuarentena, en la familia y en la cola,
   con `<tarea>.cuarentena.json`: el error, el final de stderr, la entrada (encargo, motor, carpeta,
   criterios…) y los efectos del run. Lo resuelves tú: «Volver a la cola», corregir, o Ctrl+K → «Abandonar
   la tarea en cuarentena». Patrón: reintento → cuarentena → escalada (tú) → rollback (compensación).
4. **Reporte de fallo completo** (`_reporte_fallo`): qué se intentó, qué quedó hecho (archivos comprobados y
   efectos registrados con su estado), qué no se pudo confirmar, cuánto costó (este intento y el total) y el
   siguiente paso:
   - reintentar más tarde o abandonar;
   - corregir la configuración o el encargo;
   - en cuarentena, decide tú.
5. **Compensación documentada** (`EFECTOS_COMPENSACION`, guardada con cada efecto):

   | Efecto | Compensación |
   |---|---|
   | correo | **sin compensación: revisión manual** |
   | ticket | cerrar el que lleva el run_id como marcador |
   | borrar | soft-delete primero |
   | dinero | reembolso con el fingerprint |
   | archivos | worktree o .bak |
   | pedido a la VM | retirarlo del outbox si la VM no lo leyó |

   `efecto_compensar` ejecuta la del pedido a la VM.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) run_id | encargo con 1 ronda de corrección → `run_id: t-idem-run` en los **9 archivos** (encargo, ronda, 2 resultados, 2 revisiones, familia, 2 checkpoints de ronda); el pedido de aprobación también |
| (b) sin duplicar | muerte simulada tras enviar → fila `registrado`; al reintentar → «ya_hecho: está en el buzón» (comprobado); 3.ª vez → ya hecho; **se envió 1 vez**. Sin forma de comprobar → `cuarentena`, no se repite. Dinero: 5 $ y 7 $ dan claves distintas |
| (c) cuarentena | error «0xBEEF: estado 7» → `en_cuarentena` (familia y cola), snapshot con error y entrada; luego «abandonar» → fallida |
| (d) reporte | 401: «Se intentó… No hay nada comprobado en archivos. No se pudo confirmar: HTTP 401… Costó: $0.0120… Siguiente paso: corrige la configuración o el encargo» |
| (e) compensación | pedido a la VM → «retirado …json»; correo → «sin compensación: revisión manual» |
| Tracebacks | 0 |

## FALTA
- Los efectos que hace **el motor por su cuenta** dentro de su corrida (un correo que mande Claude Code con una
  herramienta) no pasan por `efecto_ejecutar`. Bridge no intercepta las herramientas del CLI: los cubren el
  guardrail y las políticas. La puerta está para los efectos que hace Bridge (pedido a la VM; voz y otros
  cuando se conecten).
- La **escalada** de la cuarentena es humana: no hay aviso por tiempo (p. ej. «lleva 24 h en cuarentena»).

## COMO PROBARLO
`python pruebas/prueba_idempotencia.py` → `pruebas/evidencia/idempotencia/`.
