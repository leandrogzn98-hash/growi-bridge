# -*- coding: utf-8 -*-
"""El vigilante (Fase 4 del plan multi-Muse): un perro guardián tonto.

Un proceso mínimo, SOLO biblioteca estándar, que no importa nada del
proyecto: si el puente se cae entero (con su supervisión dentro), alguien
de fuera tiene que poder levantarlo. Cada ~60 s mira, por carril
instalado, el ``runner-status.json``:

- pid muerto y ``last_poll`` viejo (>180 s) → relanza la app del carril
  con su comando de arranque habitual. Tope: 3 relanzamientos por carril
  y hora; al superarlo deja de insistir y escribe UN aviso
  ``bloqueo_dueno`` en el registro compartido.
- proceso vivo pero ``last_poll`` viejo (>300 s) → escribe el aviso y NO
  hace nada más: un vigilante tonto jamás mata un proceso vivo.

Lo arranca el sistema operativo (servicio de usuario systemd en Linux,
tarea programada repetitiva en Windows) y él mismo corre con reinicio
ante fallos: la cadena es app ← vigilante ← SO. No hay tercer nivel.

Configuración en ``vigilante.json`` junto a este archivo:
``{"base": "<carpeta compartida>", "carriles": [{"nombre": "a",
"dir": "<carpeta de la app>", "arranque": ["python3", "growi-bridge.py"]}]}``.
Su estado vive en ``vigilante-estado.json`` de la carpeta compartida.
"""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

POLL_MUERTO_S = 180
POLL_VIVO_VIEJO_S = 300
TOPE_RELANZAMIENTOS_HORA = 3
ROTACION_BYTES = 5 * 1024 * 1024
INTERVALO_S = 60

AQUI = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Piezas puras / testeables
# ---------------------------------------------------------------------------

def _ts_de(valor):
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(
                valor.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def evaluar_carril(status, ahora, pid_vivo):
    """«relanzar» | «avisar» | «nada» para un runner-status ya leído.
    Sin estado legible no se actúa: un vigilante tonto no adivina."""
    if not isinstance(status, dict):
        return "nada"
    ultimo = _ts_de(status.get("last_poll"))
    if ultimo is None:
        return "nada"
    edad = ahora - ultimo
    pid = status.get("pid")
    vivo = bool(pid) and pid_vivo(pid)
    if not vivo and edad > POLL_MUERTO_S:
        return "relanzar"
    if vivo and edad > POLL_VIVO_VIEJO_S:
        return "avisar"
    return "nada"


def puede_relanzar(estado, nombre, ahora):
    marcas = [t for t in (estado.get("relanzamientos") or {}).get(
        nombre, []) if ahora - t < 3600]
    return len(marcas) < TOPE_RELANZAMIENTOS_HORA


def _pid_vivo(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Aviso mínimo duplicado (mismo lock que avisos.py; la rotación la decide
# quien gana el lock — revisión I9 de la §14 bis)
# ---------------------------------------------------------------------------

def escribir_aviso(base_dir, tipo, texto, nivel="accion"):
    base = Path(base_dir)
    ruta = base / "avisos.jsonl"
    lock = base / "avisos.jsonl.lock"
    aviso = {"id": "av-" + uuid.uuid4().hex[:8], "ts": time.time(),
             "tipo": tipo, "nivel": nivel, "cuenta": None, "raiz": None,
             "tarea": None, "texto": str(texto)[:500],
             "origen": "vigilante"}
    fd = None
    try:
        base.mkdir(parents=True, exist_ok=True)
        limite = time.time() + 10
        while True:
            try:
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > 15:
                        lock.unlink()
                        continue
                except OSError:
                    pass
                if time.time() >= limite:
                    return False
                time.sleep(0.05)
        try:
            if ruta.exists() and ruta.stat().st_size >= ROTACION_BYTES:
                viejo = ruta.with_name(ruta.name + ".1")
                try:
                    viejo.unlink()
                except OSError:
                    pass
                os.replace(str(ruta), str(viejo))
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(json.dumps(aviso, ensure_ascii=False) + "\n")
            return True
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    lock.unlink()
                except OSError:
                    pass
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Inspección
# ---------------------------------------------------------------------------

def _leer_estado(base):
    try:
        datos = json.loads((Path(base) / "vigilante-estado.json").read_text(
            encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def _guardar_estado(base, estado):
    ruta = Path(base) / "vigilante-estado.json"
    tmp = ruta.with_name(ruta.name + f".tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=1)
    os.replace(str(tmp), str(ruta))


def _leer_status(carril):
    # La app escribe su estado en <carril>/share/outbox/runner-status.json;
    # se acepta también la raíz del carril por si cambia el diseño.
    base = Path(carril["dir"])
    for ruta in (base / "share" / "outbox" / "runner-status.json",
                 base / "runner-status.json"):
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            if isinstance(datos, dict):
                return datos
        except (OSError, ValueError):
            continue
    return None


def inspeccionar(config, estado, ahora=None, pid_vivo=_pid_vivo,
                 relanzar=None, avisar=None):
    """Una pasada sobre todos los carriles. ``relanzar(carril)`` y
    ``avisar(texto)`` son inyectables (en producción: subprocess y el
    aviso mínimo de arriba). Devuelve el estado actualizado."""
    ahora = ahora or time.time()
    base = config.get("base")
    relanzar = relanzar or _relanzar_real
    avisar = avisar or (lambda texto: escribir_aviso(base, "bloqueo_dueno",
                                                     texto))
    estado.setdefault("relanzamientos", {})
    estado.setdefault("bloqueo_avisado", {})
    for carril in config.get("carriles") or []:
        nombre = carril.get("nombre") or carril.get("dir") or "?"
        status = _leer_status(carril)
        accion = evaluar_carril(status, ahora, pid_vivo)
        if accion == "relanzar":
            if puede_relanzar(estado, nombre, ahora):
                marcas = [t for t in estado["relanzamientos"].get(
                    nombre, []) if ahora - t < 3600]
                marcas.append(ahora)
                estado["relanzamientos"][nombre] = marcas
                estado["bloqueo_avisado"][nombre] = False
                relanzar(carril)
            elif not estado["bloqueo_avisado"].get(nombre):
                estado["bloqueo_avisado"][nombre] = True
                avisar(f"El carril {nombre} sigue caído y el vigilante "
                       f"ya lo relanzó {TOPE_RELANZAMIENTOS_HORA} veces "
                       "en una hora; deja de insistir y necesita al dueño")
        elif accion == "avisar":
            ultimo_aviso = (estado.get("avisos") or {}).get(nombre, 0)
            if ahora - ultimo_aviso > 600:
                estado.setdefault("avisos", {})[nombre] = ahora
                avisar(f"El carril {nombre} está vivo pero su runner no "
                       "avanza (last_poll viejo); el vigilante no mata "
                       "procesos vivos")
        else:
            estado["bloqueo_avisado"][nombre] = False
    return estado


def _relanzar_real(carril):
    comando = carril.get("arranque") or []
    if not comando:
        return False
    try:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = 0x00000008  # DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(comando, cwd=carril.get("dir") or None,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kwargs)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Bucle principal (instancia única vía lock en la carpeta compartida)
# ---------------------------------------------------------------------------

def cargar_config(ruta=None):
    ruta = Path(ruta) if ruta else AQUI / "vigilante.json"
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else None
    except (OSError, ValueError):
        return None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    una_vez = "--una-vez" in argv
    config = cargar_config()
    if not config or not config.get("base"):
        print("vigilante: falta vigilante.json válido junto al script",
              file=sys.stderr)
        return 2
    base = Path(config["base"])
    base.mkdir(parents=True, exist_ok=True)
    lock = base / "vigilante.lock"
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        try:
            otro = int(lock.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            otro = None
        if otro and _pid_vivo(otro):
            print("vigilante: ya hay otra instancia viva", file=sys.stderr)
            return 0
        try:
            lock.unlink()
        except OSError:
            pass
        return main(argv)
    try:
        while True:
            estado = _leer_estado(base)
            estado = inspeccionar(config, estado)
            try:
                _guardar_estado(base, estado)
            except OSError:
                pass
            if una_vez:
                return 0
            time.sleep(INTERVALO_S)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
