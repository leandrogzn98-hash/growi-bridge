# Spike WhatsApp: qué vía usar (t-spike-whatsapp)

> **Estado honesto: NO se probó ninguna vía en vivo.** En esta sesión no se autorizó instalar código externo:
> el mismo bloqueo que con OpenCode (spec 26). Tampoco hay un número de pruebas, y el personal no se vincula.
> Lo que sigue son datos **reales de los registros** (consultados el 28-oct-2026), lo que hay en este PC, la
> recomendación razonada y el procedimiento para la prueba en vivo. Nada de lo de abajo dice «funciona» sin
> haberlo visto.

## Lo que hay en el PC
| Pieza | Versión | Basta para |
|---|---|---|
| Node.js | v24.20.0 (npm 11.19.0) | Baileys pide `node >= 20` → **sí** |
| Python | 3.12.10 | waeys pide `>= 3.10`, pyaileys `>= 3.11` → **sí** |

## Las tres vías (datos del registro; prueba en vivo pendiente)
| | Baileys (sidecar Node) | waeys (Python) | pyaileys (Python) |
|---|---|---|---|
| Paquete | `@whiskeysockets/baileys` | `waeys` | `pyaileys` |
| Última versión | **7.0.0-rc14** (29-jul-2026; *release candidate*); estable anterior `legacy` **6.7.24** | **0.1.3** (las 4 versiones salieron el mismo día, 3-ago-2026) | **0.1.5** (19-ago-2026; primera 0.1.0 el 16-feb-2026) |
| Licencia | MIT | **no declara licencia** en PyPI | MIT |
| Dependencias | ws, pino, p-queue, libsignal, protobufjs, lru-cache, @hapi/boom, async-mutex, music-metadata, whatsapp-rust-bridge, @cacheable/node-cache | solo `websockets>=12.0` | `cryptography>=42`, `protobuf>=4.25`, `websockets>=12` (+ `qrcode` opcional) |
| Login | QR / código de emparejamiento | QR / código (según su doc) | QR (extra `qrcode`) |
| Instalar | **no probado** (instalación no autorizada en la sesión) | **no probado** (ídem) | **no probado** (ídem) |
| Conectar (QR) | FALTA: sin número de pruebas | FALTA: ídem | FALTA: ídem |
| Texto enviar/recibir | FALTA | FALTA | FALTA |
| Imagen enviar/recibir | FALTA | FALTA | FALTA |
| Estable 2 h / 48 h | FALTA (0 h medidas) | FALTA (0 h) | FALTA (0 h) |

La 4.ª vía, **Meta WhatsApp Cloud API** (oficial), es posterior. Es la única sin riesgo de baneo, pero exige
verificación de negocio, un número registrado y una URL pública para webhooks, y cobra por mensaje desde
el 1-jul-2025 (las respuestas dentro de las 24 h también, desde el 1-oct-2026). No es gratis ni inmediata.

## Recomendación (provisional hasta la prueba en vivo)
- **Ganadora: Baileys como sidecar Node gestionado por Bridge**, con el mismo patrón que llama-server: Bridge
  lo arranca, lo vigila y lo mata, y el QR sale como imagen en la ventana. Por qué:
  - Node ya está en el PC y cumple la versión.
  - Es MIT.
  - Es la librería con más uso y la que siguen los ports de Python.
  - Bridge solo empaqueta un `.js` pequeño y un `package.json` con la **versión exacta fijada**: hoy
    `6.7.24` (la estable), no la `7.0.0-rc` mientras sea *release candidate*.
  - Al usuario se le exige Node ≥ 20. Coste: $0.
  - Mantenimiento: WhatsApp cambia el protocolo, así que hay que actualizar Baileys cuando rompa. El vigía
    lo detecta (la sesión cae y no vuelve) y lo avisa.
- **Reserva: pyaileys** (Python, sin Node). Es MIT y lleva medio año de versiones, pero es pre-1.0, sin
  garantías, y según su doc no tenía grupos E2E completos.
- **Descartada para empaquetar: waeys.** Sin licencia declarada no se puede redistribuir, y todas sus
  versiones son del mismo día. Se puede mirar como referencia, no meterla en Bridge.

### Lo que NO se promete
Plantillas de WhatsApp Business, botones interactivos, catálogos, verificación de empresa, «WhatsApp
Business». Baileys no da nada de eso; solo lo da la Cloud API (de pago, fase posterior).

### Riesgo de baneo y mitigación
Baileys imita WhatsApp Web sin autorización de Meta. WhatsApp avisa de baneo temporal o permanente. La
comunidad reporta detecciones a las 2-8 semanas, y suspensiones a las 48 h con actividad 24/7 desde IP de
servidor. Mitigación:
- **número secundario**, nunca el personal (+58 414 …, canal de trabajo de Leandro);
- volumen bajo;
- solo el dueño y contactos aprobados (lista blanca);
- nada de difusión masiva ni mensajes a desconocidos;
- desde el PC de casa, no desde una IP de servidor.

## Constancia del número personal
**El número personal de Leandro NO se vinculó a nada.** No se generó ni se escaneó ningún QR con él; ni
siquiera se instaló la librería. Para vincular el personal hace falta su decisión por escrito con este
riesgo delante. No existe tal documento, así que no se hace.

## Procedimiento para la prueba en vivo (para Leandro o un task posterior)
1. Conseguir un **número de pruebas** (SIM secundaria) con WhatsApp instalado.
2. Autorizar la instalación en una carpeta aislada (no en la app instalada):
   - Baileys: `npm init -y && npm install @whiskeysockets/baileys@6.7.24 qrcode` en `%TEMP%\spike-wa\baileys`.
   - pyaileys: `python -m venv %TEMP%\spike-wa\pyaileys && ...\Scripts\pip install "pyaileys[qrcode]==0.1.5"`.
3. Para cada vía, un script corto:
   - conecta, guarda el QR como PNG y escanéalo con el **número de pruebas**;
   - manda «hola» al número personal y apunta si llega;
   - responde desde el personal y apunta si el script lo recibe;
   - lo mismo con una imagen.
   - Apuntar cada error **tal cual** en la tabla de arriba.
4. Estabilidad: dejar la vía que conecte corriendo, escribiendo cada evento de conexión (`open`, `close` y su
   motivo, reconexión) con la hora en `whatsapp-estabilidad.log`. Medir al menos **2 h continuas**; el
   criterio es **48 h sin volver a vincular**. Resultado = horas conectada, número de caídas y si alguna
   pidió QR otra vez.
5. Con eso, confirmar o cambiar la recomendación y fijar la versión exacta.
