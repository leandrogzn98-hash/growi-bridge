# ESTADO — Supervisor local en Linux (0.4.7, t-supervisor-linux-047)

Rama `Claude`, 29-oct-2026. Objetivo: probar en un Linux de verdad el camino que la 0.4.6 dejó escrito pero nunca
ejecutado (`supervisor/instalar-supervisor.sh`, systemd de usuario o cron, llavero Secret Service).

**Resultado: no hay ningún entorno Linux en este PC. Nada del camino Linux queda verificado.** Este informe cae en
el caso (e) del spec: FALTA, con los pasos manuales para Leandro.

No se tocó `VERSION`, ni `growi-bridge.py`, ni la instalación ni la tarea programada de Windows, ni ningún archivo
de `supervisor/`.

## Qué se buscó (punto 1, ruta de verificación)

| Candidato | Resultado en este PC |
|---|---|
| WSL2 (`wsl --list --verbose`) | **No instalado**: «El Subsistema de Windows para Linux no está instalado. Para instalar, ejecute "wsl.exe --install"» |
| Docker / Podman / Rancher | No hay ejecutables ni carpetas en `C:\Program Files` |
| VirtualBox | Solo queda `C:\Program Files\Oracle\VirtualBox\ExtensionPacks`; no hay `VBoxManage.exe` ni máquinas virtuales |
| Multipass / Vagrant / QEMU / LXC | No están |
| Una máquina Linux por SSH | `~/.ssh/config` solo tiene `ssh.railway.com`, que es un servicio en la nube, no este PC; usarlo sería desplegar fuera (y quizá gastar), así que no se usó |

La virtualización por firmware está activa (`VirtualizationFirmwareEnabled = True`), así que WSL2 se puede instalar.
No lo hice: hace falta ser administrador, descargar la distro y reiniciar, y el spec dice que lo que exija eso se
deja como FALTA.

## LISTO

- El inventario de arriba, comprobado hoy en este PC.
- `sh -n supervisor/instalar-supervisor.sh` sigue sin errores de sintaxis (en el `sh` de Git Bash; esto **no** es
  Linux y no verifica nada del funcionamiento).
- La lectura del instalador, que trajo un riesgo para Windows que no estaba anotado (ver el aviso de abajo).

## FALTA (todo lo verificable en Linux)

| # | Criterio del spec | Estado |
|---|---|---|
| 2 | Python 3.10+, `.venv` propio y `keyring`, `pyyaml`, `requests` en Linux | FALTA: no hay Linux |
| 3 | `instalar-supervisor.sh` deja un temporizador de systemd de usuario (o una línea de cron) visible en `systemctl --user list-timers` / `crontab -l` | FALTA: no hay Linux |
| 4a | `--verificar` OK en lo aplicable con el proveedor `mock` | FALTA: no hay Linux |
| 4b | `--dry-run` imprime `TODO_BIEN` sin enviar nada | FALTA: no hay Linux |
| 4c | `--evals` pasa con el `mock` | FALTA: no hay Linux |
| 5 | Al menos una ejecución programada real con su línea en `supervisor.log` | FALTA: no hay Linux |
| — | El llavero Secret Service (`keyring`) en Linux | FALTA: no hay Linux, y además el `mock` no usa clave |
| — | `REQUISITOS.md` sigue diciendo «Probado en su sistema real: no todavía (previsto en la 0.4.7)» para Linux. Es correcto y no lo cambié | Se actualiza cuando pase la prueba |

### Aviso: no lances el instalador de Linux sobre la carpeta de Windows

En este PC ya existe `supervisor\.venv` (el entorno de Python de Windows, con `Scripts\python.exe`). El
instalador `.sh` busca `.venv/bin/python`; al no encontrarlo, hace `python3 -m venv` **sobre esa misma carpeta**.
Eso reescribe su `pyvenv.cfg` con la ruta del Python de Linux, y la tarea programada de Windows deja de arrancar.
Por eso, en WSL, el supervisor se copia al disco de Linux (`~/`) y se prueba ahí; no desde `/mnt/c/...`. Copiarlo
evita también la lentitud de `/mnt/c` y los permisos raros de los archivos de Windows.

## CÓMO PROBARLO (pasos manuales para Leandro)

Unos 20 minutos más la descarga. No gasta nada: proveedor `mock`, sin claves y sin correo.

### 1. Instalar Linux (WSL2 con Ubuntu 24.04), una vez

En PowerShell **como administrador**:

```powershell
wsl --install -d Ubuntu-24.04
```

Reinicia el PC cuando lo pida. Al volver se abre Ubuntu y te pide un usuario y una contraseña de Linux. Comprueba:

```powershell
wsl --list --verbose     # Ubuntu-24.04 ... VERSION 2
```

### 2. Activar systemd dentro de Ubuntu

Ubuntu 24.04 en WSL suele traerlo activo. Dentro de Ubuntu:

```sh
systemctl --user show-environment >/dev/null && echo "systemd de usuario: sí"
```

Si dice que no, añade esto a `/etc/wsl.conf` (`sudo nano /etc/wsl.conf`):

```ini
[boot]
systemd=true
```

Luego, en PowerShell, `wsl --shutdown`, y abre Ubuntu de nuevo.

### 3. Python y el venv (punto 2 del spec)

```sh
sudo apt update && sudo apt install -y python3 python3-venv python3-pip
python3 --version        # tiene que ser 3.10 o más; Ubuntu 24.04 trae 3.12
```

### 4. Copiar el supervisor y su instalación de prueba al disco de Linux

`_prueba/` no está en git (es local de este PC), por eso se copia y no se clona:

```sh
rm -rf ~/growi-supervisor
cp -r /mnt/c/Users/forte/source/growi-bridge/supervisor ~/growi-supervisor
rm -rf ~/growi-supervisor/.venv ~/growi-supervisor/__pycache__ ~/growi-supervisor/proveedores/__pycache__
cd ~/growi-supervisor
# Rutas de Linux en la configuración de prueba (las de C:\ no sirven aquí)
sed -i \
  -e "s|carpeta: .*|carpeta: $HOME/growi-supervisor/_prueba/bridge|" \
  -e "s|share: .*|share: $HOME/growi-supervisor/_prueba/bridge/share|" \
  -e "s|^datos: .*|datos: $HOME/growi-supervisor/_prueba/datos|" \
  _prueba/config.yaml
rm -f _prueba/datos/supervisor.log _prueba/datos/supervisor-memoria.json   # log limpio: lo que aparezca es de Linux
grep -nE "proveedor|carpeta|share|datos|intervalo" _prueba/config.yaml     # proveedor: mock y rutas /home/...
```

### 5. Instalar la ejecución programada (punto 3)

```sh
sh instalar-supervisor.sh --config _prueba/config.yaml
systemctl --user list-timers | grep GrowiSupervisor-prueba     # con systemd
crontab -l | grep GrowiSupervisor-prueba                        # si cayó en cron
```

Tiene que decir «Temporizador GrowiSupervisor-prueba.timer activo cada 60 min (systemd de usuario)» o «cron:
GrowiSupervisor-prueba cada 60 min». El intervalo sale de `intervalo_minutos` del YAML.

### 6. Verificación funcional con `mock` (punto 4)

```sh
PY=~/growi-supervisor/.venv/bin/python
# Clave falsa solo para esta orden: con --sin-llamadas nadie la usa, no sale nada hacia Resend
RESEND_API_KEY=re_falsa_prueba $PY supervisor.py --config _prueba/config.yaml --verificar --sin-llamadas
$PY supervisor.py --config _prueba/config.yaml --dry-run                    # tiene que salir TODO_BIEN y no enviar nada
$PY supervisor.py --config _prueba/config.yaml --evals                      # todas las evals en verde
```

Lo que tiene que salir en `--verificar`: OK en «configuración», «clave del proveedor» («no hace falta», es el
`mock`) y «tarea programada» (esta es la línea que prueba systemd o cron en Linux); OMITIDO en «proveedor alcanzable»
y «Resend». Sin la variable `RESEND_API_KEY`, «Resend» sale FAIL y la orden termina con código 1: eso no es un fallo
de Linux.

### 7. Una ejecución programada de verdad (punto 5)

Con systemd, lánzala por el propio programador (esto es la misma unidad que corre el temporizador):

```sh
systemctl --user start GrowiSupervisor-prueba.service
systemctl --user status GrowiSupervisor-prueba.service --no-pager   # «status=0/SUCCESS»
journalctl --user -u GrowiSupervisor-prueba.service -n 20 --no-pager
tail -n 5 _prueba/datos/supervisor.log                              # la línea nueva de esta pasada
```

Si cayó en cron: en WSL cron no arranca solo (`sudo service cron start`). Pon `intervalo_minutos: 1` en
`_prueba/config.yaml`, vuelve a correr el paso 5, espera dos minutos y mira `tail _prueba/datos/supervisor.log`.
Después devuelve el intervalo a 60 y repite el paso 5.

### 8. Quitarlo al terminar

```sh
sh instalar-supervisor.sh --config _prueba/config.yaml --desinstalar
```

Esto no toca nada de Windows.

### Para darlo por verificado

Guarda la salida de los pasos 3, 5, 6 y 7 (por ejemplo en `share\outbox\supervisor-linux-047-salida.txt`). Con eso
se puede marcar cada fila de FALTA como LISTO y cambiar la columna Linux de `REQUISITOS.md` a «sí (0.4.7)».

## Qué cambia respecto a Windows

| | Windows (verificado en la 0.4.6) | Linux (sin verificar) |
|---|---|---|
| Programador | Programador de tareas (`schtasks`) | temporizador de systemd de usuario (`~/.config/systemd/user/<nombre>.timer`, `OnUnitActiveSec=<N>min`, `Persistent=true`); sin systemd de usuario, una línea de `crontab` marcada con `# <nombre>` |
| Cómo lo detecta `--verificar` | `schtasks /Query /TN <nombre>` | `systemctl --user is-enabled <nombre>.timer`, y si no, busca `# <nombre>` en `crontab -l` |
| Llavero | Administrador de credenciales | Secret Service (GNOME Keyring o KWallet). En WSL no suele haber ninguno, así que ahí lo práctico es `origen: entorno`; ojo, systemd y cron no leen `~/.profile` |
| Python | `supervisor\.venv\Scripts\python.exe` | `supervisor/.venv/bin/python` (necesita `python3-venv`) |
| Log | `~/.growi-supervisor/supervisor.log` (o `datos` del YAML) | igual |
| Primera ejecución | según la tarea de Windows | 5 min después del arranque (`OnBootSec=5min`) y luego cada N min |
