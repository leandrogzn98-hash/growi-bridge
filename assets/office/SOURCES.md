# SOURCES.md — origen y licencia de cada asset de la oficina

**Regla (INVESTIGACION-0.5.0 §7.4 y PALETA-Y-SKINS §8):**
- **Personajes protagonistas:** arte original de Bridge. Licencia © Leandro / HAYAI, a formalizar.
- **Decoración y props:** solo CC0, o CC-BY con su crédito aquí.
- **Nunca:** packs NC, ND o SA como base de personajes; personajes con copyright (Mario, Pokémon, Stardew Valley…); arte de licencia dudosa; ni arte de IA sin retoque humano píxel a píxel.

Cada asset de terceros lleva una fila: autor, URL, licencia, fecha de descarga, qué se usa y qué se modificó. Si un asset no tiene fila, no entra.

## Assets de terceros
| Asset | Autor | URL | Licencia | Descargado | Qué se usa | Qué se modificó |
|---|---|---|---|---|---|---|
| — | — | — | — | — | Ninguno todavía. | — |

## Assets propios
| Asset | Origen | Estado |
|---|---|---|
| `paleta.json`, `paleta.gpl` | Hex con fuente escrita (spec 9, PALETA-Y-SKINS §15, color muestreado de la mascota). Los tonos se derivan por cálculo. | **PARCIAL**: 14 de 24; falta PALETA-Y-SKINS §1. |
| `esqueleto/*` | `oficina/arte/generar_base.py` | BORRADOR de script: valida el formato y las capas. |
| `personajes/growi.*` | `oficina/arte/generar_base.py` | **BORRADOR de IA, sin retoque humano**: no se usa como arte final hasta retocarlo en Pixelorama. |
| `comun/z.*` | `oficina/arte/generar_base.py` | BORRADOR de script. |
