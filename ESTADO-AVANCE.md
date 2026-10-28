# Avance de la noche (para retomar)

Rama `Claude`. Último commit pusheado: ver `git log -1`.

| Fase | Estado |
|---|---|
| 1 — gate de calidad (`t-gate-stop-hook-calidad`) | **LISTO** → `ESTADO-GATE-CALIDAD.md`, `ESTADO-FASE-1.md` |
| 2 — revisión solo-checks (`t-revision-solo-checks`) | **LISTO** → `ESTADO-REVISION-SOLO-CHECKS.md`, `ESTADO-FASE-2.md` |
| 3 — 0.4.0 fase B | **EN CURSO** → `ESTADO-FASE-3.md` (01, 03-07, 09-11, 13, 15-17, 19-22, 24, 25, 27-36 y 38 listos; 37, 39, 40 y 42 parciales (sin instalar / sin claves); 02, 08, 12, 14 y 18 saltados por GPU/descargas; 23 saltado por dependencia; 26 saltado por permiso de instalación) |
| 4 — 0.4.5 | sin empezar |

**Para retomar:** seguir la lista de la fase 3 desde el spec **040plus #4 t-agentes-paralelos-030** (040plus: 1 saltado, 2-3 listos), en el orden de la petición. Cada spec: leer su
`specs/opus-tasks-040*/<id>.task.json`, implementar en `growi-bridge.py`,
probar con una copia aislada (puerto 8797; harness de ejemplo en
`pruebas/prueba_automations.py`), escribir `ESTADO-*.md`, pasar
`python gate-calidad.py`, y hacer commit y push.
