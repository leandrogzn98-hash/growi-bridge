#!/usr/bin/env python3
"""Growi Bridge 0.1.0-alpha — puente + runner + proxy + pantalla + mascota + APIs en uno (Windows).

Un solo proceso, una sola ventana con pestanas, un solo icono en la bandeja
(la foto de Growi). Reemplaza al servidor viejo (pc-server.py) y al runner.

Pestanas:
  Estado    — boton grande de encendido, estado de puente/runner/proxy con
              interruptor propio por servicio y pildora de valor, indicador
              de sincronizacion (que se descarga/carga), ajustes (auto-update,
              inicio automatico, mascota), botones de PC (apagar/reiniciar),
              registro.
  Carpetas  — que carpetas puede ver Claude Code (Growi tambien las puede
              modificar). Por defecto: el Inbox del puente + tu carpeta
              principal (C:\\Users\\forte).
  Skills    — las skills instaladas de Claude Code (~/.claude/skills/).
  Pantalla  — compartir pantalla con Growi (fotogramas comprimidos, solo
              cuando tu lo activas; cada grabacion guarda sus fotogramas en
              una carpeta con fecha y hora; Growi mira un fotograma cuando
              hace falta).
  APIs      — claves de APIs privadas guardadas solo en este PC. Se pueden
              añadir desde aqui o desde WhatsApp: le dices a Growi y llegan
              al PC en segundos por el puente.

Extras:
  - Mascota: Growi en la esquina inferior derecha, con animaciones segun
    el estado (descansando, trabajando, saludo al hacer clic, celebracion
    cuando Claude termina una tarea); clic para escribirle un mensaje
    rapido (llega a Growi por el puente).
  - Proxy: boton para encender/apagar el proxy (host/puerto/usuario/clave
    configurables; cada quien usa los suyos).
  - Actualizaciones: busca nuevas versiones en GitHub; con la
    actualizacion automatica activada se actualiza sola y se reinicia.
  - Administrador: detecta si corre elevado; el instalador lo deja en
    arranque automatico con privilegios maximos.

Uso:
  - Probar en ventana visible:  python growi-bridge.py
  - Oculto (solo bandeja):      pythonw growi-bridge.py
  - Arranque automatico:        instalar-growi-bridge.bat (una sola vez)

La X minimiza (la ventana queda minimizada y la mascota sigue visible).
Salir de verdad es con el boton Salir o desde el menu de la bandeja.
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import random
import time
import traceback
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "0.1.0-alpha"
GITHUB_REPO = "leandrogzn98-hash/growi-bridge"
APP_DIR = Path(__file__).resolve().parent
SHARE = APP_DIR / "share"
INBOX = SHARE / "inbox"
OUTBOX = SHARE / "outbox"
TASKS = INBOX / "runner-tasks"
PROCESSING = TASKS / "processing"
DONE = TASKS / "done"
RESULTS = OUTBOX / "runner-results"
SCREENS = OUTBOX / "screens"
MESSAGES = OUTBOX / "mensajes"
LOG_FILE = APP_DIR / "growi-bridge.log"
PHOTO = APP_DIR / "growi.png"
MASCOT_DIR = APP_DIR / "mascot"
MASCOT_SIZE = 128  # la mascota en pantalla es de 128x128 (antes 96)
# Color magico de la ventana de la mascota: el magenta puro NUNCA aparece
# en el personaje, asi que la ventana lo hace transparente sin agujeros.
# Los fotogramas de mascot/*.png van compuestos sobre este color.
MASCOT_MAGIC = "#ff00ff"
# Modelo local (Ollama, ya instalado en el PC con Hermes 3 8B Q4).
OLLAMA_MODEL = "hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M"
_keep_awake_applied = [False]
_seen_results = set()
PROXY_FILE = APP_DIR / "proxy.json"
FOLDERS_FILE = APP_DIR / "folders.json"
SETTINGS_FILE = APP_DIR / "settings.json"
BRIDGE_PORT = 8787
HOME_DIR = Path.home()

# Tema v2.3 "Mac" (ver DESIGN.md + notas-mobbin.md Superlist/Plain):
# contenido blanco, barra lateral gris muy clara, texto casi negro,
# acento azul de macOS, interruptores verdes de macOS.
FONT = "Segoe UI"
THEME = {
    "bg": "#FFFFFF", "sidebar": "#F5F5F7", "card": "#F5F5F7", "field": "#FFFFFF",
    "text": "#1D1D1F", "muted": "#6E6E73", "line": "#E5E5EA",
    "green": "#34C759", "green_text": "#248A3D", "blue": "#007AFF",
    "orange": "#FF9500", "red": "#FF3B30",
}

ICO = APP_DIR / "growi.ico"
TRAY_ICON = APP_DIR / "growi-tray.png"
HEADER_PHOTO = APP_DIR / "growi-header.png"

# ---------------------------------------------------------------- estado/log
state = {
    "bridge": "parado", "bridge_err": "",
    "runner": "parado", "tasks_done": 0, "current": None, "last_result": "",
    "proxy_on": "HTTPS_PROXY" in os.environ,
    "proxy_configured": False,
    "admin": False,
    "sharing": False, "last_frame": "", "share_folder": None, "share_frame": 0,
    "mascot": False,
    "update_available": "", "update_checked": False, "auto_update_ready": "",
    "auto_update": False, "autostart": False,
    "power": False,
}
LOG_Q = queue.Queue()
TRANSFERS = deque(maxlen=8)  # (direccion, nombre, tamano, iso) direccion: down|up


def log(msg):
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
    LOG_Q.put(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def note_transfer(direction, name, size):
    TRANSFERS.append((direction, name, size,
                      datetime.now().astimezone().isoformat(timespec="seconds")))
    if direction == "down":
        log(f"sync: descargando {name} ({size} bytes)")
    else:
        log(f"sync: enviando {name} ({size} bytes)")


def load_secret():
    try:
        return (APP_DIR / "secret.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_admin():
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ---------------------------------------------------------------- proxy
def proxy_config():
    cfg = {"host": "", "port": 18080, "user": "", "password": ""}
    try:
        cfg.update(json.loads(PROXY_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    # Si no hay nada guardado pero las variables ya existen, heredarlas
    # (también la clave, si viene en la URL: sin ella el proxy no se puede
    # volver a encender tras apagarlo).
    env = os.environ.get("HTTPS_PROXY") or ""
    if env:
        try:
            u = urlparse(env)
            if not cfg["host"]:
                cfg["host"] = u.hostname or ""
                cfg["port"] = u.port or 18080
                cfg["user"] = u.username or ""
            if not cfg["password"] and u.password:
                cfg["password"] = u.password
        except Exception:
            pass
    return cfg


def save_proxy_config(cfg):
    PROXY_FILE.write_text(json.dumps(cfg), encoding="utf-8")
    state["proxy_configured"] = bool(cfg.get("password"))


def proxy_url():
    cfg = proxy_config()
    if not cfg["host"] or not cfg["password"]:
        return ""
    return f"http://{cfg['user']}:{cfg['password']}@{cfg['host']}:{cfg['port']}"


def _broadcast_env_change():
    try:
        import ctypes
        res = ctypes.c_ulong(0)
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(res))
    except Exception:
        pass


def set_proxy(on):
    try:
        import winreg
    except ImportError:
        return False, "winreg no disponible (no es Windows?)"
    if on:
        url = proxy_url()
        if not url:
            return False, "falta configurar el proxy (host y clave)"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment",
                                 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "HTTPS_PROXY", 0, winreg.REG_SZ, url)
            winreg.SetValueEx(key, "HTTP_PROXY", 0, winreg.REG_SZ, url)
            winreg.CloseKey(key)
        except OSError as e:
            return False, f"no se pudo escribir en el registro: {e}"
        os.environ["HTTPS_PROXY"] = url
        os.environ["HTTP_PROXY"] = url
        _broadcast_env_change()
        state["proxy_on"] = True
        cfg = proxy_config()
        return True, f"proxy ENCENDIDO ({cfg['host']}:{cfg['port']})"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment",
                             0, winreg.KEY_SET_VALUE)
        for name in ("HTTPS_PROXY", "HTTP_PROXY"):
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError as e:
        return False, f"no se pudo borrar del registro: {e}"
    os.environ.pop("HTTPS_PROXY", None)
    os.environ.pop("HTTP_PROXY", None)
    _broadcast_env_change()
    state["proxy_on"] = False
    return True, "proxy APAGADO (Claude ya no sale por el VPS)"


# ---------------------------------------------------------------- inicio automatico y PC
def autostart_enabled():
    """True si existe la tarea programada GrowiBridgeApp (inicio con Windows)."""
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", "GrowiBridgeApp"],
                           capture_output=True)
        return r.returncode == 0
    except Exception:
        return False


def set_autostart(on):
    """Crea o borra la tarea programada de inicio automatico. Necesita
    permisos de administrador (la app corre elevada cuando la instalo el
    instalador)."""
    try:
        if on:
            exe = str(APP_DIR / "iniciar-growi-bridge.bat")
            r = subprocess.run(["schtasks", "/create", "/tn", "GrowiBridgeApp",
                                "/tr", f'"{exe}"', "/sc", "onlogon",
                                "/rl", "highest", "/f"], capture_output=True)
        else:
            r = subprocess.run(["schtasks", "/delete", "/tn", "GrowiBridgeApp",
                                "/f"], capture_output=True)
        if r.returncode != 0:
            log("inicio automatico: no se pudo cambiar (¿sin permisos de administrador?)")
            return False
        log(f"inicio automatico: {'activado' if on else 'desactivado'}")
        return True
    except Exception as e:
        log(f"inicio automatico: error ({e})")
        return False


def pc_power(action):
    """Apaga o reinicia el PC en 60 segundos. action: 'shutdown' o 'restart'.
    Windows muestra su propio aviso y se puede cancelar con pc_abort()."""
    cmd = (["shutdown", "/s", "/t", "60"] if action == "shutdown"
           else ["shutdown", "/r", "/t", "60"])
    try:
        subprocess.run(cmd, capture_output=True)
        what = "apagado" if action == "shutdown" else "reinicio"
        log(f"PC: {what} programado en 60 s (boton Cancelar o 'shutdown /a')")
        return True
    except Exception as e:
        log(f"PC: no se pudo programar ({e})")
        return False


def pc_abort():
    """Cancela un apagado o reinicio programado."""
    try:
        subprocess.run(["shutdown", "/a"], capture_output=True)
        log("PC: apagado/reinicio cancelado")
        return True
    except Exception as e:
        log(f"PC: no se pudo cancelar ({e})")
        return False


# ---------------------------------------------------------------- APIs privadas
APIS_FILE = APP_DIR / "apis.json"


def load_apis():
    try:
        data = json.loads(APIS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_apis(apis):
    try:
        APIS_FILE.write_text(json.dumps(apis, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    except OSError:
        pass


def mask_key(key):
    """Muestra solo los ultimos 4 caracteres de una clave."""
    k = str(key)
    return ("•" * max(0, len(k) - 4)) + k[-4:] if len(k) > 4 else "•" * len(k)


def import_api_files():
    """Toma los archivos que Growi empuja por el puente (inbox/apis/*.json)
    y los guarda en apis.json. Borra el archivo tras importarlo para que la
    clave no quede dando vueltas en el Inbox. Devuelve cuantas se añadieron."""
    api_inbox = INBOX / "apis"
    if not api_inbox.is_dir():
        return 0
    added = 0
    for p in sorted(api_inbox.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            name = str(data.get("name", "")).strip()
            key = str(data.get("key", "")).strip()
            if not name or not key or len(name) > 80:
                raise ValueError("nombre o clave invalidos")
            apis = load_apis()
            apis = [a for a in apis if a.get("name") != name]
            apis.append({"name": name, "key": key})
            save_apis(apis)
            added += 1
            log(f"APIs: '{name}' añadida desde WhatsApp (clave guardada solo en este PC)")
        except Exception as e:
            log(f"APIs: no se pudo importar {p.name} ({e})")
        finally:
            try:
                p.unlink()
            except OSError:
                pass
    if added and _widgets.get("apis_tree") is not None and _root is not None:
        try:
            _root.after(0, refresh_apis_ui)
        except Exception:
            pass
    return added


# ---------------------------------------------------------------- carpetas


def _pc_confirm(action):
    """Confirmacion antes de apagar o reiniciar el PC (60 s de margen)."""
    what = "apagar" if action == "shutdown" else "reiniciar"
    if messagebox.askyesno(
            "Apagar / reiniciar el PC",
            f"¿Seguro que quieres {what} este PC?\n\n"
            "Tienes 60 segundos para cancelarlo con el botón "
            "\"Cancelar apagado\" o con 'shutdown /a'."):
        pc_power(action)

def default_roots():
    return [str(INBOX), str(HOME_DIR)]


def load_folders():
    try:
        data = json.loads(FOLDERS_FILE.read_text(encoding="utf-8"))
        roots = [str(r) for r in data.get("allowed_roots", []) if str(r).strip()]
        if roots:
            return roots
    except (OSError, ValueError):
        pass
    return default_roots()


def save_folders(roots):
    FOLDERS_FILE.write_text(
        json.dumps({"allowed_roots": roots}, ensure_ascii=False, indent=2),
        encoding="utf-8")


# ---------------------------------------------------------------- skills
def list_skills():
    """Lee ~/.claude/skills/: cada carpeta con SKILL.md es una skill."""
    base = HOME_DIR / ".claude" / "skills"
    out = []
    if not base.is_dir():
        return out
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        skill_file = folder / "SKILL.md"
        name = folder.name
        desc = ""
        if skill_file.is_file():
            try:
                text = skill_file.read_text(encoding="utf-8", errors="replace")
                if text.startswith("---"):
                    end = text.find("---", 3)
                    if end > 0:
                        for line in text[3:end].splitlines():
                            if line.strip().lower().startswith("description:"):
                                desc = line.split(":", 1)[1].strip().strip("\"'")
                            if line.strip().lower().startswith("name:"):
                                name = line.split(":", 1)[1].strip().strip("\"'")
                if not desc:
                    for line in text.splitlines():
                        if line.strip() and not line.startswith("#") and not line.startswith("---"):
                            desc = line.strip()
                            break
            except OSError:
                pass
        out.append((name, desc, str(folder)))
    return out


# ---------------------------------------------------------------- updates
UPDATE_FILES = ["growi-bridge.py", "growi.ico", "growi-tray.png", "growi-header.png",
                "growi.png", "instalar-growi-bridge.bat", "iniciar-growi-bridge.bat",
                "probar-growi-bridge.bat", "LEEME-growi-bridge.md", "VERSION",
                "DESIGN.md", "notas-mobbin.md"]


def _version_tuple(v):
    """Tupla comparable de una version. Soporta pre-release: 0.1.0-alpha
    -> (0, 1, 0, 0); 0.1.0 -> (0, 1, 0, 3); 2.3 -> (2, 3, 0, 3)."""
    s = str(v).strip().lstrip("v")
    pre = 3
    if "-" in s:
        s, tag = s.split("-", 1)
        pre = {"alpha": 0, "beta": 1, "rc": 2}.get(tag.strip().lower(), 0)
    parts = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    parts.append(pre)
    return tuple(parts)


def check_update_available():
    """Compara con VERSION en GitHub (raw). Devuelve la version nueva o ''.
    Migracion de numeracion: la app paso de la linea 2.x a la 0.x (Alpha);
    cualquier 0.x se considera mas nueva que cualquier 2.x."""
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/VERSION"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrowiBridge"})
        with urllib.request.urlopen(req, timeout=15) as r:
            remote = r.read().decode("utf-8", errors="replace").strip()
        if not remote:
            return ""
        if VERSION.startswith("2.") and remote.startswith("0."):
            return remote
        if _version_tuple(remote) > _version_tuple(VERSION):
            return remote
    except Exception as e:
        log(f"actualizaciones: no se pudo comprobar ({type(e).__name__})")
    return ""


def download_update(version):
    """Baja TODOS los archivos de la nueva version y deja el actualizador
    listo (actualizar.bat mueve cada .new a su sitio y relanza la app).
    True si quedo todo, False si algo fallo."""
    for name in UPDATE_FILES:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GrowiBridge"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if name == "growi-bridge.py" and (b"Growi Bridge" not in data[:2000]
                                             or len(data) < 10000):
                log("actualizaciones: growi-bridge.py descargado invalido")
                return False
            (APP_DIR / (name + ".new")).write_bytes(data)
        except Exception as e:
            log(f"actualizaciones: fallo al bajar {name} ({e})")
            return False
    lines = ["@echo off", "timeout /t 2 /nobreak >nul"]
    for name in UPDATE_FILES:
        lines.append(f'move /y "{name}.new" "{name}"')
    lines += ["start /b pythonw growi-bridge.py", 'del "%~f0"']
    (APP_DIR / "actualizar.bat").write_text("\r\n".join(lines) + "\r\n",
                                            encoding="utf-8")
    return True


def _do_auto_update():
    """Auto-update (sin preguntar): lo dispara _tick cuando el hilo de
    fondo dejo una version lista en state['auto_update_ready']."""
    version = state.get("auto_update_ready", "")
    state["auto_update_ready"] = ""
    if not version or not load_settings().get("auto_update"):
        return
    if not download_update(version):
        return
    log(f"actualizaciones: auto-update a v{version}, reiniciando...")
    try:
        subprocess.Popen(["cmd", "/c", "actualizar.bat"], cwd=str(APP_DIR))
    except Exception:
        return
    quit_app()


def _auto_update_loop():
    """Hilo de fondo: cada 6 h comprueba si hay version nueva. Si la
    actualizacion automatica esta activada, deja la version lista para que
    _tick la instale sola; si no, solo avisa en la ventana."""
    time.sleep(60)
    while True:
        try:
            if load_settings().get("auto_update"):
                remote = check_update_available()
                if remote:
                    state["update_available"] = remote
                    state["update_checked"] = True
                    state["auto_update_ready"] = remote
                    log(f"actualizaciones: v{remote} lista, auto-update en curso")
        except Exception:
            pass
        time.sleep(6 * 3600)

# ---------------------------------------------------------------- puente (HTTP)
def box_dir(box):
    d = SHARE / box
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_name(name):
    if not name:
        return None
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return "/".join(parts)


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "GrowiBridge/2.0"
    SECRET = ""
    BOXES = ("inbox", "outbox")

    def _auth(self):
        return self.headers.get("X-Shared-Secret") == self.SECRET

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _box(self, qs):
        box = (qs.get("box") or [""])[0]
        return box if box in self.BOXES else None

    def do_GET(self):
        if not self._auth():
            return self._json({"error": "unauthorized"}, 401)
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == "/ping":
            return self._json({"ok": True})
        if u.path == "/list":
            box = self._box(qs)
            if not box:
                return self._json({"error": "box invalido"}, 400)
            files = []
            d = box_dir(box)
            for root, _dirs, fnames in os.walk(d):
                for fn in fnames:
                    p = os.path.join(root, fn)
                    rel = os.path.relpath(p, d).replace(os.sep, "/")
                    st = os.stat(p)
                    files.append({"name": rel, "size": st.st_size, "mtime": st.st_mtime})
            files.sort(key=lambda x: x["name"])
            return self._json({"files": files})
        if u.path == "/get":
            box = self._box(qs)
            name = safe_name((qs.get("name") or [""])[0])
            if not box or not name:
                return self._json({"error": "parametros invalidos"}, 400)
            p = os.path.join(box_dir(box), *name.split("/"))
            if not os.path.isfile(p):
                return self._json({"error": "no existe"}, 404)
            with open(p, "rb") as f:
                data = f.read()
            note_transfer("up", f"{box}/{name}", len(data))
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        return self._json({"error": "no encontrado"}, 404)

    def do_POST(self):
        if not self._auth():
            return self._json({"error": "unauthorized"}, 401)
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if u.path == "/put":
            box = self._box(qs)
            name = safe_name((qs.get("name") or [""])[0])
            if not box or not name:
                return self._json({"error": "parametros invalidos"}, 400)
            length = int(self.headers.get("Content-Length", 0) or 0)
            data = self.rfile.read(length) if length > 0 else b""
            p = os.path.join(box_dir(box), *name.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
            note_transfer("down", f"{box}/{name}", len(data))
            return self._json({"ok": True, "name": name, "size": len(data)})
        return self._json({"error": "no encontrado"}, 404)

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------- runner
POLL_SECONDS = 5
HEARTBEAT_SECONDS = 60
MAX_PROMPT_CHARS = 100_000
DEFAULT_TIMEOUT_MIN = 30
MAX_TIMEOUT_MIN = 120
MAX_RESULT_CHARS = 20_000
MAX_STDERR_CHARS = 2_000
ALLOWED_MODELS = {"sonnet", "opus", "haiku"}
SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_id(task_id):
    return (
        isinstance(task_id, str)
        and 1 <= len(task_id) <= 80
        and all(c in SAFE_ID_CHARS for c in task_id)
        and ".." not in task_id
    )


def _inside_any(cwd, roots):
    try:
        cwd_s = str(cwd)
        for r in roots:
            r_s = str(Path(r).resolve())
            if os.path.commonpath([cwd_s, r_s]) == r_s:
                return True
    except ValueError:
        pass
    return False


def validate_task(data):
    if not isinstance(data, dict):
        return None, "el task.json no es un objeto JSON"
    task_id = data.get("id")
    if not _safe_id(task_id):
        return None, "id invalido o ausente (solo letras, numeros, - _ .)"
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None, "prompt vacio o ausente"
    if len(prompt) > MAX_PROMPT_CHARS:
        return None, f"prompt demasiado largo ({len(prompt)} > {MAX_PROMPT_CHARS})"
    cwd_raw = data.get("cwd") or str(INBOX)
    try:
        cwd = Path(cwd_raw).expanduser().resolve()
    except OSError:
        return None, f"cwd invalido: {cwd_raw}"
    if not cwd.is_dir():
        return None, f"cwd no existe o no es carpeta: {cwd}"
    if not _inside_any(cwd, load_folders()):
        return None, f"cwd fuera de las carpetas permitidas: {cwd}"
    model = data.get("model")
    if model is not None:
        if not isinstance(model, str) or (
            model not in ALLOWED_MODELS
            and not model.startswith("claude-")
            and not model.startswith("ollama:")
        ):
            return None, f"model no permitido: {model}"
    allowed_tools = data.get("allowed_tools")
    if allowed_tools is not None and (
        not isinstance(allowed_tools, str) or not allowed_tools.strip()
    ):
        return None, "allowed_tools debe ser texto no vacio"
    permission_mode = data.get("permission_mode")
    if permission_mode is not None and permission_mode not in (
        "acceptEdits", "plan", "default", "bypassPermissions",
    ):
        return None, f"permission_mode no permitido: {permission_mode}"
    session_id = data.get("session_id")
    if session_id is not None and not _safe_id(session_id):
        return None, f"session_id invalido: {session_id}"
    try:
        timeout_min = int(data.get("timeout_min") or DEFAULT_TIMEOUT_MIN)
    except (TypeError, ValueError):
        return None, "timeout_min debe ser un numero"
    timeout_min = max(1, min(MAX_TIMEOUT_MIN, timeout_min))
    return {
        "id": task_id, "prompt": prompt, "cwd": str(cwd), "model": model,
        "allowed_tools": allowed_tools, "permission_mode": permission_mode,
        "session_id": session_id, "timeout_min": timeout_min,
    }, None


def _run_ollama(task):
    """Motor local: corre el prompt con Ollama (Hermes 3 8B en la RTX 3060).
    Un solo turno, sin herramientas de Claude Code: sirve para preguntas,
    resumenes, borradores y codigo en una pasada. Costo $0."""
    started = _now_iso()
    t0 = time.time()
    model = (task.get("model") or "").split("ollama:", 1)[1]
    result = {
        "runner": f"growi-bridge/{VERSION}", "id": task["id"], "status": "error",
        "started_at": started, "finished_at": None, "duration_s": None,
        "exit_code": None, "result": "", "cost_usd": 0.0, "num_turns": 1,
        "session_id": None, "stderr": "", "error": None,
    }
    if not shutil.which("ollama"):
        result["error"] = "ollama no esta en el PATH de este usuario"
        result["finished_at"] = _now_iso()
        result["duration_s"] = round(time.time() - t0, 1)
        return result
    log(f"runner [{task['id']}]: corriendo ollama run {model} (local, $0)")
    try:
        proc = subprocess.run(
            ["ollama", "run", model, task["prompt"]],
            cwd=task["cwd"], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=task["timeout_min"] * 60,
        )
        result["exit_code"] = proc.returncode
        result["stderr"] = (proc.stderr or "")[-MAX_STDERR_CHARS:]
        result["result"] = (proc.stdout or "")[:MAX_RESULT_CHARS]
        result["status"] = "ok" if proc.returncode == 0 else "error"
        if proc.returncode != 0:
            result["error"] = f"ollama salio con codigo {proc.returncode}"
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
        result["error"] = f"timeout de {task['timeout_min']} min"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    result["finished_at"] = _now_iso()
    result["duration_s"] = round(time.time() - t0, 1)
    return result


def run_task(task):
    if (task.get("model") or "").startswith("ollama:"):
        return _run_ollama(task)
    started = _now_iso()
    t0 = time.time()
    cmd = ["claude", "-p", task["prompt"], "--output-format", "json"]
    if task["model"]:
        cmd += ["--model", task["model"]]
    if task["allowed_tools"]:
        cmd += ["--allowedTools", task["allowed_tools"]]
    if task["permission_mode"]:
        cmd += ["--permission-mode", task["permission_mode"]]
    if task.get("session_id"):
        cmd += ["--resume", task["session_id"]]
    log(f"runner [{task['id']}]: corriendo claude -p en {task['cwd']} (timeout {task['timeout_min']} min)")
    result = {
        "runner": f"growi-bridge/{VERSION}", "id": task["id"], "status": "error",
        "started_at": started, "finished_at": None, "duration_s": None,
        "exit_code": None, "result": "", "cost_usd": None, "num_turns": None,
        "session_id": None, "stderr": "", "error": None,
    }
    try:
        proc = subprocess.run(
            cmd, cwd=task["cwd"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=task["timeout_min"] * 60,
        )
        result["exit_code"] = proc.returncode
        result["stderr"] = (proc.stderr or "")[-MAX_STDERR_CHARS:]
        stdout = proc.stdout or ""
        try:
            data = json.loads(stdout)
            result["result"] = str(data.get("result", ""))[:MAX_RESULT_CHARS]
            result["cost_usd"] = data.get("total_cost_usd")
            result["num_turns"] = data.get("num_turns")
            result["session_id"] = data.get("session_id")
            result["status"] = (
                "error" if data.get("is_error") or proc.returncode != 0 else "ok"
            )
            if data.get("is_error"):
                result["error"] = "claude reporto is_error=true"
        except json.JSONDecodeError:
            result["result"] = stdout[:MAX_RESULT_CHARS]
            result["status"] = "ok" if proc.returncode == 0 else "error"
            if proc.returncode != 0:
                result["error"] = f"claude salio con codigo {proc.returncode} y salida no-JSON"
    except FileNotFoundError:
        result["error"] = "claude no esta en el PATH de este usuario"
    except subprocess.TimeoutExpired as e:
        result["status"] = "timeout"
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        result["result"] = str(out)[-MAX_RESULT_CHARS:]
        result["error"] = f"timeout de {task['timeout_min']} min"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    result["finished_at"] = _now_iso()
    result["duration_s"] = round(time.time() - t0, 1)
    return result


def _write_result(result):
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{result['id']}.result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path


def _error_result(task_id, error):
    return {
        "runner": f"growi-bridge/{VERSION}", "id": task_id, "status": "error",
        "started_at": _now_iso(), "finished_at": _now_iso(), "duration_s": 0,
        "exit_code": None, "result": "", "cost_usd": None, "num_turns": None,
        "session_id": None, "stderr": "", "error": error,
    }


def process_one(task_file):
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"runner [{task_file.name}]: JSON invalido ({e}); se archiva sin correr")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_file), str(DONE / task_file.name))
        _write_result(_error_result(task_file.stem, f"JSON invalido: {e}"))
        return True
    task, error = validate_task(data)
    task_id = data.get("id") if isinstance(data.get("id"), str) else task_file.stem
    if error:
        log(f"runner [{task_id}]: rechazado: {error}")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_file), str(DONE / task_file.name))
        _write_result(_error_result(task_id, error))
        return True
    PROCESSING.mkdir(parents=True, exist_ok=True)
    DONE.mkdir(parents=True, exist_ok=True)
    processing_path = PROCESSING / task_file.name
    try:
        shutil.move(str(task_file), str(processing_path))
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo mover a processing: {e}")
        return False
    state["current"] = task["id"]
    result = run_task(task)
    state["current"] = None
    state["tasks_done"] += 1
    state["last_result"] = f"{task['id']}: {result['status']} ({result['duration_s']}s, ${result['cost_usd'] or 0})"
    try:
        _write_result(result)
        log(f"runner [{task['id']}]: terminado: {result['status']} duracion={result['duration_s']}s costo={result['cost_usd']}")
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo escribir el resultado: {e}")
    try:
        shutil.move(str(processing_path), str(DONE / task_file.name))
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo archivar el task: {e}")
    return True


def runner_heartbeat():
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        status = {
            "runner": f"growi-bridge/{VERSION}", "alive": True, "last_poll": _now_iso(),
            "tasks_done": state["tasks_done"], "current": state["current"],
            "claude": shutil.which("claude"), "pid": os.getpid(),
        }
        with open(OUTBOX / "runner-status.json", "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def runner_loop(stop_event):
    for d in (TASKS, PROCESSING, DONE, RESULTS):
        d.mkdir(parents=True, exist_ok=True)
    claude = shutil.which("claude")
    log(f"runner: arrancado (claude={claude or 'NO ENCONTRADO'})")
    if not claude:
        log("runner AVISO: `claude` no esta en el PATH; las tareas fallaran con error.")
    last_heartbeat = 0.0
    while not stop_event.is_set():
        try:
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                runner_heartbeat()
                last_heartbeat = now
            candidates = []
            for p in TASKS.glob("*.task.json"):
                try:
                    if now - p.stat().st_mtime >= 2:
                        candidates.append(p)
                except OSError:
                    continue
            candidates.sort(key=lambda p: p.stat().st_mtime)
            if candidates:
                if process_one(candidates[0]):
                    runner_heartbeat()
                    last_heartbeat = time.time()
        except Exception as e:
            log(f"runner ERROR en el loop (se sigue): {type(e).__name__}: {e}")
        stop_event.wait(POLL_SECONDS)
    log("runner: parado")


# ---------------------------------------------------------------- servicios
_bridge_server = None
_bridge_thread = None
_runner_stop = None
_runner_thread = None
_share_stop = None
_share_thread = None


def start_bridge():
    global _bridge_server, _bridge_thread
    if _bridge_thread and _bridge_thread.is_alive():
        return True, "el puente ya estaba corriendo"
    secret = load_secret()
    if not secret:
        state["bridge"] = "error"
        state["bridge_err"] = "falta secret.txt junto al programa"
        log("puente ERROR: falta secret.txt junto al programa")
        return False, "falta secret.txt junto al programa"
    BridgeHandler.SECRET = secret
    try:
        server = ThreadingHTTPServer(("0.0.0.0", BRIDGE_PORT), BridgeHandler)
    except OSError as e:
        state["bridge"] = "error"
        state["bridge_err"] = f"puerto {BRIDGE_PORT} ocupado ({e}) — ¿sigue corriendo pc-server.py?"
        log(f"puente ERROR: puerto {BRIDGE_PORT} ocupado ({e})")
        return False, state["bridge_err"]
    _bridge_server = server
    _bridge_thread = threading.Thread(target=server.serve_forever, daemon=True)
    _bridge_thread.start()
    state["bridge"] = "corriendo"
    state["bridge_err"] = ""
    log(f"puente: escuchando en puerto {BRIDGE_PORT}")
    return True, f"puente corriendo en puerto {BRIDGE_PORT}"


def stop_bridge():
    global _bridge_server, _bridge_thread
    if _bridge_server is not None:
        try:
            _bridge_server.shutdown()
            _bridge_server.server_close()
        except Exception:
            pass
        _bridge_server = None
    if _bridge_thread is not None:
        _bridge_thread.join(timeout=5)
        _bridge_thread = None
    state["bridge"] = "parado"
    log("puente: parado")


def start_runner():
    global _runner_stop, _runner_thread
    if _runner_thread and _runner_thread.is_alive():
        return True, "el runner ya estaba corriendo"
    _runner_stop = threading.Event()
    _runner_thread = threading.Thread(target=runner_loop, args=(_runner_stop,), daemon=True)
    _runner_thread.start()
    state["runner"] = "corriendo"
    log("runner: arrancado")
    return True, "runner corriendo"


def stop_runner():
    global _runner_stop, _runner_thread
    if _runner_stop is not None:
        _runner_stop.set()
    if _runner_thread is not None:
        _runner_thread.join(timeout=10)
        _runner_thread = None
    _runner_stop = None
    state["runner"] = "parado"
    state["current"] = None
    log("runner: parado")


def set_power(on):
    """El boton grande: enciende/apaga puente + runner juntos."""
    if on:
        ok_b, _ = start_bridge()
        ok_r, _ = start_runner()
        state["power"] = state["bridge"] == "corriendo" or state["runner"] == "corriendo"
        if not (ok_b and ok_r):
            log("boton: algo no arranco; revisa el registro")
    else:
        stop_runner()
        stop_bridge()
        state["power"] = False
    return state["power"]


# ---------------------------------------------------------------- pantalla
def _cleanup_old_sessions(days=7):
    """Borra las carpetas de sesiones de pantalla de mas de `days` dias."""
    try:
        now = time.time()
        for d in SCREENS.iterdir():
            if d.is_dir() and len(d.name) >= 15 and d.name[:8].isdigit() \
                    and "-" in d.name:
                if now - d.stat().st_mtime > days * 86400:
                    shutil.rmtree(d, ignore_errors=True)
                    log(f"pantalla: sesion vieja borrada ({d.name})")
    except Exception:
        pass


def _capture_frame():
    """Un fotograma comprimido: se guarda en la carpeta de la sesion actual
    (outbox/screens/AAAAMMDD-HHMMSS/frame-NNNN.jpg) y como latest.jpg."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    folder = state.get("share_folder")
    if not folder:
        return None
    SCREENS.mkdir(parents=True, exist_ok=True)
    try:
        img = ImageGrab.grab()
    except Exception as e:
        log(f"pantalla: no se pudo capturar ({e})")
        return None
    if img.width > 1280:
        img = img.resize((1280, int(img.height * 1280 / img.width)))
    img = img.convert("RGB")
    frame = state.get("share_frame", 0) + 1
    state["share_frame"] = frame
    path = Path(folder) / ("frame-%04d.jpg" % frame)
    img.save(path, "JPEG", quality=45)
    img.save(SCREENS / "latest.jpg", "JPEG", quality=45)
    info = {"at": _now_iso(), "session": Path(folder).name, "frame": frame,
            "size": path.stat().st_size, "w": img.width, "h": img.height}
    (SCREENS / "status.json").write_text(json.dumps(info), encoding="utf-8")
    state["last_frame"] = info["at"]
    return info


def screen_loop(stop_event, interval_s):
    log(f"pantalla: compartiendo en {state.get('share_folder')} "
        f"(fotograma cada {interval_s}s, JPEG 45, max 1280px)")
    count = 0
    while not stop_event.is_set():
        info = _capture_frame()
        if info:
            count += 1
            if count % 10 == 1:
                log(f"pantalla: fotograma {count} ({info['size'] // 1024} KB)")
        stop_event.wait(interval_s)
    log("pantalla: compartiendo detenido")


def start_sharing(interval_s=10):
    global _share_stop, _share_thread
    if _share_thread and _share_thread.is_alive():
        return False
    _cleanup_old_sessions()
    folder = SCREENS / datetime.now().strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    state["share_folder"] = str(folder)
    state["share_frame"] = 0
    _share_stop = threading.Event()
    _share_thread = threading.Thread(target=screen_loop,
                                     args=(_share_stop, float(interval_s)),
                                     daemon=True)
    _share_thread.start()
    state["sharing"] = True
    log(f"pantalla: nueva sesion {folder.name} (fotogramas en {folder})")
    return True


def stop_sharing():
    global _share_stop, _share_thread
    if _share_stop is not None:
        _share_stop.set()
    if _share_thread is not None:
        _share_thread.join(timeout=5)
        _share_thread = None
    _share_stop = None
    state["sharing"] = False
    try:
        (SCREENS / "status.json").write_text(
            json.dumps({"on": False, "at": _now_iso()}), encoding="utf-8")
    except OSError:
        pass
    log("pantalla: compartiendo detenido")

# ---------------------------------------------------------------- interfaz
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
    TK_OK = True
except ImportError:
    TK_OK = False
    tk = None

try:
    from tkinterdnd2 import DND_FILES
    DND_OK = True
except ImportError:
    DND_FILES = None
    DND_OK = False

try:
    import pystray
    from PIL import Image, ImageTk
    TRAY_OK = True
except ImportError:
    TRAY_OK = False
    pystray = None

_widgets = {}
_tray_icon = None
_root = None
_pulse = [0]
_tick_n = [0]


_tray_state = ["idle"]


def _tray_image(kind):
    """Genera el icono de la bandeja con un distintivo (como OneDrive):
    'idle' = solo la foto; 'sync'/'sync2' = punto verde que pulsa mientras
    hay sincronizacion (transferencia en los ultimos 10 s); 'error' = punto
    rojo (el puente esta caido)."""
    try:
        from PIL import ImageDraw
        base = Image.open(TRAY_ICON if TRAY_ICON.is_file() else PHOTO).convert("RGBA")
    except Exception:
        return None
    if kind == "idle":
        return base
    img = base.copy()
    d = ImageDraw.Draw(img)
    color = {"sync": "#34C759", "sync2": "#8BE0A4", "error": "#FF3B30"}[kind]
    d.ellipse([42, 42, 62, 62], fill=color, outline="white", width=2)
    return img


def make_switch(parent, initial, command, bg=None):
    """Interruptor estilo macOS (verde #34C759 encendido, gris claro
    apagado, perilla blanca). command(recibe True/False) se llama al
    cambiar. El estado visual se sincroniza desde refresh_ui con
    set_switch()."""
    bg = bg or THEME["bg"]
    c = tk.Canvas(parent, width=52, height=30, bg=bg, highlightthickness=0, bd=0)
    c._on = bool(initial)
    c._command = command
    c._t = 1.0 if c._on else 0.0  # 0 = apagado, 1 = encendido (animado)
    c._anim = None

    def _draw():
        t = c._t
        track = _lerp_color("#E9E9EA", THEME["green"], t)
        outline = _lerp_color("#D2D2D7", THEME["green"], t)
        c.delete("all")
        # borde (pildora 1 px mas grande detras)
        c.create_rectangle(15, 0, 37, 30, fill=outline, outline=outline)
        c.create_oval(0, 0, 30, 30, fill=outline, outline=outline)
        c.create_oval(22, 0, 52, 30, fill=outline, outline=outline)
        # interior
        c.create_rectangle(16, 1, 36, 29, fill=track, outline=track)
        c.create_oval(1, 1, 29, 29, fill=track, outline=track)
        c.create_oval(23, 1, 51, 29, fill=track, outline=track)
        kx = 2 + 22 * t
        c.create_oval(kx, 2, kx + 26, 28, fill="white", outline="#D2D2D7")

    def _animate_to(target):
        # Desliza la perilla en ~150 ms (6 pasos de 25 ms).
        if c._anim is not None:
            try:
                c.after_cancel(c._anim)
            except Exception:
                pass
            c._anim = None
        step = (target - c._t) / 6
        if abs(step) < 0.01:
            c._t = target
            _draw()
            return

        def _step(n=0):
            c._t += step
            if n >= 5:
                c._t = target
                c._anim = None
                _draw()
                return
            _draw()
            c._anim = c.after(25, lambda: _step(n + 1))

        _step()

    def _toggle(ev=None):
        c._on = not c._on
        _animate_to(1.0 if c._on else 0.0)
        if c._command:
            c._command(c._on)

    c.bind("<Button-1>", _toggle)
    c._draw = _draw
    c._animate_to = _animate_to
    _draw()
    return c

def set_switch(c, on):
    """Pone el interruptor en el estado dado (lo usa refresh_ui para que
    el dibujo siga al servicio real, no al ultimo clic). Anima el cambio."""
    if c is not None and c._on != bool(on):
        c._on = bool(on)
        c._animate_to(1.0 if c._on else 0.0)


def _dot(status):
    return {"corriendo": ("●", THEME["green"]), "parado": ("●", "#5A7086"),
            "error": ("●", THEME["red"])}.get(status, ("●", "#5A7086"))

def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(s):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# === draw_power ===
def draw_power():
    # Mientras dura la animacion de encendido/apagado, dibuja la animacion.
    if _power_anim.get("active"):
        return
    c = _widgets.get("power_canvas")
    if c is None:
        return
    c.delete("all")
    on = state["power"]
    cx, cy, r = 85, 85, 62
    if on:
        ring = THEME["green"] if _pulse[0] else "#8BE0A4"
        c.create_oval(8, 8, 162, 162, outline=ring, width=3)
        c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                      fill="#E5E5EA", outline="#E5E5EA")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=THEME["green"], outline="#2DB84C", width=2)
        sym = "white"
    else:
        c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                      fill="#E5E5EA", outline="#E5E5EA")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#E9E9EA", outline="#D2D2D7", width=2)
        sym = "#8E8E93"
    c.create_arc(cx - 26, cy - 26, cx + 26, cy + 26, start=300, extent=300,
                 style="arc", outline=sym, width=7)
    c.create_line(cx, cy - 34, cx, cy - 12, fill=sym, width=7, capstyle="round")


_power_anim = {"job": None, "active": False}


def _lerp_color(c1, c2, t):
    """Mezcla dos colores hex segun t (0..1)."""
    a = tuple(int(c1[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t)
                                  for i in range(3))


def _draw_power_frame(t, on):
    """Un fotograma de la animacion de encendido/apagado: el relleno cambia
    de color, el simbolo se dibuja poco a poco, el circulo rebota un poco
    y (al encender) sale una onda que se expande y se desvanece."""
    c = _widgets.get("power_canvas")
    if c is None:
        return
    c.delete("all")
    cx, cy = 85, 85
    # rebote: 62 -> 66 -> 62
    r = 62 + 4 * 4 * t * (1 - t)
    if on:
        fill = _lerp_color("#E9E9EA", THEME["green"], t)
        outline = _lerp_color("#D2D2D7", "#2DB84C", t)
        sym = _lerp_color("#8E8E93", "#FFFFFF", t)
        # onda expansiva que se desvanece (el color se acerca al fondo)
        wave_r = r + 8 + 12 * t
        wave_c = _lerp_color(THEME["green"], THEME["bg"], t)
        c.create_oval(cx - wave_r, cy - wave_r, cx + wave_r, cy + wave_r,
                      outline=wave_c, width=3)
    else:
        fill = _lerp_color(THEME["green"], "#E9E9EA", t)
        outline = _lerp_color("#2DB84C", "#D2D2D7", t)
        sym = _lerp_color("#FFFFFF", "#8E8E93", t)
    # sombra suave debajo del circulo
    c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                  fill="#E5E5EA", outline="#E5E5EA")
    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                  fill=fill, outline=outline, width=2)
    # el simbolo se dibuja poco a poco (al apagar, se desdibuja)
    extent = 300 * t if on else 300 * (1 - t)
    if extent > 0:
        c.create_arc(cx - 26, cy - 26, cx + 26, cy + 26, start=300,
                     extent=extent, style="arc", outline=sym, width=7)
    line_len = 22 * t if on else 22 * (1 - t)
    if line_len > 0:
        c.create_line(cx, cy - 34, cx, cy - 34 + line_len, fill=sym, width=7,
                      capstyle="round")


def _animate_power(on):
    """Anima el boton grande al encender o apagar (~360 ms). Mientras dura,
    draw_power() no redibuja (lo hace la animacion)."""
    if _root is None:
        return
    job = _power_anim.get("job")
    if job is not None:
        try:
            _root.after_cancel(job)
        except Exception:
            pass
    _power_anim["active"] = True
    steps = [0]

    def _step():
        steps[0] += 1
        t = min(1.0, steps[0] / 12.0)
        _draw_power_frame(t, on)
        if t < 1.0:
            _power_anim["job"] = _root.after(30, _step)
        else:
            _power_anim["active"] = False
            _power_anim["job"] = None
            draw_power()

    _step()

def _pulse_loop():
    if _root is None:
        return
    if state["power"]:
        _pulse[0] = 1 - _pulse[0]
        try:
            draw_power()
        except Exception:
            pass
    try:
        _root.after(500, _pulse_loop)
    except Exception:
        pass


def _sync_text():
    _tick_n[0] += 1
    glyphs = ["⟳", "↻", "⟲", "↻"]
    if not TRANSFERS:
        return "○ Sin actividad de sincronización"
    direction, name, size, iso = TRANSFERS[-1]
    try:
        dt = datetime.now().astimezone() - datetime.fromisoformat(iso)
        secs = int(dt.total_seconds())
    except Exception:
        secs = 999
    arrow = "↓ Descargando" if direction == "down" else "↑ Enviando"
    if secs < 10:
        g = glyphs[_tick_n[0] % len(glyphs)]
        return f"{g} {arrow} {name} ({size // 1024} KB)"
    return f"○ Sin actividad · último: {arrow} {name} hace {secs}s"


# === refresh_ui ===
def refresh_ui():
    w = _widgets
    if not w:
        return
    # Puente / Runner / Proxy: punto + pildora de valor + interruptor propio.
    dot, color = _dot(state["bridge"])
    w["bridge_dot"].config(text=dot, fg=color)
    w["bridge_pill"].config(
        text=f"puerto {BRIDGE_PORT}" if state["bridge"] == "corriendo" else "parado")
    set_switch(w.get("bridge_sw"), state["bridge"] == "corriendo")
    dot, color = _dot(state["runner"])
    w["runner_dot"].config(text=dot, fg=color)
    pill = f"{state['tasks_done']} tareas"
    if state["current"]:
        pill += f" · {state['current']}"
    elif state["last_result"]:
        pill += f" · {state['last_result']}"
    w["runner_pill"].config(text=pill)
    set_switch(w.get("runner_sw"), state["runner"] == "corriendo")
    cfg = proxy_config()
    dot, color = ("●", THEME["green"]) if state["proxy_on"] else ("●", "#5A7086")
    w["proxy_dot"].config(text=dot, fg=color)
    if state["proxy_on"] and cfg["host"]:
        w["proxy_pill"].config(text=f"{cfg['host']}:{cfg['port']}")
    elif state["proxy_configured"]:
        w["proxy_pill"].config(text="apagado")
    else:
        w["proxy_pill"].config(text="falta configurar")
    set_switch(w.get("proxy_sw"), state["proxy_on"])
    w["power_label"].config(
        text="Todo encendido" if state["power"] else "Todo apagado",
        fg=THEME["green_text"] if state["power"] else THEME["muted"])
    w["sync_text"].config(text=_sync_text())
    w["admin_text"].config(
        text=f"Administrador: {'sí' if state['admin'] else 'no'}"
        + ("  ·  v" + VERSION))
    if state["update_available"]:
        w["update_label"].config(
            text=f"¡Hay una actualización! v{state['update_available']} disponible.")
        w["update_btn"].config(state="normal")
    elif state["update_checked"]:
        w["update_label"].config(text="Estás en la última versión.")
    if state["sharing"]:
        folder = Path(state.get("share_folder") or "").name
        w["share_status"].config(
            text=f"Compartiendo · sesión {folder} · "
                 f"fotograma {state.get('share_frame', 0)} · "
                 f"último: {state['last_frame'] or '—'}")
        w["share_btn"].config(text="Dejar de compartir pantalla")
    else:
        w["share_status"].config(text="Pantalla no compartida")
        w["share_btn"].config(text="Compartir pantalla")
    # Ajustes (interruptores): la app los sincroniza con el estado real.
    set_switch(w.get("autoupd_sw"), state.get("auto_update", False))
    set_switch(w.get("autostart_sw"), state.get("autostart", False))
    set_switch(w.get("keepawake_sw"), state.get("keep_awake", True))
    set_switch(w.get("mascot_sw"), state["mascot"])
    # No suspender mientras Claude trabaja.
    _apply_keep_awake()
    # Contadores de la barra lateral (Plain) y pagina Tareas, cada 10 s.
    if _tick_n[0] % 10 == 0:
        try:
            w["nav_count_carpetas"].config(text=str(len(load_folders())))
            w["nav_count_skills"].config(text=str(len(list_skills())))
            w["nav_count_apis"].config(text=str(len(load_apis())))
        except Exception:
            pass
        try:
            _refresh_tasks_ui()
        except Exception:
            pass
    # Distintivo de sincronizacion en el icono de la bandeja (como OneDrive).
    if _tray_icon is not None:
        try:
            if state["bridge"] != "corriendo":
                kind = "error"
            elif TRANSFERS:
                try:
                    secs = int((datetime.now().astimezone()
                                - datetime.fromisoformat(TRANSFERS[-1][3])).total_seconds())
                except Exception:
                    secs = 999
                kind = ("sync" if _tick_n[0] % 2 == 0 else "sync2") if secs < 10 else "idle"
            else:
                kind = "idle"
            if kind != _tray_state[0]:
                _tray_state[0] = kind
                img = _tray_image(kind)
                if img is not None:
                    _tray_icon.icon = img
        except Exception:
            pass
    draw_power()
    log_box = w["log"]
    lines = []
    try:
        for _ in range(50):
            lines.append(LOG_Q.get_nowait())
    except queue.Empty:
        pass
    if lines:
        log_box.config(state="normal")
        for line in lines:
            log_box.insert("end", line + "\n")
        log_box.see("end")
        log_box.config(state="disabled")


def _tick():
    try:
        refresh_ui()
    except Exception:
        pass
    # Cada 5 s: recoger APIs que Growi empujo por el puente (desde WhatsApp)
    # y avisar si Claude termino una tarea.
    if _tick_n[0] % 5 == 0:
        try:
            import_api_files()
        except Exception:
            pass
        try:
            _watch_results()
        except Exception:
            pass
    # Auto-update listo: instalarlo solo (sin preguntar) desde el hilo
    # principal, que es el unico que puede reiniciar la app.
    if state.get("auto_update_ready"):
        try:
            _do_auto_update()
        except Exception:
            pass
    if _root is not None:
        try:
            _root.after(1000, _tick)
        except Exception:
            pass

def on_power_click():
    on = set_power(not state["power"])
    log(f"boton grande: {'todo ENCENDIDO' if on else 'todo APAGADO'}")
    try:
        _animate_power(on)
    except Exception:
        pass


def toggle_proxy():
    if state["proxy_on"]:
        ok, msg = set_proxy(False)
        log(f"proxy: {msg}")
    else:
        if not proxy_url():
            messagebox.showinfo(
                "Falta configurar el proxy",
                "Pon el host y la clave del proxy abajo y pulsa \"Guardar\" primero.")
            return
        ok, msg = set_proxy(True)
        log(f"proxy: {msg}")
        if not ok:
            messagebox.showerror("Proxy", msg)


def save_proxy_from_ui():
    w = _widgets
    try:
        port = int(w["px_port"].get().strip() or 18080)
    except ValueError:
        messagebox.showerror("Proxy", "El puerto debe ser un número.")
        return
    cfg = {
        "host": w["px_host"].get().strip(),
        "port": port,
        "user": w["px_user"].get().strip(),
        "password": w["px_pass"].get().strip(),
    }
    save_proxy_config(cfg)
    log("proxy: configuración guardada (solo en este PC)")
    messagebox.showinfo("Proxy", "Configuración guardada. Ya puedes encender el proxy.")


def check_updates_ui():
    def _run():
        remote = check_update_available()
        state["update_checked"] = True
        if remote:
            state["update_available"] = remote
            log(f"actualizaciones: hay una nueva version v{remote}")
        else:
            log("actualizaciones: estás en la última versión")
    threading.Thread(target=_run, daemon=True).start()


def do_update_ui():
    version = state["update_available"]
    if not version:
        return
    if not messagebox.askyesno(
            "Actualizar Growi Bridge",
            f"Se descargará la versión v{version} y la app se reiniciará. ¿Seguir?"):
        return
    if not download_update(version):
        messagebox.showerror("Actualizar", "No se pudo descargar la actualización.")
        return
    log(f"actualizaciones: v{version} descargada, reiniciando...")
    try:
        subprocess.Popen(["cmd", "/c", "actualizar.bat"], cwd=str(APP_DIR))
    except Exception as e:
        messagebox.showerror("Actualizar", f"No se pudo lanzar el actualizador: {e}")
        return
    quit_app()


def open_folder(path):
    try:
        os.startfile(str(path))
    except Exception as e:
        log(f"no se pudo abrir {path}: {e}")


# ---------------------------------------------------------------- mascota
_mascot = {"win": None, "label": None, "sets": {}, "animating": False,
           "drag": None, "frame_idx": 0, "last_tasks": 0, "idle_next": 0}


def _mascot_sets():
    """Carga los tres juegos de animacion (idle / working / wave) de
    mascot/*.png. Cada juego son 16 fotogramas de 256x256, con fondo
    magenta puro (la ventana lo hace transparente)."""
    if _mascot["sets"]:
        return _mascot["sets"]
    sets = {}
    for name in ("idle", "working", "wave"):
        frames = []
        try:
            for p in sorted(MASCOT_DIR.glob(f"{name}-*.png")):
                frames.append(ImageTk.PhotoImage(
                    Image.open(p).resize((MASCOT_SIZE, MASCOT_SIZE), Image.LANCZOS)))
        except Exception:
            frames = []
        sets[name] = frames
    _mascot["sets"] = sets
    return sets


def _mascot_play(name):
    """Reproduce un juego de animacion una vez (saludo, celebracion)."""
    frames = _mascot_sets().get(name) or []
    label = _mascot["label"]
    if not frames or label is None:
        return
    _mascot["animating"] = True
    idx = [0]

    def _step():
        if idx[0] >= len(frames) * 2:
            _mascot["animating"] = False
            return
        try:
            label.config(image=frames[idx[0] % len(frames)])
        except Exception:
            pass
        idx[0] += 1
        try:
            _root.after(90, _step)
        except Exception:
            _mascot["animating"] = False

    _step()


def _mascot_micro():
    """Un respiro corto: 6 fotogramas del juego idle, una sola vez. Es lo
    unico que se mueve cuando nadie toca a la mascota."""
    frames = _mascot_sets().get("idle") or []
    label = _mascot["label"]
    if not frames or label is None or _mascot["animating"]:
        return
    _mascot["animating"] = True
    idx = [0]

    def _step():
        if idx[0] >= 6:
            _mascot["animating"] = False
            try:
                label.config(image=frames[0])
            except Exception:
                pass
            return
        try:
            label.config(image=frames[idx[0] % len(frames)])
        except Exception:
            pass
        idx[0] += 1
        try:
            _root.after(120, _step)
        except Exception:
            _mascot["animating"] = False

    _step()


def _mascot_loop():
    """La mascota descansa QUIETA casi todo el tiempo: solo se mueve un
    poco cada cierto rato (un respiro corto), y anima de verdad cuando algo
    pasa (clic, arrastre, tarea terminada) o mientras Claude trabaja."""
    win = _mascot["win"]
    if win is None:
        return
    if not _mascot["animating"]:
        if state["tasks_done"] > _mascot["last_tasks"]:
            _mascot["last_tasks"] = state["tasks_done"]
            _mascot_play("wave")
        elif state.get("current"):
            # Trabajando: el loop de tecleo, continuo (tiene sentido).
            frames = _mascot_sets().get("working") or []
            if frames:
                _mascot["frame_idx"] = (_mascot["frame_idx"] + 1) % len(frames)
                try:
                    _mascot["label"].config(image=frames[_mascot["frame_idx"]])
                except Exception:
                    pass
        else:
            # Descansando: quieto, con un respiro corto cada 8-15 s.
            now = time.time()
            if now >= _mascot.get("idle_next", 0):
                _mascot["idle_next"] = now + random.uniform(8, 15)
                _mascot_micro()
            else:
                try:
                    frames = _mascot_sets().get("idle") or []
                    if frames:
                        _mascot["label"].config(image=frames[0])
                except Exception:
                    pass
    try:
        _root.after(120, _mascot_loop)
    except Exception:
        pass


def _mascot_pos():
    sw = _root.winfo_screenwidth()
    sh = _root.winfo_screenheight()
    return sw - (MASCOT_SIZE + 20), sh - (MASCOT_SIZE + 20)



def show_mascot():
    if _root is None or _mascot["win"] is not None:
        return
    if not TRAY_OK or not PHOTO.is_file():
        log("mascota: falta la foto (growi.png)")
        return
    win = tk.Toplevel(_root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    try:
        win.attributes("-transparentcolor", MASCOT_MAGIC)
    except Exception:
        pass
    x, y = _mascot_pos()
    win.geometry(f"{MASCOT_SIZE}x{MASCOT_SIZE}+{x}+{y}")
    try:
        first = MASCOT_DIR / "idle-01.png"
        img_path = first if first.is_file() else PHOTO
        img = Image.open(img_path).resize((MASCOT_SIZE, MASCOT_SIZE), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
    except Exception:
        win.destroy()
        return
    label = tk.Label(win, image=photo, bg=MASCOT_MAGIC, bd=0)
    label.image = photo
    label.pack()
    win._photo = photo
    _mascot["win"] = win
    _mascot["label"] = label
    _mascot["idle_next"] = time.time() + 5
    # Arrastrar archivos sobre la mascota: los copia al Inbox (tkinterdnd2).
    if DND_OK:
        try:
            label.drop_target_register(DND_FILES)
            label.dnd_bind("<<DropEnter>>", _mascot_drag_enter)
            label.dnd_bind("<<DropPosition>>", _mascot_drag_position)
            label.dnd_bind("<<DropLeave>>", _mascot_drag_leave)
            label.dnd_bind("<<Drop>>", _mascot_drop)
        except Exception as e:
            log(f"mascota: no se pudo activar el arrastre ({e})")

    def _press(e):
        _mascot["drag"] = (e.x_root, e.y_root, win.winfo_x(), win.winfo_y(), False)

    def _move(e):
        d = _mascot["drag"]
        if not d:
            return
        dx = e.x_root - d[0]
        dy = e.y_root - d[1]
        if abs(dx) + abs(dy) > 5:
            _mascot["drag"] = (d[0], d[1], d[2], d[3], True)
            win.geometry(f"192x192+{d[2] + dx}+{d[3] + dy}")

    def _release(e):
        d = _mascot["drag"]
        _mascot["drag"] = None
        if d and not d[4]:
            on_mascot_click()

    label.bind("<ButtonPress-1>", _press)
    label.bind("<B1-Motion>", _move)
    label.bind("<ButtonRelease-1>", _release)
    log("mascota: Growi está en la esquina inferior derecha")
    _mascot["last_tasks"] = state["tasks_done"]
    _root.after(120, _mascot_loop)
    _root.after(700, lambda: _mascot_play("wave"))  # saludo al arrancar


def on_mascot_click():
    win = _mascot["win"]
    label = _mascot["label"]
    if win is None or label is None or _mascot["animating"]:
        return
    _mascot_play("wave")
    open_prompt_box()

def _big_file_dialog(name, size_mb):
    """Pregunta si de verdad se quiere copiar un archivo grande (>200 MB).
    Devuelve True si se copia, False si se cancela. El boton "No mostrar
    durante 30 min" silencia el aviso media hora (se guarda en settings)."""
    result = {"ok": False}
    box = tk.Toplevel(_root)
    box.title("Archivo grande")
    box.attributes("-topmost", True)
    box.configure(bg=THEME["bg"])
    x = max(0, _root.winfo_x() + 100)
    y = max(0, _root.winfo_y() + 100)
    box.geometry(f"360x190+{x}+{y}")
    tk.Label(box, text=f"'{name}' pesa {size_mb:.0f} MB.",
             font=(FONT, 11, "bold"), bg=THEME["bg"], fg=THEME["text"],
             wraplength=320, justify="left").pack(padx=16, pady=(14, 2))
    tk.Label(box, text="Copiarlo a Growi Bridge puede tardar un rato en "
             "sincronizarse. ¿Seguro que quieres copiarlo?",
             font=(FONT, 10), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=320, justify="left").pack(padx=16, pady=(0, 10))
    row = tk.Frame(box, bg=THEME["bg"])
    row.pack(pady=4)
    tk.Button(row, text="Sí, copiar", bg=THEME["blue"], fg="white",
              borderwidth=0, font=(FONT, 10, "bold"),
              command=lambda: (result.__setitem__("ok", True), box.destroy())
              ).pack(side="left", padx=4)
    tk.Button(row, text="Cancelar", bg="#E8E8ED", fg=THEME["text"],
              borderwidth=0, font=(FONT, 10),
              command=box.destroy).pack(side="left", padx=4)
    tk.Button(box, text="No mostrar durante 30 min", bg=THEME["bg"],
              fg=THEME["muted"], borderwidth=0, font=(FONT, 9),
              command=lambda: (_snooze_big_file_warn(), box.destroy())
              ).pack(pady=4)
    box.grab_set()
    _root.wait_window(box)
    return result["ok"]


def _snooze_big_file_warn():
    s = load_settings()
    s["big_file_warn_snooze_until"] = time.time() + 30 * 60
    save_settings(s)
    log("mascota: aviso de archivo grande silenciado 30 min")


def _big_file_warn_snoozed():
    try:
        return time.time() < float(load_settings().get(
            "big_file_warn_snooze_until", 0))
    except (TypeError, ValueError):
        return False


def _copy_dropped_file(path):
    """Copia un archivo soltado sobre la mascota al Inbox del puente
    (llega a Growi por la sincronizacion). En un hilo para no congelar
    la ventana."""
    def _run():
        try:
            size = os.path.getsize(path)
            name = os.path.basename(path)
            dest = INBOX / name
            i = 1
            while dest.exists():
                stem, ext = os.path.splitext(name)
                dest = INBOX / f"{stem} ({i}){ext}"
                i += 1
            shutil.copy2(path, dest)
            log(f"mascota: '{dest.name}' copiado al Inbox "
                f"({size // (1024 * 1024)} MB) — llega a Growi por el puente")
            try:
                _root.after(0, lambda: _mascot_play("wave"))
            except Exception:
                pass
        except Exception as e:
            log(f"mascota: no se pudo copiar '{path}' ({e})")

    threading.Thread(target=_run, daemon=True).start()


def _mascot_drop(event):
    """Archivo(s) soltados sobre la mascota: Growi levanta la mano para
    recibirlos y se copian al Inbox. Mas de 200 MB: aviso con opcion de
    silenciarlo 30 min."""
    try:
        _mascot_play("wave")
    except Exception:
        pass
    data = (event.data or "").strip()
    if not data:
        return
    # tkinterdnd2 entrega las rutas entre llaves cuando tienen espacios.
    paths = []
    for part in re.findall(r"\{([^}]+)\}|(\S+)", data):
        p = part[0] or part[1]
        if p:
            paths.append(p)
    for p in paths:
        try:
            if not os.path.isfile(p):
                continue
            size = os.path.getsize(p)
            name = os.path.basename(p)
            if size > 200 * 1024 * 1024 and not _big_file_warn_snoozed():
                if not _big_file_dialog(name, size / (1024 * 1024)):
                    log(f"mascota: copia de '{name}' cancelada por el usuario")
                    continue
            _copy_dropped_file(p)
        except Exception as e:
            log(f"mascota: no se pudo procesar '{p}' ({e})")


def _mascot_drag_enter(event):
    """Un archivo entra sobre la mascota: Growi levanta la mano."""
    try:
        _mascot_play("wave")
    except Exception:
        pass


def _mascot_drag_position(event):
    """Mientras el archivo se mueve sobre la mascota, Growi se inclina un
    poco hacia el cursor, como buscandolo."""
    win = _mascot["win"]
    if win is None:
        return
    try:
        cx = win.winfo_x() + win.winfo_width() // 2
        cy = win.winfo_y() + win.winfo_height() // 2
        dx = max(-8, min(8, (event.x_root - cx) // 12))
        dy = max(-8, min(8, (event.y_root - cy) // 12))
        base_x, base_y = _mascot_pos()
        win.geometry(f"{MASCOT_SIZE}x{MASCOT_SIZE}+{base_x + dx}+{base_y + dy}")
    except Exception:
        pass


def _mascot_drag_leave(event):
    """El archivo se aleja: Growi vuelve a su sitio."""
    win = _mascot["win"]
    if win is None:
        return
    try:
        x, y = _mascot_pos()
        win.geometry(f"{MASCOT_SIZE}x{MASCOT_SIZE}+{x}+{y}")
    except Exception:
        pass



def open_prompt_box():
    """Cajita para escribirle a Growi (estilo Mac: avatar, campo con borde,
    boton de acento). El mensaje llega a Growi por el puente."""
    win = _mascot["win"]
    if win is None:
        return
    box = tk.Toplevel(_root)
    box.title("Escríbeme")
    box.attributes("-topmost", True)
    box.configure(bg=THEME["bg"])
    box.resizable(False, False)
    x = max(0, win.winfo_x() - 220)
    y = max(0, win.winfo_y() - 190)
    box.geometry(f"380x230+{x}+{y}")
    # Cabecera: avatar + saludo.
    head = tk.Frame(box, bg=THEME["bg"])
    head.pack(fill="x", padx=18, pady=(16, 4))
    try:
        img = Image.open(PHOTO).resize((40, 40), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        tk.Label(head, image=photo, bg=THEME["bg"]).pack(side="left")
        head.image = photo
    except Exception:
        pass
    tk.Label(head, text="¡Hola! ¿Qué necesitas?", font=(FONT, 13, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(side="left", padx=(10, 0))
    # Campo con borde (como los campos de la app).
    field = tk.Frame(box, bg=THEME["line"], padx=1, pady=1)
    field.pack(fill="x", padx=18, pady=10)
    entry = tk.Entry(field, font=(FONT, 11), bg="#FFFFFF", fg=THEME["text"],
                     insertbackground=THEME["text"], borderwidth=0,
                     highlightthickness=0)
    entry.pack(fill="x", ipady=8, padx=8)
    entry.focus_set()
    status = tk.Label(box, text="", font=(FONT, 9), fg=THEME["green_text"],
                      bg=THEME["bg"])
    status.pack()

    def _send(_e=None):
        text = entry.get().strip()
        if not text:
            return
        MESSAGES.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt"
        (MESSAGES / name).write_text(text, encoding="utf-8")
        log(f"mascota: mensaje enviado a Growi ({name})")
        entry.delete(0, "end")
        status.config(text="✓ Enviado, te respondo en el chat")

    entry.bind("<Return>", _send)
    row = tk.Frame(box, bg=THEME["bg"])
    row.pack(pady=(6, 4))
    ttk.Button(row, text="Enviar a Growi", style="Accent.TButton",
               command=_send).pack(side="left", padx=4)
    ttk.Button(row, text="Cerrar", command=box.destroy).pack(side="left", padx=4)
    tk.Label(box, text="Llega a Growi por el puente y te responde en el chat.",
             font=(FONT, 9), fg=THEME["muted"], bg=THEME["bg"]).pack(pady=(2, 10))


def hide_mascot():
    win = _mascot["win"]
    if win is not None:
        try:
            win.destroy()
        except Exception:
            pass
    _mascot["win"] = None
    _mascot["label"] = None
    log("mascota: oculta")


def toggle_mascot():
    if _mascot["win"] is None:
        show_mascot()
        state["mascot"] = True
    else:
        hide_mascot()
        state["mascot"] = False
    s = load_settings()
    s["mascot"] = state["mascot"]
    save_settings(s)


# ---------------------------------------------------------------- pestanas
def refresh_folders_ui():
    lb = _widgets.get("folders_list")
    if lb is None:
        return
    lb.delete(0, "end")
    for r in load_folders():
        lb.insert("end", r)


def add_folder_ui():
    path = filedialog.askdirectory(title="Elegir carpeta que Claude Code puede ver")
    if not path:
        return
    roots = load_folders()
    if path not in roots:
        roots.append(path)
        save_folders(roots)
        log(f"carpetas: añadida {path}")
    refresh_folders_ui()


def remove_folder_ui():
    lb = _widgets.get("folders_list")
    if lb is None:
        return
    sel = lb.curselection()
    if not sel:
        return
    roots = load_folders()
    removed = roots.pop(sel[0])
    save_folders(roots)
    log(f"carpetas: quitada {removed}")
    refresh_folders_ui()


def reset_folders_ui():
    save_folders(default_roots())
    log("carpetas: restablecidas a los valores por defecto")
    refresh_folders_ui()


def refresh_skills_ui():
    tree = _widgets.get("skills_tree")
    if tree is None:
        return
    for item in tree.get_children():
        tree.delete(item)
    skills = list_skills()
    for name, desc, _path in skills:
        tree.insert("", "end", values=(name, desc))
    _widgets["skills_count"].config(text=f"{len(skills)} skills instaladas")

def refresh_apis_ui():
    tree = _widgets.get("apis_tree")
    if tree is None:
        return
    for item in tree.get_children():
        tree.delete(item)
    for a in load_apis():
        tree.insert("", "end", values=(a.get("name", ""), mask_key(a.get("key", ""))))


def add_api_ui():
    name = _widgets["api_name"].get().strip()
    key = _widgets["api_key"].get().strip()
    if not name or not key:
        messagebox.showwarning("APIs", "Pon el nombre y la clave de la API.")
        return
    apis = load_apis()
    apis = [a for a in apis if a.get("name") != name]
    apis.append({"name": name, "key": key})
    save_apis(apis)
    _widgets["api_name"].delete(0, "end")
    _widgets["api_key"].delete(0, "end")
    log(f"APIs: '{name}' guardada (solo en este PC)")
    refresh_apis_ui()


def remove_api_ui():
    tree = _widgets.get("apis_tree")
    if tree is None:
        return
    sel = tree.selection()
    if not sel:
        return
    name = tree.item(sel[0], "values")[0]
    apis = [a for a in load_apis() if a.get("name") != name]
    save_apis(apis)
    log(f"APIs: '{name}' quitada")
    refresh_apis_ui()


def add_api_whatsapp():
    """Abre WhatsApp Web en Chrome: le escribes a Growi la API y la clave,
    y Growi la empuja al PC en segundos por el puente (inbox/apis/)."""
    import webbrowser
    try:
        webbrowser.open("https://web.whatsapp.com")
    except Exception as e:
        log(f"APIs: no se pudo abrir el navegador ({e})")
        return
    log("APIs: abre WhatsApp Web y dile a Growi la API que quieres añadir; "
        "llega al PC en segundos por el puente")

def show_window():
    if _root is None:
        return
    try:
        _root.deiconify()
        _root.lift()
        _root.focus_force()
    except Exception:
        pass


def hide_to_tray():
    """Minimiza la ventana (la mascota sigue visible en su esquina)."""
    if _root is None:
        return
    try:
        _root.iconify()
    except Exception:
        pass
    log("ventana minimizada (el programa sigue corriendo)")
    if _tray_icon is not None:
        try:
            _tray_icon.notify("Growi Bridge sigue corriendo.", "Growi Bridge")
        except Exception:
            pass


def quit_app():
    global _tray_icon
    log("saliendo de Growi Bridge...")
    try:
        stop_sharing()
    except Exception:
        pass
    try:
        hide_mascot()
    except Exception:
        pass
    try:
        stop_runner()
    except Exception:
        pass
    try:
        stop_bridge()
    except Exception:
        pass
    if _tray_icon is not None:
        try:
            _tray_icon.stop()
        except Exception:
            pass
        _tray_icon = None
    if _root is not None:
        try:
            _root.quit()
            _root.destroy()
        except Exception:
            pass


def build_tray():
    global _tray_icon
    if not TRAY_OK:
        log("bandeja: pystray no instalado (pip install pystray pillow); sin icono en la bandeja")
        return None
    try:
        tray_img = TRAY_ICON if TRAY_ICON.is_file() else PHOTO
        image = Image.open(tray_img) if tray_img.is_file() else Image.new("RGBA", (64, 64), (5, 32, 72, 255))
    except Exception:
        image = Image.new("RGBA", (64, 64), (5, 32, 72, 255))
    menu = pystray.Menu(
        pystray.MenuItem(lambda item: _sync_text(), lambda: show_window(),
                         enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Mostrar ventana", lambda: show_window(), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            lambda item: "Puente: parar" if state["bridge"] == "corriendo" else "Puente: iniciar",
            lambda: set_power(False) if state["bridge"] == "corriendo" else start_bridge()),
        pystray.MenuItem(
            lambda item: "Runner: parar" if state["runner"] == "corriendo" else "Runner: iniciar",
            lambda: stop_runner() if state["runner"] == "corriendo" else start_runner()),
        pystray.MenuItem("Proxy", lambda: toggle_proxy(),
                         checked=lambda item: state["proxy_on"]),
        pystray.MenuItem("Mascota", lambda: toggle_mascot(),
                         checked=lambda item: state["mascot"]),
        pystray.MenuItem("Compartir pantalla",
                         lambda: stop_sharing() if state["sharing"] else start_sharing(),
                         checked=lambda item: state["sharing"]),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", lambda: quit_app()),
    )
    icon = pystray.Icon("GrowiBridge", image, "Growi Bridge", menu)
    try:
        icon.run_detached()
    except AttributeError:
        threading.Thread(target=icon.run, daemon=True).start()
    return icon


# === build_gui ===
# === build_gui (v2.3 "Mac": barra lateral + titulo grande + contenido con scroll) ===
def _scrollable(parent):
    """Un area con scroll vertical (nada queda fuera de la ventana, aunque
    la ventana sea pequeña). Devuelve el Frame interior donde se pone el
    contenido."""
    canvas = tk.Canvas(parent, bg=THEME["bg"], highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=THEME["bg"])
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner(_e=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas(e):
        canvas.itemconfig(win_id, width=e.width)

    inner.bind("<Configure>", _on_inner)
    canvas.bind("<Configure>", _on_canvas)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _on_wheel(e):
        if canvas.winfo_ismapped():
            canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    canvas.bind_all("<MouseWheel>", _on_wheel)
    return inner


def _lerp_color(c1, c2, t):
    """Mezcla dos colores hex (#RRGGBB) segun t (0..1)."""
    def _ch(c, i):
        return int(c[i:i + 2], 16)
    r = round(_ch(c1, 1) + (_ch(c2, 1) - _ch(c1, 1)) * t)
    g = round(_ch(c1, 3) + (_ch(c2, 3) - _ch(c1, 3)) * t)
    b = round(_ch(c1, 5) + (_ch(c2, 5) - _ch(c1, 5)) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _apply_keep_awake():
    """No suspender: mientras Claude corre una tarea, le dice a Windows
    que no duerma el equipo (ES_SYSTEM_REQUIRED). Al quedar libre, lo
    suelta. Solo si el ajuste esta activado."""
    try:
        import ctypes
        want = bool(state.get("current")) and bool(state.get("keep_awake", True))
        if want == _keep_awake_applied[0]:
            return
        _keep_awake_applied[0] = want
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        if want:
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
            log("PC: no se suspendera mientras Claude trabaja")
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def _notify_task(title, msg):
    """Aviso de Windows cuando Claude termina una tarea (via pystray)."""
    try:
        if _tray_icon is not None:
            _tray_icon.notify(msg, title)
    except Exception:
        pass


def _watch_results():
    """Cada 5 s revisa si llego un resultado nuevo del runner: avisa con
    un toast y hace celebrar a la mascota. Al arrancar marca los que ya
    existen como vistos (no avisa de lo viejo)."""
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        current = {f.name for f in RESULTS.glob("*.result.json")}
        if not _seen_results:
            _seen_results.update(current)
            return
        new = current - _seen_results
        _seen_results.update(current)
        for name in sorted(new):
            try:
                d = json.loads((RESULTS / name).read_text(encoding="utf-8"))
            except Exception:
                continue
            status = d.get("status", "?")
            cost = d.get("cost_usd")
            dur = d.get("duration_s")
            cost_txt = f" · ${cost:.2f}" if isinstance(cost, (int, float)) else ""
            dur_txt = f" · {dur}s" if dur is not None else ""
            _notify_task("Growi Bridge",
                         f"Claude terminó: {d.get('id', name)} · {status}{dur_txt}{cost_txt}")
            log(f"aviso: tarea {d.get('id')} terminada ({status}{dur_txt}{cost_txt})")
            try:
                _mascot_play("wave")
            except Exception:
                pass
    except Exception:
        pass


def _dpi_awareness():
    """Nítido en Windows con escalado de pantalla >100%: sin esto, Windows
    reescala la ventana entera como un mapa de bits y todo se ve borroso
    (iconos pixelados, texto suave). Se declara antes de crear la ventana."""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # por monitor v2
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass


def _dpi_scaling(root):
    """Ajusta el escalado de tkinter al DPI real, para que con DPI activo
    la ventana mantenga su tamaño físico (si no, se vería más pequeña)."""
    try:
        import ctypes
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi and dpi != 96:
            root.tk.call("tk", "scaling", dpi / 72)
            log(f"DPI del sistema: {dpi} ({round(dpi / 96 * 100)}% de escalado)")
    except Exception:
        pass


_PALETTE_CMDS = []
_tasks_fp = [None]
_ASK_ENGINES = {
    "Claude Sonnet": "sonnet", "Claude Opus": "opus", "Claude Haiku": "haiku",
    "Local Hermes 3 (Ollama · $0)": "ollama:" + OLLAMA_MODEL,
}


def toggle_window():
    """Muestra u oculta la ventana (la usa el atajo global Ctrl+Alt+G)."""
    if _root is None:
        return
    try:
        if _root.state() == "iconic" or not _root.winfo_viewable():
            show_window()
        else:
            hide_to_tray()
    except Exception:
        show_window()


def _open_palette():
    """Paleta de comandos estilo Raycast (Ctrl+K): escribe la accion y
    se ejecuta al instante, sin recorrer menus. Filtra mientras escribes."""
    if _root is None or not _PALETTE_CMDS:
        return
    pal = tk.Toplevel(_root)
    pal.title("Buscar acciones")
    pal.attributes("-topmost", True)
    pal.configure(bg=THEME["bg"])
    pal.resizable(False, False)
    try:
        x = _root.winfo_x() + max(0, (_root.winfo_width() - 520) // 2)
        y = _root.winfo_y() + 80
        pal.geometry(f"520x320+{x}+{y}")
    except Exception:
        pal.geometry("520x320")
    entry = tk.Entry(pal, font=(FONT, 12), bg="#FFFFFF", fg=THEME["text"],
                     insertbackground=THEME["text"], borderwidth=0,
                     highlightthickness=0)
    entry.pack(fill="x", padx=12, pady=(12, 6), ipady=8)
    entry.focus_set()
    lb = tk.Listbox(pal, font=(FONT, 11), bg="#FFFFFF", fg=THEME["text"],
                    selectbackground=THEME["blue"], selectforeground="white",
                    borderwidth=0, highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    cur = [list(_PALETTE_CMDS)]

    def _fill(items):
        cur[0] = items
        lb.delete(0, "end")
        for label, _kw, _fn in items:
            lb.insert("end", label)
        if items:
            lb.selection_set(0)

    def _on_type(_e=None):
        q = entry.get().strip().lower()
        if not q:
            _fill(list(_PALETTE_CMDS))
        else:
            _fill([c for c in _PALETTE_CMDS
                   if q in c[0].lower() or q in c[1].lower()])

    def _run(_e=None):
        sel = lb.curselection()
        if not sel or not cur[0]:
            return
        _lab, _kw, fn = cur[0][sel[0]]
        pal.destroy()
        try:
            fn()
        except Exception as e:
            log(f"paleta: no se pudo ejecutar ({e})")

    entry.bind("<KeyRelease>", _on_type)
    entry.bind("<Return>", _run)
    lb.bind("<Double-Button-1>", _run)
    pal.bind("<Escape>", lambda _e: pal.destroy())
    _fill(list(_PALETTE_CMDS))


def _send_ask():
    """Manda la tarea escrita en la pagina Tareas al runner (Claude u
    Ollama local, segun el motor elegido)."""
    w = _widgets
    text = w.get("ask_text")
    if text is None:
        return
    prompt = text.get("1.0", "end").strip()
    if not prompt:
        return
    engine = "Claude Sonnet"
    try:
        engine = w["ask_engine"].get() or engine
    except Exception:
        pass
    model = _ASK_ENGINES.get(engine, "sonnet")
    TASKS.mkdir(parents=True, exist_ok=True)
    base = "t-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = base
    i = 1
    while (TASKS / f"{task_id}.task.json").exists():
        task_id = f"{base}-{i}"
        i += 1
    data = {"id": task_id, "prompt": prompt, "cwd": str(INBOX), "model": model,
            "timeout_min": 30, "allowed_tools": "Read,Write,Edit,Bash",
            "permission_mode": "acceptEdits"}
    (TASKS / f"{task_id}.task.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"tareas: '{task_id}' enviado al runner ({engine})")
    text.delete("1.0", "end")
    if w.get("ask_status") is not None:
        w["ask_status"].config(text=f"✓ Enviado al runner ({engine})")


def _refresh_tasks_ui():
    """Actualiza la pagina Tareas: historial desde los result.json del
    runner, con costo del dia y total. Solo re-dibuja si algo cambio."""
    w = _widgets
    tree = w.get("tasks_tree")
    if tree is None:
        return
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        files = sorted(RESULTS.glob("*.result.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        fp = (len(files), max((f.stat().st_mtime for f in files), default=0))
        if fp == _tasks_fp[0]:
            return
        _tasks_fp[0] = fp
        rows = []
        total = 0.0
        today_total = 0.0
        today = datetime.now().astimezone().date().isoformat()
        for f in files:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            cost = d.get("cost_usd") or 0
            if isinstance(cost, (int, float)):
                total += cost
                if (d.get("finished_at") or "")[:10] == today:
                    today_total += cost
            dur = d.get("duration_s")
            rows.append((d.get("id", f.stem), d.get("status", "?"),
                         f"{dur}s" if dur is not None else "—",
                         f"${cost:.2f}" if isinstance(cost, (int, float)) else "—"))
        for item in tree.get_children():
            tree.delete(item)
        for r in rows[:30]:
            tree.insert("", "end", values=r)
        if w.get("tasks_summary") is not None:
            w["tasks_summary"].config(
                text=f"Hoy: ${today_total:.2f}  ·  Total: ${total:.2f}  ·  {len(rows)} tareas")
        if w.get("nav_count_tareas") is not None:
            w["nav_count_tareas"].config(text=str(len(rows)))
    except Exception:
        pass


def build_gui():
    global _root
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        state["dnd"] = True
    except ImportError:
        root = tk.Tk()
        state["dnd"] = False
    _root = root
    _dpi_scaling(root)
    root.title("Growi Bridge")
    root.geometry("940x680")
    root.minsize(820, 560)
    root.configure(bg=THEME["bg"])
    root.protocol("WM_DELETE_WINDOW", hide_to_tray)
    cfg = proxy_config()
    try:
        if ICO.is_file():
            root.iconbitmap(str(ICO))
    except Exception:
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TButton", background="#FFFFFF", foreground=THEME["text"],
                    borderwidth=1, relief="solid",
                    padding=(12, 6), font=(FONT, 10))
    style.map("TButton", background=[("active", "#F5F5F7")])
    style.configure("Accent.TButton", background=THEME["blue"], foreground="white",
                    borderwidth=0, padding=(12, 6), font=(FONT, 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#0A6CFF")])
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=THEME["text"],
                    borderwidth=1, relief="solid", insertcolor=THEME["text"])
    try:  # bordercolor no existe en todos los Tk; si falla, se sigue sin el
        style.configure("TButton", bordercolor="#D2D2D7")
        style.configure("TEntry", bordercolor="#D2D2D7")
    except Exception:
        pass
    style.configure("TCombobox", fieldbackground="#FFFFFF", foreground=THEME["text"])
    style.configure("Treeview", background="#FFFFFF", foreground=THEME["text"],
                    fieldbackground="#FFFFFF", borderwidth=0, font=(FONT, 10))
    style.configure("Treeview.Heading", background="#F5F5F7",
                    foreground=THEME["muted"], font=(FONT, 10, "bold"))
    style.configure("TCheckbutton", background=THEME["bg"], foreground=THEME["text"],
                    font=(FONT, 10))

    # ---------------- barra lateral (Superlist / Plain)
    sidebar = tk.Frame(root, bg=THEME["sidebar"], width=220)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    head = tk.Frame(sidebar, bg=THEME["sidebar"])
    head.pack(fill="x", padx=16, pady=(16, 8))
    photo = None
    if TRAY_OK and HEADER_PHOTO.is_file():
        try:
            img = Image.open(HEADER_PHOTO).resize((64, 64), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            tk.Label(head, image=photo, bg=THEME["sidebar"]).pack(anchor="w")
            head.image = photo
            root.iconphoto(True, photo)
        except Exception:
            pass
    tk.Label(head, text="Growi Bridge", font=(FONT, 15, "bold"),
             bg=THEME["sidebar"], fg=THEME["text"]).pack(anchor="w", pady=(8, 0))
    _widgets["admin_text"] = tk.Label(head, text="", font=(FONT, 9),
                                      bg=THEME["sidebar"], fg=THEME["muted"])
    _widgets["admin_text"].pack(anchor="w")

    # ---------------- contenido (una pagina por seccion, con scroll)
    content = tk.Frame(root, bg=THEME["bg"])
    content.pack(side="right", fill="both", expand=True)
    pages = {}
    for name in ("estado", "carpetas", "skills", "pantalla", "apis",
                 "tareas", "ajustes", "registro"):
        holder = tk.Frame(content, bg=THEME["bg"])
        pages[name] = _scrollable(holder)
        holder._inner = pages[name]
        pages[name + "_holder"] = holder

    def _show_page(name):
        for n, holder in ((k, v) for k, v in pages.items() if k.endswith("_holder")):
            holder.pack_forget()
        pages[name + "_holder"].pack(fill="both", expand=True)
        for n, btn in _nav_btns.items():
            if n == name:
                btn.config(bg="#E8E8ED", fg=THEME["text"])
                btn._bar.config(bg=THEME["blue"])
            else:
                btn.config(bg=THEME["sidebar"], fg=THEME["text"])
                btn._bar.config(bg=THEME["sidebar"])

    _nav_btns = {}
    nav = tk.Frame(sidebar, bg=THEME["sidebar"])
    nav.pack(fill="x", padx=8, pady=8)
    for name, label in (("estado", "Estado"), ("carpetas", "Carpetas"),
                        ("skills", "Skills"), ("pantalla", "Pantalla"),
                        ("apis", "APIs"), ("tareas", "Tareas"),
                        ("ajustes", "Ajustes"), ("registro", "Registro")):
        row = tk.Frame(nav, bg=THEME["sidebar"])
        row.pack(fill="x", pady=1)
        bar = tk.Frame(row, bg=THEME["sidebar"], width=3)
        bar.pack(side="left", fill="y")
        btn = tk.Button(row, text="  " + label, font=(FONT, 11),
                        bg=THEME["sidebar"], fg=THEME["text"], bd=0,
                        activebackground="#E8E8ED", anchor="w",
                        command=lambda n=name: _show_page(n))
        btn.pack(side="left", fill="x", expand=True, ipady=6)
        btn._bar = bar
        _nav_btns[name] = btn
        if name in ("carpetas", "skills", "apis", "tareas"):
            cnt = tk.Label(row, text="", font=(FONT, 10),
                           bg=THEME["sidebar"], fg=THEME["muted"])
            cnt.pack(side="right", padx=(0, 10))
            _widgets[f"nav_count_{name}"] = cnt

    tk.Label(sidebar, text="Ctrl+K  ·  buscar acciones", font=(FONT, 9),
             bg=THEME["sidebar"], fg=THEME["muted"]).pack(anchor="w", padx=18, pady=(0, 4))

    # Pie de la barra lateral: la mascota siempre a la vista (Superlist /
    # Plain ponen el avatar abajo). El interruptor enciende o apaga a Growi.
    foot = tk.Frame(sidebar, bg=THEME["sidebar"])
    foot.pack(side="bottom", fill="x", padx=16, pady=14)
    tk.Frame(foot, bg=THEME["line"], height=1).pack(fill="x", pady=(0, 10))
    frow = tk.Frame(foot, bg=THEME["sidebar"])
    frow.pack(fill="x")
    mini = None
    if TRAY_OK and PHOTO.is_file():
        try:
            img = Image.open(PHOTO).resize((40, 40), Image.LANCZOS)
            mini = ImageTk.PhotoImage(img)
            tk.Label(frow, image=mini, bg=THEME["sidebar"]).pack(side="left")
            frow.image = mini
        except Exception:
            pass
    tk.Label(frow, text="Mascota", font=(FONT, 11, "bold"),
             bg=THEME["sidebar"], fg=THEME["text"]).pack(side="left", padx=(8, 0))

    def _sw_mascot_sidebar(on):
        if on and _mascot["win"] is None:
            show_mascot()
            state["mascot"] = True
        elif not on and _mascot["win"] is not None:
            hide_mascot()
            state["mascot"] = False
        s = load_settings()
        s["mascot"] = state["mascot"]
        save_settings(s)

    _widgets["mascot_sw"] = make_switch(frow, state["mascot"],
                                        _sw_mascot_sidebar, bg=THEME["sidebar"])
    _widgets["mascot_sw"].pack(side="right")

    # ================= pagina Estado
    tab = pages["estado"]
    tk.Label(tab, text="Estado", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 4))
    tk.Label(tab, text="Puente · Runner · Proxy · Pantalla · Mascota",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"]).pack(
        anchor="w", padx=20, pady=(0, 10))

    power = tk.Frame(tab, bg=THEME["bg"])
    power.pack(pady=4)
    canvas = tk.Canvas(power, width=170, height=170, bg=THEME["bg"],
                       highlightthickness=0)
    canvas.pack()
    canvas.bind("<Button-1>", lambda e: on_power_click())
    _widgets["power_canvas"] = canvas
    _widgets["power_label"] = tk.Label(power, text="Todo apagado",
                                       font=(FONT, 13, "bold"),
                                       bg=THEME["bg"], fg=THEME["muted"])
    _widgets["power_label"].pack()

    status = tk.Frame(tab, bg=THEME["card"])
    status.pack(fill="x", padx=20, pady=8)
    tk.Label(status, text="ESTADO", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))

    def _service_row(key, label, on_switch):
        row = tk.Frame(status, bg=THEME["card"])
        row.pack(fill="x", padx=16, pady=5)
        dot = tk.Label(row, text="●", font=(FONT, 13), bg=THEME["card"])
        dot.pack(side="left", padx=(0, 8))
        tk.Label(row, text=label, font=(FONT, 10, "bold"),
                 bg=THEME["card"], fg=THEME["text"]).pack(side="left")
        pill = tk.Label(row, text="", font=(FONT, 9), bg="#E8E8ED",
                        fg=THEME["text"], padx=8, pady=2)
        pill.pack(side="left", padx=(10, 0))
        sw = make_switch(row, False, on_switch, bg=THEME["card"])
        sw.pack(side="right")
        _widgets[f"{key}_dot"] = dot
        _widgets[f"{key}_pill"] = pill
        _widgets[f"{key}_sw"] = sw
        sep = tk.Frame(status, bg=THEME["line"], height=1)
        sep.pack(fill="x", padx=16)

    def _sw_bridge(on):
        if on:
            start_bridge()
        else:
            stop_bridge()

    def _sw_runner(on):
        if on:
            start_runner()
        else:
            stop_runner()

    def _sw_proxy(on):
        if on:
            toggle_proxy()
        else:
            set_proxy(False)

    _service_row("bridge", "Puente", _sw_bridge)
    _service_row("runner", "Runner", _sw_runner)
    _service_row("proxy", "Proxy", _sw_proxy)
    sync = tk.Label(status, text="", font=(FONT, 10, "bold"), bg=THEME["card"],
                    fg=THEME["green_text"], anchor="w")
    sync.pack(fill="x", padx=16, pady=(8, 14))
    _widgets["sync_text"] = sync

    px = tk.Frame(tab, bg=THEME["card"])
    px.pack(fill="x", padx=20, pady=8)
    tk.Label(px, text="PROXY", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(px, text="Cada quien usa el suyo. Encendido, Claude sale por el proxy.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"]).pack(
        anchor="w", padx=16, pady=(0, 8))
    grid = tk.Frame(px, bg=THEME["card"])
    grid.pack(fill="x", padx=16)
    fields = (("Host", "px_host", 22, None), ("Puerto", "px_port", 8, None),
              ("Usuario", "px_user", 14, None), ("Clave", "px_pass", 16, "•"))
    for i, (label, key, width, show) in enumerate(fields):
        cell = tk.Frame(grid, bg=THEME["card"])
        cell.grid(row=i // 2, column=i % 2, padx=(0, 12), pady=4, sticky="w")
        tk.Label(cell, text=label, font=(FONT, 9), bg=THEME["card"],
                 fg=THEME["muted"]).pack(anchor="w")
        ent = ttk.Entry(cell, width=width, font=(FONT, 10), show=show or "")
        ent.pack(anchor="w")
        _widgets[key] = ent
    _widgets["px_host"].insert(0, cfg.get("host", ""))
    _widgets["px_port"].insert(0, str(cfg.get("port", 18080)))
    _widgets["px_user"].insert(0, cfg.get("user", ""))
    if cfg.get("password"):
        _widgets["px_pass"].insert(0, cfg["password"])
    prow = tk.Frame(px, bg=THEME["card"])
    prow.pack(fill="x", padx=16, pady=(8, 14))
    ttk.Button(prow, text="Guardar", style="Accent.TButton",
               command=save_proxy_from_ui).pack(side="left", padx=(0, 8))


    # ================= pagina Carpetas
    tab2 = pages["carpetas"]
    tk.Label(tab2, text="Carpetas", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab2, text="Claude Code solo trabaja dentro de estas carpetas. "
             "Growi también puede modificar esta lista pidiéndole a Claude "
             "que edite folders.json.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    lb = tk.Listbox(tab2, height=12, font=(FONT, 10), bg="#FFFFFF",
                    fg=THEME["text"], selectbackground=THEME["blue"],
                    selectforeground="white", borderwidth=0,
                    highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=20, pady=4)
    _widgets["folders_list"] = lb
    brow = tk.Frame(tab2, bg=THEME["bg"])
    brow.pack(fill="x", padx=20, pady=(4, 16))
    ttk.Button(brow, text="Añadir carpeta", command=add_folder_ui).pack(side="left", padx=2)
    ttk.Button(brow, text="Quitar seleccionada", command=remove_folder_ui).pack(side="left", padx=2)
    ttk.Button(brow, text="Restablecer", command=reset_folders_ui).pack(side="left", padx=2)
    refresh_folders_ui()

    # ================= pagina Skills
    tab3 = pages["skills"]
    tk.Label(tab3, text="Skills", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab3, text=f"Carpeta: {HOME_DIR / '.claude' / 'skills'}",
             font=(FONT, 9), bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=20)
    _widgets["skills_count"] = tk.Label(tab3, text="", font=(FONT, 10),
                                        bg=THEME["bg"], fg=THEME["muted"])
    _widgets["skills_count"].pack(anchor="w", padx=20, pady=(4, 0))
    tree = ttk.Treeview(tab3, columns=("skill", "descripcion"), show="headings", height=14)
    tree.heading("skill", text="Skill")
    tree.heading("descripcion", text="Descripción")
    tree.column("skill", width=150)
    tree.column("descripcion", width=420)
    tree.pack(fill="both", expand=True, padx=20, pady=6)
    _widgets["skills_tree"] = tree
    ttk.Button(tab3, text="Actualizar lista", command=refresh_skills_ui).pack(
        anchor="w", padx=20, pady=(0, 16))
    refresh_skills_ui()

    # ================= pagina Pantalla
    tab4 = pages["pantalla"]
    tk.Label(tab4, text="Pantalla", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab4, text="Cuando lo activas, la app manda un fotograma comprimido "
             "(JPEG, max 1280px) cada pocos segundos al outbox, y Growi lo puede "
             "ver por el puente. Cada vez que empiezas a compartir se crea una "
             "carpeta nueva con la fecha y la hora (outbox/screens/AAAAMMDD-HHMMSS) "
             "y todos los fotogramas de esa grabación quedan allí guardados. "
             "Growi solo mira un fotograma cuando se lo pides o cuando hace falta "
             "para ayudarte: no es video en vivo. Puedes pararlo cuando quieras.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    _widgets["share_btn"] = ttk.Button(tab4, text="Compartir pantalla",
                                       style="Accent.TButton",
                                       command=lambda: stop_sharing() if state["sharing"]
                                       else start_sharing(float(_widgets["share_interval"].get().split()[0])))
    _widgets["share_btn"].pack(anchor="w", padx=20, pady=4)
    irow = tk.Frame(tab4, bg=THEME["bg"])
    irow.pack(anchor="w", padx=20, pady=4)
    tk.Label(irow, text="Fotograma cada:", font=(FONT, 10), bg=THEME["bg"],
             fg=THEME["text"]).pack(side="left")
    _widgets["share_interval"] = ttk.Combobox(irow, values=["0.5 s", "1 s", "5 s", "10 s", "30 s"],
                                              width=8, state="readonly")
    _widgets["share_interval"].set("10 s")
    _widgets["share_interval"].pack(side="left", padx=6)
    tk.Label(tab4, text="A 0.5 s y 1 s se guardan muchos fotogramas: cada sesión "
             "puede pesar decenas de MB. Las sesiones de más de 7 días se borran "
             "solas al empezar una nueva grabación.",
             font=(FONT, 9), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(4, 2))
    _widgets["share_status"] = tk.Label(tab4, text="Pantalla no compartida",
                                        font=(FONT, 10, "bold"),
                                        bg=THEME["bg"], fg=THEME["green_text"])
    _widgets["share_status"].pack(anchor="w", padx=20, pady=8)
    ttk.Button(tab4, text="Limpiar sesiones viejas",
               command=lambda: (_cleanup_old_sessions(),
                                log("pantalla: limpieza de sesiones viejas hecha"))).pack(
        anchor="w", padx=20, pady=2)
    ttk.Button(tab4, text="Abrir carpeta de sesiones",
               command=lambda: open_folder(SCREENS)).pack(anchor="w", padx=20, pady=2)

    # ================= pagina APIs
    tab5 = pages["apis"]
    tk.Label(tab5, text="APIs", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab5, text="Las claves se guardan solo en este PC (apis.json) y "
             "nunca se sincronizan ni se suben a ningún sitio. Growi nunca "
             "muestra una clave completa: aquí solo se ven los últimos 4 "
             "caracteres. Puedes añadir una desde aquí o desde WhatsApp: le "
             "dices a Growi la API y la clave, y llega al PC en segundos por "
             "el puente.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    tree = ttk.Treeview(tab5, columns=("api", "clave"), show="headings", height=10)
    tree.heading("api", text="API")
    tree.heading("clave", text="Clave")
    tree.column("api", width=170)
    tree.column("clave", width=420)
    tree.pack(fill="both", expand=True, padx=20, pady=6)
    _widgets["apis_tree"] = tree
    form = tk.Frame(tab5, bg=THEME["bg"])
    form.pack(fill="x", padx=20, pady=4)
    tk.Label(form, text="Nombre", font=(FONT, 9), bg=THEME["bg"],
             fg=THEME["muted"]).grid(row=0, column=0, sticky="w")
    _widgets["api_name"] = ttk.Entry(form, width=22, font=(FONT, 10))
    _widgets["api_name"].grid(row=1, column=0, padx=(0, 12), sticky="w")
    tk.Label(form, text="Clave", font=(FONT, 9), bg=THEME["bg"],
             fg=THEME["muted"]).grid(row=0, column=1, sticky="w")
    _widgets["api_key"] = ttk.Entry(form, width=34, font=(FONT, 10), show="•")
    _widgets["api_key"].grid(row=1, column=1, padx=(0, 12), sticky="w")
    ttk.Button(form, text="Guardar", style="Accent.TButton",
               command=add_api_ui).grid(row=1, column=2, sticky="w")
    brow5 = tk.Frame(tab5, bg=THEME["bg"])
    brow5.pack(fill="x", padx=20, pady=(4, 16))
    ttk.Button(brow5, text="Quitar seleccionada", command=remove_api_ui).pack(
        side="left", padx=2)
    ttk.Button(brow5, text="Añadir por WhatsApp", command=add_api_whatsapp).pack(
        side="left", padx=2)
    refresh_apis_ui()

    # ================= pagina Tareas
    tabt = pages["tareas"]
    tk.Label(tabt, text="Tareas", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tabt, text="Lo que Claude (y Hermes, en local) ha hecho por ti, con su costo. "
             "La lista se actualiza sola cuando termina una tarea.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    _widgets["tasks_summary"] = tk.Label(tabt, text="", font=(FONT, 11, "bold"),
                                         bg=THEME["bg"], fg=THEME["green_text"])
    _widgets["tasks_summary"].pack(anchor="w", padx=20, pady=(0, 6))
    tree = ttk.Treeview(tabt, columns=("tarea", "estado", "duracion", "costo"),
                        show="headings", height=8)
    for _col, _txt, _w in (("tarea", "Tarea", 260), ("estado", "Estado", 80),
                          ("duracion", "Duración", 90), ("costo", "Costo", 90)):
        tree.heading(_col, text=_txt)
        tree.column(_col, width=_w)
    tree.pack(fill="x", padx=20, pady=4)
    _widgets["tasks_tree"] = tree
    ask = tk.Frame(tabt, bg=THEME["card"])
    ask.pack(fill="x", padx=20, pady=8)
    tk.Label(ask, text="PEDIRLE ALGO", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(ask, text="Escribe la tarea y elige el motor. Claude hace el trabajo pesado; "
             "Hermes 3 corre en local, gratis, para lo rápido.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
             wraplength=560, justify="left").pack(anchor="w", padx=16, pady=(0, 6))
    _widgets["ask_text"] = tk.Text(ask, height=3, font=(FONT, 10), bg="#FFFFFF",
                                   fg=THEME["text"], insertbackground=THEME["text"],
                                   borderwidth=0, highlightthickness=0)
    _widgets["ask_text"].pack(fill="x", padx=16, pady=4)
    arow = tk.Frame(ask, bg=THEME["card"])
    arow.pack(fill="x", padx=16, pady=(0, 12))
    _widgets["ask_engine"] = ttk.Combobox(arow, width=30, font=(FONT, 10),
        values=["Claude Sonnet", "Claude Opus", "Claude Haiku",
                "Local Hermes 3 (Ollama · $0)"])
    _widgets["ask_engine"].set("Claude Sonnet")
    _widgets["ask_engine"].pack(side="left", padx=(0, 8))
    ttk.Button(arow, text="Enviar", style="Accent.TButton",
               command=_send_ask).pack(side="left")
    _widgets["ask_status"] = tk.Label(ask, text="", font=(FONT, 9),
                                      bg=THEME["card"], fg=THEME["green_text"])
    _widgets["ask_status"].pack(anchor="w", padx=16, pady=(0, 12))

    # ================= pagina Ajustes
    tab_aj = pages["ajustes"]
    tk.Label(tab_aj, text="Ajustes", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab_aj, text="Todo lo de la app en un solo sitio.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    aj = tk.Frame(tab_aj, bg=THEME["card"])
    aj.pack(fill="x", padx=20, pady=8)
    tk.Label(aj, text="AJUSTES", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))

    def _setting_row(label, expl, initial, on_change):
        row = tk.Frame(aj, bg=THEME["card"])
        row.pack(fill="x", padx=16, pady=5)
        left = tk.Frame(row, bg=THEME["card"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=label, font=(FONT, 10, "bold"),
                 bg=THEME["card"], fg=THEME["text"]).pack(anchor="w")
        tk.Label(left, text=expl, font=(FONT, 9),
                 bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w")
        sw = make_switch(row, initial, on_change, bg=THEME["card"])
        sw.pack(side="right")
        sep = tk.Frame(aj, bg=THEME["line"], height=1)
        sep.pack(fill="x", padx=16)
        return sw

    def _sw_autoupd(on):
        state["auto_update"] = on
        s = load_settings()
        s["auto_update"] = on
        save_settings(s)
        log(f"ajustes: actualizacion automatica {'activada' if on else 'desactivada'}")

    def _sw_autostart(on):
        if set_autostart(on):
            state["autostart"] = on
        else:
            state["autostart"] = autostart_enabled()
            messagebox.showwarning(
                "Inicio automático",
                "No se pudo cambiar el inicio automático. "
                "La app necesita correr como administrador.")

    _widgets["autoupd_sw"] = _setting_row(
        "Actualización automática",
        "Se actualiza sola desde GitHub cuando hay una versión nueva.",
        state.get("auto_update", False), _sw_autoupd)
    _widgets["autostart_sw"] = _setting_row(
        "Iniciar al encender la PC",
        "Arranca sola con Windows al iniciar sesión.",
        state.get("autostart", False), _sw_autostart)

    def _sw_keepawake(on):
        state["keep_awake"] = on
        s = load_settings()
        s["keep_awake"] = on
        save_settings(s)
        log(f"ajustes: no suspender mientras trabaja {'activado' if on else 'desactivado'}")

    _widgets["keepawake_sw"] = _setting_row(
        "No suspender mientras trabaja",
        "La PC no se duerme mientras Claude corre una tarea.",
        state.get("keep_awake", True), _sw_keepawake)

    pc = tk.Frame(tab_aj, bg=THEME["card"])
    pc.pack(fill="x", padx=20, pady=8)
    tk.Label(pc, text="PC", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(pc, text="Apagar o reiniciar este PC. Te pide confirmación y "
             "tienes 60 segundos para cancelarlo.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"]).pack(
        anchor="w", padx=16, pady=(0, 8))
    prow2 = tk.Frame(pc, bg=THEME["card"])
    prow2.pack(fill="x", padx=16, pady=(0, 14))
    ttk.Button(prow2, text="Apagar PC",
               command=lambda: _pc_confirm("shutdown")).pack(side="left", padx=(0, 8))
    ttk.Button(prow2, text="Reiniciar PC",
               command=lambda: _pc_confirm("restart")).pack(side="left", padx=(0, 8))
    ttk.Button(prow2, text="Cancelar apagado",
               command=pc_abort).pack(side="left")

    btns = tk.Frame(tab_aj, bg=THEME["bg"])
    btns.pack(fill="x", padx=20, pady=8)
    ttk.Button(btns, text="Abrir Inbox",
               command=lambda: open_folder(INBOX)).grid(row=0, column=0, padx=2, pady=2)
    ttk.Button(btns, text="Abrir Outbox",
               command=lambda: open_folder(OUTBOX)).grid(row=0, column=1, padx=2, pady=2)
    ttk.Button(btns, text="Buscar actualizaciones",
               command=check_updates_ui).grid(row=0, column=2, padx=2, pady=2)
    ttk.Button(btns, text="Salir", command=quit_app).grid(row=0, column=3, padx=2, pady=2)
    _widgets["update_label"] = tk.Label(tab_aj, text="", font=(FONT, 9),
                                        bg=THEME["bg"], fg=THEME["green_text"])
    _widgets["update_label"].pack(anchor="w", padx=22)
    _widgets["update_btn"] = ttk.Button(tab_aj, text="Actualizar ahora", state="disabled",
                                        command=do_update_ui)
    _widgets["update_btn"].pack(anchor="w", padx=20, pady=2)


    # ================= pagina Registro
    tab_reg = pages["registro"]
    tk.Label(tab_reg, text="Registro", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab_reg, text="Todo lo que la app ha hecho, en orden.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=600, justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    log_box = tk.Frame(tab_reg, bg=THEME["card"])
    log_box.pack(fill="both", expand=True, padx=20, pady=(4, 16))
    tk.Label(log_box, text="REGISTRO", font=(FONT, 9, "bold"),
             bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w", padx=16, pady=(12, 2))
    text = scrolledtext.ScrolledText(log_box, height=18, font=("Consolas", 9),
                                     bg="#FFFFFF", fg=THEME["text"],
                                     insertbackground=THEME["text"],
                                     state="disabled", borderwidth=0)
    text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    _widgets["log"] = text

    # ---------------- paleta de comandos (Ctrl+K) y atajo
    def _sw_click(key):
        sw = _widgets.get(key)
        if sw is not None:
            try:
                sw.event_generate("<Button-1>")
            except Exception:
                pass

    _PALETTE_CMDS.clear()
    for _n, _l in (("estado", "Estado"), ("carpetas", "Carpetas"),
                   ("skills", "Skills"), ("pantalla", "Pantalla"),
                   ("apis", "APIs"), ("tareas", "Tareas"),
                   ("ajustes", "Ajustes"), ("registro", "Registro")):
        _PALETTE_CMDS.append((f"Ir a {_l}", f"ir pagina {_l}",
                              lambda n=_n: _show_page(n)))
    _PALETTE_CMDS += [
        ("Encender / apagar todo", "power todo encender apagar", on_power_click),
        ("Puente: encender / apagar", "puente bridge",
         lambda: _sw_click("bridge_sw")),
        ("Runner: encender / apagar", "runner",
         lambda: _sw_click("runner_sw")),
        ("Proxy: encender / apagar", "proxy",
         lambda: _sw_click("proxy_sw")),
        ("Mascota: mostrar / ocultar", "mascota growi", toggle_mascot),
        ("Pedirle algo a Claude", "pedir claude tarea preguntar",
         lambda: (_show_page("tareas"), _widgets["ask_text"].focus_set())),
        ("Abrir Inbox", "abrir inbox carpeta", lambda: open_folder(INBOX)),
        ("Abrir Outbox", "abrir outbox carpeta", lambda: open_folder(OUTBOX)),
        ("Buscar actualizaciones", "actualizar update", check_updates_ui),
        ("Apagar PC", "apagar pc shutdown", lambda: _pc_confirm("shutdown")),
        ("Reiniciar PC", "reiniciar pc restart", lambda: _pc_confirm("restart")),
        ("Mostrar / ocultar ventana", "ventana mostrar ocultar", toggle_window),
        ("Salir de Growi Bridge", "salir cerrar", quit_app),
    ]
    root.bind_all("<Control-k>", lambda _e: _open_palette())

    _show_page("estado")
    return root

def main():
    if not TK_OK:
        print("ERROR: tkinter no esta disponible en este Python.")
        print("Reinstala Python marcando la opcion Tcl/Tk, o corre los programas por separado.")
        return 2
    _dpi_awareness()
    state["admin"] = is_admin()
    state["proxy_configured"] = bool(proxy_config().get("password"))
    state["proxy_on"] = "HTTPS_PROXY" in os.environ
    settings = load_settings()
    state["mascot"] = bool(settings.get("mascot", False))
    state["keep_awake"] = bool(settings.get("keep_awake", True))
    state["auto_update"] = bool(settings.get("auto_update", False))
    state["autostart"] = autostart_enabled()
    try:
        root = build_gui()
    except Exception:
        traceback.print_exc()
        log(f"no se pudo crear la ventana: {traceback.format_exc()}")
        return 2
    global _tray_icon
    _tray_icon = build_tray()
    log(f"Growi Bridge v{VERSION} arrancado. Administrador: {'sí' if state['admin'] else 'no'}.")
    set_power(True)
    if state["mascot"]:
        try:
            show_mascot()
        except Exception as e:
            log(f"mascota: no se pudo mostrar ({e})")
    # Atajo global Ctrl+Alt+G para mostrar/ocultar la ventana (estilo Raycast).
    try:
        import keyboard
        keyboard.add_hotkey("ctrl+alt+g", lambda: _root.after(0, toggle_window))
        log("atajo global Ctrl+Alt+G activo")
    except Exception as e:
        log(f"atajo global no disponible ({type(e).__name__})")
    threading.Thread(target=_auto_update_check, daemon=True).start()
    threading.Thread(target=_auto_update_loop, daemon=True).start()
    root.after(1000, _tick)
    root.after(500, _pulse_loop)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    quit_app()
    return 0


def _auto_update_check():
    remote = check_update_available()
    state["update_checked"] = True
    if remote:
        state["update_available"] = remote
        log(f"actualizaciones: hay una nueva version v{remote}")


def _set_update(remote):
    if remote:
        state["update_available"] = remote
        log(f"actualizaciones: hay una nueva version v{remote}")


if __name__ == "__main__":
    sys.exit(main())
