# CRON-045.md — BORRADOR (no crear todavía)

**Estado: BORRADOR.** Este archivo es solo el contenido exacto del cron que moverá la cadena de la 0.4.5. **NO está creado en `~/workspace/cron.d/`** — eso lo decide el coordinador. Cuando lo apruebe, el archivo va en `~/workspace/cron.d/minutely/cadena-diseno-045__interval@15m.md` con este contenido.

**Pendiente de rellenar al crearlo:** `chat_id` y `device_id` (en `delivery` y en `metadata.originating_chat_context_json`) son los del chat desde el que el coordinador cree el cron. No se inventan: se copian del cron de la cadena que esté activa en ese momento (hoy, `cadena-fase-b-040`). El `at` es la hora de creación.

---

```yaml
---
id: cadena-diseno-045
title: Cadena automática 0.4.5 rediseño de interfaz (Growi Bridge)
enabled: true
mode: task
schedule:
  kind: interval
  timezone: America/Caracas
  at: 2026-10-27T00:00:00
  every: 15m
timeout_secs: 300
delivery:
  - chat_id: <CHAT_ID_DEL_COORDINADOR>
metadata:
  tags: [cron:automatic-interval-anchor]
  originating_chat_context_json: '{"chat_id":"<CHAT_ID_DEL_COORDINADOR>","origin_provider":"main","chat_kind":"direct","event_kind":"message","require_mention":false,"device_id":"<DEVICE_ID_DEL_COORDINADOR>"}'
  presentation_locale: es-ES
---
Cadena automática 0.4.5 (rediseño de interfaz) de Growi Bridge: cada 15 minutos corre el script `python3 /home/hatch/workspace/shared-bridge/cadena-045.py` (modo real, sin --dry-run) y lee el resultado.

El script es el que decide: solo envía un spec al runner del PC cuando la fase en `~/workspace/shared-bridge/opus-tasks-045/CADENA-ESTADO-045.json` es "diseno-045" Y la Fase B está completa (`~/workspace/shared-bridge/opus-tasks-040/CADENA-ESTADO-040.json` en "completa"), el runner está libre y el spec anterior quedó verificado OK. Si algo falla, el script detiene la cadena solo y lo anota en `CADENA-LOG-045.md`.

Tu trabajo en cada corrida:
1. Ejecuta el script con `muse.exec` y lee las últimas líneas de `~/workspace/shared-bridge/opus-tasks-045/CADENA-LOG-045.md`.
2. NO escribas ningún mensaje a Leandro ni a ningún chat, pase lo que pase (ENVIADO, verificado OK, DETENIDO o CADENA COMPLETA). Estamos de noche con mandato de silencio: el coordinador nocturno revisa el log y el informe de la mañana lo entrega el agente principal. Quédate en silencio siempre.
3. Nunca envíes un spec a mano, nunca edites CADENA-ESTADO-045.json ni CADENA-LOG-045.md, nunca cambies la fase. Solo el coordinador nocturno cambia la fase a "diseno-045" cuando la Fase B esté completa. No toques el runner ni el PC.
4. Si el script da error de conexión con el puente, anótalo solo en el log y quédate en silencio.
```

---

## Recomendación: cadena propia, NO dentro de la cadena de Fase B

**La 0.4.5 va con cadena propia (`cadena-045.py` + este cron). No se mete dentro de `cadena-040.py`. Motivos:**

1. **Una cadena por release (precedente 030/040/050).** Cada release tiene su propio script, su propio estado y su propio log. Meter 18 specs de rediseño dentro de la cadena de Fase B mezclaría dos releases en un mismo estado y un mismo log, y la marca de «Fase B completa» dejaría de significar nada.
2. **El gate es distinto.** La cadena de Fase B se activa cuando la Fase A está completa; la 0.4.5 se activa cuando la Fase B está completa. Son dos condiciones diferentes que no caben en un solo `ORDEN` sin reescribir la lógica de fases de `cadena-040.py` (que ya está en producción corriendo cada 15 min; tocarla de noche para añadir otra release es el tipo de cambio que rompe una cadena que funciona).
3. **El orden de la 0.4.5 depende de la Fase B terminada** (t-ajustes-reorg, t-mapa-ampliado, t-teclado-foco, t-matriz-estados, t-politicas-persistentes-030, t-mascota-estados). Si los specs 045 corrieran dentro de la cadena 040, podrían enviarse antes de que esos specs de Fase B existieran. Con cadena propia, el gate (`CADENA-ESTADO-040.json` en `completa`) lo impide por construcción.
4. **Detener una no detiene la otra.** Si un spec 045 falla y detiene su cadena, la Fase B sigue (o ya terminó) sin contaminarse, y viceversa. El `detenido` de cada release vive en su propio estado.
5. **Coste cero de la separación.** `cadena-045.py` es el mismo patrón probado de `cadena-040.py` (mismo puente, mismo mtime de `processing/`, mismo fail-closed). No hay código nuevo que depurar, solo otro cron cada 15 min que no hace nada hasta que su fase se active a mano.

**Cuándo activar:** crear este cron cuando la Fase B esté cerca de terminar (o ahora mismo: mientras su fase sea `espera-fase-b` no envía nada). Cambiar la fase a `diseno-045` en `CADENA-ESTADO-045.json` solo cuando `CADENA-ESTADO-040.json` diga `completa`. No desactivar el cron de Fase B hasta que la Fase B esté completa; los dos crons pueden convivir (cada uno no hace nada fuera de su fase).
