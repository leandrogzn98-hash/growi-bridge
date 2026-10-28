# ESTADO — Puerta USB/serie para un gadget (t-gadget-esp32)

Rama `Claude`, 28-oct-2026. **Solo la puerta en software, sin hardware.**

- Prueba: `pruebas/prueba_gadget.py`. Arranca la app real desde una copia, en el puerto de prueba 8797.
- El gadget es el emulador `pruebas/emulador_gadget.py`, en `tcp://127.0.0.1:8830`.
- Evidencia: `pruebas/evidencia/gadget/` (`evidencia.json` + 2 capturas).

## LISTO
1. **La puerta USB/serie, abierta en software** (`gadget_puertos`, `gadget_abrir`, `gadget_ui`; Ctrl+K → «Gadget»).
   - Lista los puertos serie **reales** con su nombre del sistema, sacados de
     `HKLM\HARDWARE\DEVICEMAP\SERIALCOMM`. Si no hay ninguno: «Ningún dispositivo».
   - El puerto se elige y se abre en la ventana, con **baudios** (9600, 57600, 115200 o 230400) y **timeout**
     visibles.
   - Usa Win32 con ctypes (`CreateFile`, `SetCommState`, `ReadFile`, `WriteFile`), sin pyserial: instalar
     paquetes externos no está permitido.
   - La ventana es de CustomTkinter, con la clásica de respaldo.
2. **Protocolo mínimo documentado**: `PROTOCOLO-GADGET.md`, marcado como **PROPUESTA**.
   - Texto UTF-8 por líneas, con las órdenes HOLA, PING, ESTADO, MOSTRAR y LED, y respuestas OK/ERR.
   - El gadget avisa con EVENTO (solo se registra) o PEDIR (un encargo).
   - Lo prueba el emulador `pruebas/emulador_gadget.py`.
3. **Nada de hardware**: no se compró, no se pidió y no se diseñó nada. Sin gadget, la app funciona igual: la
   puerta no arranca sola.
4. **Seguridad de la puerta**:
   - Solo se abre el puerto **elegido en la app**. Queda en `settings.json` (`gadget_puerto`), en el registro y en
     `gadget.log` (ignorado por git).
   - Abrir otro devuelve «no es el puerto elegido en la app: no se abre».
   - Un `PEDIR` por serie es un encargo con `canal: "serie"`, que pasa por el guardrail: R2 espera aprobación y R3
     se deniega.
   - EVENTO solo se registra. No existe ninguna orden que ejecute nada directamente.

## Evidencia
| Criterio | Resultado real |
|---|---|
| (a) puertos reales | `COM3 — \Device\BthModem2`, `COM4 — …BthModem1`, `COM6 — …BthModem3`, `COM7 — …BthModem0`: los módems Bluetooth de este PC, iguales a `reg query HKLM\HARDWARE\DEVICEMAP\SERIALCOMM`. Captura 1 |
| (b) protocolo + emulador | `HOLA 1` → `OK HOLA emulador-gadget 1`; `PING` → `OK PONG`; `LED ON` → `OK LED ON`; `MOSTRAR Hola Leandro` → `OK MOSTRAR`; `ESTADO` → `OK ESTADO led=ON pantalla=Hola Leandro`; `BAILA` → `ERR DESCONOCIDO BAILA` |
| (c) abrir el elegido y registro | `settings.gadget_puerto = tcp://127.0.0.1:8830`; `gadget.log` con «puerto elegido por el usuario», «abierto a 115200 baudios, timeout 2 s» y cada línea `>>` / `<<`. Captura 2 |
| seguridad | `gadget_abrir("COM3")` sin elegirlo → `(False, "COM3 no es el puerto elegido en la app: no se abre")` |
| guardrail por serie | `PEDIR Borra el archivo …viejo.txt.` → `esperando_aprobacion`, aprobación `pendiente`. `PEDIR … rm -rf …` → `necesita_decision`, «R3 pedida por canal remoto (serie): denegada al instante» |
| (d) sin hardware | constancia: este spec no compró, no pidió ni diseñó hardware. No se le pidió nada a Leandro sobre hardware |
| Tracebacks | 0 |

## FALTA
- **Abrir un COM físico de verdad**: la ruta Win32 compila y se llama, pero **no se abrió** ninguno de los COM
  reales.
  - Los cuatro son módems Bluetooth, y abrirlos intentaría conectar con el teléfono emparejado.
  - No hay un gadget USB conectado.
  - Se probará el día que haya una placa: elegir su COMx en la ventana.
- **El protocolo es PROPUESTA**: no está validado contra un ESP32 real.
- **El emulador va por TCP en loopback**, no por un COM virtual: no hay un par com0com instalado y no se instala
  nada.
- **Incidente durante la prueba**: en dos intentos tempranos, la prueba simuló teclas y un clic, y el foco no
  estaba en la ventana de prueba. Una de esas veces la ventana de la **app instalada** pasó al frente. No hay
  evidencia de que algo cambiara en ella: estaba en la pantalla Estado, sin campos de texto. Aun así, conviene
  mirarla. La prueba final ya no simula teclado.

## CÓMO PROBARLO
1. `python pruebas/prueba_gadget.py`: arranca el emulador y la app de prueba, y deja la evidencia en
   `pruebas/evidencia/gadget/`.
2. A mano:
   1. `python pruebas/emulador_gadget.py 8830`.
   2. En la app: Ctrl+K → «Gadget». Escribe `tcp://127.0.0.1:8830` y pulsa «Elegir y abrir».
   3. Manda `PING` y `ESTADO`.
