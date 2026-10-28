# ESTADO — Pedir cosecha (t-pedir-cosecha)

Rama `Claude`. Prueba: `pruebas/prueba_pedir_cosecha.py` (app real en una copia, puerto 8797; **no corre
Apify ni gasta nada**). Evidencia: `pruebas/evidencia/pedir-cosecha/` (`evidencia.json` + 6 capturas).

## LISTO
1. **Botón «Pedir cosecha»**: la app no tiene vista de radar/pipeline, así que la tarjeta «Cosecha de
   tendencias» va en **Tareas** (CustomTkinter con respaldo clásico) y en la paleta Ctrl+K («Pedir cosecha de
   tendencias»). El formulario pide en palabras: red (TikTok / Instagram), tema o cuentas, cuántos resultados y
   para qué brief (C1-C4 u otro). El id del Actor solo sale en «Detalle técnico».
2. **Estimación antes de enviar**: resultados, $ con la tarifa real del TikTok Scraper (**$3,70 por 1.000**)
   y lo que queda del Free ($5/mes). El gasto del mes sale de `inbox\cosecha\estado-vm.json` si la VM lo
   publica (`apify.usado_mes_usd`) más lo enviado sin resultado; si no, se suma de los pedidos que pasaron por
   la app, y se dice de dónde sale. Si no alcanza lo avisa (Apify se bloquea al agotarse). **Instagram: no
   hay tarifa real en el spec y no se inventa**: sin tarifa no hay estimación y no se envía (se puede poner
   en `settings.json` → `cosecha_tarifas.instagram`).
3. **Encolar a la VM con OK explícito**: «Guardar pedido» solo lo deja «esperando tu OK» (local, en
   `cosecha-pedidos.json`, ignorado por git). El OK es otro botón, «Dar el OK y enviar», con una confirmación
   que repite el costo («Esto GASTA créditos de Apify…»). Solo entonces se escribe
   `outbox\cosecha\<id>.json` con el pedido, su estimación, el Actor, `ok_explicito: true`, quién y cuándo
   lo dio, y dónde devolver el resultado.
4. **Resultado al volver**: la app lee `inbox\cosecha\<id>.resultado.json` (cada 10 s y al abrir) y muestra
   resultados, costo real vs. estimado y dónde quedó el dataset. Si pasan más de 2 h sin respuesta:
   «Pedido enviado hace X, sin respuesta de la VM» en rojo.
5. **Sin token, sin cosecha**: si ni la VM (`estado-vm.json` → `tiktok_ms_token`) ni este PC
   (`TIKTOK_MS_TOKEN`) lo tienen, la tarjeta dice «Falta el token de TikTok, lo pone Leandro» y un pedido
   de TikTok queda como **FALTA** sin enviarse.

## Evidencia (evidencia.json)
| Criterio | Resultado |
|---|---|
| (a) botón y formulario | desde la paleta abre Tareas con el formulario; campos en palabras; el Actor no se ve sin «Detalle técnico» |
| (b) estimación | 500 resultados ≈ **$1,85** (a $3,70/1.000); Free: quedan **$4,40** (0,60 usados según la VM, simulado) |
| (c) OK explícito | «no» en la confirmación → 0 archivos; «sí» → `outbox\cosecha\cosecha-…json` con `ok_explicito: true` |
| (d) resultado | «Listo: 487 resultados, costó $1,80 (estimado $1,85). Guardado en …» (respuesta de la VM simulada) |
| (d) sin respuesta | «Pedido enviado hace 3 h 0 min, sin respuesta de la VM» |
| (e) sin token | «Falta el token de TikTok, lo pone Leandro…»; pedido FALTA; 0 archivos para la VM |
| Tracebacks en el log | 0 |

## FALTA
- **La cosecha real de punta a punta**: falta `TIKTOK_MS_TOKEN` (cookie msToken, la pone Leandro) y correr el
  Actor GASTA créditos: no se hizo. La respuesta de la VM y su `estado-vm.json` se simularon en la prueba.
- **El lado de la VM** (leer `outbox\cosecha\*.json` con `ok_explicito`, correr `apify.py run`, escribir
  `inbox\cosecha\<id>.resultado.json` con `resultados`, `costo_usd`, `dataset` o `error`, y publicar
  `estado-vm.json` con `tiktok_ms_token` y `apify.usado_mes_usd`) no vive en este repo: ese es el contrato.
- Tarifa de Instagram: sin dato real; no se inventó.

## COMO PROBARLO
`python pruebas/prueba_pedir_cosecha.py` → mira `pruebas/evidencia/pedir-cosecha/`.
En la app: Tareas → «Cosecha de tendencias» → «Pedir cosecha», o Ctrl+K → «Pedir cosecha».
