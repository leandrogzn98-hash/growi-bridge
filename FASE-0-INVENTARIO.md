# Fase 0 — Inventario de costuras y paridad Linux

Fecha: 2026-11-16. Rama: `fase-0-paridad-linux`.
Método: búsqueda y lectura directa del código (`growi-bridge.py`, 32.459 líneas, más módulos), verificación de compilación en Linux (Python 3.12.3) y segunda pasada de revisión con Claude Opus 5.5, cuyas sospechas se verificaron una a una con búsqueda antes de entrar en este documento.

Objetivo: mapa de todo punto que hoy asume **un solo asistente / un solo secreto / una sola cola**, y de todo punto **solo-Windows** que hay que adaptar para que Linux tenga la misma UI y funciones. Este mapa manda sobre la Fase 1 del `PLAN-MULTI-MUSE.md`.

---

## A. Costuras de «uno solo»

| # | Costura | Dónde | Qué hay hoy | Fase que la toca |
|---|---|---|---|---|
| A1 | Secreto único del puente | `growi-bridge.py` ~L237, `APP_DIR/secret.txt` | Un solo `secret.txt` para todo el puente. Ya existe migración de su valor a un token (~L14079) y `browser/browser-server.py` **todavía lee `secret.txt`** | 1 |
| A2 | Token de plano de control por carril | ~L14068–L14107 | Token por carril cifrado con **DPAPI** en `%LOCALAPPDATA%\GrowiBridge\plano-control-<carril>.dpapi`. Es el precedente más cercano a «un secreto por carril/cuenta», pero el cifrado es solo-Windows | 0 (adaptador) y 1 |
| A3 | Asistente activo único | getter ~L29757, setter ~L29990 | `settings.json -> asistente_activo`; perfiles en `asistentes/*.md`. Solo 3 puntos de contacto directos: costura chica y limpia | 1 |
| A4 | Configuración global única | `SETTINGS_FILE` L133 | Un solo `settings.json` por instalación. Puerto: env `GROWI_BRIDGE_PORT` > settings > 8787 (L145). Carril: env `GROWI_BRIDGE_LANE` > settings > `"a"` (L159) | 1 |
| A5 | Una cola por instancia, sin cuenta | `COLA_DB` L12444; tabla `tareas` L12502 | Ruta: env `GROWI_BRIDGE_COLA` > según `SHARE` > `APP_DIR/cola.db`. SQLite WAL + `synchronous=FULL`, lock de hilos. **Cada carril tiene su propia `cola.db`: no hay cola compartida entre carriles.** La tabla `tareas` tiene columna `motor` y `tarea_padre` (útil para la consulta de la Fase 2) pero **ninguna columna de cuenta**. Sin `PRAGMA user_version`: **no hay versionado de esquema** | 1 y 2 |
| A6 | Instancia única por carpeta | ~L13899–L13991 | Mutex con nombre (`CreateMutexW`, solo-Windows) + `gateway.lock` con pid de respaldo. El candado es por `APP_DIR`, no por cuenta | 0 (equivalente Linux: `flock`) y 1 |
| A7 | Sesiones de motor sin separar por cuenta | `engines.json`, ~L4531 y ~L6933 | Los motores declaran reanudar con `--resume {session_id}`; **no existe `CLAUDE_CONFIG_DIR` ni separación de sesiones por cuenta en todo el código**. Dos cuentas con el mismo motor compartirían sesión | 1 |
| A8 | Cuota por motor, no por cuenta | `quota-tracker.py`, `config-quota.json` | Contadores por motor (`motores`), resueltos por prefijo de nombre. Dos cuentas sobre el motor `claude` compartirían contador | 2 |
| A9 | Credenciales atadas a Windows | ~L2851–L2981 | `keyring` comprobando el backend `WinVaultKeyring`, proceso «ayudante» de credenciales **solo-Windows** (L2978: «solo en Windows»), respaldo DPAPI. En Linux no hay camino de credenciales hoy | 0 y 1 |
| A10 | Concurrencia de un solo proceso | todo el monolito | **75 `threading.Thread`** y cachés globales de módulo alimentadas desde el asistente activo: cualquier global sin clave de cuenta es una fuga potencial entre cuentas al pasar a multi-cuenta | 1 (auditoría de globales) |
| A11 | Escritura de JSON no siempre atómica | todo el monolito | 81 `json.dump` frente a 34 `os.replace`: parte de los estados se escriben con reemplazo atómico y parte no. Con dos escritores (app + browser-server) hay riesgo de corrupción que multi-cuenta agrava | 1 |

## B. Costuras de plataforma (Windows → Linux)

| # | Punto | Dónde | Equivalente Linux a construir |
|---|---|---|---|
| B1 | `ctypes.windll`: admin (L258), `SendMessageTimeoutW` (L304), `GlobalMemoryStatusEx` (L2611) | disperso | Guardas por plataforma; memoria vía `psutil`/`/proc` (la pestaña Recursos ya usa `psutil` con respaldo) |
| B2 | `winreg`: proxy en el entorno (L312), leer entorno (L1109), nombre de CPU (L2618) | disperso | Proxy: variables de entorno del proceso/servicio; CPU: `/proc/cpuinfo` o `psutil` |
| B3 | Arranque con `schtasks` (tarea `GrowiBridgeApp`) | L355–L373 | Servicio de usuario `systemd --user` + autostart XDG |
| B4 | Matar árboles de procesos con `taskkill /T /F` | L5974, L6311, L6889 | Grupos de proceso: `start_new_session` + `killpg` (o alcances de systemd) |
| B5 | Procesos sin ventana: `CREATE_NO_WINDOW` + `STARTUPINFO` | L2057–L2080 | Ya degradado con `getattr` y `os.name == "nt"`: en Linux basta no heredar terminal (mismo helper, rama POSIX) |
| B6 | Token DPAPI del plano de control | L14068 | Secret Service vía `keyring`; si no hay servicio, archivo 0600 cifrado con clave del llavero (decisión Fase 1) |
| B7 | Rutas `%LOCALAPPDATA%`, `%USERPROFILE%\growi-bridge\share` | L104, L107, L2094, L14068 | `APP_DIR` ya es la carpeta del script (portable); `SHARE` por env ya existe; falta el default Linux (`~/.local/share/growi-bridge` o junto a la app, a decidir en Fase 0) |
| B8 | Teclas virtuales (VK) de Windows | L27089 (`sys.platform != "win32"` ya guarda) | Atajos en Linux vía la capa de paleta/comandos; alcance limitado, revisar en la paridad de UI |
| B9 | `MessageBoxW` para un aviso | L14040 | Diálogo Tk equivalente (la UI ya es Tk) |
| B10 | Bandeja del sistema (`pystray`, import tardío L14733) | UI | En Linux depende de AppIndicator; verificar en escritorio real (checklist C) |
| B11 | 35 referencias a `.exe` | disperso | Resolución de binarios por plataforma (`shutil.which` y nombre sin extensión) |
| B12 | Sin constante central de plataforma | — | Crear `ES_WINDOWS`/`ES_LINUX` únicos y enrutar las guardas dispersas; sin esto, cada adaptación será un parche suelto |

**Lo que juega a favor (verificado):** la codificación se cuida (166 menciones de `encoding=` frente a 85 `open(`), los import de GUI pesada (`pystray`, `customtkinter`) son tardíos y dentro de funciones, y el helper de procesos ocultos ya degrada fuera de Windows.

## C. Verificación hecha en Linux (esta máquina, 2026-11-16)

- ✅ Los **17 archivos `.py` compilan** sin error con Python 3.12.3 en Linux.
- ✅ `tkinter` 8.6 presente y funcional a nivel de import en Linux.
- ⚠️ `keyring` no está instalado en esta máquina de trabajo: es dependencia a declarar en el instalador Linux (en Windows hoy lo trae el entorno de la app).
- ⏳ **Pendiente de escritorio real** (no verificable en esta máquina sin pantalla): ventana principal y pestañas, bandeja/AppIndicator, mascota, paleta de comandos, temas CustomTkinter en X11 y Wayland, y el arranque con sesión gráfica. Esta checklist se verifica en la PC Linux del dueño y es **puerta de salida de la Fase 0** junto con «el modo servidor responde idéntico».

## D. Conclusiones para la Fase 1

1. El orden de ataque que deja este mapa: **A9/B6 (credenciales en Linux) → A1/A2 (secreto por cuenta sobre el precedente del token por carril) → A3 (asistente por carril) → A5 (columna de cuenta + versionado de esquema en la cola)**.
2. A7 (sesiones por cuenta) entra en la Fase 1 aunque no se use Claude Code como objetivo: la separación de sesiones es lo que evita que dos cuentas se pisen el contexto.
3. Antes de tocar multi-cuenta hay que crear la constante central de plataforma (B12) y el equivalente Linux del mutex (A6) y de `taskkill /T` (B4): son la base de todo lo demás.
4. Ninguna costura obliga a reescribir: todas son puntos concretos y contados. La más ancha es A10 (globales del proceso único), que se ataca con auditoría dirigida, no con reescritura.
