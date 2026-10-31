# ESTADO — t-agente-ventas-052 (0.5.2, componente 5 de 5: agente de ventas)

**Fecha:** 31 oct 2026, 01:00. **Veredicto:** LISTO la parte segura del diseño (`DISENO-052-SKILLS-Y-VENTAS.md`, **propuesta sin aprobar por Leandro**). Es un asistente hecho de piezas que ya existen (perfil + skills como unidades + workflow) que **trabaja solo en borrador**.

**El envío NO se implementó a propósito.** Escribir a un prospecto es una acción hacia fuera: canal, remitente, plantilla legal y si alguna vez se envía sin aprobar uno por uno los decide Leandro. Verificado con Haiku real en una instancia aislada, sobre una lista **inventada y rotulada**. La app instalada no se tocó.

## Qué hay
- `asistentes/ventas.md`: perfil «Ventas».
  - Tono cercano, guardrail «Preguntarme siempre», carpeta propia `growi-bridge\ventas` y skills `prospectar`, `redactar-propuesta` y `seguimiento`.
  - Reglas: nunca envía, no inventa, solo la lista que deja Leandro, datos personales en su carpeta.
- Tres skills con contrato (unidades del #4):
  - `prospectar` (entradas lista, nicho, ciudad, cuántos → `prospectos.csv`)
  - `redactar-propuesta` (oferta, cuántas → `propuestas.md`, con «BORRADOR — no enviado» arriba)
  - `seguimiento` (días → `seguimiento.md`)
- `workflows/ventas-semana.json`: prospectar → propuestas → seguimiento, con parámetros lista, nicho y oferta (por defecto `[PENDIENTE: oferta]`).
- `growi-bridge.py`: las `entradas` de un paso de workflow se rellenan con sus parámetros, igual que el prompt. Parche reproducible: `parches/parche_entradas_wf_052.py`.

## LISTO (evidencia en `pruebas/evidencia/agente-ventas-052/`; prueba: `pruebas/prueba_agente_ventas_052.py`)
| Caso | Resultado |
|---|---|
| Perfil y skills | `asis_buscar("ventas")` carga el perfil (guardrail «siempre», sus 3 skills). Las 3 skills son válidas y tienen sus entradas y salidas en el índice. |
| Workflow | Pasa `wf_validar`. Costo estimado antes de lanzarlo: «$0.011 eq. Max (rango $0.004–$0.033), sin ejecuciones previas: estimado grueso por tokens». |
| Corrida real (Haiku, de suscripción) | Plan **terminado**, las 3 fases terminadas. Entradas rellenadas desde los parámetros (`nicho: comercios de comida en Barquisimeto`). Salen `prospectos.csv`, `propuestas.md` y `seguimiento.md` (copias en la carpeta de evidencia). |
| Honestidad de las salidas | **Prospectos:** los 2 de Barquisimeto y de comida con prioridad 1 y los otros 2 con prioridad 3, cada uno con su motivo tomado de la lista; contactos `[PENDIENTE: dato]`, no inventados. **Propuestas:** «BORRADOR — no enviado…» arriba, oferta `[PENDIENTE: oferta]`, **0 precios**, y «la lista no indica un problema concreto; no lo supongo». |
| Sin envío | 0 coincidencias de smtp, sendmail, Resend, `wa.me`, la API de WhatsApp, `send_message` o `requests.post` en las skills, el perfil y el workflow. 0 `acciones` declaradas en los task de las fases. |

## [DECIDE LEANDRO]
1. **Qué negocio vende el agente** (HAYAI, Summit, SalPro…) y **la oferta**. Hoy es `[PENDIENTE: oferta]`.
2. **Fuentes de prospectos.** Hoy solo un CSV que dejas en `ventas\`. Firecrawl, Apify y Bright Data son de pago y no se usan sin tu OK.
3. **Envío:** canal (Resend o WhatsApp), remitente, plantilla y política (¿siempre uno por uno?). No existe ningún código de envío.
4. Aprobar o cambiar el diseño de #4 y #5 (`DISENO-052-SKILLS-Y-VENTAS.md`).

## FALTA
- La carpeta `C:\Users\forte\growi-bridge\ventas` no se creó en la instalación: se crea al instalar este componente (y el perfil necesita que exista).
- El perfil se ve en la app cuando se instale el `growi-bridge.py` del repo: los asistentes ya existen en la app instalada, pero falta copiar `asistentes/ventas.md`.

## COMO PROBARLO
```
python pruebas\prueba_agente_ventas_052.py     # ~5 min; Haiku de suscripción ($0 real)
```
En la app (tras instalar): Tareas → Workflows → «Ventas de la semana (borrador)» → nicho → Ejecutar. Los borradores quedan en la carpeta de la ejecución.
