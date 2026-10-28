# Protocolo del gadget por serie — versión 1 (PROPUESTA)

> **Es una PROPUESTA.** Sin hardware no se puede validar contra un ESP32 real. Se probó con el emulador
> `pruebas/emulador_gadget.py`. No está atado a ningún modelo de gadget: vale cualquier cosa que hable texto por
> USB/serie.

## Línea
- **Texto plano UTF-8**, una orden por línea, terminada en `\n` (un `\r` se ignora). Máximo **240 caracteres**.
- **Por defecto**: 115200 baudios, 8N1, sin control de flujo. En la app se eligen los baudios (9600, 57600,
  115200 o 230400) y el timeout de lectura.
- Cada orden de la app recibe **una** respuesta que empieza por `OK` o `ERR`.
- El gadget puede mandar en cualquier momento líneas `EVENTO` o `PEDIR`.

## La app pide → el gadget responde
| Orden | Respuesta | Para qué |
|---|---|---|
| `HOLA <versión>` | `OK HOLA <nombre> <versión>` | Saludo al abrir: el gadget dice quién es. Si no contesta, la app lo dice |
| `PING` | `OK PONG` | ¿Sigue ahí? |
| `ESTADO` | `OK ESTADO clave=valor …` | Lo que el gadget quiera contar (`led=ON pantalla=…`) |
| `MOSTRAR <texto>` | `OK MOSTRAR` | Poner un texto en su pantalla, si la tiene |
| `LED ON` / `LED OFF` | `OK LED ON` / `OK LED OFF` | Encender o apagar su luz |
| otra cosa | `ERR DESCONOCIDO <orden>` | — |

## El gadget avisa → la app
| Línea | Qué hace la app |
|---|---|
| `EVENTO <nombre> [datos]` | **Solo lo registra** (`gadget.log` y el registro). No ejecuta nada |
| `PEDIR <encargo>` | Lo convierte en un **encargo** con `canal: "serie"` y contesta `OK ENCOLADO <id>`. Pasa por el **guardrail como cualquier encargo**: R0/R1 corre, R2 espera la aprobación en la app y R3 se deniega al instante (canal remoto) |

## Lo que la puerta NUNCA hace
- **Abrir un puerto por su cuenta**. Solo se abre el que el usuario elige en la app. La elección queda en
  `settings.json` (`gadget_puerto`), en el registro y en `gadget.log`. Abrir otro devuelve «no es el puerto
  elegido».
- **Ejecutar lo que llegue por serie** sin pasar por el guardrail. No existe ninguna orden que ejecute nada
  directamente.
- **Atarse a un gadget concreto**. La lista de puertos sale del registro de Windows
  (`HKLM\HARDWARE\DEVICEMAP\SERIALCOMM`), con su nombre real.
