# Estado: la X y minimizar esconden de verdad en la bandeja

Rama `Claude`, 27 oct 2026. Antes la X (con «minimizar») hacía `iconify()`: la
ventana se quedaba en la barra de tareas. Ahora, en el carril A, la ventana
desaparece y solo queda el icono de la bandeja.

## Qué se hizo (todo en `growi-bridge.py`)

### 1. Esconder de verdad
- **`hide_to_tray()`**:
  - en el carril A con icono de bandeja usa `_root.withdraw()`: sin ventana,
    sin botón en la barra de tareas y sin entrada en Alt+Tab;
  - `iconify()` queda solo para el carril B, que se deja como estaba, y para
    el caso sin pystray. Sin icono, esconder del todo dejaría la app sin
    forma de volver.
  - Lo decide `_a_la_bandeja()`.
- **Botón minimizar**: `_al_minimizar()` está enganchado a `<Unmap>` de la
  ventana principal. Cuando la ventana pasa a `iconic`, la esconde igual que
  la X (`withdraw`). Solo afecta a la ventana principal y solo en el carril A.
- **Lo que sigue corriendo**: el puente, el runner, la mascota y el proxy
  siguen igual; esconder no para nada.
- **Aviso de la bandeja**: «Sigo en la bandeja. Salir: clic derecho» sale una
  sola vez, con `close_toast_shown` en `settings.json`, como antes.

### 2. Por defecto, minimizar a la bandeja
- `close_mode()` dice lo que hace la X: `minimize`, `quit` o `ask`. Se lee en
  cada clic, así que el cambio en Ajustes vale al momento.
- **Instalación nueva del carril A**: al arrancar, si `settings.json` no tiene
  `on_close`, se guarda `"minimize"`. Una elección ya guardada (`quit`, `ask`
  o `minimize`) no se toca.
- **«Preguntarme»** ahora se guarda como `"on_close": "ask"`. Antes se guardaba
  *borrando* la clave, y entonces «preguntar» y «nunca elegí» se veían igual.
- Si «Preguntarme» lo elegiste tú, el diálogo de la X sale con «Recordar mi
  elección» **desmarcado**, para no pisar tu ajuste con la primera respuesta.
- **Ajustes**: las dos páginas (la clásica y la nueva) muestran el modo real
  (`close_mode()`) con las tres opciones: Preguntarme / Minimizar a la bandeja
  / Salir del todo.

### 3. Restaurar y salir desde la bandeja
- **`show_window()`**: `deiconify()` + `lift()` + `focus_force()`, más un
  instante `-topmost`. Sin eso, `lift()` no gana a la ventana que tiene el
  foco. Sirve tanto desde escondida como desde minimizada.
- **Doble clic en el icono**: ya llamaba a `show_window()`. Arreglé un
  fallo: el `WM_LBUTTONUP` que Windows manda *después* del doble clic se
  tomaba como un clic nuevo y, medio segundo después, cambiaba a la página de
  Tareas. Ahora se ignora.
- **Menú contextual**: «Abrir Growi Bridge» y «Salir» (`quit_app()`) ya
  existían; verificados abajo.

### 4. Sin zombies al salir
- **`quit_app()` es idempotente**. Antes corría dos veces: desde «Salir» y otra
  vez al terminar `mainloop()`.
- **Hilos colgados**: después de `quit_app()`, `_salida_sin_zombis()` espera
  hasta 8 s a que acaben los hilos que no son daemon. Si alguno queda colgado,
  lo nombra en el log y hace `os._exit(0)`. En todas las pruebas los hilos
  terminaron solos y no hizo falta.
- **Fin de sesión / apagado de Windows**:
  - **Qué había**: la app se lanza con `pythonw` y no tiene consola, así que
    el manejador de control de consola no aplica. La ventana oculta de pystray
    es de nivel superior y recibe los mensajes de difusión, pero pystray
    contesta **0** a todo mensaje que no conoce. A `WM_QUERYENDSESSION` eso
    le dice a Windows «no cierres la sesión»: la app frenaba el apagado y
    luego Windows la mataba sin limpiar nada (verificado abajo con la versión
    anterior).
  - **Qué hace ahora**: `_fin_de_sesion_registrar()` añade dos manejadores a
    esa ventana:
    - `WM_QUERYENDSESSION` → contesta 1 (sí);
    - `WM_ENDSESSION` (con wParam=1) → corre `quit_app()` en el hilo de la
      ventana y lo espera hasta 15 s antes de devolver el control a Windows.
  - Vale para los dos carriles: no cambia ni la ventana ni la bandeja.

### 5. Carril B
- **Ventana y bandeja**: la ventana y la bandeja del carril B quedan como
  estaban:
  - minimizar hace `iconify` y la ventana se queda en la barra de tareas;
  - sin `on_close` guardado, la X pregunta;
  - el icono sigue siendo `GrowiBridgeB`;
  - no se guarda ningún valor por defecto.
- **Spec de carril B sin ventana**: no está en este repo y no lo adelanté.
- **Fin de sesión**: el manejo de fin de sesión sí corre también en B.
- **Lo que no toqué**: `VERSION`, el secreto, el runner y el watchdog.

## Cómo se probó

`pruebas/prueba_bandeja.py` arranca una copia **aislada** del `growi-bridge.py`
de este repo en `%TEMP%\growi-prueba-bandeja`, con lo suyo propio:
- share, cola, token (`GROWI_BRIDGE_TOKEN_DIR`) y mutex;
- puerto **8795**.

No usé el 8787: ahí está corriendo el carril A instalado (pid 30592), que no
se podía parar ni tocar. La copia es carril A con `settings.json` **sin
`on_close`**, es decir, una instalación nueva, y con la mascota encendida.

Todo se manejó con **clics reales de ratón** (`SetCursorPos` + `mouse_event`):
- **X y minimizar**: en la posición que da DWM
  (`DWMWA_CAPTION_BUTTON_BOUNDS`). `WM_NCHITTEST` da el diseño clásico y en
  Windows 11 su «minimizar» cae en el borde del «maximizar» visible: el
  primer intento maximizó la ventana.
- **Icono de la bandeja**: Windows 11 lo pone en el desborde «^», donde
  `Shell_NotifyIconGetRect` no funciona (E_FAIL). El driver abre el desborde
  con UI Automation (`pruebas/bandeja_uia.ps1`) y, para cada icono «Growi»,
  hace clic derecho y comprueba que el menú `#32768` que se abre es **del pid
  de la prueba**; si no, Escape. Así nunca se pulsó nada en la app instalada
  ni en el carril B real.
- **Estado de las ventanas**: `IsWindowVisible`, `IsIconic`, la regla de
  Windows para la barra de tareas/Alt+Tab (visible, sin `WS_EX_TOOLWINDOW`,
  sin dueño o con `WS_EX_APPWINDOW`), `GetForegroundWindow` y el botón
  agrupado de la barra de tareas (UI Automation).
- **Capturas**: están en `%TEMP%\growi-prueba-bandeja\capturas\`. **No están
  en el repo** porque muestran el escritorio personal (chats, navegador).

### (a) La X → solo queda el icono
Tras un clic real en la X (`on_close` = `minimize` por defecto):
- **ventana principal**: `visible: false`, `en_barra_de_tareas: false`; la
  única ventana visible del proceso es la mascota (128×128, que no sale en la
  barra);
- **barra de tareas**: el botón agrupado pasó de «Growi Bridge - 2 ventanas de
  ejecución» a «Growi Bridge - 1 ventana de ejecución». La que queda es la del
  carril A instalado, que comparte el AppUserModelID;
- **puente**: `GET /gateway/salud` → `HTTP 200 {"ok": true, "pid": 29088,
  "puerto": 8795, "carril": "a"}`. `/health` da 404: esa ruta no existe en el
  puente; la de salud es `/gateway/salud`;
- **`tasklist /v /fi "PID eq 29088"`**: `pythonw.exe … Running … Título de
  ventana: Growi Bridge`. Ese título es el de la **mascota**, que sigue
  visible a propósito;
- **ajuste**: `close_toast_shown` pasó a `true` tras la primera X;
- **log**: `ventana escondida en la bandeja (el programa sigue corriendo)`;
- **capturas**: `a1-antes-de-la-x.png` (ventana a la vista) y
  `a2-despues-de-la-x.png` (ya no está; la mascota sí).

### (b) Doble clic en el icono y botón minimizar
- **Doble clic real en el icono, desde escondida**: `visible: true`, en la
  barra y `GetForegroundWindow() == ventana principal`, es decir, al frente.
  Se queda en la página donde estaba («Estado»; captura
  `b1-tras-doble-clic.png`): el clic de más ya no cambia de página.
- **Clic real en minimizar**:
  - la ventana queda `visible: false` (`IsIconic` true pero oculta) y fuera
    de la barra; el botón agrupado vuelve a «1 ventana»;
  - log: `ventana escondida en la bandeja`.
- **Doble clic otra vez**: vuelve visible, sin minimizar y al frente.

### (c) Las tres opciones de Ajustes (clic real en Ajustes → «Al cerrar la ventana»)
| Ajuste pulsado | `settings.json` | La X hace |
|---|---|---|
| (defecto, instalación nueva) | `"on_close": "minimize"` (lo escribió el arranque) | se esconde en la bandeja |
| Preguntarme | `"on_close": "ask"` | abre «¿Qué hago al cerrar la ventana?» con «Recordar» **desmarcado**. «Minimizar a la bandeja» → se esconde; «Cancelar» → la ventana se queda. El ajuste sigue en `ask` |
| Minimizar a la bandeja | `"on_close": "minimize"` | se esconde; el puente sigue en 200 |
| Salir del todo | `"on_close": "quit"` | la app se cierra entera. Log: `saliendo… atajos soltados… pantalla detenido… mascota oculta… runner parado… puente parado`. No queda ningún `pythonw` de la prueba y el icono desaparece del desborde (3 → 2 iconos «Growi») |

Cada cambio se aplicó sin reiniciar: la X siguiente ya hizo lo nuevo.

### (d) Salir desde la bandeja
Copia nueva (pid 23160): X → escondida → clic derecho en el icono. El menú
era del pid 23160:
`Abrir Growi Bridge | … | Paleta | Estado del proxy | Pausar mascota | Salir`.
- **«Abrir»** (probado antes con el pid 29088): visible y al frente.
- **«Salir»**:
  - log con la secuencia completa de `quit_app()`;
  - `tasklist /fi "PID eq 23160"` → «no hay tareas ejecutándose que
    coincidan»;
  - ningún python/pythonw con la copia de prueba en su línea de comandos;
  - el icono ya no está en el desborde (3 → 2).
- **Hilos colgados**: no saltó el aviso de `_salida_sin_zombis()`; los hilos
  terminaron solos.

### (e) Fin de sesión (simulado)
A cada ventana de nivel superior del proceso (pid 8564) se mandó lo que manda
Windows al cerrar sesión:
- `WM_QUERYENDSESSION` (lParam = `ENDSESSION_LOGOFF`) con `SendMessageTimeout`;
- después, `WM_ENDSESSION` (wParam = 1).

Resultados:
- **Versión nueva**:
  - todas contestan 1, incluida la ventana de pystray;
  - log: `windows: pide cerrar la sesión o apagar; contesto que sí` → `se
    cierra la sesión o se apaga: salgo del todo` → `saliendo…` → … →
    `puente: parado`;
  - el proceso terminó solo en **5,9 s**, no quedó ningún `pythonw` de la
    prueba y el puerto 8795 rechaza conexiones.
- **Versión anterior** (`git show HEAD:growi-bridge.py`, misma prueba,
  pid 18200):
  - la ventana de pystray contestó **0** a `WM_QUERYENDSESSION` («no
    apagues»);
  - tras `WM_ENDSESSION` el proceso **siguió vivo**; hubo que cerrarlo con
    «Salir».

**FALTA (explícita):** no se cerró una sesión real de Windows ni se apagó el
PC (habría cortado esta sesión de trabajo y la app instalada). La simulación
manda los mismos mensajes a las mismas ventanas, pero no reproduce dos cosas:
- el orden exacto entre procesos que usa Windows;
- el plazo con el que Windows mata al proceso tras `WM_ENDSESSION`.

Si pystray no está instalado no hay ventana oculta y no hay manejo de fin de
sesión. En ese caso la app ya avisa «pystray no instalado» en el log, y la X
no esconde del todo.

### Carril B (copia aislada en modo B, puerto 8796)
- **Icono**: clase de la ventana `GrowiBridgeB…SystemTrayIcon`; título «Growi
  Bridge — carril B».
- **Ajustes**: `settings.json` sigue **sin** `on_close` (no se escribe el
  defecto), y la X abre el diálogo de preguntar, como antes.
- **Minimizar**: `minimizada: true`, `visible: true`, **en la barra de
  tareas** (iconify), como antes; el log no dice «escondida».
- **Salir**: «Salir» del menú (verificado como menú de su pid) cierra sin
  dejar procesos.
- **Carriles reales**: los dos siguieron vivos y sin tocar durante todas las
  pruebas (8787 = pid 30592, 8789 = pid 28664).

## Cómo cambiar el comportamiento
- **En la app**: **Ajustes → General → «Al cerrar la ventana»**, con tres
  opciones:
  - **Preguntarme**: la X pregunta cada vez (con «Recordar» se guarda la
    respuesta);
  - **Minimizar a la bandeja** (por defecto): la X y el botón minimizar
    esconden la ventana; se vuelve con doble clic en el icono o con «Abrir»
    en su menú;
  - **Salir del todo**: la X cierra la app (puente, runner, bandeja, mascota).
- **Sin reiniciar**: el cambio vale al momento.
- **Salir siempre**: desde el menú del icono de la bandeja → **Salir**.
- **A mano**: en `settings.json`, `"on_close": "minimize" | "ask" | "quit"`.
- **Icono a la vista**: Windows 11 pone los iconos nuevos en el desborde
  «^». Para tenerlo siempre visible: Configuración → Personalización → Barra
  de tareas → Otros iconos de la bandeja del sistema → activar Growi Bridge
  (pythonw).

## Cómo repetir las pruebas
Desde la raíz del repo (Python con psutil y Pillow, que ya usa la app):
```powershell
python pruebas/prueba_bandeja.py lanzar 8795        # copia aislada, carril A, instalación nueva
python pruebas/prueba_bandeja.py estado             # ventanas, barra de tareas, puente, tasklist /v
python pruebas/prueba_bandeja.py captura a1
python pruebas/prueba_bandeja.py x                  # (a) clic real en la X
python pruebas/prueba_bandeja.py estado
python pruebas/prueba_bandeja.py dobleclic          # (b) doble clic real en el icono
python pruebas/prueba_bandeja.py min                # (b) clic real en minimizar
python pruebas/prueba_bandeja.py ajuste             # (c) on_close guardado (tras pulsar en Ajustes)
python pruebas/prueba_bandeja.py menu "Abrir"       # menú contextual
python pruebas/prueba_bandeja.py menu "Salir"       # (d) y luego: estado / tasklist
python pruebas/prueba_bandeja.py lanzar 8795
python pruebas/prueba_bandeja.py fin_sesion         # (e) WM_QUERYENDSESSION + WM_ENDSESSION
python pruebas/prueba_bandeja.py lanzar 8796 b      # carril B
```
- **Ajustes**: para (c) se pulsa con el ratón en Ajustes → «Al cerrar la
  ventana» (o `python pruebas/prueba_bandeja.py clic <x> <y>`) y luego `x`.
- **Versión anterior**: `$env:PRUEBA_GB_ORIGEN = "<ruta a otro
  growi-bridge.py>"` antes de `lanzar` prueba esa versión.

## Notas
- **Quien ya eligió «Preguntarme» antes de este cambio**: esa elección se
  guardaba *borrando* `on_close`, y no se distingue de «nunca elegí». En el
  carril A pasa a minimizar por defecto; se vuelve a elegir «Preguntarme» en
  Ajustes y queda guardado. Quien eligió «Salir del todo» o «Minimizar» no
  cambia.
- **El aviso de la bandeja**: se pidió (`close_toast_shown` quedó en `true`),
  pero no lo vi en pantalla. Windows tenía «No molestar» activado, que oculta
  los avisos.
