# Avance de la noche (para retomar)

Rama `Claude`. Último commit pusheado: ver `git log -1`.

| Fase | Estado |
|---|---|
| 1 — gate de calidad (`t-gate-stop-hook-calidad`) | **LISTO** → `ESTADO-GATE-CALIDAD.md`, `ESTADO-FASE-1.md` |
| 2 — revisión solo-checks (`t-revision-solo-checks`) | **LISTO** → `ESTADO-REVISION-SOLO-CHECKS.md`, `ESTADO-FASE-2.md` |
| 3 — 0.4.0 fase B | **EN CURSO** → `ESTADO-FASE-3.md` (01 listo, 02 saltado, 03 listo) |
| 4 — 0.4.5 | sin empezar |

**Para retomar:** seguir la lista de la fase 3 desde el spec **04
t-blender-herramienta**, en el orden de la petición. Cada spec: leer su
`specs/opus-tasks-040*/<id>.task.json`, implementar en `growi-bridge.py`,
probar con una copia aislada (puerto 8797; harness de ejemplo en
`pruebas/prueba_automations.py`), escribir `ESTADO-*.md`, pasar
`python gate-calidad.py`, y hacer commit y push.
