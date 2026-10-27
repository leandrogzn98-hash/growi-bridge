# Estado: instancia única que trae al frente la ventana existente

Rama `Claude`, 27 oct 2026. Antes, una segunda copia de Growi Bridge detectaba
la primera (mutex + `gateway.lock`) y mostraba un aviso de 15 s («busca el
icono en la bandeja»). Ahora pide a la primera que se traiga al frente y sale
sin ventana. Se completó el mecanismo que ya existía, sin rehacerlo:
`instancia_unica()`, `_pid_vivo()`, `_lock_*()` y el manejo del error 5 están
**sin cambios**.

## Qué se hizo (todo en `growi-bridge.py`)

### 1. Mecanismo: evento con nombre de Windows
Es la opción preferida del encargo. `FindWindowW` quedó descartado por dos
motivos:
- con la ventana escondida (`withdraw`), `ShowWindow` se salta el estado de
  Tk;
- una copia sin elevar no puede manejar con fiabilidad ventanas de un proceso
  elevado (UIPI).

Las piezas:
- **`_nombre_mostrar()`**: deriva el nombre del evento del nombre del mutex.
  Así lleva el mismo sufijo de carril:

  | Carril | Mutex | Evento |
  |---|---|---|
  | A | `Local\GrowiBridgeInstanciaUnica` | `Local\GrowiBridgeMostrar` |
  | B | `Local\GrowiBridgeInstanciaUnica-carrilB` | `Local\GrowiBridgeMostrar-carrilB` |
  | copia de prueba con `GROWI_BRIDGE_MUTEX` | su nombre | el derivado de ese nombre |

- **`_mostrar_crear()`**: lo llama `main()` justo cuando `instancia_unica()`
  dice que somos la única. Crea un evento auto-reset con DACL explícita:
  - SYSTEM, Administradores y el dueño tienen acceso total;
  - los usuarios autenticados solo tienen `EVENT_MODIFY_STATE | SYNCHRONIZE`;
  - etiqueta de integridad media.

  Así una copia **sin elevar** puede marcarlo aunque la app corra elevada
  (verificado abajo con una copia de integridad media). Si el descriptor de
  seguridad falla, el evento se crea con la DACL por defecto.
- **`_mostrar_poll()`**: el bucle de Tk mira el evento cada 300 ms
  (`WaitForSingleObject(h, 0)`, sin hilos ni bloqueo). Si está marcado llama a
  **`show_window()`**, el mismo camino que el doble clic en la bandeja
  (`deiconify` + `lift` + un instante `-topmost` + `focus_force`). Sirve igual
  con la ventana escondida (`withdraw`, carril A) que minimizada (`iconify`,
  carril B). `show_window()` no se tocó.
- **`_mostrar_comprobar()`**: a los 500 ms mira si la ventana quedó en primer
  plano y lo deja en el registro. Si quedó visible y encima pero sin el foco
  del teclado (la copia que lo pidió no tenía derecho a ceder el primer plano,
  por ejemplo porque la lanzó un proceso de fondo), lo toma con
  `AttachThreadInput` + `SetForegroundWindow`. Solo pasa en este camino:
  alguien acaba de pedir la ventana.
- **`_mostrar_senalar()`**: en la segunda copia, `OpenEventW(EVENT_MODIFY_STATE)`,
  luego `AllowSetForegroundWindow(ASFW_ANY)` (cede su derecho de primer plano
  a la primera) y `SetEvent`.

### 2. La segunda copia
`main()` sigue igual:
```
ok, motivo = instancia_unica()
if not ok:
    _aviso_ya_corre(motivo)
    return 0
```
`_aviso_ya_corre()` ahora marca el evento y sale. No abre ventana Tk, ni
puerto, ni cola, ni runner, ni watchdog; todo eso va después en `main()`. En
las pruebas salió en 0,9-2 s con código 0.

### 3. El aviso de 15 segundos
Decisión: **si traer al frente funciona, no hay aviso**. La primera ventana
aparece, y eso ya dice que la app estaba abierta. Si no se pudo marcar el
evento, queda un aviso **de 3 s** (antes 15 s) con el mismo texto. Pasa, por
ejemplo, si la primera instancia todavía está arrancando o es una versión
anterior sin evento. Motivo: así nunca queda una ventana modal de 15 s
mientras la primera ya está al frente, y en el caso raro de fallo la persona
no se queda sin saber qué pasó.

### 4. Carriles
Mutex y evento llevan el sufijo `-carrilB`. Abrir el B cuando corre el A
arranca el B normal y no toca el A. La segunda copia del B trae al frente el
B, no el A.

### 5. Caídas y watchdog
No cambió nada:
- el mutex lo suelta Windows al morir el proceso (y el evento también);
- `_pid_vivo()` descarta el pid muerto del `gateway.lock`;
- el error 5 sigue siendo «ya hay otra» (`instancia_unica()` sin tocar).

## Cómo se probó
Con `pruebas/prueba_mutex.py` (nuevo). Lanza copias **aisladas** del
`growi-bridge.py` de este repo en `%TEMP%\growi-prueba-mutex\<carril>`. Cada
copia tiene share, cola, token, puerto (8797 el A, 8799 el B) y mutex propios
(`Local\GrowiBridgeInstanciaUnicaPrueba` y `…Prueba-carrilB`; eventos
derivados `Local\GrowiBridgeMostrarPrueba` y `…-carrilB`). No se tocó la app
instalada ni `C:\Users\forte\growi-bridge\`.

Las dos formas de lanzar la segunda copia:
- **«fondo»**: desde el proceso de la prueba;
- **«usuario»**: con Win+R, escribiendo la orden con `SendInput`, como una
  persona.

Para esconder la ventana se manda `WM_CLOSE`, que es el mismo camino que la X:
en una instalación nueva del carril A la X va a la bandeja. En el B se usa
`SC_MINIMIZE`.

La evidencia JSON está en `pruebas/evidencia/mutex/` (numerada en el orden de
ejecución). En esos JSON, los títulos de ventanas ajenas a Growi se cambiaron
por «(otra app)». Las capturas de pantalla no se suben porque muestran el
escritorio personal; quedan en `%TEMP%\growi-prueba-mutex\capturas\`.

Las pruebas corrieron con el código final. Después solo cambió el texto de un
docstring.

### Resultado por criterio

| # | Prueba | Evidencia | Resultado |
|---|---|---|---|
| a | A con ventana visible + segunda copia (fondo y usuario) | `01`, `02` | código 0 en 0,98 s / 4,6 s (Win+R incluido); primera visible, arriba en orden Z y **en primer plano**; 1 pythonw (27200), 1 icono, 1 proceso escuchando en 8797; registro: «otra copia pidió la ventana… en primer plano» |
| b | A escondida en la bandeja (`withdraw`: no visible, sin botón en la barra) + segunda copia | `03`→`04` (usuario), `05`→`06` (fondo) | ventana restaurada (visible, no minimizada), arriba y en primer plano; código 0; 1 pythonw, 1 icono, 1 puerto. Captura `04-a-bandeja-usuario.png`: la ventana de prueba aparece delante |
| c | Carril B con el A escondido | `08` (arranca B), `09` (segunda B visible), `10`→`11` (B minimizado + segunda) | B arranca normal (pid 17216, 8799) sin tocar el A (el A sigue escondido en `08`, `09` y `11`); la segunda copia del B usa `…-carrilB`, trae al frente el **B** (de minimizado a normal), código 0; el A no se movió |
| 3 | Un proceso, un puente, un icono por carril | todas las filas `despues` | siempre 1 pythonw por copia, 1 pid escuchando en su puerto y 1 icono de bandeja por pid |
| d | `taskkill /F` y arranque nuevo | `13`→`14` (A), `18`→`19` (B) | el `gateway.lock` con el pid muerto (27200 / 17216) no bloquea: arranca otro pid (27252 / 27492), toma el lock, el puente responde |
| d | Relanzado del watchdog | `15`→`16`→`17` | se corrió **el `watchdog-gateway.ps1` real** con las rutas y el puerto de la copia de prueba (y su espera de 60 s acortada a 5 s): puerto caído → lock con pid muerto → sin proceso → `iniciar-growi-bridge.bat` → `watchdog.log`: «carril A (8797) reinicio». Arrancó el pid 26312 y una segunda copia posterior lo trajo al frente (`17`). La tarea programada `GrowiBridgeWatchdog` en sí no se disparó (no se tocó la instalación) |
| e | Error 5 en el código | `instancia_unica()` sin cambios | `if not h and err == 5: return False, "... (lo creó una copia con más privilegios)"` sigue igual |
| e | Error 5 de verdad (forzado) | `24` | el proceso de prueba crea un mutex que solo SYSTEM puede abrir (`D:(A;;GA;;;SY)`; abrirlo da 5 incluso elevado) y el evento derivado. La copia sale con código 0 en 0,93 s; registro: «el mutex … ya existe (lo creó una copia con más privilegios); se pidió a la instancia que ya corre que se traiga al frente»; el evento quedó marcado; no apareció ningún pythonw ni proceso escuchando nuevo |
| e | Copia **sin elevar** contra la primera elevada | `21`, `22`→`23` | segunda copia lanzada por una tarea `/RL LIMITED` (`whoami`: integridad media, S-1-16-8192) contra la primera lanzada en elevado (`22`: tarea `/RL HIGHEST`, como `GrowiBridgeApp`). La copia media **abrió y marcó el evento** (la DACL explícita funciona) y la primera volvió de la bandeja al frente; código 0 |
| 4 | Respaldo sin evento | `25` | mutex de una «primera» sin evento (como la versión anterior): la copia muestra el aviso (#32770 «Growi Bridge»), sale con código 0 a los **3,99 s** (aviso de 3 s), y el registro dice «no se pudo avisar a la instancia que ya corre» |

## Lo que no se pudo verificar o quedó distinto de lo esperado
- **El error 5 natural no se reprodujo en este PC.** Con la primera instancia
  elevada, tanto por shell elevado como por tarea `/RL HIGHEST`, la copia de
  integridad media **abrió** el mutex: `CreateMutexW` dio 183, no 5 (`21`,
  `23`). Igual se trata como «ya hay otra», así que el resultado es el mismo.
  La rama del 5 se verificó forzándola (`24`). El docstring de
  `instancia_unica()` dice que en la instalación real sí sale 5; no lo
  contradigo, pero aquí no lo vi.
- Con `runas /trustlevel:0x20000` (`12`) la copia no quedó con menos
  privilegios efectivos (183). Por eso se repitió con una tarea `/RL LIMITED`
  (`21`, `23`).
- **Foco del teclado en la primera pasada**: antes de la batería final el PC
  estaba en uso. Los clics de la persona devolvían el foco a Chrome y una vez
  minimizaron la ventana de prueba, así que esa corrida se descartó. La
  batería final (`00`–`25`) se hizo con el PC sin tocar.
- **Las pruebas usan nombres de mutex de prueba**, no los reales: así no se
  choca con la app instalada que estaba corriendo. Los nombres reales salen
  de la misma derivación (`replace("GrowiBridgeInstanciaUnica",
  "GrowiBridgeMostrar")`), pero con los nombres reales no se probó.

## Fuera de alcance, para revisar aparte
- `watchdog-gateway.ps1` vigila el **carril B en el puerto 8788**, pero el
  carril B instalado escucha en **8789**. En 8788 escucha
  `share\inbox\growi-bridge-browser\browser-server.py`. Mientras ese servidor
  esté vivo, el watchdog cree que el B está bien aunque haya caído. No se tocó.
- Si el watchdog llegara a lanzar una copia con la instancia viva, ahora esa
  copia traería la ventana al frente en vez de un aviso de 15 s. No debería
  pasar: el watchdog mira antes el pid del `gateway.lock` y no relanza si está
  vivo.
- Durante la sesión el pid del carril A instalado cambió (8316 → 4668). Las
  pruebas solo matan pids de las copias de `%TEMP%\growi-prueba-mutex`
  (`taskkill /PID` del pid de la prueba y `salir`, que filtra por la ruta de la
  copia). El reinicio vino de otro lado (probablemente de la integración en
  curso de los fixes anteriores).

## Archivos
- `growi-bridge.py`: `_nombre_mostrar`, `_mostrar_crear`, `_mostrar_poll`,
  `_mostrar_comprobar`, `_mostrar_senalar`; `_aviso_ya_corre` (señal + aviso de
  3 s solo como respaldo); `main()`: `_mostrar_crear()` tras
  `instancia_unica()` y `root.after(300, _mostrar_poll)`.
- `pruebas/prueba_mutex.py`: el arnés (reutiliza las utilidades de
  `prueba_bandeja.py`).
- `pruebas/evidencia/mutex/*.json`: la evidencia.
