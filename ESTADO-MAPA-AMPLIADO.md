# Estado: mapa ampliado (t-mapa-ampliado, dentro de t-lote-conectividad-040)

Rama `Claude`, 28 oct 2026. **LISTO.**

## Qué se hizo
- **5 filas nuevas** en `availability.json` (son datos; el formato del archivo
  no cambió): `ollama_registry` (registry.ollama.ai), `huggingface`,
  `github` (api.github.com), `tailscale_ctrl`
  (controlplane.tailscale.com) y `cloudflare`.
- **Tipo nuevo `servicio`** (`_check_servicio` en `growi-bridge.py`).
  - Cada fila se mide **dos veces**: directo y por el proxy del VPS. Sin proxy
    guardado, lo dice («sin proxy guardado, no se mide»).
  - Resultado: «Responde directo y por el proxy» / «solo directo» / «solo por
    el proxy» / «No responde» / **«No se pudo comprobar en N s»**. Un timeout
    nunca deja la fila en blanco.
  - Cada fila lleva latencia y vía (`ruta`: directo / proxy / ambas).
  - **Lento** = más de **2 s** (`MAPA_LENTO_MS`, umbral nuevo) en la ruta
    más rápida → la fila pasa a aviso con «lento (más de 2 s)».
- **El mapa alimenta al router y al descargador:**
  - **Router** (`_router_available` → `mapa_permite_nube`): regla de oro. Si
    el mapa tiene el **proxy en rojo** y Claude (o codex o gemini) no llega
    directo, **ni se intenta**. También si «forzar proxy» está puesto con el
    proxy caído.
  - **Descargador** (`lib_route`): en `auto`, si la fila de Hugging Face es
    reciente (< 15 min) decide con ella: solo proxy → por el proxy; directo o
    ambas → directo. Si no hay fila reciente, mide como antes.
- **Sin congelar:** el mapa ya medía en hilos (`start_availability`). Las
  filas nuevas usan el mismo camino.

## Verificación (red real; `pruebas/prueba_mapa_ampliado.py` → `pruebas/evidencia/mapa-ampliado/evidencia.json`)
| | Prueba | Resultado |
|---|---|---|
| a+b | Las 5 filas, directo **y** por proxy | Todas «Responde directo y por el proxy». Directo: registry.ollama.ai 350 ms (HTTP 404, responde), huggingface 545 ms, github 720 ms, controlplane.tailscale.com 689 ms, cloudflare. Por el proxy: ~4 s. El detalle de cada fila trae las dos medidas |
| c | Proxy caído (simulado: el proxy apunta a un puerto cerrado) | Mapa: proxy **falla** («El proxy no responde: rechaza la conexión…»), Claude falla, Hugging Face «solo directo». Router: `claude` → **no disponible**: «el mapa tiene el proxy en rojo… y claude no llega directo». `route_task`: «Automático eligió Sonnet…, pero sonnet no está disponible: el mapa tiene el proxy en rojo…» |
| c' | Descargador | Con el mapa normal: «directo a huggingface.co (el mapa dice: Responde directo y por el proxy (971 ms).)» |
| d | Sin congelar | Mientras el mapa medía las 5 filas en segundo plano (6,6 s), un reloj de 50 ms en la ventana tuvo un **hueco máximo de 346 ms** (100 ticks). La vuelta completa del mapa (11 filas) tarda **34 s**, en hilos |

## FALTA / notas
- El hueco de 346 ms está un poco por encima de 300 ms: es el
  `_render_avail()` que dibuja el estado «comprobando…» al empezar. No es
  un cuelgue.
- Las filas nuevas salen en la página Estado como las demás, pero sin
  captura en esta prueba.
