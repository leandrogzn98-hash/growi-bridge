# Specs re-nivelados (para Claude Code)

Estos son los specs de Growi Bridge re-nivelados por modelo (Opus/Sonnet/Haiku) el 27 oct 2026, copiados desde la VM. Cada `.task.json` es autocontenido: trae su `model` (qué modelo usar), `prompt` (con MODO NO-INTERACTIVO), `criterios` y `timeout_min`.

## Estructura

- `opus-tasks-030/` — Fase A 0.3.0 (28 specs; la cadena del puente ya los está corriendo; `CADENA-ESTADO.json` dice en cuál va).
- `opus-tasks-040/` — Fase B 0.4.0 (39 specs; la cadena arranca cuando la Fase A esté completa).
- `opus-tasks-040plus/` — 0.4.0+ manuales (12 specs que no van en cadena automática).
- `opus-tasks-045/` — 0.4.5 (20 specs).
- `opus-tasks-050/` — 0.5.0 oficina (18 specs).
- `opus-tasks/` — Fixes y tareas manuales: `t-mutex-instancia-unica`, `t-gate-stop-hook-calidad`, `t-revision-solo-checks`, `t-minimizar-bandeja`, `t-integrar-timeout-bandeja`, `t-r3-riesgos` y resto; `leandro-directo/` trae los dos fixes directos (`t-timeout-latido-lanzador`, `t-carril-b-sin-ventana`).
- `LOTES.md` — 6 lotes fusionados (95 specs → 89 ítems) y el mapa de qué se fusionó.
- `REVISION-LIGERA-ANALISIS.md` — por qué la revisión ya es barata (checks deterministas + juez local primero) y qué falta para la dieta completa del prompt.

## Reglas para trabajar con estos specs

- Lee el `model` de cada spec y úsalo (Opus solo donde el spec lo pide; Sonnet/Haiku donde indica).
- Los specs asumen que trabajas en este repo, rama `Claude`. NO toques `C:\Users\forte\growi-bridge\` directamente: todo cambio va aquí y se integra después.
- Cada spec pide un `ESTADO-<TEMA>.md` con evidencia real por subfunción. Sin evidencia, no está terminado.
- Los `CADENA-ESTADO*.json` y `CADENA-LOG*.md` son una foto del estado de la cadena en la VM al copiar; la fuente de verdad de la cadena vive en la VM, no aquí.
- Nada de aquí contiene secretos: si un spec menciona un token o una clave, es como requisito documentado (lo pone Leandro), nunca el valor.
