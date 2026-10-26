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
              principal (la de tu usuario de Windows).
  Skills    — las skills instaladas de Claude Code (~/.claude/skills/).
  Pantalla  — compartir pantalla con Growi (fotogramas comprimidos, solo
              cuando tu lo activas; cada grabacion guarda sus fotogramas en
              una carpeta con fecha y hora; Growi mira un fotograma cuando
              hace falta).
  APIs      — claves de APIs privadas guardadas solo en este PC. Se pueden
              añadir desde aqui o desde WhatsApp: le dices a Growi y llegan
              al PC en segundos por el puente. Cada proveedor (Anthropic,
              OpenAI, Gemini, Groq, OpenRouter) tiene su boton Probar.
  Modelos   — orquestador de modelos estilo Ollama: libreria de modelos
              locales con semaforo segun tu PC (Comprobar mi PC), instalar /
              borrar / elegir el modelo local por defecto, quien responde,
              habilidades con interruptor, canales y reglas. Todo lo que hace
              la ventana lo puede hacer el asistente mandando tasks al runner
              con "ollama_action" (pull / rm / list).
  Tareas    — orquestacion: cada tarea corre con su motor (engines.json:
              claude, llama, ollama, codex, meshy), se revisa sola al
              terminar y, si falta algo, se corrige hasta 3 rondas. Estado,
              motor, ronda, costo y revision por tarea; banner con Parar;
              aprobacion antes de borrar, publicar, gastar o enviar.
  Recursos  — cuanto CPU, RAM, GPU (nvidia-smi) y disco se usa, y que
              proceso lo usa: primero los de Growi (la app, lo que lanzo el
              runner, claude, ollama, llama-server...); cerrar un proceso
              siempre pide confirmacion y los criticos de Windows no se
              pueden cerrar. psutil (si falta, se instala; si no, tasklist).

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

La X hace lo que elijas en Ajustes (minimizar a la bandeja o salir); la
primera vez lo pregunta y lo recuerda. Salir del todo tambien es con el
boton Salir o desde el menu de la bandeja.
"""

import json
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import random
import re
import secrets
import sqlite3
import time
import traceback
import unicodedata
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "0.1.0-alpha"
GITHUB_REPO = "leandrogzn98-hash/growi-bridge"
APP_DIR = Path(__file__).resolve().parent
# GROWI_BRIDGE_SHARE: carpeta share alternativa (solo para pruebas aisladas;
# por defecto es la carpeta share junto al programa).
SHARE = (Path(os.environ["GROWI_BRIDGE_SHARE"]) if os.environ.get("GROWI_BRIDGE_SHARE")
         else APP_DIR / "share")
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
# Modelo local por defecto: se elige en la pestana Modelos y se guarda en
# settings.json (clave ollama_model). Esta constante es solo el respaldo si
# settings.json no dice nada (cada PC elige el suyo).
OLLAMA_MODEL = "hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M"
_keep_awake_applied = [False]
_seen_results = set()
PROXY_FILE = APP_DIR / "proxy.json"
FOLDERS_FILE = APP_DIR / "folders.json"
SETTINGS_FILE = APP_DIR / "settings.json"


def _startup_setting(key):
    """Lee una clave de settings.json al arrancar (antes de load_settings)."""
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get(key)
    except (OSError, ValueError, AttributeError):
        return None


def _bridge_port():
    """Puerto del puente: GROWI_BRIDGE_PORT > settings.json (bridge_port) > 8787."""
    for raw in (os.environ.get("GROWI_BRIDGE_PORT"), _startup_setting("bridge_port")):
        try:
            port = int(raw)
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535:
            return port
    return 8787


BRIDGE_PORT = _bridge_port()
# Carril (ver ESTADO-DOS-CARRILES.md): "a" es la app de siempre; "b" es la
# copia en growi-bridge-lane2 que solo corre tareas que no tocan la app.
# GROWI_BRIDGE_LANE > settings.json (lane) > "a".
LANE = ("b" if str(os.environ.get("GROWI_BRIDGE_LANE") or _startup_setting("lane") or "a")
        .strip().lower() == "b" else "a")
HOME_DIR = Path.home()

# Tema v2.3 "Mac" (ver DESIGN.md + notas-mobbin.md Superlist/Plain):
# contenido blanco, barra lateral gris muy clara, texto casi negro,
# acento azul de macOS, interruptores verdes de macOS.
FONT = "Segoe UI"
# Colores de texto con contraste AA (>= 4,5:1 sobre blanco): green_text
# 5,40:1, blue 5,57:1, muted (contadores y notas) 5,21:1 y red (texto
# destructivo) 5,74:1. "green" solo es relleno (interruptores, boton
# grande), nunca texto.
THEME = {
    "bg": "#FFFFFF", "sidebar": "#F5F5F7", "card": "#F5F5F7", "field": "#FFFFFF",
    "text": "#1D1D1F", "muted": "#5F5F63", "line": "#E5E5EA",
    "green": "#34C759", "green_text": "#1F7A33", "blue": "#0066CC",
    "orange": "#FF9500", "orange_text": "#9A5200", "red": "#C81E1E",
}
# Titulo de cada tarjeta: formato oracion, sin mayusculas sostenidas.
SECTION_FONT = (FONT, 11, "bold")

# Escala de pantalla (DPI de la ventana / 96): 1.0 a 100 %, 1.25 a 125 %,
# 1.5 a 150 %. La fija _dpi_scaling() al crear la ventana. Toda medida fija
# en pixeles pasa por S(); los padx/pady de pack y grid se escalan solos.
SCALE = 1.0


def S(px):
    """Una medida en pixeles pensada a 100 % -> pixeles reales a este DPI."""
    return int(round(px * SCALE))

ICO = APP_DIR / "growi.ico"
# Carril B: el mismo personaje con una «B» violeta arriba a la izquierda, para
# distinguir los dos iconos de la bandeja (abajo a la derecha va el de estado).
TRAY_ICON = (APP_DIR / "growi-tray-b.png"
             if LANE == "b" and (APP_DIR / "growi-tray-b.png").is_file()
             else APP_DIR / "growi-tray.png")
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
    "paso": None, "llama_autostart": "",
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
    """Lee secret.txt. Si no existe (instalacion nueva en otro PC), crea uno
    aleatorio: el asistente lo necesita para conectarse al puente."""
    path = APP_DIR / "secret.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        try:
            secret = secrets.token_hex(24)
            path.write_text(secret, encoding="utf-8")
            log("puente: se creó un secret.txt nuevo; pásaselo a tu asistente "
                "para que se conecte")
            return secret
        except OSError:
            return ""
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
                "DESIGN.md", "notas-mobbin.md", "models-catalog.json", "README.md",
                "engines.json", "availability.json"]


def _update_repo():
    """Repositorio de donde se baja la app. Por defecto el publico de Growi
    Bridge; quien use un fork lo cambia en settings.json (update_repo)."""
    repo = str(load_settings().get("update_repo") or "").strip()
    return repo if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) else GITHUB_REPO


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
    url = f"https://raw.githubusercontent.com/{_update_repo()}/main/VERSION"
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
    True si quedo todo, False si algo fallo. Los archivos opcionales
    (catalogo de modelos, README) se saltan si el repo aun no los tiene."""
    optional = {"models-catalog.json", "README.md"}
    got = []
    for name in UPDATE_FILES:
        url = f"https://raw.githubusercontent.com/{_update_repo()}/main/{name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GrowiBridge"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if name == "growi-bridge.py" and (b"Growi Bridge" not in data[:2000]
                                             or len(data) < 10000):
                log("actualizaciones: growi-bridge.py descargado invalido")
                return False
            (APP_DIR / (name + ".new")).write_bytes(data)
            got.append(name)
        except Exception as e:
            if name in optional:
                log(f"actualizaciones: {name} no está en el repo, se deja el actual")
                continue
            log(f"actualizaciones: fallo al bajar {name} ({e})")
            return False
    lines = ["@echo off", "timeout /t 2 /nobreak >nul"]
    for name in got:
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


# ---------------------------------------------------------------- modelos
# Growi Bridge junta lo que aporta Ollama (modelos que viven y corren en el
# PC) con la forma de trabajar de un agente estilo OpenClaw (un solo
# asistente que usa herramientas, tiene habilidades, te habla por varios
# canales y cumple tus reglas). Todo lo que hace la pestana Modelos lo puede
# hacer tambien el asistente desde la VM con tasks "ollama_action"
# (pull / rm / list): la ventana y el asistente mueven los mismos botones.
CATALOG_FILE = APP_DIR / "models-catalog.json"
PC_SPECS_FILE = APP_DIR / "pc-specs.json"
RULES_FILE = APP_DIR / "rules.json"
MODEL_ACTIONS = ("pull", "rm", "list")
# Misma regla que los ids del runner + "/" y ":" (los nombres de Ollama los
# llevan). Debe empezar por letra o numero: nada de "-flag" ni rutas.
MODEL_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/:-]{0,199}")
DEFAULT_RULES = ["Pregúntame antes de gastar dinero",
                 "No borres nada sin pedirme permiso"]
MODEL_JOBS = {}  # id del task -> {"action", "model", "line", "status"}
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def valid_model_name(name):
    """Solo letras, numeros, - _ . / : (sin URLs, sin '..', sin flags)."""
    return (isinstance(name, str) and bool(MODEL_NAME_RE.fullmatch(name))
            and ".." not in name and "//" not in name)


def ollama_exe():
    exe = shutil.which("ollama")
    if exe:
        return exe
    cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(cand) if cand.is_file() else None


def default_ollama_model():
    """El modelo local elegido en la pestana Modelos (settings.json)."""
    m = str(load_settings().get("ollama_model") or "").strip()
    return m if valid_model_name(m) else ""


def _same_model(a, b):
    """'mistral' y 'mistral:latest' son el mismo modelo para Ollama."""
    def _norm(n):
        n = (n or "").strip().lower()
        last = n.rsplit("/", 1)[-1]
        return n if ":" in last else n + ":latest"
    return _norm(a) == _norm(b)


def _size_to_gb(text):
    m = re.match(r"\s*([\d.]+)\s*(KB|MB|GB|TB)", text or "", re.I)
    if not m:
        return None
    mult = {"KB": 1e-6, "MB": 1e-3, "GB": 1.0, "TB": 1000.0}[m.group(2).upper()]
    return round(float(m.group(1)) * mult, 2)


def _ago_es(text):
    """'5 days ago' -> 'hace 5 días' (la salida de ollama list viene en inglés)."""
    t = (text or "").strip()
    m = re.match(r"(\d+|an?|about an?)\s+(second|minute|hour|day|week|month|year)s?\s+ago", t, re.I)
    if not m:
        return t
    n = m.group(1).lower()
    n = "1" if n.startswith(("a", "an", "about")) else n
    unit = {"second": ("segundo", "segundos"), "minute": ("minuto", "minutos"),
            "hour": ("hora", "horas"), "day": ("día", "días"),
            "week": ("semana", "semanas"), "month": ("mes", "meses"),
            "year": ("año", "años")}[m.group(2).lower()]
    return f"hace {n} {unit[0] if n == '1' else unit[1]}"


def parse_ollama_list(text):
    """Convierte la salida de `ollama list` en filas {name, size, size_gb,
    modified}. Ignora la cabecera y cualquier linea rara."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        cols = re.split(r"\s{2,}", line)
        if not cols or not valid_model_name(cols[0]):
            continue
        size = cols[2] if len(cols) > 2 else ""
        out.append({"name": cols[0], "id": cols[1] if len(cols) > 1 else "",
                    "size": size, "size_gb": _size_to_gb(size),
                    "modified": _ago_es(cols[3]) if len(cols) > 3 else ""})
    return out


def _clean_line(raw):
    """Quita colores/cursor y el spinner (⠋⠙⠹…) de la salida de ollama."""
    text = _ANSI_RE.sub("", raw.decode("utf-8", "replace"))
    text = re.sub(r"[⠀-⣿]", "", text).strip()
    # ollama redibuja la misma linea: "pulling manifest  pulling manifest" -> una vez
    return re.sub(r"^(.+?)(?:\s+\1)+$", r"\1", text)


def _run_capture(cmd, timeout_s, cwd=None):
    """Como subprocess.run(capture_output=True) pero con archivos temporales
    en vez de tuberias: si `ollama` arranca su servidor de fondo, ese
    servidor hereda la salida y con tuberias Python esperaria para siempre.
    Devuelve (codigo, stdout, stderr); lanza TimeoutExpired como run()."""
    import tempfile
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                cwd=cwd, creationflags=_NO_WINDOW)
        try:
            rc = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise
        out.seek(0)
        err.seek(0)
        return (rc, out.read().decode("utf-8", "replace"),
                err.read().decode("utf-8", "replace"))


def run_model_action(action, model=None, timeout_s=3600, job_id=None):
    """Corre `ollama pull|rm|list` (nunca otra cosa, nunca por shell).
    Devuelve (ok, salida, error). El pull va con progreso en MODEL_JOBS y
    en el registro (cada 10 %), y en outbox/runner-results/<id>.progress.json
    para que el asistente lo vea desde la VM."""
    if action not in MODEL_ACTIONS:
        return False, "", f"acción no permitida: {action}"
    if action != "list" and not valid_model_name(model):
        return False, "", ("nombre de modelo no válido (solo letras, números, "
                           "- _ . / :)")
    exe = ollama_exe()
    if not exe:
        return False, "", "Ollama no está instalado en este PC (ollama.com, gratis)"
    cmd = [exe, action] + ([model] if action != "list" else [])
    if action != "pull":
        try:
            rc, stdout, stderr = _run_capture(cmd, timeout_s)
        except subprocess.TimeoutExpired:
            return False, "", f"ollama {action} tardó más de {max(1, timeout_s // 60)} min"
        except Exception as e:
            return False, "", f"{type(e).__name__}: {e}"
        out = _ANSI_RE.sub("", stdout).strip()
        if rc != 0:
            err = [l for l in _ANSI_RE.sub("", stderr).splitlines()
                   if l.strip() and "level=" not in l]
            return False, out, (err[-1].strip() if err else
                                f"ollama salió con código {rc}")
        return True, out, None
    # pull: lee la salida a trozos para mostrar el progreso sin esperar al final.
    key = job_id or model
    job = MODEL_JOBS.setdefault(key, {})
    job.update(action="pull", model=model, line="Preparando…", status="running")
    progress_file = RESULTS / f"{key}.progress.json"
    seen = []
    last = {"bucket": None, "write": 0.0}

    try:
        # Con tuberia para ver el progreso al momento; se espera al proceso
        # (proc.wait), no a la tuberia, asi que no se cuelga aunque ollama
        # arranque su servidor de fondo.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        _track_launch(proc, f"Modelos: instalando {model}")
    except Exception as e:
        job["status"] = "error"
        return False, "", f"{type(e).__name__}: {e}"

    def _reader():
        buf = b""
        while True:
            try:
                chunk = proc.stdout.read1(4096)
            except Exception:
                break
            if not chunk:
                break
            buf += chunk
            parts = re.split(rb"[\r\n]", buf)
            buf = parts[-1]
            for raw in parts[:-1]:
                t = _clean_line(raw)
                if not t or "level=" in t:
                    continue
                job["line"] = t
                pct = re.search(r"(\d{1,3})%", t)
                if pct:
                    bucket = (t.split(":")[0], int(pct.group(1)) // 10)
                    if bucket != last["bucket"]:
                        last["bucket"] = bucket
                        log(f"modelos: descargando {model}: {pct.group(1)}%")
                elif not seen or seen[-1] != t:
                    seen.append(t)
                now = time.time()
                if now - last["write"] >= 5:
                    last["write"] = now
                    try:
                        RESULTS.mkdir(parents=True, exist_ok=True)
                        progress_file.write_text(json.dumps(
                            {"id": key, "model": model, "line": t, "at": _now_iso()},
                            ensure_ascii=False), encoding="utf-8")
                    except OSError:
                        pass
        t = _clean_line(buf)
        if t:
            job["line"] = t
            seen.append(t)

    th = threading.Thread(target=_reader, daemon=True)
    th.start()
    try:
        rc = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        th.join(5)
        job["status"] = "error"
        _rm_quiet(progress_file)
        return False, "\n".join(seen[-20:]), f"timeout de {max(1, timeout_s // 60)} min"
    th.join(10)
    _rm_quiet(progress_file)
    out = "\n".join(seen[-20:])
    job["status"] = "ok" if rc == 0 else "error"
    if rc != 0:
        return False, out, (seen[-1] if seen else f"ollama salió con código {rc}")
    return True, out, None


def _rm_quiet(path):
    try:
        Path(path).unlink()
    except OSError:
        pass


def load_catalog():
    """Libreria curada de modelos (models-catalog.json junto al programa).
    Se amplia editando el archivo, sin tocar codigo."""
    try:
        data = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("models", []) if isinstance(data, dict) else data
    out = []
    for m in items if isinstance(items, list) else []:
        try:
            if not valid_model_name(m.get("id")):
                continue
            size = float(m.get("size_gb") or 0)
            out.append({"id": m["id"], "name": str(m.get("name") or m["id"]),
                        "size_gb": size,
                        "vram_gb": float(m.get("vram_gb") or round(size * 1.15, 1)),
                        "use": str(m.get("use") or ""),
                        "kind": str(m.get("kind") or "")})
        except (AttributeError, TypeError, ValueError):
            continue
    return out


def friendly_model_name(name, catalog=None):
    """Nombre normal de un modelo (sin etiquetas tecnicas)."""
    for m in catalog if catalog is not None else load_catalog():
        if _same_model(m["id"], name):
            return m["name"]
    base = name.rsplit("/", 1)[-1]
    base, _, tag = base.partition(":")
    base = re.sub(r"-?GGUF$", "", base, flags=re.I).replace("-", " ").replace("_", " ")
    if tag and tag != "latest" and re.fullmatch(r"\d+(\.\d+)?b", tag, re.I):
        base += " " + tag.upper()
    return base.strip() or name


# --- especificaciones del PC (todo local, sin gastar nada)
def _gpu_query():
    smi = shutil.which("nvidia-smi")
    if not smi:
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        smi = str(cand) if cand.is_file() else None
    if not smi:
        return None
    try:
        p = subprocess.run([smi, "--query-gpu=name,memory.total,memory.free",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=_NO_WINDOW)
        line = next((l for l in (p.stdout or "").splitlines() if l.strip()), "")
        name, total, free = [x.strip() for x in line.split(",")[:3]]
        return {"name": name, "vram_total_gb": round(int(float(total)) / 1024, 1),
                "vram_free_gb": round(int(float(free)) / 1024, 1)}
    except Exception:
        return None


def gpu_free_vram_gb():
    g = _gpu_query()
    return g["vram_free_gb"] if g else None


def detect_pc_specs():
    """GPU (nvidia-smi), RAM, CPU, disco libre y version de Ollama. Guarda el
    resultado en pc-specs.json y lo devuelve."""
    specs = {"detected_at": _now_iso(), "gpu": _gpu_query()}
    try:
        import ctypes

        class _MEM(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = _MEM()
        st.dwLength = ctypes.sizeof(_MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
        specs["ram_total_gb"] = round(st.ullTotalPhys / 1024 ** 3, 1)
        specs["ram_free_gb"] = round(st.ullAvailPhys / 1024 ** 3, 1)
    except Exception:
        specs["ram_total_gb"] = specs["ram_free_gb"] = None
    cpu = {"name": "", "cores": None, "threads": os.cpu_count()}
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu["name"] = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        winreg.CloseKey(k)
    except Exception:
        pass
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance Win32_Processor | Measure-Object "
                            "-Property NumberOfCores -Sum).Sum"],
                           capture_output=True, text=True, timeout=20,
                           creationflags=_NO_WINDOW)
        cpu["cores"] = int((p.stdout or "").strip())
    except Exception:
        pass
    specs["cpu"] = cpu
    try:
        drive = Path.home().anchor or "C:\\"
        specs["disk_drive"] = drive
        specs["disk_free_gb"] = round(shutil.disk_usage(drive).free / 1024 ** 3, 1)
    except Exception:
        specs["disk_free_gb"] = None
    specs["ollama_version"] = ""
    exe = ollama_exe()
    if exe:
        try:
            _rc, so, se = _run_capture([exe, "--version"], 20)
            m = re.search(r"version is (\d+\.\d+\.\d+)", so + se) or \
                re.search(r"(\d+\.\d+\.\d+)", so + se)
            specs["ollama_version"] = m.group(1) if m else ""
        except Exception:
            pass
    try:
        PC_SPECS_FILE.write_text(json.dumps(specs, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except OSError:
        pass
    return specs


def load_pc_specs():
    try:
        data = json.loads(PC_SPECS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _gb(x):
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _y_join(parts):
    """['a', 'b', 'c'] -> 'a, b y c' (enumeracion en espanol)."""
    parts = [str(x) for x in parts if x]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " y " + parts[-1]


def pc_specs_summary(specs):
    """'RTX 3060 Laptop con 6 GB de VRAM, 16 GB de RAM y 100 GB libres'."""
    if not specs:
        return "Aún no comprobé tu PC."
    parts = []
    gpu = specs.get("gpu")
    if gpu:
        name = re.sub(r"\b(NVIDIA|GeForce|GPU)\b", "", gpu.get("name", "")).strip()
        parts += [re.sub(r"\s+", " ", name) or "GPU NVIDIA",
                  f"{_gb(gpu.get('vram_total_gb') or 0)} GB VRAM"]
    else:
        parts.append("Sin GPU dedicada (los modelos corren en el procesador)")
    if specs.get("ram_total_gb"):
        parts.append(f"{round(specs['ram_total_gb'])} GB RAM")
    if specs.get("disk_free_gb") is not None:
        parts.append(f"{round(specs['disk_free_gb'])} GB libres")
    return _y_join(parts)


def model_fit(vram_need, size_gb, specs, installed=False):
    """Semaforo: (color, motivo). color: green / orange / red / gray.
    Con GPU: verde <= 80 % de la VRAM total, naranja 80-100 %, rojo si no
    cabe (o si no cabe en el disco). Sin GPU usa la RAM (corre en CPU):
    verde <= 50 %, naranja 50-90 %, rojo por encima."""
    if not specs:
        return "gray", "Pulsa Comprobar mi PC para ver si cabe"
    vram_need = float(vram_need or 0)
    gpu = specs.get("gpu")
    disk = specs.get("disk_free_gb")
    disk_red = (not installed and size_gb and disk is not None and size_gb > disk)
    if gpu and gpu.get("vram_total_gb"):
        tot = float(gpu["vram_total_gb"])
        if vram_need > tot:
            return "red", f"No cabe: necesita {_gb(vram_need)} GB de VRAM y tienes {_gb(tot)} GB"
        if disk_red:
            return "red", f"No cabe: necesita {_gb(size_gb)} GB de disco y tienes {_gb(disk)} GB libres"
        pct = vram_need / tot * 100
        if pct <= 80:
            return "green", "Cabe holgado"
        return "orange", f"Va justo: usa ~{round(pct)}% de tu VRAM"
    ram = specs.get("ram_total_gb")
    if not ram:
        return "gray", "No pude leer la memoria de tu PC"
    if vram_need > ram * 0.9:
        return "red", (f"No cabe: necesita {_gb(vram_need)} GB de RAM y tienes "
                       f"{_gb(ram)} GB (sin GPU, corre en CPU)")
    if disk_red:
        return "red", f"No cabe: necesita {_gb(size_gb)} GB de disco y tienes {_gb(disk)} GB libres"
    pct = vram_need / ram * 100
    if pct <= 50:
        return "green", "Cabe holgado (sin GPU, corre en CPU)"
    return "orange", f"Va justo: usa ~{round(pct)}% de tu RAM (sin GPU, corre en CPU)"


# --- reglas (las instrucciones del agente, en palabras del usuario)
def load_rules():
    try:
        data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [{"text": str(r.get("text", "")).strip()[:300],
                     "on": bool(r.get("on", True))}
                    for r in data if isinstance(r, dict) and str(r.get("text", "")).strip()]
    except FileNotFoundError:
        rules = [{"text": t, "on": True} for t in DEFAULT_RULES]
        save_rules(rules)
        return rules
    except (OSError, ValueError):
        pass
    return [{"text": t, "on": True} for t in DEFAULT_RULES]


def save_rules(rules):
    try:
        RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    except OSError:
        pass


# --- habilidades (herramientas del runner + skills de Claude Code)
TOOL_ABILITIES = (
    ("Read", "Leer tus archivos", "Abre y lee archivos de tus carpetas permitidas."),
    ("Write", "Crear archivos", "Guarda archivos nuevos en tus carpetas permitidas."),
    ("Edit", "Editar tus archivos", "Cambia archivos que ya existen."),
    ("Bash", "Usar los programas del PC", "Abre programas y hace tareas en tu PC."),
    ("WebSearch", "Buscar en internet", "Busca información actualizada en la web."),
    ("WebFetch", "Abrir páginas web", "Lee una página que le indiques."),
)
SKILL_FRIENDLY = {
    "hypit": ("Hacer videos", "Dirige y produce videos de principio a fin."),
}


def list_abilities():
    """Lo que el agente puede hacer, en palabras normales, con su estado.
    Los nombres se pueden cambiar en settings.json (ability_names)."""
    s = load_settings()
    off = set(s.get("disabled_abilities") or [])
    names = s.get("ability_names") or {}
    out = []
    for tool, name, desc in TOOL_ABILITIES:
        key = f"tool:{tool}"
        out.append({"key": key, "name": name, "desc": desc, "on": key not in off})
    base = HOME_DIR / ".claude" / "skills"
    if base.is_dir():
        for folder in sorted(base.iterdir()):
            if not (folder / "SKILL.md").is_file():
                continue
            key = f"skill:{folder.name}"
            custom = names.get(folder.name)
            if isinstance(custom, (list, tuple)) and len(custom) >= 2:
                name, desc = str(custom[0]), str(custom[1])
            elif folder.name in SKILL_FRIENDLY:
                name, desc = SKILL_FRIENDLY[folder.name]
            else:
                name = folder.name.replace("-", " ").replace("_", " ").strip().capitalize()
                desc = "Una habilidad extra que instalaste."
            out.append({"key": key, "name": name, "desc": desc, "on": key not in off})
    return out


def disabled_abilities():
    return set(load_settings().get("disabled_abilities") or [])


def rules_prefix():
    """Lo que va AL PRINCIPIO de cada prompt (Claude, Ollama y APIs): las
    reglas activas del usuario y las habilidades que apago."""
    lines = []
    active = [r["text"] for r in load_rules() if r["on"]]
    if active:
        who = str(load_settings().get("user_name") or "").strip()
        lines.append(f"Reglas de {who}:" if who else "Reglas del usuario:")
        lines += [f"- {t}" for t in active]
    off_skills = [a["name"] for a in list_abilities()
                  if not a["on"] and a["key"].startswith("skill:")]
    if off_skills:
        lines.append("No uses estas habilidades (el usuario las apagó): "
                     + ", ".join(off_skills))
    return ("\n".join(lines) + "\n\n") if lines else ""


# --- conexiones con APIs (urllib, sin librerias nuevas)
API_PROVIDERS = {
    "anthropic": {"label": "Anthropic", "aliases": ("anthropic", "claude", "anthropic api"),
                  "kind": "anthropic", "base": "https://api.anthropic.com/v1",
                  "test": "https://api.anthropic.com/v1/models",
                  "model": "claude-haiku-5-5"},
    "openai": {"label": "OpenAI", "aliases": ("openai", "chatgpt", "openai api"),
               "kind": "openai", "base": "https://api.openai.com/v1",
               "test": "https://api.openai.com/v1/models", "model": "gpt-4o-mini"},
    "gemini": {"label": "Google Gemini", "aliases": ("gemini", "google", "google gemini"),
               "kind": "openai",
               "base": "https://generativelanguage.googleapis.com/v1beta/openai",
               "test": "https://generativelanguage.googleapis.com/v1beta/models",
               "model": "gemini-2.5-flash"},
    "groq": {"label": "Groq", "aliases": ("groq",), "kind": "openai",
             "base": "https://api.groq.com/openai/v1",
             "test": "https://api.groq.com/openai/v1/models",
             "model": "llama-3.1-8b-instant"},
    "openrouter": {"label": "OpenRouter", "aliases": ("openrouter", "open router"),
                   "kind": "openai", "base": "https://openrouter.ai/api/v1",
                   "test": "https://openrouter.ai/api/v1/key",
                   "model": "openai/gpt-4o-mini"},
}
API_PROVIDERS["xai"] = {"label": "Grok (xAI)", "aliases": ("xai", "grok", "x.ai"), "kind": "openai",
                        "base": "https://api.x.ai/v1", "test": "https://api.x.ai/v1/models",
                        "model": "grok-4"}
API_ORDER = ("anthropic", "openai", "gemini", "groq", "openrouter", "xai")


def api_key_for(provider):
    info = API_PROVIDERS.get(provider)
    if not info:
        return ""
    for a in load_apis():
        name = str(a.get("name", "")).strip().lower()
        if a.get("provider") == provider or name in info["aliases"]:
            return str(a.get("key", "")).strip()
    return ""


def api_model_for(provider):
    """Modelo por defecto de cada proveedor (se cambia en settings.json,
    clave api_models)."""
    custom = (load_settings().get("api_models") or {}).get(provider)
    if isinstance(custom, str) and valid_model_name(custom):
        return custom
    return API_PROVIDERS[provider]["model"]


def _api_headers(provider, key):
    h = {"User-Agent": "GrowiBridge", "Content-Type": "application/json"}
    if provider == "anthropic":
        h.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    else:
        # Gemini tambien acepta Bearer en su ruta compatible con OpenAI.
        h["Authorization"] = f"Bearer {key}"
    return h


def _scrub(text, key):
    """Quita cualquier rastro de la clave de un mensaje de error."""
    t = str(text or "")
    if key:
        t = t.replace(key, mask_key(key))
    return re.sub(r"(sk|gsk|AIza|sk-ant|sk-or)[-_A-Za-z0-9]{8,}", r"\1-…", t)


def _http_reason(code):
    return {400: "petición rechazada (400)", 401: "clave rechazada (401)",
            403: "sin permiso (403)", 404: "no encontrado (404)",
            429: "límite de uso alcanzado (429)"}.get(
        code, f"el servicio falló ({code})" if code >= 500 else f"error {code}")


def test_api(provider):
    """Peticion minima real y gratis (listar modelos o ver la clave).
    Devuelve (ok, motivo corto). La clave nunca se muestra ni se registra."""
    info = API_PROVIDERS.get(provider)
    if not info:
        return False, "proveedor desconocido"
    key = api_key_for(provider)
    if not key:
        return False, "falta la clave"
    headers = _api_headers(provider, key)
    if provider == "gemini":
        # La lista de modelos de Gemini es la ruta nativa: clave en cabecera
        # (nunca en la URL, para que no quede en ningun registro).
        headers.pop("Authorization", None)
        headers["x-goog-api-key"] = key
    req = urllib.request.Request(info["test"], headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read(4000)
        return True, "conectada"
    except urllib.error.HTTPError as e:
        return False, _http_reason(e.code)
    except urllib.error.URLError as e:
        return False, _scrub(f"sin conexión ({getattr(e, 'reason', e)})", key)[:120]
    except Exception as e:
        return False, _scrub(f"{type(e).__name__}", key)


def _run_api(task):
    """Motor por API: model 'api:<proveedor>:<modelo>'. OpenAI, Groq,
    OpenRouter y Gemini por /chat/completions (Bearer); Anthropic por
    /v1/messages. Un turno; cost_usd = null (lo cobra el proveedor)."""
    started = _now_iso()
    t0 = time.time()
    _, provider, model = task["model"].split(":", 2)
    info = API_PROVIDERS[provider]
    result = {
        "runner": f"growi-bridge/{VERSION}", "id": task["id"], "status": "error",
        "started_at": started, "finished_at": None, "duration_s": None,
        "exit_code": None, "result": "", "cost_usd": None, "num_turns": 1,
        "session_id": None, "stderr": "", "error": None,
    }
    key = api_key_for(provider)
    if not key:
        result["error"] = f"falta la clave de {info['label']} en APIs"
    else:
        prompt = rules_prefix() + task["prompt"]
        if info["kind"] == "anthropic":
            url = info["base"] + "/messages"
            body = {"model": model, "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]}
        else:
            url = info["base"] + "/chat/completions"
            body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        log(f"runner [{task['id']}]: llamando a {info['label']} ({model})")
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=_api_headers(provider, key), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=task["timeout_min"] * 60) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            if info["kind"] == "anthropic":
                text = "".join(b.get("text", "") for b in data.get("content", [])
                               if isinstance(b, dict))
            else:
                text = data["choices"][0]["message"]["content"] or ""
            result["result"] = str(text)[:MAX_RESULT_CHARS]
            result["status"] = "ok"
            result["exit_code"] = 0
            us = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            tin = us.get("input_tokens", us.get("prompt_tokens"))
            tout = us.get("output_tokens", us.get("completion_tokens"))
            if isinstance(tin, int) or isinstance(tout, int):
                result["uso"] = {"tokens_in": tin or 0, "tokens_out": tout or 0, "modelo_real": model,
                                 "por_modelo": {model: {"tokens_in": tin or 0, "tokens_out": tout or 0,
                                                        "cost_usd": None}},
                                 "fuente": "al cerrar"}
                live_tokens("tarea", model, tin, tout, modo="al cerrar")
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                err = json.loads(e.read().decode("utf-8", "replace"))
                detail = (err.get("error") or {}).get("message", "") \
                    if isinstance(err.get("error"), dict) else str(err.get("error", ""))
            except Exception:
                pass
            result["error"] = _scrub(f"{info['label']}: {_http_reason(e.code)}"
                                     + (f" — {detail[:200]}" if detail else ""), key)
        except urllib.error.URLError as e:
            result["error"] = _scrub(f"{info['label']}: sin conexión ({getattr(e, 'reason', e)})", key)
        except Exception as e:
            result["error"] = _scrub(f"{info['label']}: {type(e).__name__}: {e}", key)[:300]
    result["finished_at"] = _now_iso()
    result["duration_s"] = round(time.time() - t0, 1)
    return result


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


# ---------------------------------------------------------------- carriles
# Carril B: copia de la app en otra carpeta, con su puerto y su cola, para
# trabajo que NO toca los archivos del carril A (verificaciones, documentos,
# prototipos en su carpeta). No es paralelo de codigo: es separacion de
# carpetas con esta guardia. Los carriles no se fusionan solos.
LANE_A_DIR = Path(os.environ.get("GROWI_BRIDGE_LANE_A_DIR") or (HOME_DIR / "growi-bridge"))
LANE_B_MOTORES = ("claude", "codex")  # solo nube: la VRAM es del carril A
LANE_A_ESPERA_MAX_S = 600
LANE_A_STATUS_VIEJO_S = 180


def _lane_norm(path, base=None):
    pth = Path(str(path)).expanduser()
    if not pth.is_absolute():
        pth = Path(base or APP_DIR) / pth
    return os.path.normcase(os.path.abspath(str(pth)))


def _lane_inside(path_n, root):
    root_n = _lane_norm(root)
    try:
        return os.path.commonpath([path_n, root_n]) == root_n
    except ValueError:
        return False


def _lane_b_prohibidos():
    """(archivos, carpetas) que un task del carril B nunca puede tocar."""
    files = [d / n for d in (LANE_A_DIR, APP_DIR)
             for n in ("growi-bridge.py", "runner.py", "engines.json", "settings.json")]
    files.append(LANE_A_DIR / "share" / "inbox" / "runner" / "runner.py")
    dirs = [LANE_A_DIR / "share" / "inbox" / "growi-bridge-app"]
    return files, dirs


def _lane_guard(data):
    """None si el task puede correr en este carril; si no, el motivo exacto."""
    lane = str(data.get("lane") or "").strip().lower()
    if LANE == "a":
        if lane in ("", "a"):
            return None
        return (f'este task trae "lane": "{data.get("lane")}" y este es el carril A '
                f'(puerto {BRIDGE_PORT}); los del carril B van a growi-bridge-lane2 (puerto 8788)')
    if lane != "b":
        return ('carril B: rechazado sin ejecutar: el task no trae "lane": "b"'
                + (f' (trae "lane": "{data.get("lane")}")' if lane else "")
                + '. Este carril solo corre tareas marcadas para él')
    if "ollama_action" in data:
        return ("carril B: rechazado sin ejecutar: pide modelos locales (ollama_action). El "
                "carril B nunca usa llama-server ni ollama: dos modelos locales a la vez en "
                "6 GB de VRAM se pelean la memoria")
    archivos = data.get("archivos")
    if (not isinstance(archivos, list) or not archivos
            or not all(isinstance(a, str) and a.strip() for a in archivos)):
        return ('carril B: rechazado sin ejecutar: falta la lista "archivos" (los archivos que '
                'la tarea va a tocar), o está vacía o no es una lista de rutas')
    files, dirs = _lane_b_prohibidos()
    prohib = {_lane_norm(f) for f in files}
    for a in archivos:
        an = _lane_norm(a.strip())
        if an in prohib or any(_lane_inside(an, d) for d in dirs):
            return (f"carril B: rechazado sin ejecutar: declara {a} en \"archivos\", que está en "
                    "la lista prohibida (growi-bridge.py, runner.py, engines.json, settings.json "
                    "y share\\inbox\\growi-bridge-app del carril A, y el código del propio carril B)")
        if not _lane_inside(an, APP_DIR):
            return (f"carril B: rechazado sin ejecutar: declara {a} en \"archivos\", que está "
                    f"fuera de la carpeta del carril B ({APP_DIR})")
    lee = data.get("lee")
    if lee is not None and (not isinstance(lee, list)
                            or not all(isinstance(x, str) and x.strip() for x in lee)):
        return 'carril B: rechazado sin ejecutar: "lee" debe ser una lista de rutas'
    cwd = _lane_norm(data.get("cwd") or APP_DIR)
    if not _lane_inside(cwd, APP_DIR):
        return (f"carril B: rechazado sin ejecutar: cwd {data.get('cwd')} está fuera de la "
                f"carpeta del carril B ({APP_DIR})")
    return None


def _lane_lee_carril_a(data):
    """True si la tarea declara que lee archivos del carril A."""
    if data.get("lee_carril_a") is True:
        return True
    return any(_lane_inside(_lane_norm(x), LANE_A_DIR) for x in (data.get("lee") or []))


def _lane_a_libre():
    """(libre, detalle) segun runner-status.json del carril A: libre solo con
    current null y un latido reciente (un latido viejo no prueba nada)."""
    path = LANE_A_DIR / "share" / "outbox" / "runner-status.json"
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, f"no pude leer {path} ({type(e).__name__})"
    if st.get("current"):
        cur = st["current"]
        return False, f"el carril A trabaja en {cur.get('id') if isinstance(cur, dict) else cur}"
    try:
        edad = time.time() - datetime.fromisoformat(str(st.get("last_poll"))).timestamp()
    except (TypeError, ValueError):
        return False, "runner-status.json del carril A sin last_poll válido"
    if edad > LANE_A_STATUS_VIEJO_S:
        return False, (f"el latido del carril A tiene {int(edad)} s (más de "
                       f"{LANE_A_STATUS_VIEJO_S} s): no puedo confirmar que esté libre")
    return True, "carril A libre (current null, latido de hace %d s)" % int(edad)


def _lane_b_espera_a(task):
    """Regla de verificacion: si la tarea lee archivos del carril A, espera a
    que el carril A este libre (max. 10 min). None si puede seguir; si no,
    el motivo."""
    if LANE != "b" or not task.get("lee_carril_a"):
        return None
    t0 = time.time()
    while True:
        libre, det = _lane_a_libre()
        if libre:
            log(f"runner [{task['id']}]: {det}; la tarea puede leer el carril A")
            return None
        if time.time() - t0 >= LANE_A_ESPERA_MAX_S:
            return (f"carril B: no se ejecutó: la tarea lee archivos del carril A y el carril A "
                    f"no quedó libre en {LANE_A_ESPERA_MAX_S // 60} min ({det}); no leo archivos "
                    "a mitad de escritura")
        state["paso"] = f"esperando a que el carril A quede libre ({det})"
        log(f"runner [{task['id']}]: espera al carril A: {det}")
        time.sleep(15)


def _lane_snapshot():
    """Huella (tamaño, mtime) de lo prohibido, para avisar si cambió durante
    una tarea del carril B (el carril A también puede cambiarlo: es un aviso)."""
    files, dirs = _lane_b_prohibidos()
    files = [f for f in files if f != APP_DIR / "settings.json"]  # lo escribe la propia app
    snap = {}
    for f in files:
        try:
            st = f.stat()
            snap[str(f)] = (st.st_size, st.st_mtime)
        except OSError:
            snap[str(f)] = None
    for d in dirs:
        try:
            for f in d.iterdir():
                if f.is_file():
                    st = f.stat()
                    snap[str(f)] = (st.st_size, st.st_mtime)
        except OSError:
            pass
    return snap


def validate_task(data):
    if not isinstance(data, dict):
        return None, "el task.json no es un objeto JSON"
    task_id = data.get("id")
    if not _safe_id(task_id):
        return None, "id invalido o ausente (solo letras, numeros, - _ .)"
    lane_err = _lane_guard(data)
    if lane_err:
        return None, lane_err
    if "ollama_action" in data:
        return _validate_model_task(data, task_id)
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None, "prompt vacio o ausente"
    if len(prompt) > MAX_PROMPT_CHARS:
        return None, f"prompt demasiado largo ({len(prompt)} > {MAX_PROMPT_CHARS})"
    cwd_raw = data.get("cwd") or str(APP_DIR if LANE == "b" else INBOX)
    try:
        cwd = Path(cwd_raw).expanduser().resolve()
    except OSError:
        return None, f"cwd invalido: {cwd_raw}"
    if not cwd.is_dir():
        return None, f"cwd no existe o no es carpeta: {cwd}"
    if not _inside_any(cwd, load_folders()):
        return None, f"cwd fuera de las carpetas permitidas: {cwd}"
    # Motor: el campo "motor" (engines.json). Sin el, como antes: model
    # "ollama:<m>" -> motor ollama, "api:..." -> APIs, lo demas -> claude.
    model = data.get("modelo") if data.get("modelo") is not None else data.get("model")
    motor = data.get("motor")
    enrutado = None
    if motor == AUTO or (motor is None and model is None and global_auto()):
        # Modo Automatico: reglas de engines.json -> router ($0, sin modelo).
        crit0 = data.get("criterios")
        crit0 = [crit0] if isinstance(crit0, str) else crit0 if isinstance(crit0, list) else []
        enrutado, err = route_task(prompt, crit0)
        if enrutado:
            data["_enrutado"] = enrutado
        if err:
            return None, err
        motor, model = enrutado["motor"], enrutado.get("modelo")
        log(f"router [{task_id}]: Automático -> {enrutado['motivo']}")
    elif isinstance(data.get("enrutado"), dict) and data["enrutado"].get("elegido"):
        # Ronda o fase de una tarea Automatica: hereda la eleccion, no se re-enruta.
        e = data["enrutado"]
        enrutado = {"elegido": str(e["elegido"])[:40], "motivo": str(e.get("motivo") or "")[:400]}
    if motor is None:
        if isinstance(model, str) and model.startswith("ollama:"):
            motor, model = "ollama", model.split(":", 1)[1]
        elif isinstance(model, str) and model.startswith("api:"):
            motor = "api"
        else:
            motor = str(load_engines()[0].get("por_defecto") or "claude")
    if not isinstance(motor, str) or not _safe_id(motor):
        return None, f"motor invalido: {motor}"
    if LANE == "b" and motor not in LANE_B_MOTORES:
        return None, (f"carril B: rechazado sin ejecutar: el motor '{motor}' no es de nube. El "
                      "carril B solo usa claude o codex; nunca llama-server ni ollama (dos "
                      "modelos locales a la vez en 6 GB de VRAM se pelean la memoria)")
    eng = get_engine(motor)
    if motor != "api" and eng is None:
        return None, (f"el motor '{motor}' no existe en engines.json "
                      f"(hay: {', '.join(engine_ids())})")
    if motor not in ("claude", "api"):
        if model in ("", "default"):
            model = None
        if model is not None and not valid_model_name(model):
            return None, f"modelo no valido para {motor}: {model}"
    if motor == "claude" and model is not None:
        if not isinstance(model, str) or (
            model not in ALLOWED_MODELS and not model.startswith("claude-")
        ):
            return None, f"model no permitido: {model}"
    if motor == "api":
        if not isinstance(model, str) or not model.startswith("api:"):
            return None, "model api invalido: usa api:<proveedor>:<modelo>"
        parts = model.split(":", 2)
        if len(parts) != 3 or parts[1] not in API_PROVIDERS:
            return None, ("model api invalido: usa api:<proveedor>:<modelo> con "
                          "proveedor " + "/".join(API_ORDER))
        if parts[2] in ("", "default"):
            model = f"api:{parts[1]}:{api_model_for(parts[1])}"
        elif not valid_model_name(parts[2]):
            return None, f"modelo de API no valido: {parts[2]}"
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
    por_modo = ((eng or {}).get("permisos") or {}).get("por_modo")
    if isinstance(por_modo, dict) and (permission_mode or "") not in por_modo:
        return None, (f"el motor {motor} no acepta permission_mode={permission_mode} "
                      f"(acepta: {', '.join(k or 'ninguno' for k in por_modo)})")
    session_id = data.get("session_id")
    if session_id is not None and not _safe_id(session_id):
        return None, f"session_id invalido: {session_id}"
    try:
        timeout_min = int(data.get("timeout_min") or (eng or {}).get("timeout_min")
                          or DEFAULT_TIMEOUT_MIN)
    except (TypeError, ValueError):
        return None, "timeout_min debe ser un numero"
    timeout_min = max(1, min(MAX_TIMEOUT_MIN, timeout_min))
    # Orquestacion: criterios de aceptacion, rondas de correccion y fases.
    criterios = data.get("criterios")
    if isinstance(criterios, str):
        criterios = [criterios]
    if criterios is None:
        criterios = []
    if not isinstance(criterios, list) or not all(isinstance(c, str) for c in criterios):
        return None, "criterios debe ser una lista de frases"
    criterios = [c.strip()[:500] for c in criterios if c.strip()][:20]
    try:
        ronda = int(data.get("ronda") or 0)
    except (TypeError, ValueError):
        return None, "ronda debe ser un numero"
    if not 0 <= ronda <= MAX_ROUNDS:
        return None, f"ronda fuera de rango (0 a {MAX_ROUNDS})"
    refs = {}
    for k in ("tarea_padre", "raiz", "fase_base", "fase_anterior"):
        v = data.get(k)
        if v is not None and not _safe_id(v):
            return None, f"{k} invalido: {v}"
        refs[k] = v
    fase = data.get("fase")
    if fase is not None and (not isinstance(fase, str) or len(fase) > 80):
        return None, "fase debe ser un texto corto (p. ej. 'fase 1 de 3')"
    sig = data.get("siguiente_fase")
    if sig is not None:
        sp = sig.get("prompt") if isinstance(sig, dict) else sig
        if not isinstance(sp, str) or not sp.strip() or len(sp) > MAX_PROMPT_CHARS:
            return None, "siguiente_fase debe ser el prompt de la fase siguiente (o {\"prompt\": ...})"
    sensible = data.get("sensible") or []
    if isinstance(sensible, str):
        sensible = [sensible]
    if not isinstance(sensible, list) or not all(s in SENSITIVE for s in sensible):
        return None, f"sensible debe ser una lista de: {', '.join(SENSITIVE)}"
    return {
        "id": task_id, "prompt": prompt, "cwd": str(cwd),
        "model": model if motor in ("claude", "api") else None,
        "motor": motor, "modelo": model if motor != "api" else model,
        "allowed_tools": allowed_tools, "permission_mode": permission_mode,
        "session_id": session_id, "timeout_min": timeout_min,
        "criterios": criterios, "ronda": ronda,
        "tarea_padre": refs["tarea_padre"], "raiz": refs["raiz"] or task_id,
        "fase": fase, "siguiente_fase": sig, "fase_base": refs["fase_base"],
        "fase_anterior": refs["fase_anterior"], "sensible": sensible,
        "revisar": data.get("revisar", True) is not False,
        "enrutado": enrutado,
        "lane": LANE if LANE == "b" else (data.get("lane") or None),
        "archivos": data.get("archivos") if LANE == "b" else None,
        "lee": data.get("lee") if LANE == "b" else None,
        "lee_carril_a": LANE == "b" and _lane_lee_carril_a(data),
    }, None


def _validate_model_task(data, task_id):
    """Task de modelos: {"ollama_action": "pull"|"rm"|"list", "model": ...}.
    No pasa por Claude Code. El modelo pasa la validacion estricta."""
    action = data.get("ollama_action")
    if action not in MODEL_ACTIONS:
        return None, f"ollama_action no permitida: {action} (usa pull, rm o list)"
    model = data.get("model")
    if action in ("pull", "rm"):
        if not valid_model_name(model):
            return None, ("model invalido para ollama_action (solo letras, numeros, "
                          "- _ . / :; sin URLs ni rutas)")
    else:
        model = None
    try:
        timeout_min = int(data.get("timeout_min") or (60 if action == "pull" else 5))
    except (TypeError, ValueError):
        return None, "timeout_min debe ser un numero"
    timeout_min = max(1, min(MAX_TIMEOUT_MIN, timeout_min))
    return {"id": task_id, "ollama_action": action, "model_name": model,
            "model": None, "prompt": "", "cwd": str(INBOX),
            "timeout_min": timeout_min}, None


def run_model_task(task):
    """Ejecuta una accion de modelos y devuelve el resultado en el mismo
    esquema que las tareas de Claude (cost_usd 0.0)."""
    started = _now_iso()
    t0 = time.time()
    action, model = task["ollama_action"], task.get("model_name")
    log(f"runner [{task['id']}]: modelos: ollama {action}{' ' + model if model else ''}")
    ok, out, err = run_model_action(action, model, task["timeout_min"] * 60,
                                    job_id=task["id"])
    if ok and action == "pull":
        ok2, listing, _e = run_model_action("list", timeout_s=60)
        if ok2 and any(_same_model(m["name"], model) for m in parse_ollama_list(listing)):
            out = (out + "\n\nVerificado con ollama list: el modelo ya está instalado.").strip()
        else:
            ok, err = False, "la descarga terminó pero el modelo no aparece en ollama list"
    if ok and action == "rm" and _same_model(default_ollama_model(), model or ""):
        s = load_settings()
        s.pop("ollama_model", None)
        save_settings(s)
        log("modelos: el modelo por defecto se borró; elige otro en Modelos")
    return {
        "runner": f"growi-bridge/{VERSION}", "id": task["id"],
        "status": "ok" if ok else "error", "started_at": started,
        "finished_at": _now_iso(), "duration_s": round(time.time() - t0, 1),
        "exit_code": 0 if ok else 1, "result": (out or "")[:MAX_RESULT_CHARS],
        "cost_usd": 0.0, "num_turns": 0, "session_id": None, "stderr": "",
        "error": err, "ollama_action": action, "model": model,
    }


# ---------------------------------------------------------------- motores (engines.json)
# Un corredor, muchos motores: cada task elige su motor con "motor" (por
# defecto "claude"). engines.json dice como se lanza cada uno, como se le
# pasa el modelo, como se reanuda la sesion y como se lee el resultado. El
# resultado es el MISMO para todos (id, status, started_at, finished_at,
# duration_s, exit_code, result, cost_usd, num_turns, session_id, stderr,
# error). Modo seguro: ningun motor lleva bypassPermissions ni --yolo por
# defecto; los permisos los pide cada tarea.
ENGINES_FILE = APP_DIR / "engines.json"
SESSIONS_DIR = APP_DIR / "sesiones"  # historial de los motores sin sesion propia
WAITING = TASKS / "esperando"        # tareas que esperan tu aprobacion
MAX_ROUNDS = 3
LOCAL_HOSTS = ("127.0.0.1", "localhost")
_PH_RE = re.compile(r"\{(\w+)\}")
# Si falta engines.json o esta roto, el runner sigue con Claude como antes.
_FALLBACK_ENGINES = {
    "por_defecto": "claude",
    "revision": {"orden": [{"motor": "claude", "modelo": "haiku",
                            "allowed_tools": "Read,Glob,Grep"}], "max_rondas": MAX_ROUNDS},
    "motores": {"claude": {
        "nombre": "Claude", "tipo": "cli_sincrono", "binario": "claude",
        "comando": ["{binario}", "-p", "{prompt}", "--output-format", "json"],
        "prompt_por": "argumento",
        "modelo": {"opcional": ["--model", "{modelo}"], "por_defecto": None},
        "sesion": {"tipo": "nativa", "opcional": ["--resume", "{session_id}"]},
        "permisos": {"opcionales": [["--allowedTools", "{allowed_tools}"],
                                    ["--disallowedTools", "{disallowed_tools}"],
                                    ["--permission-mode", "{permission_mode}"]]},
        "salida": {"formato": "json", "texto": "result",
                   "costo": ["total_cost_usd", "cost_usd"], "turnos": "num_turns",
                   "sesion": "session_id", "error_si": "is_error"},
        "timeout_min": DEFAULT_TIMEOUT_MIN, "entorno": {}, "healthcheck": {"tipo": "binario"}}},
}
_eng_cache = {"mtime": None, "data": None, "err": None}
# Lo que esta corriendo ahora (para el boton Parar, que lo mata de verdad).
_RUN = {"proc": None, "conn": None, "stop": False, "id": None}
# Procesos que lanzo la app (pid -> (quien lo lanzo, hora)), para la pestana
# Recursos.
_LAUNCHED = {}


# ---- consumo en vivo (outbox/runner-live.json)
# Mientras una tarea corre, el hilo lector del motor va sumando lo que
# reporta el propio motor (tokens de cada mensaje) y el archivo se reescribe
# cada ~5 s. Es la unica fuente de verdad en vivo: la ventana lo lee, no
# calcula nada por su cuenta. Nunca se inventan numeros: si el motor no
# reporta uso, el vivo queda 'sin vivo' y solo cuenta el tiempo.
LIVE_FILE = OUTBOX / "runner-live.json"
LIVE_EVERY_S = 5
_LIVE_LOCK = threading.RLock()
_LIVE = {"d": None, "written": 0.0, "t0": 0.0, "acc": {}, "rol": "tarea"}
_HB = {"t": 0.0}
_STATUS_LOCK = threading.Lock()


def _price_table():
    p = load_engines()[0].get("precios")
    return p if isinstance(p, dict) else {}


def _price_for(model):
    """Precio por token a precio de lista de cada tipo de token, o None si
    engines.json no tiene precio para ese modelo."""
    tab = _price_table()
    pm = tab.get("por_millon") or {}
    m = str(model or "")
    m = (tab.get("alias") or {}).get(m, m)
    e = pm.get(m)
    if not isinstance(e, dict):
        for fam in ("opus", "sonnet", "haiku"):
            if fam in m.lower():
                e = next((v for k, v in pm.items() if fam in k and isinstance(v, dict)), None)
                break
    try:
        f = _price_table().get("factores") or {}
        pin = float(e["entrada"]) / 1e6
        own = {k: e.get(k) for k in ("cache_lectura", "cache_escritura_5m", "cache_escritura_1h")}
        return {"input": pin, "output": float(e["salida"]) / 1e6,
                "cache_read": float(own["cache_lectura"]) / 1e6 if own["cache_lectura"] is not None
                else pin * float(f.get("cache_lectura", 0.1)),
                "cache_5m": float(own["cache_escritura_5m"]) / 1e6 if own["cache_escritura_5m"] is not None
                else pin * float(f.get("cache_escritura_5m", 1.25)),
                "cache_1h": float(own["cache_escritura_1h"]) / 1e6 if own["cache_escritura_1h"] is not None
                else pin * float(f.get("cache_escritura_1h", 2.0))}
    except (TypeError, KeyError, ValueError):
        return None


def estimate_cost(model, u):
    """Costo a precio de lista de un uso normalizado (ver _usage_norm), o
    None si no hay precio para el modelo."""
    pr = _price_for(model)
    if pr is None:
        return None
    return sum(u.get(k, 0) * pr[k] for k in ("input", "cache_5m", "cache_1h", "cache_read", "output"))


def _usage_norm(us):
    """usage de Anthropic/Claude Code -> {input, cache_5m, cache_1h,
    cache_read, output}."""
    us = us if isinstance(us, dict) else {}
    cc = us.get("cache_creation") if isinstance(us.get("cache_creation"), dict) else {}
    total_cc = int(us.get("cache_creation_input_tokens") or 0)
    c1h = int(cc.get("ephemeral_1h_input_tokens") or 0)
    c5m = int(cc.get("ephemeral_5m_input_tokens") or 0)
    if total_cc and not (c1h or c5m):
        c5m = total_cc
    return {"input": int(us.get("input_tokens") or 0), "cache_5m": c5m, "cache_1h": c1h,
            "cache_read": int(us.get("cache_read_input_tokens") or 0),
            "output": int(us.get("output_tokens") or 0), "_split": bool(c1h or c5m) and bool(cc)}


def _merge_usage(prev, u):
    """Mismo mensaje visto dos veces (inicio y final): el mayor de cada campo.
    El final (message_delta) no trae el desglose de cache 5 min / 1 h: se
    conserva el del que si lo trajo, para no contar la cache dos veces."""
    out = {k: max(int(prev.get(k, 0)), int(u.get(k, 0))) for k in ("input", "cache_read", "output")}
    total = max(prev.get("cache_5m", 0) + prev.get("cache_1h", 0), u.get("cache_5m", 0) + u.get("cache_1h", 0))
    src = u if u.get("_split") else prev if prev.get("_split") else None
    c1h = min(src.get("cache_1h", 0), total) if src else 0
    out.update(cache_1h=c1h, cache_5m=total - c1h, _split=bool(src))
    return out


def _tok_in(u):
    return u.get("input", 0) + u.get("cache_5m", 0) + u.get("cache_1h", 0) + u.get("cache_read", 0)


def _live_dinero(motor_id, model=None):
    """real (API con tu clave) / equiv (sesion Max, a precio de lista) /
    local ($0) / otro."""
    return _money_kind({"motor": motor_id, "modelo": model or ""}, _claude_plan())


def _live_blank(motor_id, modelo):
    return {"motor": motor_id, "modelo": modelo, "modelo_real": None,
            "tokens_in": 0, "tokens_out": 0, "cost_usd_estimado": None,
            "cost_usd_final": None, "modo_vivo": "esperando", "por_modelo": {},
            "dinero": _live_dinero(motor_id, modelo)}


def live_start(task, motor_id, modelo):
    """Empieza el vivo de una tarea (estado 'en curso')."""
    with _LIVE_LOCK:
        d = {"task_id": task["id"], "raiz": task.get("raiz") or task["id"],
             "estado": "en curso", "started_at": _now_iso(), "elapsed_s": 0,
             "ronda": task.get("ronda", 0), "tarea_padre": task.get("tarea_padre"),
             "revision": None, "nota": None}
        d.update(_live_blank(motor_id, modelo))
        if d["dinero"] == "local":
            d["cost_usd_estimado"] = 0.0
        _LIVE.update(d=d, t0=time.time(), acc={"tarea": {}, "revision": {}}, rol="tarea", written=0.0)
    live_write(force=True)


def _live_part(rol):
    d = _LIVE["d"]
    if d is None:
        return None
    if rol == "revision":
        return d.get("revision")
    return d


def live_set(rol="tarea", **kw):
    with _LIVE_LOCK:
        part = _live_part(rol)
        if part is not None:
            part.update(kw)
    live_write()


def live_review_start(motor_id, modelo):
    """La revision corre aparte: sus tokens no se mezclan con los de la tarea."""
    with _LIVE_LOCK:
        d = _LIVE["d"]
        if d is None:
            return
        d["estado"] = "revisando"
        d["revision"] = _live_blank(motor_id, modelo)
        if d["revision"]["dinero"] == "local":
            d["revision"]["cost_usd_estimado"] = 0.0
        _LIVE["acc"]["revision"] = {}
    live_write(force=True)


def _live_recalc(rol):
    """Totales desde lo acumulado por mensaje (cada mensaje cuenta una vez)."""
    part = _live_part(rol)
    if part is None:
        return
    msgs = _LIVE["acc"].get(rol) or {}
    por, tin, tout, cost, sin_precio = {}, 0, 0, 0.0, False
    local = part.get("dinero") == "local"
    for model, u in msgs.values():
        b = por.setdefault(model or "?", {"tokens_in": 0, "tokens_out": 0, "cost_usd_estimado": 0.0})
        b["tokens_in"] += _tok_in(u)
        b["tokens_out"] += u.get("output", 0)
        tin += _tok_in(u)
        tout += u.get("output", 0)
        c = 0.0 if local else estimate_cost(model, u)
        if c is None:
            sin_precio = True
            b["cost_usd_estimado"] = None
        else:
            cost += c
            if b["cost_usd_estimado"] is not None:
                b["cost_usd_estimado"] = round(b["cost_usd_estimado"] + c, 6)
    part.update(tokens_in=tin, tokens_out=tout, por_modelo=por,
                cost_usd_estimado=None if sin_precio else round(cost, 6))


def live_msg(rol, key, model, u):
    """Uso de un mensaje del motor (el mismo mensaje puede llegar varias
    veces: se queda el mayor de cada campo)."""
    with _LIVE_LOCK:
        part = _live_part(rol)
        if part is None:
            return
        acc = _LIVE["acc"].setdefault(rol, {})
        prev = acc.get(key)
        if prev is not None:
            model = model or prev[0]
            u = _merge_usage(prev[1], u)
        acc[key] = (model, u)
        if model:
            part["modelo_real"] = model
        part["modo_vivo"] = "en vivo"
        _live_recalc(rol)
    live_write()


def live_tokens(rol, model, tin, tout, modo="en vivo"):
    """Motores locales/API: totales directos (los locales cuestan $0)."""
    with _LIVE_LOCK:
        part = _live_part(rol)
        if part is None:
            return
        part.update(tokens_in=int(tin or 0), tokens_out=int(tout or 0), modo_vivo=modo)
        if model:
            part["modelo_real"] = model
            part["por_modelo"] = {model: {"tokens_in": int(tin or 0), "tokens_out": int(tout or 0),
                                          "cost_usd_estimado": part.get("cost_usd_estimado")}}
    live_write()


def live_final(rol, cost_final, uso=None):
    """Cierra los numeros de la tarea (o de la revision) con lo que reporto
    el motor al terminar. cost_final None = el motor no dio costo."""
    with _LIVE_LOCK:
        part = _live_part(rol)
        if part is None:
            return
        if isinstance(uso, dict) and (uso.get("tokens_in") or uso.get("tokens_out")):
            part["tokens_in"], part["tokens_out"] = uso.get("tokens_in", 0), uso.get("tokens_out", 0)
            if uso.get("por_modelo"):
                part["por_modelo"] = uso["por_modelo"]
            if uso.get("modelo_real"):
                part["modelo_real"] = uso["modelo_real"]
        if isinstance(cost_final, (int, float)):
            part["cost_usd_final"] = round(float(cost_final), 6)
        elif part.get("dinero") == "local":
            part["cost_usd_final"] = 0.0
    live_write(force=True)


def live_finish(nota=None):
    with _LIVE_LOCK:
        d = _LIVE["d"]
        if d is None:
            return
        d["estado"] = "terminado"
        if nota:
            d["nota"] = nota
    live_write(force=True)


def live_write(force=False):
    """Escribe runner-live.json (como mucho cada ~5 s salvo force)."""
    with _LIVE_LOCK:
        d = _LIVE["d"]
        if d is None or (not force and time.time() - _LIVE["written"] < LIVE_EVERY_S):
            return
        if d.get("estado") != "terminado":
            d["elapsed_s"] = round(time.time() - _LIVE["t0"], 1)
        d["actualizado"] = _now_iso()
        _LIVE["written"] = time.time()
        text = json.dumps(d, ensure_ascii=False, indent=2)
        try:
            OUTBOX.mkdir(parents=True, exist_ok=True)
            tmp = LIVE_FILE.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            for i in range(5):
                try:
                    os.replace(tmp, LIVE_FILE)
                    break
                except PermissionError:  # alguien lo esta leyendo en ese instante
                    time.sleep(0.1 * (i + 1))
        except OSError:
            pass


def read_live():
    """Lo que hay en runner-live.json (o None)."""
    try:
        d = json.loads(LIVE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _uso_from_result_event(ev):
    """Del mensaje final de Claude Code: tokens totales y por modelo."""
    u = _usage_norm(ev.get("usage"))
    por = {}
    for m, mu in (ev.get("modelUsage") or {}).items():
        if not isinstance(mu, dict):
            continue
        por[m] = {"tokens_in": int(mu.get("inputTokens") or 0) + int(mu.get("cacheReadInputTokens") or 0)
                  + int(mu.get("cacheCreationInputTokens") or 0),
                  "tokens_out": int(mu.get("outputTokens") or 0),
                  "cost_usd": mu.get("costUSD") if isinstance(mu.get("costUSD"), (int, float)) else None}
    tin, tout = _tok_in(u), u["output"]
    if por and not (tin or tout):
        tin = sum(v["tokens_in"] for v in por.values())
        tout = sum(v["tokens_out"] for v in por.values())
    main = max(por, key=lambda k: por[k]["tokens_out"] + por[k]["tokens_in"]) if por else None
    if not (tin or tout or por):
        return None
    return {"tokens_in": tin, "tokens_out": tout, "modelo_real": main, "por_modelo": por,
            "detalle": {k: v for k, v in u.items() if not k.startswith("_")}}


def _track_launch(proc, who):
    try:
        _LAUNCHED[proc.pid] = (who, time.time())
        if len(_LAUNCHED) > 200:
            _LAUNCHED.pop(next(iter(_LAUNCHED)), None)
    except Exception:
        pass


_llama_lock = threading.Lock()
_FAM_LOCK = threading.Lock()


def _ensure_no_proxy(env=None):
    """127.0.0.1 nunca va por el proxy: en este PC hay un proxy local que
    intercepta localhost y devuelve un 500 falso."""
    env = os.environ if env is None else env
    for k in ("NO_PROXY", "no_proxy"):
        cur = [x.strip() for x in (env.get(k) or "").split(",") if x.strip()]
        for h in LOCAL_HOSTS:
            if h not in cur:
                cur.append(h)
        env[k] = ",".join(cur)
    return env


_ensure_no_proxy()


def load_engines():
    """(config, aviso). Relee engines.json solo si cambio."""
    try:
        mt = ENGINES_FILE.stat().st_mtime
    except OSError:
        mt = None
    if _eng_cache["data"] is not None and mt == _eng_cache["mtime"]:
        return _eng_cache["data"], _eng_cache["err"]
    data, err = _FALLBACK_ENGINES, None
    if mt is None:
        err = "falta engines.json junto a growi-bridge.py: solo está Claude"
    else:
        try:
            raw = json.loads(ENGINES_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not isinstance(raw.get("motores"), dict):
                raise ValueError("falta la sección 'motores'")
            data = raw
        except (OSError, ValueError) as e:
            err = f"engines.json no se pudo leer ({e}): solo está Claude"
    if err and err != _eng_cache["err"]:
        log(f"motores AVISO: {err}")
    _eng_cache.update(mtime=mt, data=data, err=err)
    return data, err


def get_engine(motor_id):
    eng = (load_engines()[0].get("motores") or {}).get(motor_id)
    return eng if isinstance(eng, dict) else None


def engine_ids():
    return [k for k in (load_engines()[0].get("motores") or {}) if not k.startswith("_")]


def _app_path(p):
    p = Path(str(p or ""))
    return p if p.is_absolute() else APP_DIR / p


def _fill(obj, vars_):
    """Rellena {prompt}, {modelo}... en una plantilla de engines.json. Un
    texto que es solo "{x}" se cambia por el valor tal cual (lista, dict)."""
    if isinstance(obj, str):
        m = _PH_RE.fullmatch(obj)
        if m and m.group(1) in vars_:
            return vars_[m.group(1)]
        return _PH_RE.sub(lambda mm: str(vars_[mm.group(1)])
                          if mm.group(1) in vars_ and not isinstance(vars_[mm.group(1)], (list, dict))
                          else mm.group(0), obj)
    if isinstance(obj, list):
        return [_fill(x, vars_) for x in obj]
    if isinstance(obj, dict):
        return {k: _fill(v, vars_) for k, v in obj.items() if not str(k).startswith("_")}
    return obj


def _get_path(data, path):
    """'choices.0.message.content' -> data['choices'][0]['message']['content']."""
    cur = data
    for part in str(path or "").split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _deep_merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _engine_env(eng):
    env = dict(os.environ)
    for k, v in (eng.get("entorno") or {}).items():
        if k not in ("NO_PROXY", "no_proxy"):
            env[str(k)] = str(v)
    return _ensure_no_proxy(env)


def _resolve_binary(eng):
    """Ruta del binario como lista de argumentos. Un .cmd de npm (codex) se
    lanza con node + su script: un .cmd con argumentos pasaria por cmd.exe,
    y un prompt con & o | podria colarse como comando."""
    exe = shutil.which(str(eng.get("binario") or ""))
    if not exe:
        return None
    if exe.lower().endswith((".cmd", ".bat")):
        node = shutil.which("node")
        script = Path(exe).parent / str(eng.get("script_npm") or "")
        if node and eng.get("script_npm") and script.is_file():
            return [node, str(script)]
        return None
    return [exe]


def _named_api_key(name):
    name = str(name or "").strip().lower()
    for a in load_apis():
        if str(a.get("name", "")).strip().lower() == name or a.get("provider") == name:
            return str(a.get("key", "")).strip()
    return ""


# ---- llamadas HTTP a 127.0.0.1 (llama-server, Ollama)
class LocalCallError(Exception):
    """Fallo de una llamada local, con el motivo dicho claro (proxy,
    codificacion, servidor apagado...)."""


def _explain_local_error(code, headers, data, text, where):
    hdrs = {k.lower(): v for k, v in headers}
    msg = ""
    if isinstance(data, dict):
        e = data.get("error")
        msg = str(e.get("message", "")) if isinstance(e, dict) else str(e or data.get("message") or "")
    proxyish = (any(h in hdrs for h in ("via", "proxy-agent", "proxy-connection", "x-proxy-id"))
                or "proxy" in (hdrs.get("server", "") + text[:300]).lower())
    loading = code == 503 and "loading" in msg.lower()
    if code == 407 or (code in (500, 502, 503, 504) and not loading and (data is None or proxyish)):
        why = "trae cabeceras de proxy" if proxyish else "no es la respuesta JSON del motor"
        return (f"PROXY: {where} respondió {code} y la respuesta {why} ({text[:120]!r}). "
                "La llamada iba directa y con NO_PROXY=127.0.0.1: algo en este PC intercepta "
                "127.0.0.1 (el proxy local).")
    if code == 400 and any(w in (msg + text).lower() for w in
                           ("json", "utf", "parse", "decode", "unicode", "codec", "invalid")):
        return (f"CODIFICACIÓN: {where} rechazó el JSON (400: {(msg or text)[:160]}). El cuerpo se "
                "mandó en UTF-8; revisa caracteres raros en el prompt.")
    if loading:
        return f"{where} todavía está cargando el modelo (503)"
    return f"{where} respondió {code}: {(msg or text)[:200]}"


def _http_local(method, url, body=None, timeout=60, track=False):
    """GET/POST a 127.0.0.1 sin proxy (http.client no usa ningun proxy y
    ademas NO_PROXY=127.0.0.1) y con el JSON en UTF-8. Devuelve el JSON."""
    import http.client
    u = urlparse(url)
    host, port = u.hostname or "", u.port or 80
    if host not in LOCAL_HOSTS:
        raise LocalCallError(f"{url} no es una dirección local")
    where = f"{host}:{port}"
    _ensure_no_proxy()
    headers = {"Accept": "application/json", "User-Agent": "GrowiBridge"}
    payload = None
    if body is not None:
        text = json.dumps(body, ensure_ascii=False)
        # surrogates sueltos (texto pegado roto) no son UTF-8: se cambian por
        # '?' en vez de mandar bytes que el servidor rechazaria con un 400.
        payload = text.encode("utf-8", "replace")
        headers["Content-Type"] = "application/json; charset=utf-8"
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    if track:
        _RUN["conn"] = conn
    try:
        try:
            conn.request(method, u.path + (("?" + u.query) if u.query else ""),
                         body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
        except ConnectionRefusedError:
            raise LocalCallError(f"no responde: nada escucha en {where} (servidor apagado)")
        except TimeoutError:
            raise LocalCallError(f"sin respuesta de {where} en {timeout:.0f} s")
        except (OSError, http.client.HTTPException) as e:
            if _RUN.get("stop"):
                raise LocalCallError("parado por el usuario (se cortó la conexión con el motor)")
            raise LocalCallError(f"conexión cortada con {where} ({type(e).__name__}: {e})")
    finally:
        if track:
            _RUN["conn"] = None
        conn.close()
    text = raw.decode("utf-8", "replace")
    try:
        data = json.loads(text) if text.strip() else None
    except ValueError:
        data = None
    if 200 <= resp.status < 300:
        if data is None:
            raise LocalCallError(f"PROXY: {where} respondió {resp.status} pero sin JSON "
                                 f"({text[:120]!r}); ¿el proxy local en medio?")
        return data
    raise LocalCallError(_explain_local_error(resp.status, resp.getheaders(), data, text, where))


class _NoStream(Exception):
    """El servidor no contesto en streaming: se repite sin streaming."""


def _first_num(data, paths):
    for p in paths if isinstance(paths, list) else [paths]:
        v = _get_path(data, p) if p else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return int(v)
    return None


def _http_local_stream(url, body, timeout, vivo, on_piece):
    """POST en streaming a 127.0.0.1 (SSE de llama-server o NDJSON de
    Ollama). Llama on_piece(n_trozos) segun llegan. Devuelve (texto,
    tokens_entrada, tokens_salida); los tokens son los que el servidor
    reporta al final (None si no los reporta)."""
    import http.client
    u = urlparse(url)
    host, port = u.hostname or "", u.port or 80
    if host not in LOCAL_HOSTS:
        raise LocalCallError(f"{url} no es una dirección local")
    where = f"{host}:{port}"
    _ensure_no_proxy()
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8", "replace")
    headers = {"Accept": "text/event-stream, application/x-ndjson, application/json",
               "User-Agent": "GrowiBridge", "Content-Type": "application/json; charset=utf-8"}
    fmt = vivo.get("formato", "sse")
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    _RUN["conn"] = conn
    parts, n, tin, tout, deadline = [], 0, None, None, time.time() + timeout
    try:
        try:
            conn.request("POST", u.path + (("?" + u.query) if u.query else ""),
                         body=payload, headers=headers)
            resp = conn.getresponse()
            if not 200 <= resp.status < 300:
                raw = resp.read()
                text = raw.decode("utf-8", "replace")
                try:
                    data = json.loads(text) if text.strip() else None
                except ValueError:
                    data = None
                raise LocalCallError(_explain_local_error(resp.status, resp.getheaders(), data,
                                                          text, where))
            while True:
                if time.time() > deadline:
                    raise LocalCallError(f"sin respuesta completa de {where} en {timeout:.0f} s")
                line = resp.readline()
                if not line:
                    break
                s = line.decode("utf-8", "replace").strip()
                if not s:
                    continue
                if fmt == "sse":
                    if not s.startswith("data:"):
                        continue
                    s = s[5:].strip()
                    if s == "[DONE]":
                        break
                try:
                    obj = json.loads(s)
                except ValueError:
                    if not n:
                        raise _NoStream(s[:120])
                    continue
                if not isinstance(obj, dict):
                    continue
                if obj.get("error"):
                    e = obj["error"]
                    raise LocalCallError(f"{where} dijo: "
                                         + str(e.get("message", e) if isinstance(e, dict) else e)[:200])
                piece = _get_path(obj, vivo.get("trozo"))
                if isinstance(piece, str) and piece:
                    parts.append(piece)
                    n += 1
                    on_piece(n)
                tin = _first_num(obj, vivo.get("uso_in")) or tin
                tout = _first_num(obj, vivo.get("uso_out")) or tout
                if vivo.get("fin") and obj.get(vivo["fin"]) is True:
                    break
        except ConnectionRefusedError:
            raise LocalCallError(f"no responde: nada escucha en {where} (servidor apagado)")
        except TimeoutError:
            raise LocalCallError(f"sin respuesta de {where} en {timeout:.0f} s")
        except (OSError, http.client.HTTPException) as e:
            if _RUN.get("stop"):
                raise LocalCallError("parado por el usuario (se cortó la conexión con el motor)")
            raise LocalCallError(f"conexión cortada con {where} ({type(e).__name__}: {e})")
    finally:
        _RUN["conn"] = None
        conn.close()
    if not n and tin is None and tout is None:
        raise _NoStream("sin trozos")
    return "".join(parts), tin, tout


def _health(eng, timeout=2):
    hc = (eng.get("healthcheck") or {}).get("url")
    if not hc:
        return False, "engines.json no dice cómo comprobarlo"
    try:
        _http_local("GET", hc, timeout=timeout)
        return True, ""
    except LocalCallError as e:
        return False, str(e)


def _llama_installed(eng):
    srv = eng.get("servidor") or {}
    exe, gguf = _app_path(srv.get("exe")), _app_path(srv.get("gguf"))
    if srv.get("exe") and srv.get("gguf") and exe.is_file() and gguf.is_file():
        return True, ""
    falta = []
    if not exe.is_file():
        falta.append(f"falta {exe}")
    if not gguf.is_file():
        falta.append(f"falta {gguf}")
    return False, ("llama-server no está instalado (" + "; ".join(falta) + "). "
                   + str(srv.get("como_instalar") or ""))


def _llama_ensure(eng):
    """Si llama-server no responde, lo arranca oculto con el exe y el GGUF de
    engines.json (los de growi-bridge) y espera a que cargue el modelo."""
    ok, why = _health(eng)
    if ok:
        return True, ""
    inst, msg = _llama_installed(eng)
    if not inst:
        return False, msg
    srv = eng["servidor"]
    with _llama_lock:
        ok, why = _health(eng)
        if ok:
            return True, ""
        exe, gguf = _app_path(srv["exe"]), _app_path(srv["gguf"])
        args = [str(exe)] + [str(a).replace("{gguf}", str(gguf)) for a in srv.get("args") or []]
        logp = _app_path(srv.get("log") or "llama/llama-server.log")
        state["paso"] = "Arrancando llama-server (Hermes 3 directo)…"
        log(f"motores: llama-server no respondía ({why}); lo arranco oculto: {exe.name} -m {gguf.name}")
        t0 = time.time()
        try:
            logf = open(logp, "ab")
            proc = subprocess.Popen(
                args, cwd=str(exe.parent), stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                env=_engine_env(eng),
                creationflags=_NO_WINDOW | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            logf.close()
            _track_launch(proc, "runner: motor Hermes directo (llama-server)")
        except OSError as e:
            return False, f"no se pudo arrancar llama-server ({e})"
        wait_s = float(srv.get("espera_s") or 180)
        while time.time() - t0 < wait_s:
            if proc.poll() is not None:
                tail = ""
                try:
                    tail = logp.read_text(encoding="utf-8", errors="replace")[-400:]
                except OSError:
                    pass
                return False, f"llama-server se cerró al arrancar (código {proc.returncode}): {tail}"
            if _RUN.get("stop"):
                return False, "parado por el usuario mientras arrancaba llama-server"
            ok, why = _health(eng, timeout=2)
            if ok:
                secs = round(time.time() - t0, 1)
                note = f"llama-server no respondía en el puerto 8080; el runner lo arrancó solo (pid {proc.pid}, listo en {secs} s)"
                state["llama_autostart"] = f"{_now_iso()}: {note}"
                log(f"motores: {note}")
                return True, note
            time.sleep(1)
        return False, f"llama-server arrancó (pid {proc.pid}) pero no respondió en {wait_s:.0f} s: {why}"


def _ollama_wake(eng):
    """Ollama apagado: `ollama list` despierta su servidor de fondo."""
    exe = ollama_exe()
    if not exe:
        return
    try:
        _run_capture([exe, "list"], 60)
    except Exception:
        pass


def engine_status(motor_id, autostart=False):
    """(disponible, motivo en palabras normales)."""
    eng = get_engine(motor_id)
    if eng is None:
        return False, f"el motor '{motor_id}' no existe en engines.json"
    tipo = eng.get("tipo")
    if tipo == "cli_sincrono":
        b = _resolve_binary(eng)
        return (True, f"binario: {b[-1]}") if b else (
            False, f"no está instalado: no encuentro '{eng.get('binario')}' en el PATH")
    if tipo == "api_sincrona":
        if eng.get("servidor"):
            if autostart:
                return _llama_ensure(eng)
            ok, why = _health(eng)
            if ok:
                return True, "responde"
            inst, msg = _llama_installed(eng)
            return (True, "apagado; se arranca solo al usarlo") if inst else (False, msg)
        ok, why = _health(eng)
        if not ok and autostart and motor_id == "ollama":
            _ollama_wake(eng)
            ok, why = _health(eng, timeout=5)
        return (True, "responde") if ok else (False, why)
    if tipo == "api_asincrona":
        return (True, "clave guardada") if _named_api_key(eng.get("clave_api")) else (
            False, f"falta la clave en APIs (ponle de nombre '{eng.get('clave_api')}')")
    return False, f"tipo de motor desconocido en engines.json: {tipo}"


def engines_summary():
    out = {}
    for mid in engine_ids():
        ok, why = engine_status(mid)
        out[mid] = {"disponible": ok, "motivo": why}
    return out


# ---- modo Automatico: elige el motor con reglas de engines.json -> router
# Sin llamar a ningun modelo: cuesta $0 y no anade espera.
AUTO = "auto"
AUTO_LABEL = "Automático (recomendado)"


def _router_cfg():
    r = load_engines()[0].get("router")
    return r if isinstance(r, dict) else {}


def global_auto():
    """En Ajustes > Modelos esta elegido Automatico."""
    return load_settings().get("motor") == AUTO


def _num(v, default=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _kw_hit(norm_text, words):
    """Primera palabra clave que aparece (sin tildes ni mayusculas).
    'depur*' = cualquier palabra que empiece por depur."""
    for w in words or []:
        k = _norm(w).strip()
        pref = k.endswith("*")
        k = k.rstrip("*").strip()
        if not k:
            continue
        pat = ((r"(?<!\w)" if k[0].isalnum() else "") + re.escape(k)
               + ("" if pref or not k[-1].isalnum() else r"(?!\w)"))
        if re.search(pat, norm_text):
            return w
    return None


def _looks_like_code(prompt, cfg):
    for p in cfg.get("patrones_codigo") or []:
        try:
            if re.search(str(p), prompt, re.M):
                return True
        except re.error:
            continue
    return False


def _n_partes(prompt):
    items = len(re.findall(r"^\s*(?:[-*•]|\d+[.)])\s+\S", prompt, re.M))
    return max(items, prompt.count("?"))


def _router_conds(cond, ctx):
    """(encaja, por que). Todas las condiciones del bloque deben cumplirse."""
    why = []
    for k, v in (cond or {}).items():
        if str(k).startswith("_"):
            continue
        if k == "palabras":
            hit = _kw_hit(ctx["norm"], v)
            if not hit:
                return False, []
            why.append(f"«{hit}»")
        elif k == "sin_palabras":
            if _kw_hit(ctx["norm"], v):
                return False, []
        elif k == "min_chars":
            if ctx["chars"] < _num(v):
                return False, []
            why.append(f"{ctx['chars']} letras")
        elif k == "max_chars":
            if ctx["chars"] > _num(v):
                return False, []
            why.append(f"{ctx['chars']} letras")
        elif k == "codigo":
            if ctx["codigo"] != bool(v):
                return False, []
            why.append("parece código" if v else "sin código")
        elif k == "min_partes":
            if ctx["partes"] < _num(v):
                return False, []
            why.append(f"{ctx['partes']} partes")
        elif k == "min_criterios":
            if ctx["criterios"] < _num(v):
                return False, []
            why.append(f"{ctx['criterios']} criterios")
        else:
            log(f"router AVISO: condición desconocida '{k}' en engines.json; esa regla no encaja")
            return False, []
    return True, why


def _router_available(motor_id):
    """Disponible para elegirlo, sin esperar: un motor que se arranca solo
    (llama) cuenta si esta instalado; preguntarle a un puerto apagado tarda
    2 s en Windows y el runner lo enciende al usarlo."""
    eng = get_engine(motor_id)
    if eng and eng.get("tipo") == "api_sincrona" and eng.get("servidor"):
        inst, msg = _llama_installed(eng)
        return (True, "instalado") if inst else (False, msg)
    return engine_status(motor_id)


def route_task(prompt, criterios=None):
    """Modo Automatico. ({elegido, motor, modelo, motivo, regla}, None) o
    (info_parcial, error). Primera regla que encaja gana; luego sube un
    escalon si la tarea es exigente; luego mira que el motor este disponible."""
    cfg = _router_cfg()
    targets = {k: v for k, v in (cfg.get("objetivos") or {}).items()
               if isinstance(v, dict) and not str(k).startswith("_")}
    if not targets:
        return None, ("Automático: engines.json no tiene la sección router.objetivos; "
                      "elige un motor a mano o añade el router")
    prompt = str(prompt or "")
    crits = [c for c in (criterios or []) if isinstance(c, str) and c.strip()]
    ctx = {"norm": _norm(prompt), "chars": len(prompt.strip()), "codigo": _looks_like_code(prompt, cfg),
           "partes": _n_partes(prompt), "criterios": len(crits)}
    pick = str(cfg.get("por_defecto") or "sonnet")
    motivo, regla, no_subir = "ninguna regla encaja: el de por defecto", None, False
    for r in cfg.get("reglas") or []:
        if not isinstance(r, dict) or r.get("objetivo") not in targets:
            continue
        ok, why = _router_conds(r.get("si"), ctx)
        if not ok:
            continue
        alts = r.get("y_alguno_de")
        if alts:
            for c in alts:
                ok2, why2 = _router_conds(c, ctx)
                if ok2:
                    why += why2
                    break
            else:
                continue
        pick, regla, no_subir = r["objetivo"], r.get("nombre"), bool(r.get("no_subir"))
        motivo = str(r.get("motivo") or regla or "regla") + (f" ({', '.join(why)})" if why else "")
        break
    up = cfg.get("subir_escalon") or {}
    escalera = [x for x in (up.get("escalera") or []) if x in targets]
    if not no_subir and pick in escalera and escalera.index(pick) + 1 < len(escalera):
        reason = None
        hit = _kw_hit(_norm(" ".join(crits)), up.get("palabras_en_criterios")) if crits else None
        if up.get("min_criterios") and len(crits) >= _num(up["min_criterios"], 99):
            reason = f"{len(crits)} criterios de aceptación"
        elif hit:
            reason = f"criterio exigente «{hit}»"
        elif up.get("min_chars") and ctx["chars"] >= _num(up["min_chars"], 10 ** 9):
            reason = f"encargo muy largo ({ctx['chars']} letras)"
        if reason:
            nxt = escalera[escalera.index(pick) + 1]
            motivo += f"; sube un escalón ({pick} → {nxt}) por {reason}"
            pick = nxt
    # El elegido tiene que estar disponible; si no, sus respaldos en orden.
    first, cola_, seen, faltan = pick, [pick], [], []
    while cola_:
        cur = cola_.pop(0)
        if cur in seen or cur not in targets:
            continue
        seen.append(cur)
        t = targets[cur]
        ok, why = _router_available(str(t.get("motor") or ""))
        if ok:
            txt = f"{cur}: {motivo}"
            if faltan:
                txt += " (" + "; ".join(faltan) + f"; respondió {cur})"
            return {"elegido": cur, "motor": str(t.get("motor")), "modelo": t.get("modelo"),
                    "motivo": txt[:400], "regla": regla}, None
        faltan.append(f"{cur} no está disponible: {why}")
        cola_ += [x for x in (t.get("respaldo") or []) if x not in seen]
    etq = targets[first].get("etiqueta") or first
    info = {"elegido": first, "motor": str(targets[first].get("motor")), "modelo": None,
            "motivo": f"{first}: {motivo}", "regla": regla}
    return info, f"Automático eligió {etq} ({motivo}), pero {'; '.join(faltan)}"


def auto_label(elegido):
    """'Sonnet', 'Hermes'... para la ventana."""
    t = (_router_cfg().get("objetivos") or {}).get(elegido)
    return (t.get("etiqueta") if isinstance(t, dict) else None) or str(elegido).capitalize()


def _auto_fields(enr):
    """Campos que llevan el resultado y la familia de una tarea en Automatico."""
    if not isinstance(enr, dict) or not enr.get("elegido"):
        return {}
    return {"modo_motor": "auto", "motor_elegido": enr["elegido"],
            "motivo_eleccion": enr.get("motivo") or ""}


# ---- sesiones locales (motores HTTP sin sesion propia)
def _session_load(sid):
    try:
        data = json.loads((SESSIONS_DIR / f"{sid}.json").read_text(encoding="utf-8"))
        return [m for m in data if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    except (OSError, ValueError, TypeError):
        return []


def _session_save(sid, msgs):
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        (SESSIONS_DIR / f"{sid}.json").write_text(
            json.dumps(msgs[-40:], ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def _trim_messages(msgs, budget=14000):
    """Cabe en el contexto (8192 tokens en llama-server): se queda el primer
    mensaje (el encargo) y los mas recientes."""
    if sum(len(m["content"]) for m in msgs) <= budget:
        return msgs
    first = dict(msgs[0], content=msgs[0]["content"][:4000])
    rest, total = [], len(first["content"])
    for m in reversed(msgs[1:]):
        if total + len(m["content"]) > budget and rest:
            break
        rest.insert(0, m)
        total += len(m["content"])
    return [first] + rest


# ---- un resultado, el mismo para todos los motores
def _base_result(task, motor_id):
    return {
        "runner": f"growi-bridge/{VERSION}", "id": task["id"], "status": "error",
        "started_at": _now_iso(), "finished_at": None, "duration_s": None,
        "exit_code": None, "result": "", "cost_usd": None, "num_turns": None,
        "session_id": None, "stderr": "", "error": None,
        "motor": motor_id, "modelo": task.get("modelo"),
        "ronda": task.get("ronda", 0), "tarea_padre": task.get("tarea_padre"),
        "raiz": task.get("raiz") or task["id"], "fase": task.get("fase"),
    }


def _kill_tree(proc):
    """Mata el proceso y todos sus hijos (claude/codex lanzan node)."""
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=15, creationflags=_NO_WINDOW)
    except Exception:
        pass
    try:
        if proc.poll() is None:
            proc.kill()
    except Exception:
        pass


def stop_current_task():
    """Boton Parar: mata de verdad el proceso del motor (o corta la conexion
    con el motor local) y no deja que se creen mas rondas."""
    tid = state.get("current")
    if not tid:
        return False, "no hay ninguna tarea corriendo"
    _RUN["stop"] = True
    hecho = []
    proc = _RUN.get("proc")
    if proc is not None and proc.poll() is None:
        _kill_tree(proc)
        hecho.append(f"proceso {proc.pid} terminado")
    conn = _RUN.get("conn")
    if conn is not None:
        try:
            if conn.sock is not None:
                conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except Exception:
            pass
        hecho.append("conexión con el motor local cortada")
    msg = f"Parar: {tid}: " + (", ".join(hecho) or "se para en cuanto termine el paso actual")
    log(msg)
    return True, msg


def _build_cli_cmd(task, motor_id, eng, prompt, abilities=True):
    base = _resolve_binary(eng)
    if not base:
        return None
    resume = bool(task.get("session_id"))
    tpl = eng.get("comando_reanudar") if resume and eng.get("comando_reanudar") else eng.get("comando")
    allowed = task.get("allowed_tools")
    off_tools = []
    if motor_id == "claude" and abilities:
        off_tools = [k.split(":", 1)[1] for k in disabled_abilities() if k.startswith("tool:")]
        allowed = _filter_tools(allowed, off_tools)
    vars_ = {
        "prompt": prompt, "cwd": task["cwd"],
        "modelo": task.get("modelo") or (eng.get("modelo") or {}).get("por_defecto") or "",
        "session_id": task.get("session_id") or "",
        "allowed_tools": allowed or "", "disallowed_tools": ",".join(off_tools),
        "permission_mode": task.get("permission_mode") or "",
    }
    opc = []
    mflag = (eng.get("modelo") or {}).get("opcional")
    if vars_["modelo"] and mflag:
        opc += _fill(mflag, vars_)
    sflag = (eng.get("sesion") or {}).get("opcional")
    if resume and sflag and not eng.get("comando_reanudar"):
        opc += _fill(sflag, vars_)
    perms = eng.get("permisos") or {}
    for pair in perms.get("opcionales") or []:
        if all(vars_.get(p) for p in _PH_RE.findall(" ".join(pair))):
            opc += _fill(pair, vars_)
    perm_args = []
    if isinstance(perms.get("por_modo"), dict):
        perm_args = list(perms["por_modo"].get(task.get("permission_mode") or "", []))
    cmd, placed = [], False
    for part in tpl or []:
        if part == "{binario}":
            cmd += base
        elif part == "{permisos}":
            cmd += perm_args
        elif part == "{opcionales}":
            cmd += opc
            placed = True
        else:
            cmd.append(str(_fill(part, vars_)))
    if not placed:
        cmd += opc
    return cmd


def _parse_cli_output(motor_id, eng, stdout, rc, result):
    sal = eng.get("salida") or {}
    fmt = sal.get("formato", "texto")
    if fmt == "json":
        try:
            data = json.loads(stdout)
        except ValueError:
            data = None
        if not isinstance(data, dict):
            result["result"] = stdout[:MAX_RESULT_CHARS]
            result["status"] = "ok" if rc == 0 else "error"
            if rc != 0:
                result["error"] = f"{motor_id} salio con codigo {rc} y salida no-JSON"
            return
        result["result"] = str(_get_path(data, sal.get("texto", "result")) or "")[:MAX_RESULT_CHARS]
        costs = sal.get("costo") or []
        for k in costs if isinstance(costs, list) else [costs]:
            if isinstance(data.get(k), (int, float)):
                result["cost_usd"] = data[k]
                break
        if sal.get("turnos"):
            result["num_turns"] = data.get(sal["turnos"])
        if sal.get("sesion"):
            result["session_id"] = data.get(sal["sesion"])
        if isinstance(data.get("usage"), dict) or isinstance(data.get("modelUsage"), dict):
            uso = _uso_from_result_event(data)
            if uso:
                result["uso"] = uso
        flag = sal.get("error_si")
        is_err = bool(flag and data.get(flag))
        result["status"] = "error" if is_err or rc != 0 else "ok"
        if is_err:
            result["error"] = f"{motor_id} reporto {flag}=true"
        elif rc != 0:
            result["error"] = f"{motor_id} salio con codigo {rc}"
        return
    if fmt == "jsonl":
        ses, txt = sal.get("sesion") or {}, sal.get("texto") or {}
        tur, errc = sal.get("turnos") or {}, sal.get("error") or {}
        texts, errs, turns, sid = [], [], 0, None
        for line in stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            t = ev.get("type")
            if t == ses.get("evento") and ev.get(ses.get("campo")):
                sid = ev.get(ses.get("campo"))
            if t == txt.get("evento"):
                item = ev.get("item") or {}
                if item.get("type") == txt.get("tipo_item") and item.get(txt.get("campo")):
                    texts.append(str(item.get(txt.get("campo"))))
            if t == tur.get("evento"):
                turns += 1
            if t in (errc.get("eventos") or []):
                e = ev.get("error")
                errs.append(str(e.get("message", e)) if isinstance(e, dict) else str(e or ev.get("message") or t))
        result["result"] = (texts[-1] if texts else "")[:MAX_RESULT_CHARS]
        result["num_turns"] = turns or None
        result["session_id"] = sid
        if rc == 0 and texts and not errs:
            result["status"] = "ok"
        else:
            result["error"] = (errs[-1] if errs else (f"{motor_id} salio con codigo {rc}" if rc
                               else f"{motor_id} no devolvió ningún mensaje"))[:300]
        return
    result["result"] = stdout[:MAX_RESULT_CHARS]
    result["status"] = "ok" if rc == 0 and stdout.strip() else "error"
    if result["status"] != "ok":
        result["error"] = f"{motor_id} salio con codigo {rc}" if rc else f"{motor_id} no devolvió nada"


def _swap_args(cmd, old, new):
    """cmd con la secuencia old cambiada por new (None si old no esta)."""
    old, new = list(old or []), list(new or [])
    if not old:
        return None
    for i in range(len(cmd) - len(old) + 1):
        if cmd[i:i + len(old)] == old:
            return cmd[:i] + new + cmd[i + len(old):]
    return None


def _run_cli_engine(task, motor_id, eng, result, prompt, abilities=True, rol="tarea"):
    cmd = _build_cli_cmd(task, motor_id, eng, prompt, abilities=abilities)
    if cmd is None:
        result["error"] = (f"motor {motor_id} no disponible: no encuentro "
                           f"'{eng.get('binario')}' en el PATH de este usuario")
        return
    log(f"runner [{task['id']}]: corriendo {motor_id} en {task['cwd']} (timeout {task['timeout_min']} min)")
    vivo = eng.get("vivo") if isinstance(eng.get("vivo"), dict) else {}
    live_cmd = (_swap_args(cmd, vivo.get("reemplaza"), vivo.get("argumentos"))
                if vivo.get("formato") == "stream-json" else None)
    if live_cmd:
        if _run_cli_stream(task, motor_id, eng, result, prompt, live_cmd, rol):
            return
        # stream-json no anduvo (no salio ni un evento): como siempre, con json.
        log(f"runner [{task['id']}]: {motor_id} no dio salida en vivo (stream-json); "
            "lo corro como antes (--output-format json), sin vivo")
        for k in ("status", "error", "result", "exit_code", "stderr"):
            result[k] = _base_result(task, motor_id)[k]
        live_set(rol, modo_vivo="sin vivo",
                 nota="el motor no dio salida en vivo; se corrió sin vivo")
    else:
        live_set(rol, modo_vivo="sin vivo")
    _run_cli_plain(task, motor_id, eng, result, prompt, cmd, rol)


def _live_event(ev, rol, st):
    """Un evento de stream-json de Claude Code -> vivo."""
    t = ev.get("type")
    if t == "stream_event":
        e = ev.get("event") or {}
        et = e.get("type")
        key = ev.get("api_message_id") or ((e.get("message") or {}).get("id"))
        if et == "message_start":
            m = e.get("message") or {}
            st["model_of"][key] = m.get("model")
            if isinstance(m.get("usage"), dict):
                st["uso"] = True
                live_msg(rol, key, m.get("model"), _usage_norm(m["usage"]))
        elif et == "message_delta" and isinstance(e.get("usage"), dict):
            st["uso"] = True
            live_msg(rol, key, st["model_of"].get(key), _usage_norm(e["usage"]))
    elif t == "assistant":
        m = ev.get("message") or {}
        if isinstance(m.get("usage"), dict):
            st["uso"] = True
            live_msg(rol, m.get("id"), m.get("model"), _usage_norm(m["usage"]))
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "text" and b.get("text"):
                st["last_text"] = b["text"]
    elif t == "system" and ev.get("subtype") == "init" and ev.get("model"):
        live_set(rol, modelo_real=ev.get("model"))
    elif t == "result":
        st["final"] = ev


def _run_cli_stream(task, motor_id, eng, result, prompt, cmd, rol):
    """Corre el motor con salida en vivo (stream-json): un hilo lector va
    leyendo cada linea segun llega y suma el uso de cada mensaje. Devuelve
    False si no llego ni un evento (el motor no entiende stream-json): el
    que llama lo repite como siempre."""
    import tempfile
    stdin_mode = eng.get("prompt_por") == "stdin"
    timeout_s = task["timeout_min"] * 60
    st = {"final": None, "events": 0, "uso": False, "model_of": {}, "last_text": "",
          "raw": deque(maxlen=60)}
    with tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(
                cmd, cwd=task["cwd"], stdout=subprocess.PIPE, stderr=err,
                stdin=subprocess.PIPE if stdin_mode else subprocess.DEVNULL,
                env=_engine_env(eng), creationflags=_NO_WINDOW)
        except FileNotFoundError:
            result["error"] = f"{motor_id} no esta en el PATH de este usuario"
            return True
        except OSError as e:
            result["error"] = f"no se pudo lanzar {motor_id}: {e}"
            return True
        _RUN["proc"] = proc
        _track_launch(proc, f"runner: tarea {task['id']}, motor {MOTOR_CORTO.get(motor_id, motor_id)}")

        def _reader():
            try:
                for raw in proc.stdout:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    # Los trozos de texto (cientos) no traen uso: se saltan sin parsear.
                    if '"content_block_delta"' in line[:160]:
                        st["events"] += 1
                        continue
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        st["raw"].append(line)
                        continue
                    if not isinstance(ev, dict):
                        continue
                    st["events"] += 1
                    try:
                        _live_event(ev, rol, st)
                    except Exception as e:  # el vivo nunca tumba la tarea
                        st["raw"].append(f"(vivo: {type(e).__name__}: {e})")
            except (OSError, ValueError):
                pass

        th = threading.Thread(target=_reader, daemon=True)
        th.start()
        rc = None
        try:
            if stdin_mode:
                try:
                    proc.stdin.write(prompt.encode("utf-8", "replace"))
                    proc.stdin.close()
                except OSError:
                    pass
            try:
                rc = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                result["status"] = "timeout"
                result["error"] = f"timeout de {task['timeout_min']} min (se mató el proceso)"
        finally:
            _RUN["proc"] = None
        th.join(15)
        err.seek(0)
        stderr = err.read().decode("utf-8", "replace")
    result["exit_code"] = rc
    result["stderr"] = _ANSI_RE.sub("", stderr)[-MAX_STDERR_CHARS:]
    tail = st["last_text"] or "\n".join(st["raw"])
    if not st["uso"]:
        live_set(rol, modo_vivo="sin vivo",
                 nota="el motor no reportó uso mientras corría (sin vivo)")
    if _RUN.get("stop"):
        result["status"] = "error"
        result["error"] = "parado por el usuario (se mató el proceso)"
        result["result"] = tail[-MAX_RESULT_CHARS:]
        return True
    if result["status"] == "timeout":
        result["result"] = tail[-MAX_RESULT_CHARS:]
        return True
    final = st["final"]
    if final is None:
        if st["events"] == 0:
            return False
        result["result"] = tail[-MAX_RESULT_CHARS:]
        result["error"] = f"{motor_id} salio con codigo {rc} sin el mensaje final"
        return True
    # El mensaje final trae los mismos campos que --output-format json.
    _parse_cli_output(motor_id, eng, json.dumps(final), rc, result)
    if result.get("uso"):
        result["uso"]["fuente"] = "stream-json"
    live_final(rol, result.get("cost_usd"), result.get("uso"))
    return True


def _run_cli_plain(task, motor_id, eng, result, prompt, cmd, rol="tarea"):
    import tempfile
    stdin_mode = eng.get("prompt_por") == "stdin"
    timeout_s = task["timeout_min"] * 60
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        try:
            proc = subprocess.Popen(
                cmd, cwd=task["cwd"], stdout=out, stderr=err,
                stdin=subprocess.PIPE if stdin_mode else subprocess.DEVNULL,
                env=_engine_env(eng), creationflags=_NO_WINDOW)
        except FileNotFoundError:
            result["error"] = f"{motor_id} no esta en el PATH de este usuario"
            return
        except OSError as e:
            result["error"] = f"no se pudo lanzar {motor_id}: {e}"
            return
        _RUN["proc"] = proc
        _track_launch(proc, f"runner: tarea {task['id']}, motor {MOTOR_CORTO.get(motor_id, motor_id)}")
        rc = None
        try:
            if stdin_mode:
                try:
                    proc.stdin.write(prompt.encode("utf-8", "replace"))
                    proc.stdin.close()
                except OSError:
                    pass
            try:
                rc = proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)
                result["status"] = "timeout"
                result["error"] = f"timeout de {task['timeout_min']} min (se mató el proceso)"
        finally:
            _RUN["proc"] = None
        out.seek(0)
        err.seek(0)
        stdout = out.read().decode("utf-8", "replace")
        stderr = err.read().decode("utf-8", "replace")
    result["exit_code"] = rc
    result["stderr"] = _ANSI_RE.sub("", stderr)[-MAX_STDERR_CHARS:]
    if _RUN.get("stop"):
        result["status"] = "error"
        result["error"] = "parado por el usuario (se mató el proceso)"
        result["result"] = stdout[-MAX_RESULT_CHARS:]
        return
    if result["status"] == "timeout":
        result["result"] = stdout[-MAX_RESULT_CHARS:]
        return
    _parse_cli_output(motor_id, eng, stdout, rc, result)
    if result.get("uso"):
        result["uso"]["fuente"] = "json (al terminar)"
    live_final(rol, result.get("cost_usd"), result.get("uso"))


def _local_model(eng, task):
    m = task.get("modelo") or (eng.get("modelo") or {}).get("por_defecto") or ""
    if m == "@ollama_por_defecto":
        m = default_ollama_model() or OLLAMA_MODEL
    return m


def _run_http_engine(task, motor_id, eng, result, prompt, for_review=False):
    """Motor HTTP local (llama-server, Ollama): un POST con stream:false. La
    sesion es un historial guardado en sesiones/<session_id>.json."""
    name = eng.get("nombre") or motor_id
    if eng.get("servidor") and not for_review:
        ok, why = _llama_ensure(eng)
        if ok and why:
            result.setdefault("avisos", []).append(why)
    else:
        ok, why = engine_status(motor_id, autostart=not for_review)
    if not ok:
        result["error"] = f"motor {motor_id} no disponible: {why}"
        return
    sid = None if for_review else task.get("session_id")
    messages = _trim_messages((_session_load(sid) if sid else [])
                              + [{"role": "user", "content": prompt}])
    model = _local_model(eng, task)
    body = _fill(eng.get("cuerpo") or {}, {"mensajes": messages, "modelo": model, "prompt": prompt})
    if for_review:
        body = _deep_merge(body, eng.get("cuerpo_revision") or {})
    if (eng.get("modelo") or {}).get("campo"):
        body[eng["modelo"]["campo"]] = model
    result["modelo"] = model or None
    rol = "revision" if for_review else "tarea"
    if not for_review:
        log(f"runner [{task['id']}]: corriendo {motor_id} ({name}) local, $0")
    sal = eng.get("salida") or {}
    vivo = eng.get("vivo") if isinstance(eng.get("vivo"), dict) else {}
    timeout = task["timeout_min"] * 60
    data, text, tin, tout, fuente = None, None, None, None, None
    try:
        if vivo.get("stream") and not for_review:
            # En vivo: cada trozo que llega es un token de salida (el
            # servidor manda uno por trozo); al final, el uso que el
            # servidor reporta reemplaza la cuenta.
            sbody = _deep_merge(body, vivo.get("cuerpo") or {})
            try:
                text, tin, tout = _http_local_stream(
                    eng["url"], sbody, timeout, vivo,
                    lambda k: live_tokens(rol, model, 0, k, modo="en vivo (trozos)"))
                fuente = "streaming"
            except _NoStream as e:
                log(f"runner [{task['id']}]: {name} no contestó en streaming ({e}); lo repito sin streaming")
                live_set(rol, nota="el motor no contestó en streaming; tokens al cerrar")
        if fuente is None:
            data = _http_local("POST", eng["url"], body, timeout=timeout, track=True)
            text = _get_path(data, sal.get("texto"))
            tin, tout = _first_num(data, sal.get("uso_in")), _first_num(data, sal.get("uso_out"))
            fuente = "al cerrar"
    except LocalCallError as e:
        result["error"] = (str(e) if "parado por el usuario" in str(e) or _RUN.get("stop")
                           else f"{name}: {e}")
        if _RUN.get("stop") and "parado" not in result["error"]:
            result["error"] = "parado por el usuario (se cortó la conexión con el motor)"
        return
    if tin is not None or tout is not None:
        result["uso"] = {"tokens_in": tin or 0, "tokens_out": tout or 0, "modelo_real": model or None,
                         "por_modelo": {model or motor_id: {"tokens_in": tin or 0, "tokens_out": tout or 0,
                                                            "cost_usd": 0.0}},
                         "fuente": fuente}
        live_tokens(rol, model, tin, tout, modo="en vivo" if fuente == "streaming" else "al cerrar")
    else:
        live_set(rol, modo_vivo="sin vivo", nota=f"{name} no reportó tokens")
    live_final(rol, float(sal.get("costo") or 0.0), result.get("uso"))
    if not isinstance(text, str) or not text.strip():
        result["error"] = f"{name} respondió sin texto"
        result["result"] = json.dumps(data, ensure_ascii=False)[:2000] if data is not None else ""
        return
    result.update(status="ok", exit_code=0, result=text[:MAX_RESULT_CHARS],
                  cost_usd=float(sal.get("costo") or 0.0))
    result["num_turns"] = sal.get("turnos") if isinstance(sal.get("turnos"), int) else 1
    if not for_review:
        sid = sid or ("s-" + secrets.token_hex(8))
        _session_save(sid, messages + [{"role": "assistant", "content": text}])
        result["session_id"] = sid
        result["num_turns"] = sum(1 for m in messages if m["role"] == "user")


def _http_inet(method, url, body, headers, timeout, key=""):
    req = urllib.request.Request(
        url, method=method, headers=headers,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        raise LocalCallError(_scrub(f"{_http_reason(e.code)} {detail}", key))
    except urllib.error.URLError as e:
        raise LocalCallError(_scrub(f"sin conexión ({getattr(e, 'reason', e)})", key))


def _run_async_engine(task, motor_id, eng, result, prompt):
    """Motor asincrono (Meshy, 3D): crea la tarea, sondea el estado
    (PENDING / IN_PROGRESS / SUCCEEDED / FAILED) y descarga el archivo."""
    name = eng.get("nombre") or motor_id
    key = _named_api_key(eng.get("clave_api"))
    if not key:
        result["error"] = (f"motor {motor_id} no disponible: falta la clave en APIs "
                           f"(ponle de nombre '{eng.get('clave_api')}')")
        return
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
           "User-Agent": "GrowiBridge"}
    crear, est, desc = eng.get("crear") or {}, eng.get("estado") or {}, eng.get("descargar") or {}
    try:
        data = _http_inet(crear.get("metodo", "POST"), crear["url"],
                          _fill(crear.get("cuerpo") or {}, {"prompt": task["prompt"],
                                                            "modelo": task.get("modelo") or ""}),
                          hdr, 60, key)
        remote = _get_path(data, crear.get("campo_id", "result"))
        if not remote:
            result["error"] = f"{name} no devolvió el id de la tarea"
            return
        log(f"runner [{task['id']}]: {name} tarea creada ({remote})")
        deadline = time.time() + task["timeout_min"] * 60
        while True:
            if _RUN.get("stop"):
                result["error"] = f"parado por el usuario (la tarea {remote} de {name} puede seguir en su web)"
                return
            if time.time() > deadline:
                result["status"] = "timeout"
                result["error"] = f"timeout de {task['timeout_min']} min esperando a {name}"
                return
            d = _http_inet(est.get("metodo", "GET"), _fill(est["url"], {"tarea_id": remote}),
                           None, hdr, 60, key)
            st = str(d.get(est.get("campo", "status")) or "")
            state["paso"] = f"{name}: {st.lower() or 'esperando'} {d.get('progress', '')}%".strip()
            if st == est.get("exito", "SUCCEEDED"):
                break
            if st in (est.get("fallo") or ["FAILED"]):
                msg = _get_path(d, "task_error.message") or st
                result["error"] = f"{name} dijo {st}: {msg}"
                return
            for _ in range(int(est.get("cada_s") or 10)):
                if _RUN.get("stop"):
                    break
                time.sleep(1)
        url = _get_path(d, desc.get("campo_url", "model_urls.glb"))
        if not url:
            result["error"] = f"{name} terminó pero no dio la URL del archivo"
            return
        folder = SHARE / str(desc.get("carpeta") or "outbox/meshy")
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{task['id']}{desc.get('extension', '.glb')}"
        with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        size = dest.stat().st_size if dest.is_file() else 0
        if size <= 0:
            result["error"] = f"la descarga de {name} quedó vacía"
            return
        result.update(status="ok", exit_code=0, num_turns=1, session_id=str(remote),
                      result=f"Modelo 3D descargado en {dest} ({size // 1024} KB). Tarea {name}: {remote}.")
        result["archivos"] = [str(dest)]
    except LocalCallError as e:
        result["error"] = f"{name}: {e}"


def run_engine(task, prompt=None):
    """Corre una tarea con su motor de engines.json."""
    motor_id = task.get("motor") or "claude"
    result = _base_result(task, motor_id)
    result.update(_auto_fields(task.get("enrutado")))
    t0 = time.time()
    eng = get_engine(motor_id)
    if eng is None:
        result["error"] = (f"el motor '{motor_id}' no existe en engines.json "
                           f"(hay: {', '.join(engine_ids())})")
    else:
        prompt = prompt if prompt is not None else rules_prefix() + task["prompt"]
        tipo = eng.get("tipo")
        try:
            if tipo == "cli_sincrono":
                _run_cli_engine(task, motor_id, eng, result, prompt)
            elif tipo == "api_sincrona":
                _run_http_engine(task, motor_id, eng, result, prompt)
            elif tipo == "api_asincrona":
                live_set("tarea", modo_vivo="sin vivo", nota=f"{eng.get('nombre') or motor_id} no reporta tokens")
                _run_async_engine(task, motor_id, eng, result, prompt)
            else:
                result["error"] = f"tipo de motor desconocido en engines.json: {tipo}"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"[:300]
    result["finished_at"] = _now_iso()
    result["duration_s"] = round(time.time() - t0, 1)
    return result


def _filter_tools(allowed, off_tools):
    """Quita de allowed_tools las herramientas que el usuario apago."""
    if not allowed or not off_tools:
        return allowed
    # Separadas por comas (o por espacios si no hay comas): "Bash(git *)"
    # lleva un espacio dentro y no se debe partir.
    parts = allowed.split(",") if "," in allowed else allowed.split()
    keep = [t.strip() for t in parts
            if t.strip() and t.strip().split("(", 1)[0] not in off_tools]
    return ",".join(keep) or None


def run_task(task):
    if task.get("ollama_action"):
        return run_model_task(task)
    if task.get("motor") == "api":
        res = _run_api(task)
        res.update(motor="api", modelo=task.get("model"), ronda=task.get("ronda", 0),
                   tarea_padre=task.get("tarea_padre"), raiz=task.get("raiz") or task["id"],
                   fase=task.get("fase"))
        return res
    return run_engine(task)


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


# ---------------------------------------------------------------- orquestacion
# Bucle cerrado: corre -> revisa -> (si falta algo) ronda de correccion,
# maximo 3 -> aprobada / necesita decision. Cada tarea original es una
# "familia" (su raiz) con su estado en <raiz>.orquestacion.json.
ESTADOS = {
    "pendiente": "pendiente", "esperando_aprobacion": "esperando aprobación",
    "en_curso": "en curso", "revisando": "revisando", "aprobada": "aprobada",
    "necesita_decision": "necesita decisión", "fallida": "fallida",
    "sin_revision": "sin revisión", "rechazada": "rechazada",
    "esperando_reintento": "esperando reintento",
}
FINAL_STATES = ("aprobada", "necesita_decision", "fallida", "sin_revision", "rechazada")
NO_CONFIRMADO = "Lo intenté pero no pude confirmar que funcionara."


def _family_path(raiz):
    return RESULTS / f"{raiz}.orquestacion.json"


def load_family(raiz):
    try:
        d = json.loads(_family_path(raiz).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _family_update(raiz, **kw):
    with _FAM_LOCK:
        fam = load_family(raiz) or {"raiz": raiz, "tareas": [], "costo_usd": 0.0,
                                    "creada": _now_iso(), "ronda": 0, "max_rondas": MAX_ROUNDS}
        add = kw.pop("sumar_costo", None)
        if isinstance(add, (int, float)):
            fam["costo_usd"] = round((fam.get("costo_usd") or 0) + add, 4)
        tid = kw.pop("tarea", None)
        if tid and tid not in fam["tareas"]:
            fam["tareas"].append(tid)
        for k, v in kw.items():
            if k.startswith("solo_si_falta_"):
                fam.setdefault(k[len("solo_si_falta_"):], v)
            else:
                fam[k] = v
        fam["actualizado"] = _now_iso()
        fam["final"] = fam.get("estado") in FINAL_STATES
        RESULTS.mkdir(parents=True, exist_ok=True)
        tmp = _family_path(raiz).with_suffix(".tmp")
        tmp.write_text(json.dumps(fam, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, _family_path(raiz))
        return fam


# ---- aprobacion humana en lo sensible
GUARDRAIL_LEVELS = (("siempre", "Preguntarme siempre",
                     "Antes de borrar, publicar, gastar o enviar algo, te enseño el plan y espero tu sí."),
                    ("delicado", "Preguntarme solo lo delicado",
                     "Solo pregunto si es grave: gastar dinero, publicar, borrar en masa o escribir a otras personas."),
                    ("nunca", "Hazlo sin preguntar",
                     "Growi lo hace todo sin enseñarte el plan. Pide doble confirmación."))
# categoria -> (palabras leves, palabras fuertes). "Preguntarme siempre" pregunta
# por cualquiera; "solo lo delicado" solo por las fuertes.
SENSITIVE = {
    "borrar": ([r"\bborr", r"\belimin", r"\bdelete\b", r"\bremove\b", r"\brm\s", r"\bdel\s",
                r"\bquit\w* (?:el|la|los|las) (?:archivo|carpeta)"],
               [r"\bborr\w* (?:todo|toda|todos|todas|la carpeta|el disco)", r"\brm\s+-\w*r",
                r"\bformate", r"\bdel\s+/s", r"\belimin\w* (?:todo|todos|permanente|la carpeta)",
                r"\bvac[ií]a\w* (?:la|el) (?:carpeta|disco|papelera)"]),
    "publicar": ([r"\bpublic", r"\bsub[ei]r? (?:a|al) ", r"\bupload", r"\bgit push\b", r"\bdeploy",
                  r"\bdespl[ei]eg"],
                 [r"\bpublic", r"\bdeploy", r"\bdespl[ei]eg", r"\bgit push\b", r"\bproducci[oó]n\b",
                  r"\bredes sociales\b", r"\btweet", r"\binstagram\b", r"\byoutube\b"]),
    "gastar": ([r"\bgast", r"\bcompr[aeo]", r"\bpag(?:a|ar|o|ue|ues)\b", r"\bsuscri", r"\bcr[eé]ditos?\b"],
               [r"\bgast\w* (?:dinero|\$|\d)", r"\bcompr[aeo]", r"\bpag(?:a|ar|o|ue|ues)\b", r"\bsuscri",
                r"\btarjeta\b", r"\$\s?\d", r"\bfactur"]),
    "enviar": ([r"\benv[ií]", r"\bmand[ae]r?\b", r"\bsend\b", r"\bcorreo\b", r"\bemail\b"],
               [r"\bcorreo\b", r"\be-?mail\b", r"\bwhatsapp\b", r"\bsms\b", r"\btelegram\b",
                r"\benv[ií]\w* (?:a|al|un mensaje|un correo)\b", r"\bmand\w* un (?:mensaje|correo)\b"]),
}
# Aprobaciones: solo en memoria. Ni el puente ni una tarea pueden escribir
# aqui, asi que nadie se puede autoaprobar; solo el clic del usuario.
_APPROVED = {}  # raiz -> set(categorias aprobadas)


def guardrail_level():
    v = load_settings().get("guardrail")
    return v if v in ("siempre", "delicado", "nunca") else "siempre"


def detect_sensitive(task):
    """{categoria: {"nivel": "fuerte"|"leve", "palabras": [...]}} de la tarea."""
    text = " ".join(str(x) for x in (task.get("prompt") or "",
                                     " ".join(task.get("criterios") or []))).lower()
    found = {}
    for cat, (leves, fuertes) in SENSITIVE.items():
        hits_f = [m.group(0).strip() for r in fuertes for m in [re.search(r, text)] if m]
        hits_l = [m.group(0).strip() for r in leves for m in [re.search(r, text)] if m]
        if hits_f or hits_l:
            found[cat] = {"nivel": "fuerte" if hits_f else "leve",
                          "palabras": sorted(set(hits_f + hits_l))[:6]}
    for cat in task.get("sensible") or []:
        found[cat] = {"nivel": "fuerte", "palabras": ["la tarea lo marca como sensible"]}
    eng = get_engine(task.get("motor") or "") or {}
    for cat in eng.get("sensible") or []:
        found[cat] = {"nivel": "fuerte", "palabras": [f"el motor {task.get('motor')} {cat}"]}
    if task.get("permission_mode") == "bypassPermissions":
        found["permisos totales"] = {"nivel": "fuerte", "palabras": ["bypassPermissions"]}
    return found


def _approval_needed(task):
    level = guardrail_level()
    if level == "nunca":
        return None
    found = detect_sensitive(task)
    need = {c: v for c, v in found.items() if level == "siempre" or v["nivel"] == "fuerte"}
    if not need:
        return None
    if set(need) <= _APPROVED.get(task["raiz"], set()):
        return None
    return need


def _park_for_approval(task_file, task, need):
    WAITING.mkdir(parents=True, exist_ok=True)
    dest = WAITING / task_file.name
    shutil.move(str(task_file), str(dest))
    plan = {"motor": task["motor"], "modelo": task.get("modelo"), "cwd": task["cwd"],
            "permisos": {"permission_mode": task.get("permission_mode"),
                         "allowed_tools": task.get("allowed_tools")},
            "prompt": task["prompt"][:3000], "criterios": task.get("criterios") or [],
            "acciones": need, "nivel": guardrail_level(), "tarea": task["id"],
            **_auto_fields(task.get("enrutado"))}
    _family_update(task["raiz"], estado="esperando_aprobacion", plan=plan,
                   archivo_espera=dest.name, motor=task["motor"], tarea=task["id"],
                   ronda=task.get("ronda", 0), solo_si_falta_encargo=task["prompt"][:2000],
                   solo_si_falta_criterios=task.get("criterios") or [], fase=task.get("fase"),
                   **_auto_fields(task.get("enrutado")))
    log(f"runner [{task['id']}]: espera tu aprobación ({', '.join(need)}); no se ejecuta sola")


def approve_waiting(raiz):
    """Clic en Aprobar: la tarea vuelve a la cola y ya no se para."""
    fam = load_family(raiz) or {}
    name = fam.get("archivo_espera")
    src = WAITING / str(name or "")
    if not name or not src.is_file():
        return False, "esa tarea ya no está esperando"
    _APPROVED.setdefault(raiz, set()).update((fam.get("plan") or {}).get("acciones") or {})
    dest = TASKS / src.name
    shutil.move(str(src), str(dest))
    t = time.time() - 5
    os.utime(dest, (t, t))
    cola_registrar(dest)
    _family_update(raiz, estado="pendiente", archivo_espera=None, aprobada_por_usuario=_now_iso())
    log(f"tareas: aprobaste {raiz}; vuelve a la cola")
    return True, "aprobada; vuelve a la cola"


def reject_waiting(raiz):
    fam = load_family(raiz) or {}
    name = fam.get("archivo_espera")
    src = WAITING / str(name or "")
    if not name or not src.is_file():
        return False, "esa tarea ya no está esperando"
    DONE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(DONE / src.name))
    tid = (fam.get("plan") or {}).get("tarea") or raiz
    res = _error_result(tid, "rechazada por el usuario antes de empezar")
    res.update(raiz=raiz, estado="rechazada", reporte="No se hizo nada: la rechazaste antes de empezar.",
               reintentos=0)
    _write_result(res)
    cola_set(tid, estado="fallida", archivo=str(DONE / src.name),
             motivo="rechazada por el usuario (definitivo, sin reintentos)")
    _family_update(raiz, estado="rechazada", archivo_espera=None,
                   reporte="No se hizo nada: la rechazaste antes de empezar.")
    log(f"tareas: rechazaste {raiz}")
    return True, "rechazada"


# ---- revision automatica
_FILE_RE = re.compile(r"(?<![\w.-])((?:[A-Za-z]:[\\/])?[\w.\\/-]*\w\.[A-Za-z][A-Za-z0-9]{0,7})(?![\w])")
_MARK_RE = re.compile(r"\"([^\"\n]{1,120})\"|“([^”\n]{1,120})”|«([^»\n]{1,120})»|`([^`\n]{1,120})`|'([^'\n]{2,120})'")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "processing", "done", "esperando"}


def _iso_ts(iso):
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return time.time()


def _touched_files(cwd, since_ts, limit=40, max_entries=20000, max_s=3.0):
    """Archivos modificados dentro de cwd mientras corria la tarea."""
    skip = {str(p).lower() for p in (TASKS, RESULTS, SESSIONS_DIR)}
    out, n, t0, stack = [], 0, time.time(), [str(cwd)]
    while stack and n < max_entries and time.time() - t0 < max_s:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                n += 1
                try:
                    if e.is_dir(follow_symlinks=False):
                        if (e.name not in _SKIP_DIRS and not e.name.startswith(".")
                                and str(Path(e.path)).lower() not in skip):
                            stack.append(e.path)
                    elif e.is_file(follow_symlinks=False) and e.stat().st_mtime >= since_ts:
                        out.append(e.path)
                except OSError:
                    continue
    out.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)
    return out[:limit]


def _file_facts(path):
    p = Path(path)
    if not p.is_file():
        return {"existe": False}
    size = p.stat().st_size
    facts = {"existe": True, "bytes": size, "lineas": None}
    if size <= 5_000_000:
        try:
            data = p.read_bytes()
            facts["lineas"] = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
        except OSError:
            pass
    return facts


def _read_text(path, limit=2_000_000):
    try:
        p = Path(path)
        if p.stat().st_size > limit:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _resolve_mentioned(tok, cwd, touched):
    p = Path(tok.replace("\\", "/"))
    cand = p if p.is_absolute() else Path(cwd) / p
    try:
        cand = cand.resolve()
    except OSError:
        pass
    if not cand.exists():
        same = [t for t in touched if Path(t).name.lower() == p.name.lower()]
        if same:
            cand = Path(same[0])
    if not _inside_any(cand, load_folders()):
        return None
    return cand


def _check_criterion(crit, cwd, touched, text):
    """Comprueba un criterio contra los archivos reales cuando se puede
    (existe, numero de lineas, marcadores entre comillas). None si no hay
    nada que comprobar a maquina (lo decide la revision del modelo)."""
    low = crit.lower()
    toks = list(dict.fromkeys(m.group(1).rstrip(".") for m in _FILE_RE.finditer(crit)))
    marks = [next(g for g in m.groups() if g) for m in _MARK_RE.finditer(crit)]
    marks = [m for m in marks if m not in toks and not _FILE_RE.fullmatch(m)]
    textual = (re.search(r"\b(respuesta|responde|menciona|dice|nombra|explica|resumen|texto)\b", low)
               and not re.search(r"\b(archivo|fichero|carpeta|existe|l[ií]neas)\b", low))
    if textual:
        toks = []
    if not toks and not marks:
        return None
    oks, fails = [], []
    negate = re.search(r"\bno\s+(?:debe\s+)?(?:existe|existir|est[aá]|quede)|\b(?:borrad|eliminad)[oa]s?\b", low)
    mlines = re.search(r"(m[aá]s\s+de|mayor\s+(?:a|que)|al\s+menos|como\s+m[ií]nimo|m[ií]nimo|>=|>)\s*(\d+)\s*l[ií]neas", low)
    pool = []
    for tok in toks:
        p = _resolve_mentioned(tok, cwd, touched)
        if p is None:
            fails.append(f"{tok}: está fuera de las carpetas permitidas, no lo puedo comprobar")
            continue
        f = _file_facts(p)
        if negate:
            (fails if f["existe"] else oks).append(
                f"{p} todavía existe" if f["existe"] else f"{p} no existe (comprobado)")
            continue
        if not f["existe"]:
            fails.append(f"el archivo {tok} no existe (busqué en {p})")
            continue
        pool.append(p)
        oks.append(f"{p} existe ({f['lineas']} líneas, {f['bytes']} bytes)")
        if mlines and f["lineas"] is not None:
            n = int(mlines.group(2))
            strict = not re.search(r"al\s+menos|m[ií]nimo|>=", mlines.group(1))
            good = f["lineas"] > n if strict else f["lineas"] >= n
            (oks if good else fails).append(
                f"{p} tiene {f['lineas']} líneas ({'más de' if strict else 'al menos'} {n}: "
                f"{'sí' if good else 'no'})")
    if marks:
        if textual:
            sources = [("el resultado", text)]
        else:
            files = pool or [Path(t) for t in touched if Path(t).is_file()][:20]
            sources = [(str(f), _read_text(f)) for f in files]
        for mk in marks:
            where = [name for name, body in sources if mk.lower() in body.lower()]
            (oks if where else fails).append(
                f"marcador '{mk}' presente en {where[0]}" if where
                else f"falta el marcador '{mk}'" + (" en el resultado" if textual else " en los archivos"))
    return {"criterio": crit, "resultado": "no cumple" if fails else "cumple",
            "detalle": oks + fails, "falla": fails}


def _review_prompt(task, result, checks, touched, can_read):
    crits = task.get("criterios") or []
    fam = load_family(task["raiz"]) or {}
    encargo = fam.get("encargo") or task["prompt"]
    parts = ["Eres un revisor estricto. NO hagas el trabajo: solo comprueba si está hecho.",
             "", "ENCARGO:", encargo[:3000], "", "CRITERIOS DE ACEPTACIÓN:"]
    parts += [f"{i}. {c}" for i, c in enumerate(crits, 1)]
    parts += ["", "RESULTADO QUE DEVOLVIÓ EL MOTOR:", (result.get("result") or "")[:5000] or "(vacío)"]
    if checks:
        parts += ["", "HECHOS COMPROBADOS POR EL RUNNER EN LOS ARCHIVOS REALES (son fiables):"]
        parts += [f"- {d}" for c in checks for d in c["detalle"]]
    parts += ["", "ARCHIVOS MODIFICADOS EN LA CARPETA MIENTRAS CORRÍA LA TAREA:"]
    parts += [f"- {t}" for t in touched[:20]] or ["- ninguno"]
    shown = 0
    for c in checks:
        for d in c["detalle"]:
            m = re.match(r"(.+?) existe \(", d)
            if m and shown < 3:
                body = _read_text(m.group(1))[:1500]
                if body:
                    parts += ["", f"EXTRACTO DE {m.group(1)}:", body]
                    shown += 1
    parts += ["", "Reglas: un criterio solo se cumple si hay evidencia en los hechos comprobados, "
              "en los extractos o en el resultado. Si el resultado dice que hizo algo pero los hechos "
              "no lo confirman, NO se cumple. No inventes archivos ni líneas."]
    if can_read:
        parts.append("Puedes leer archivos de la carpeta para comprobarlo (solo leer).")
    parts += ["Responde SOLO con un JSON así, sin nada más:",
              '{"aprobado": "si" o "no", "que_falta": ["cosa concreta que falta"], '
              '"evidencia": ["archivo o línea que lo demuestra"]}',
              "que_falta va vacío si está aprobado."]
    return "\n".join(parts)


def _parse_review_json(text):
    text = text or ""
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        d = json.loads(text[a:b + 1])
    except ValueError:
        return None
    if not isinstance(d, dict) or "aprobado" not in d:
        return None
    v = d.get("aprobado")
    ok = v is True or str(v).strip().lower() in ("si", "sí", "yes", "true", "1", "aprobado")

    def _lst(x):
        if isinstance(x, str):
            x = [x] if x.strip() else []
        return [str(i).strip() for i in (x or []) if str(i).strip()][:20]
    return {"aprobado": ok, "que_falta": _lst(d.get("que_falta")), "evidencia": _lst(d.get("evidencia"))}


def _llm_review(task, result, checks, touched):
    """Prueba los motores de revision en orden. (opinion, motor, costo, error)."""
    errs, cost = [], 0.0
    for spec in (load_engines()[0].get("revision") or {}).get("orden") or []:
        mid = spec.get("motor")
        if LANE == "b" and mid not in LANE_B_MOTORES:
            errs.append(f"{mid}: el carril B no usa motores locales")
            continue
        eng = get_engine(mid)
        if eng is None:
            errs.append(f"{mid}: no existe en engines.json")
            continue
        ok, why = engine_status(mid)
        if not ok or (eng.get("servidor") and why != "responde"):
            errs.append(f"{mid}: {why}")
            continue
        if _RUN.get("stop"):
            return None, None, cost, "parado por el usuario"
        name = eng.get("nombre") or mid
        state["paso"] = f"Revisando {task['raiz']} con {name}"
        rtask = {"id": task["id"] + "-revision", "cwd": task["cwd"], "timeout_min": 10,
                 "modelo": spec.get("modelo"), "session_id": None, "prompt": "",
                 "allowed_tools": spec.get("allowed_tools"), "permission_mode": None}
        r = _base_result(rtask, mid)
        prompt = _review_prompt(task, result, checks, touched, eng.get("tipo") == "cli_sincrono")
        if eng.get("tipo") in ("cli_sincrono", "api_sincrona"):
            live_review_start(mid, spec.get("modelo") or (eng.get("modelo") or {}).get("por_defecto"))
        if eng.get("tipo") == "cli_sincrono":
            _run_cli_engine(rtask, mid, eng, r, prompt, abilities=False, rol="revision")
        elif eng.get("tipo") == "api_sincrona":
            _run_http_engine(rtask, mid, eng, r, prompt, for_review=True)
        else:
            errs.append(f"{mid}: no sirve para revisar texto")
            continue
        if isinstance(r.get("cost_usd"), (int, float)):
            cost += r["cost_usd"]
        if _RUN.get("stop"):
            return None, None, cost, "parado por el usuario"
        if r["status"] != "ok":
            errs.append(f"{mid}: {r['error']}")
            continue
        op = _parse_review_json(r["result"])
        if op is None:
            errs.append(f"{mid}: no devolvió un JSON válido ({r['result'][:80]!r})")
            continue
        op["motor"], op["modelo"] = mid, r.get("modelo")
        return op, mid, cost, None
    return None, None, cost, "; ".join(errs) or "no hay motores de revisión en engines.json"


def review_task(task, result):
    """Revision al terminar. Sin criterios: solo que el resultado no este
    vacio ni traiga error. Con criterios: lo comprobable se mira en los
    archivos reales y el resto lo juzga un motor barato."""
    eng = get_engine(task.get("motor") or "") or {}
    crits = task.get("criterios") or []
    text = (result.get("result") or "").strip()
    can_touch = eng.get("tipo") in ("cli_sincrono", "api_asincrona") or task.get("motor") == "api"
    touched = _touched_files(task["cwd"], _iso_ts(result.get("started_at")) - 2) if can_touch else []
    touched = list(dict.fromkeys((result.get("archivos") or []) + touched))
    rev = {"id": task["id"], "raiz": task["raiz"], "ronda": task.get("ronda", 0),
           "aprobado": None, "que_falta": [], "evidencia": [], "motor_revision": None,
           "verificacion_automatica": [], "opinion_modelo": None, "archivos_tocados": touched,
           "criterios": crits, "cost_usd": 0.0, "revisado_at": None, "error": None}
    if not crits:
        ok = bool(text) and not result.get("error")
        rev.update(aprobado=ok, motor_revision="reglas (la tarea no trae criterios)",
                   evidencia=[f"el resultado tiene {len(text)} caracteres y no trae error"] if ok else [],
                   que_falta=[] if ok else ["el resultado llegó vacío"], revisado_at=_now_iso())
        return rev
    checks = [c for c in (_check_criterion(c, task["cwd"], touched, text) for c in crits) if c]
    rev["verificacion_automatica"] = checks
    det_fail = [f for c in checks for f in c["falla"]]
    all_ok = len(checks) == len(crits) and not det_fail
    op, mid, cost, err = _llm_review(task, result, checks, touched)
    rev["cost_usd"] = round(cost, 4)
    rev["opinion_modelo"] = op
    verified = [d for c in checks for d in c["detalle"] if d not in c["falla"]]
    if op is None:
        if _RUN.get("stop"):
            rev["error"] = "parado por el usuario durante la revisión"
        elif det_fail:
            rev.update(aprobado=False, que_falta=det_fail,
                       motor_revision=f"comprobación de archivos (sin modelo: {err})")
        elif all_ok:
            rev.update(aprobado=True, motor_revision=f"comprobación de archivos (sin modelo: {err})")
        else:
            rev["error"] = f"no hay motor de revisión disponible: {err}"
    else:
        rev["motor_revision"] = mid
        if det_fail:
            rev["aprobado"] = False
            rev["que_falta"] = det_fail + [x for x in op["que_falta"] if x not in det_fail]
        elif all_ok:
            rev["aprobado"] = True
        else:
            rev["aprobado"] = op["aprobado"]
            rev["que_falta"] = [] if op["aprobado"] else op["que_falta"]
        if rev["aprobado"] is False and not rev["que_falta"]:
            rev["que_falta"] = ["la revisión no aprobó pero no dijo qué falta: revisa el resultado"]
        for e in op["evidencia"]:
            bad = [t for t in (m.group(1) for m in _FILE_RE.finditer(e))
                   if (lambda p: p is not None and not p.exists())(_resolve_mentioned(t, task["cwd"], touched))]
            rev["evidencia"].append(f"según la revisión: {e}" + (
                f" (pero {', '.join(bad)} no existe: no cuenta)" if bad else ""))
    rev["evidencia"] = verified + rev["evidencia"]
    rev["revisado_at"] = _now_iso()
    return rev


def _honest_report(estado, task, rev, fam, error=None):
    """Regla anti-exito-inventado: solo se dice que algo funciono si esta
    comprobado contra archivos reales (o, sin criterios, si hay respuesta)."""
    rondas = fam.get("ronda", 0) if fam else task.get("ronda", 0)
    motor = task.get("motor")
    checks = (rev or {}).get("verificacion_automatica") or []
    verified = [d for c in checks for d in c["detalle"] if d not in c["falla"]]
    if estado == "aprobada":
        base = f"Aprobada por la revisión ({(rev or {}).get('motor_revision')})"
        base += f" tras {rondas} ronda(s) de corrección." if rondas else "."
        if verified:
            return base + " Comprobado en archivos: " + "; ".join(verified[:6]) + "."
        if task.get("criterios"):
            return base + (" La aprobación se basa en el texto del resultado: no hay archivos "
                           "que lo confirmen.")
        return base + " Solo se comprobó que hay respuesta y no hay error."
    if estado == "necesita_decision":
        faltas = "; ".join((rev or {}).get("que_falta") or []) or "no se sabe"
        txt = (f"Se intentó el encargo con {motor} en {rondas} ronda(s) de corrección (máximo "
               f"{MAX_ROUNDS}). No se pudo confirmar: {faltas}.")
        if verified:
            return txt + " Lo que sí está comprobado en archivos: " + "; ".join(verified[:6]) + "."
        return NO_CONFIRMADO + " " + txt
    if estado == "sin_revision":
        return (f"Terminó, pero no se pudo revisar ({error or (rev or {}).get('error')}). "
                "Nadie ha comprobado que esté bien.")
    return f"{NO_CONFIRMADO} {error or 'falló'}."


def _new_task_file(data):
    TASKS.mkdir(parents=True, exist_ok=True)
    base, i = data["id"], 1
    while any((d / f"{data['id']}.task.json").exists() for d in (TASKS, PROCESSING, DONE, WAITING)):
        data["id"] = f"{base}-{i}"
        i += 1
    path = TASKS / f"{data['id']}.task.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    t = time.time() - 5
    os.utime(path, (t, t))
    cola_registrar(path, data)
    return data["id"]


def _task_core(task):
    """Lo que hereda una ronda o una fase de su tarea."""
    d = {"cwd": task["cwd"], "motor": task["motor"], "timeout_min": task["timeout_min"],
         "allowed_tools": task.get("allowed_tools"), "permission_mode": task.get("permission_mode"),
         "sensible": task.get("sensible") or None, "enrutado": task.get("enrutado"),
         "lane": task.get("lane"), "archivos": task.get("archivos"), "lee": task.get("lee"),
         "lee_carril_a": task.get("lee_carril_a") or None}
    if task["motor"] in ("claude", "api"):
        d["model"] = task.get("model")
    else:
        d["modelo"] = task.get("modelo")
    return {k: v for k, v in d.items() if v is not None}


def _enqueue_round(task, result, rev):
    n = task.get("ronda", 0) + 1
    raiz = task["raiz"]
    sid = result.get("session_id") or task.get("session_id")
    prompt = ("Revisé tu trabajo y faltan estas cosas. Corrígelas (solo esto):\n"
              + "\n".join(f"- {x}" for x in rev["que_falta"]))
    if not sid:
        fam = load_family(raiz) or {}
        prompt += ("\n\n(No hay sesión que continuar; este era el encargo:)\n"
                   + (fam.get("encargo") or task["prompt"])[:4000])
    data = dict(_task_core(task), id=f"{raiz[:70]}-r{n}", prompt=prompt, session_id=sid,
                criterios=task.get("criterios") or [], ronda=n, tarea_padre=raiz, raiz=raiz,
                fase=task.get("fase"), siguiente_fase=task.get("siguiente_fase"),
                fase_base=task.get("fase_base"), creada_por="runner: ronda de corrección")
    return _new_task_file({k: v for k, v in data.items() if v is not None})


def _next_fase_label(fase):
    m = re.search(r"(\d+)(\s*(?:de|/)\s*\d+)?", str(fase or ""))
    if not m:
        return None
    return fase[:m.start(1)] + str(int(m.group(1)) + 1) + fase[m.end(1):]


def _enqueue_next_phase(task, result):
    nxt = task.get("siguiente_fase")
    if isinstance(nxt, dict):
        prompt, crits = nxt.get("prompt"), nxt.get("criterios")
        after, label = nxt.get("siguiente_fase"), nxt.get("fase")
    else:
        prompt, crits, after, label = nxt, None, None, None
    label = label or _next_fase_label(task.get("fase"))
    base = (task.get("fase_base") or task["raiz"])[:68]
    m = re.search(r"(\d+)", str(label or ""))
    k = int(m.group(1)) if m else 2
    resumen = re.sub(r"\s+", " ", (result.get("result") or "")).strip()[:700]
    sid = result.get("session_id") or task.get("session_id")
    full = (f"{prompt}\n\nContexto de lo ya hecho en la fase anterior ({task.get('fase') or task['raiz']}), "
            f"resumen corto:\n{resumen or '(sin texto)'}")
    data = dict(_task_core(task), id=f"{base}-f{k}", prompt=full, session_id=sid,
                criterios=crits or [], fase=label, siguiente_fase=after, fase_base=base,
                fase_anterior=task["raiz"], creada_por="runner: siguiente fase")
    data = {k2: v for k2, v in data.items() if v is not None}
    new_id = _new_task_file(data)
    _family_update(new_id, estado="pendiente", motor=task["motor"], fase=label,
                   fase_anterior=task["raiz"], encargo=full[:2000], criterios=crits or [])
    return new_id


def _after_run(task, result):
    """Despues de correr: revisar y decidir (aprobada / otra ronda /
    necesita decision / fallida / sin revision)."""
    raiz, n = task["raiz"], task.get("ronda", 0)
    _family_update(raiz, sumar_costo=result.get("cost_usd"), ultimo_resultado=task["id"],
                   session_id=result.get("session_id"), en_curso=None)
    rev = None
    if result["status"] != "ok":
        motivo = result.get("error") or result["status"]
        estado, reporte = "fallida", _honest_report("fallida", task, None, None, motivo)
    elif not task.get("revisar", True):
        estado, reporte = "sin_revision", _honest_report("sin_revision", task, None, None,
                                                         "la tarea pidió no revisarla")
    else:
        state["paso"] = f"Revisando {raiz}" + (f" (ronda {n}/{MAX_ROUNDS})" if n else "")
        _family_update(raiz, estado="revisando")
        rev = review_task(task, result)
        try:
            with open(RESULTS / f"{task['id']}.revision.json", "w", encoding="utf-8") as f:
                json.dump(rev, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log(f"runner [{task['id']}]: no se pudo guardar la revisión: {e}")
        result["revision"] = f"{task['id']}.revision.json"
        fam = _family_update(raiz, sumar_costo=rev.get("cost_usd"), ultima_revision={
            "id": task["id"], "aprobado": rev["aprobado"], "que_falta": rev["que_falta"],
            "motor": rev["motor_revision"], "evidencia": rev["evidencia"][:8]})
        log(f"runner [{task['id']}]: revisión ({rev['motor_revision'] or 'ninguna'}): "
            f"{'aprobada' if rev['aprobado'] else 'no aprobada' if rev['aprobado'] is False else 'sin revisión'}")
        if rev.get("error") and "parado" in rev["error"]:
            estado, reporte = "fallida", _honest_report("fallida", task, rev, fam, rev["error"])
        elif rev["aprobado"] is None:
            estado, reporte = "sin_revision", _honest_report("sin_revision", task, rev, fam)
        elif rev["aprobado"]:
            estado, reporte = "aprobada", _honest_report("aprobada", task, rev, fam)
            if task.get("siguiente_fase"):
                nid = _enqueue_next_phase(task, result)
                reporte += f" Siguiente fase encolada: {nid}."
                _family_update(raiz, siguiente=nid)
                log(f"runner [{task['id']}]: aprobada; encolo la siguiente fase {nid}")
        elif n < MAX_ROUNDS and not _RUN.get("stop"):
            nid = _enqueue_round(task, result, rev)
            _family_update(raiz, estado="en_curso", ronda=n + 1, ultima_ronda=nid)
            log(f"runner [{task['id']}]: no aprobada; ronda de corrección {n + 1}/{MAX_ROUNDS}: {nid}")
            result["estado"] = "en_curso"
            _write_result(result)
            return
        else:
            estado, reporte = "necesita_decision", _honest_report("necesita_decision", task, rev, fam)
    reporte += _cola_nota(result)
    result["estado"], result["reporte"] = estado, reporte
    _write_result(result)
    _family_update(raiz, estado=estado, reporte=reporte)
    log(f"runner [{raiz}]: {ESTADOS[estado]}: {reporte[:160]}")


# ---------------------------------------------------------------- cola persistente
# cola.db (SQLite en modo WAL con synchronous=FULL, para que un apagon no la
# corrompa) es el registro de estado de cada tarea que entra a runner-tasks/.
# El .task.json sigue siendo el encargo; la base es lo que sobrevive. Al
# arrancar, lo que quedo en_curso por un corte vuelve a en_cola (intentos+1)
# y su resultado dira «recuperada tras corte». Nada se pierde en silencio.
COLA_DB = (Path(os.environ["GROWI_BRIDGE_COLA"]) if os.environ.get("GROWI_BRIDGE_COLA")
           else SHARE.parent / "cola.db" if os.environ.get("GROWI_BRIDGE_SHARE")
           else APP_DIR / "cola.db")
COLA_FINALES = ("terminada", "fallida", "necesita_decision", "archivada")
RETRY_BACKOFF_S = (30, 120, 480)  # 30 s, 2 min, 8 min, con +-20 % de azar (jitter)
MAX_RETRIES = len(RETRY_BACKOFF_S)
MAX_CORTES = 3                    # cortada 3 veces mientras corria: no se repite mas sola
ARCHIVE_DAYS = 30
CORTE = "recuperada tras corte"
_COLA_LOCK = threading.Lock()
_cola_err = [None]
_cola_vistos = set()
_cola_corriendo = set()  # ids que este mismo proceso esta corriendo ahora
# Errores pasajeros (se reintentan) y definitivos (nunca). Se mira primero lo
# definitivo: un "falta la clave" no se arregla esperando.
_DEFINITIVO_RE = re.compile(
    r"no existe en engines\.json|falta la clave|parado por el usuario|rechazad|"
    r"no est[aá] en el PATH|no encuentro '|tipo de motor desconocido|no est[aá] instalado|"
    r"CODIFICACI[OÓ]N|clave rechazada|sin permiso \(403\)|no encontrado \(404\)|"
    r"petici[oó]n rechazada \(400\)|JSON invalido|no es una direcci[oó]n local", re.I)
_TRANSITORIO_RE = re.compile(
    r"no responde|servidor apagado|sin respuesta de|conexi[oó]n cortada|PROXY:|sin conexi[oó]n|"
    r"todav[ií]a est[aá] cargando|no respondi[oó] en|se cerr[oó] al arrancar|timed? ?out|timeout|"
    r"ECONNRE|ETIMEDOUT|ENOTFOUND|EAI_AGAIN|socket hang up|fetch failed|network|overloaded|"
    r"\b5(?:00|02|03|04|29)\b|el servicio fall[oó]|l[ií]mite de uso|rate.?limit|\b429\b|"
    r"Connection(?:Reset|Aborted|Refused)Error|RemoteDisconnected|temporarily|temporalmente", re.I)


def _cola_conn():
    con = sqlite3.connect(str(COLA_DB), timeout=15, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    return con


def _cola(sql, args=(), fetch=False):
    """Una sentencia en cola.db (cada una se confirma sola). Si la base
    falla, el runner sigue como antes y lo dice en el registro."""
    try:
        with _COLA_LOCK:
            con = _cola_conn()
            try:
                cur = con.execute(sql, args)
                out = [dict(r) for r in cur.fetchall()] if fetch else cur.rowcount
            finally:
                con.close()
        _cola_err[0] = None
        return out
    except sqlite3.Error as e:
        if str(e) != _cola_err[0]:
            log(f"cola: ERROR en {COLA_DB.name} ({e}); el runner sigue, pero sin registro")
        _cola_err[0] = str(e)
        return [] if fetch else 0


def cola_init():
    _cola("""CREATE TABLE IF NOT EXISTS tareas (
        id TEXT PRIMARY KEY, archivo TEXT, estado TEXT NOT NULL,
        intentos INTEGER NOT NULL DEFAULT 0, reintentos INTEGER NOT NULL DEFAULT 0,
        cortes INTEGER NOT NULL DEFAULT 0, motor TEXT, ronda INTEGER,
        tarea_padre TEXT, raiz TEXT, fase TEXT, creado_en TEXT NOT NULL,
        actualizado_en TEXT NOT NULL, actualizado_ts REAL NOT NULL,
        proximo_intento REAL, motivo TEXT, historial TEXT)""")
    _cola("CREATE INDEX IF NOT EXISTS tareas_estado ON tareas(estado)")


def cola_get(tid):
    rows = _cola("SELECT * FROM tareas WHERE id=?", (tid,), fetch=True)
    return rows[0] if rows else None


def cola_set(tid, **kw):
    kw.update(actualizado_en=_now_iso(), actualizado_ts=time.time())
    if isinstance(kw.get("historial"), list):
        kw["historial"] = json.dumps(kw["historial"], ensure_ascii=False)
    cols = ", ".join(f"{k}=?" for k in kw)
    return _cola(f"UPDATE tareas SET {cols} WHERE id=?", (*kw.values(), tid))


def _cola_hist(row):
    try:
        h = json.loads((row or {}).get("historial") or "[]")
        return h if isinstance(h, list) else []
    except ValueError:
        return []


def _cola_id(task_file, data):
    tid = data.get("id") if isinstance(data, dict) else None
    return tid if _safe_id(tid) else Path(task_file).name.split(".task.json")[0]


def cola_registrar(task_file, data=None):
    """Apunta en cola.db una tarea de runner-tasks/ ANTES de recogerla. Si
    ya estaba terminada y vuelve a llegar con el mismo id, cuenta como nueva."""
    task_file = Path(task_file)
    if data is None:
        try:
            data = json.loads(task_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    tid = _cola_id(task_file, data)
    row = cola_get(tid)
    if row is not None and row["estado"] == "en_cola" and row["archivo"] == str(task_file):
        return tid
    now = _now_iso()
    try:
        ronda = int(data.get("ronda") or 0)
    except (TypeError, ValueError):
        ronda = 0
    info = dict(motor=data.get("motor") or ("modelos" if "ollama_action" in data else None),
                ronda=ronda, tarea_padre=data.get("tarea_padre"),
                raiz=data.get("raiz") or tid, fase=data.get("fase"))
    if row is None:
        _cola("INSERT OR IGNORE INTO tareas (id, archivo, estado, motor, ronda, tarea_padre, raiz,"
              " fase, creado_en, actualizado_en, actualizado_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tid, str(task_file), "en_cola", *info.values(), now, now, time.time()))
    elif row["estado"] in COLA_FINALES:
        cola_set(tid, archivo=str(task_file), estado="en_cola", intentos=0, reintentos=0, cortes=0,
                 proximo_intento=None, motivo="llegó otra vez con el mismo id", historial=None,
                 creado_en=now, **info)
    else:  # aprobada (venia de esperando) o devuelta a la cola
        cola_set(tid, archivo=str(task_file), estado="en_cola")
    return tid


def _cola_ver(p):
    """Registra el archivo si es nuevo (o cambio) desde la ultima vuelta."""
    key = (p.name, p.stat().st_mtime_ns)
    if key not in _cola_vistos:
        if len(_cola_vistos) > 5000:
            _cola_vistos.clear()
        cola_registrar(p)
        _cola_vistos.add(key)


def cola_en_espera():
    """{nombre de archivo: hora} de las que esperan su reintento."""
    rows = _cola("SELECT archivo, proximo_intento FROM tareas WHERE estado='en_cola' "
                 "AND proximo_intento > ?", (time.time(),), fetch=True)
    return {Path(r["archivo"] or "").name: r["proximo_intento"] for r in rows}


def _hora(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def cola_resumen():
    rows = _cola("SELECT estado, COUNT(*) AS n, MIN(CASE WHEN proximo_intento > ? THEN "
                 "proximo_intento END) AS prox FROM tareas GROUP BY estado",
                 (time.time(),), fetch=True)
    cuenta = {r["estado"]: r["n"] for r in rows}
    prox = min((r["prox"] for r in rows if r["prox"]), default=None)
    return {"cuenta": cuenta, "pendiente": cuenta.get("en_cola", 0) + cuenta.get("en_curso", 0),
            "proximo_reintento": _hora(prox) if prox else None}


def _es_transitorio(result):
    """Red, timeout del motor, llama-server/Ollama caido, proxy caido: se
    reintenta. Motor inexistente, falta de clave, parado/rechazado: no."""
    if result.get("status") == "timeout":
        return True
    err = str(result.get("error") or "")
    if not err or _DEFINITIVO_RE.search(err):
        return False
    txt = " ".join((err, str(result.get("stderr") or "")[-1500:], str(result.get("result") or "")[:500]))
    return bool(_TRANSITORIO_RE.search(txt))


def _veces(n):
    return "1 vez" if n == 1 else f"{n} veces"


def _cola_nota(result):
    """Lo que se añade al reporte si hubo cortes o reintentos."""
    nota = ""
    if result.get("recuperada_tras_corte"):
        nota += (f" Recuperada tras corte: se cortó {_veces(result.get('cortes') or 1)} "
                 "mientras corría y se repitió desde el principio.")
    if result.get("reintentos"):
        ult = (result.get("historial_reintentos") or [{}])[-1].get("error") or "?"
        nota += (f" Hicieron falta {result['reintentos']} reintento(s) por errores pasajeros "
                 f"(último: {str(ult)[:120]}).")
    return nota


def _programar_reintento(cid, task, task_file, processing_path, result, row):
    """Error pasajero: la tarea vuelve a runner-tasks/ y espera su turno
    (30 s, 2 min, 8 min, con jitter). Queda en cola.db, no en memoria."""
    n = (row.get("reintentos") or 0) + 1
    espera = RETRY_BACKOFF_S[n - 1] * random.uniform(0.8, 1.2)
    cuando = time.time() + espera
    err = str(result.get("error") or result.get("status"))[:300]
    hist = _cola_hist(row) + [{"reintento": n, "error": err, "at": _now_iso(),
                               "proximo": _hora(cuando), "cost_usd": result.get("cost_usd")}]
    dest = TASKS / task_file.name
    cola_set(cid, estado="en_cola", archivo=str(dest), intentos=(row.get("intentos") or 0) + 1,
             reintentos=n, proximo_intento=cuando, motivo=err, historial=hist)
    try:
        os.replace(processing_path, dest)
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo devolver a la cola para reintentar: {e}")
    _family_update(task["raiz"], estado="esperando_reintento", en_curso=None, reintentos=n,
                   proximo_reintento=_hora(cuando), motivo_reintento=err,
                   sumar_costo=result.get("cost_usd"))
    log(f"runner [{task['id']}]: error pasajero ({err[:140]}); reintento {n}/{MAX_RETRIES} "
        f"en {espera:.0f} s (a las {_hora(cuando)[11:19]})")


def _cola_resultado(path):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def cola_recuperar():
    """Al arrancar: lo que un corte dejo a medias vuelve a la cola (o, si ya
    se corto MAX_CORTES veces, queda fallida con el motivo). Nunca en silencio."""
    for d in (TASKS, PROCESSING, DONE, RESULTS, WAITING):
        d.mkdir(parents=True, exist_ok=True)
    cola_init()
    recuperadas, avisos = [], []
    for r in _cola("SELECT * FROM tareas WHERE estado IN ('en_cola', 'en_curso')", fetch=True):
        tid, name = r["id"], Path(r["archivo"] or f"{r['id']}.task.json").name
        if tid in _cola_corriendo:  # runner apagado y encendido con la tarea aun corriendo
            continue
        en_t, en_p, en_d, en_w = TASKS / name, PROCESSING / name, DONE / name, WAITING / name
        if r["estado"] == "en_cola":
            if en_t.exists():
                continue
            if en_p.exists():  # cortada entre apuntar y mover: vuelve a su sitio
                os.replace(en_p, en_t)
                cola_set(tid, archivo=str(en_t))
            elif en_w.exists():
                cola_set(tid, estado="esperando_aprobacion", archivo=str(en_w))
            else:
                motivo = "su archivo .task.json ya no está en runner-tasks/ (¿se movió a mano?)"
                cola_set(tid, estado="fallida", motivo=motivo)
                avisos.append(f"{tid}: {motivo}")
            continue
        # en_curso: se corto (luz, reinicio, cuelgue) mientras corria
        res = _cola_resultado(RESULTS / f"{tid}.result.json")
        if (not en_p.exists() and not en_t.exists() and en_d.exists() and res
                and res.get("estado") in FINAL_STATES + ("en_curso",)):
            # habia terminado; solo faltaba apuntarlo
            est = res.get("estado")
            cola_set(tid, archivo=str(en_d), estado=(
                "necesita_decision" if est == "necesita_decision" else
                "terminada" if res.get("status") == "ok" and est != "fallida" else "fallida"))
            continue
        src = next((p for p in (en_p, en_t, en_d) if p.exists()), None)
        cortes, intentos = r["cortes"] + 1, r["intentos"] + 1
        hist = _cola_hist(r) + [{"corte": _now_iso(), "intento": intentos}]
        raiz = r["raiz"] or tid
        es_modelo = r["motor"] == "modelos"
        if src is None or cortes > MAX_CORTES:
            motivo = (f"{CORTE}, pero su archivo .task.json no está en ninguna carpeta"
                      if src is None else
                      f"se cortó {cortes} veces mientras corría; no la repito sola para no "
                      "entrar en bucle (mándala otra vez si la quieres)")
            if src is not None and src != en_d:
                os.replace(src, en_d)
            cola_set(tid, estado="fallida", intentos=intentos, cortes=cortes, motivo=motivo,
                     historial=hist, proximo_intento=None,
                     archivo=str(en_d) if src is not None else r["archivo"])
            res = _error_result(tid, motivo)
            res.update(raiz=raiz, estado="fallida", recuperada_tras_corte=True, cortes=cortes,
                       intentos=intentos, reintentos=r["reintentos"],
                       reporte=f"{NO_CONFIRMADO} {motivo}.")
            _write_result(res)
            if not es_modelo:
                _family_update(raiz, estado="fallida", reporte=res["reporte"], en_curso=None,
                               recuperada_tras_corte=True)
            avisos.append(f"{tid}: {motivo}")
            continue
        if src != en_t:
            os.replace(src, en_t)
        cola_set(tid, estado="en_cola", archivo=str(en_t), intentos=intentos, cortes=cortes,
                 proximo_intento=None, motivo=f"{CORTE} ({_now_iso()})", historial=hist)
        if not es_modelo:
            _family_update(raiz, estado="pendiente", en_curso=None, recuperada_tras_corte=True,
                           nota_cola=f"{CORTE}: se cortó mientras corría (intento {intentos}); "
                                     "vuelve a la cola")
        recuperadas.append(tid)
    # Huerfanas en processing/ sin registro (de antes de la cola): no se
    # repiten solas (podrian ser instalaciones viejas), pero se ven.
    for p in PROCESSING.glob("*.task.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        tid = _cola_id(p, data)
        if cola_get(tid) is not None:
            continue
        cola_registrar(p, data)
        motivo = (f"{CORTE}: quedó a medias en processing/ (archivo del "
                  f"{datetime.fromtimestamp(p.stat().st_mtime):%d/%m %H:%M}) antes de existir la "
                  "cola; no la repito sola. Para repetirla: Tareas → elígela → «Volver a la cola»")
        cola_set(tid, estado="necesita_decision", archivo=str(p), motivo=motivo)
        if isinstance(data, dict) and "ollama_action" not in data:
            _family_update(tid, estado="necesita_decision", reporte=motivo, tarea=tid,
                           motor=data.get("motor") or "claude", recuperada_tras_corte=True,
                           solo_si_falta_encargo=str(data.get("prompt") or "")[:2000])
        avisos.append(f"{tid}: huérfana sin registro en processing/, necesita tu decisión")
    if recuperadas:
        log(f"cola: {len(recuperadas)} tarea(s) {CORTE}, vuelven a la cola: {', '.join(recuperadas)}")
    for a in avisos:
        log(f"cola AVISO: {a}")
    return recuperadas, avisos


def cola_reencolar(tid):
    """Devuelve a la cola una tarea fallida, huerfana o que necesita decision."""
    r = cola_get(tid)
    if r is None:
        return False, "esa tarea no está en la cola"
    if r["estado"] in ("en_cola", "en_curso", "esperando_aprobacion"):
        return False, "ya está en la cola"
    name = Path(r["archivo"] or f"{tid}.task.json").name
    src = next((d / name for d in (PROCESSING, DONE, TASKS) if (d / name).exists()), None)
    if src is None:
        return False, "su archivo .task.json ya no está"
    dest = TASKS / name
    t = time.time() - 5
    cola_set(tid, estado="en_cola", archivo=str(dest), proximo_intento=None,
             motivo="la volviste a encolar")
    if src != dest:
        os.replace(src, dest)
    os.utime(dest, (t, t))
    _cola_vistos.add((dest.name, dest.stat().st_mtime_ns))
    log(f"cola: {tid} vuelve a la cola (a mano)")
    return True, "vuelve a la cola"


def cola_archivar(days=ARCHIVE_DAYS):
    """Terminadas/fallidas de hace mas de 30 dias -> archivada. No se borra
    nada: .task.json, .result.json y .revision.json quedan intactos."""
    n = _cola("UPDATE tareas SET estado='archivada', actualizado_en=? WHERE estado IN "
              "('terminada', 'fallida') AND actualizado_ts < ?",
              (_now_iso(), time.time() - days * 86400))
    if n:
        log(f"cola: {n} tarea(s) de hace más de {days} días pasan a archivada (no se borra nada)")
    return n


def cola_archivadas():
    return {r["id"] for r in _cola("SELECT id FROM tareas WHERE estado='archivada'", fetch=True)}


def process_one(task_file):
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"runner [{task_file.name}]: JSON invalido ({e}); se archiva sin correr")
        DONE.mkdir(parents=True, exist_ok=True)
        cid = cola_registrar(task_file, {})
        shutil.move(str(task_file), str(DONE / task_file.name))
        cola_set(cid, estado="fallida", archivo=str(DONE / task_file.name), motivo=f"JSON invalido: {e}")
        _write_result(_error_result(task_file.stem, f"JSON invalido: {e}"))
        return True
    cid = cola_registrar(task_file, data)
    task, error = validate_task(data)
    task_id = data.get("id") if isinstance(data.get("id"), str) else task_file.stem
    if not error:
        error = _lane_b_espera_a(task)
    if error:
        log(f"runner [{task_id}]: rechazado: {error}")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_file), str(DONE / task_file.name))
        res = _error_result(task_id, error)
        res["reintentos"] = 0
        if _safe_id(task_id) and isinstance(data, dict) and "ollama_action" not in data:
            rep = f"{NO_CONFIRMADO} La tarea se rechazó antes de empezar: {error}."
            res.update(raiz=task_id, estado="fallida", reporte=rep, motor=data.get("motor"),
                       **_auto_fields(data.get("_enrutado")))
            _family_update(task_id, estado="fallida", reporte=rep, error=error,
                           **_auto_fields(data.get("_enrutado")),
                           motor=data.get("motor") or "claude", tarea=task_id,
                           solo_si_falta_encargo=str(data.get("prompt") or "")[:2000])
        cola_set(cid, estado="fallida", archivo=str(DONE / task_file.name),
                 motivo=f"definitivo, sin reintentos: {error}"[:300])
        _write_result(res)
        return True
    is_model = bool(task.get("ollama_action"))
    if not is_model:
        need = _approval_needed(task)
        if need:
            _park_for_approval(task_file, task, need)
            cola_set(cid, estado="esperando_aprobacion", archivo=str(WAITING / task_file.name))
            return True
    PROCESSING.mkdir(parents=True, exist_ok=True)
    DONE.mkdir(parents=True, exist_ok=True)
    processing_path = PROCESSING / task_file.name
    row = cola_get(cid) or {}
    # Primero se apunta en_curso y despues se mueve: si se va la luz entre
    # medias, al volver cola_recuperar() la encuentra igual.
    cola_set(cid, estado="en_curso", archivo=str(processing_path), proximo_intento=None)
    try:
        shutil.move(str(task_file), str(processing_path))
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo mover a processing: {e}")
        cola_set(cid, estado="en_cola", archivo=str(task_file))
        return False
    _cola_corriendo.add(cid)
    if is_model:
        # Acciones de modelos: carril propio, no cuentan como "Claude
        # trabajando" (ni la mascota teclea ni el PC se queda despierto).
        result = run_task(task)
    else:
        _RUN.update(stop=False, id=task["id"], proc=None, conn=None)
        state["current"] = task["id"]
        n = task.get("ronda", 0)
        eng = get_engine(task["motor"]) or {}
        _mod = (task.get("model") if task["motor"] == "api" else task.get("modelo")) or \
            (eng.get("modelo") or {}).get("por_defecto")
        if isinstance(_mod, str) and _mod.startswith("@"):
            _mod = _local_model(eng, task) or None
        state["current_motor"], state["current_modelo"] = task["motor"], _mod
        live_start(task, task["motor"], _mod)
        runner_heartbeat()  # 'current' ya trae la tarea desde el primer segundo
        state["paso"] = (f"{eng.get('nombre') or task['motor']} trabaja en {task['raiz']}"
                         + (f" (ronda {n}/{MAX_ROUNDS})" if n else "")
                         + (f" (reintento {row['reintentos']}/{MAX_RETRIES})" if row.get("reintentos") else ""))
        _family_update(task["raiz"], estado="en_curso", motor=task["motor"],
                       modelo=task.get("modelo"), ronda=n, tarea=task["id"], en_curso=task["id"],
                       proximo_reintento=None,
                       solo_si_falta_encargo=task["prompt"][:2000],
                       solo_si_falta_criterios=task.get("criterios") or [],
                       fase=task.get("fase"), siguiente_fase=bool(task.get("siguiente_fase")),
                       **_auto_fields(task.get("enrutado")))
        snap = _lane_snapshot() if LANE == "b" else None
        result = run_task(task)
        if snap is not None:
            result["carril"] = "b"
            cambios = [f for f, v in _lane_snapshot().items() if snap.get(f) != v]
            if cambios:
                result["carril_b_alerta"] = cambios
                result.setdefault("avisos", []).append(
                    "carril B: durante esta tarea cambiaron archivos prohibidos (puede haber "
                    "sido el carril A, revísalo): " + ", ".join(cambios[:8]))
                log(f"runner [{task['id']}]: AVISO carril B: cambiaron {cambios[:8]}")
        try:
            # El costo final es el que reporto el motor al terminar (el
            # mismo que va al .result.json); el estimado se queda al lado.
            live_final("tarea", result.get("cost_usd"), result.get("uso"))
            if result.get("status") != "ok" and not (_LIVE["d"] or {}).get("tokens_in"):
                live_set("tarea", nota=f"terminó con error: {str(result.get('error') or '')[:160]}")
        except Exception as e:
            log(f"runner [{task['id']}]: vivo: {type(e).__name__}: {e}")
        state["tasks_done"] += 1
        state["last_result"] = f"{task['id']}: {result['status']} ({result['duration_s']}s)"
        reintentos = row.get("reintentos") or 0
        if (result.get("status") != "ok" and not _RUN.get("stop") and reintentos < MAX_RETRIES
                and _es_transitorio(result)):
            try:
                _programar_reintento(cid, task, task_file, processing_path, result, row)
            finally:
                live_finish("reintento programado")
                state["current"] = None
                state["paso"] = None
                state["current_motor"] = state["current_modelo"] = None
                _RUN.update(proc=None, conn=None, id=None)
                _cola_corriendo.discard(cid)
            return True
    hist = _cola_hist(row)
    result["intentos"] = (row.get("intentos") or 0) + 1
    result["reintentos"] = row.get("reintentos") or 0
    if [h for h in hist if "reintento" in h]:
        result["historial_reintentos"] = [h for h in hist if "reintento" in h]
    if row.get("cortes"):
        result.update(recuperada_tras_corte=True, cortes=row["cortes"])
        result.setdefault("avisos", []).append(
            f"{CORTE}: se cortó {_veces(row['cortes'])} mientras corría; se repitió entera")
    try:
        _write_result(result)
        log(f"runner [{task['id']}]: terminado: {result['status']} duracion={result['duration_s']}s costo={result['cost_usd']}"
            + (f" reintentos={result['reintentos']}" if result["reintentos"] else "")
            + (f" ({CORTE})" if row.get("cortes") else ""))
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo escribir el resultado: {e}")
    if not is_model:
        try:
            if result.get("status") == "ok" and task.get("revisar", True):
                live_set("tarea", estado="revisando")
            _after_run(task, result)
        except Exception as e:
            log(f"runner [{task['id']}]: ERROR en la revisión/orquestación: {type(e).__name__}: {e}")
            _family_update(task["raiz"], estado="sin_revision",
                           reporte=_honest_report("sin_revision", task, None, None, f"{type(e).__name__}: {e}"))
        finally:
            live_finish()
            state["current"] = None
            state["paso"] = None
            state["current_motor"] = state["current_modelo"] = None
            _RUN.update(proc=None, conn=None, id=None)
    # Se archiva el task DESPUES de revisar: si se corta durante la revision,
    # sigue en processing/ y al volver se repite.
    try:
        shutil.move(str(processing_path), str(DONE / task_file.name))
    except OSError as e:
        log(f"runner [{task['id']}]: no se pudo archivar el task: {e}")
    est = result.get("estado")
    cola_set(cid, archivo=str(DONE / task_file.name), intentos=result["intentos"],
             estado=("necesita_decision" if est == "necesita_decision" else
                     "terminada" if result.get("status") == "ok" and est != "fallida" else "fallida"),
             motivo=(str(result.get("error") or "")[:300] or None))
    _cola_corriendo.discard(cid)
    return True


def runner_heartbeat():
    """runner-status.json. Lo escribe el bucle cuando esta libre y el hilo de
    pulso cada 60 s mientras una tarea corre: un last_poll viejo ya no
    significa 'Claude trabajando', significa problema."""
    with _STATUS_LOCK:
        _HB["t"] = time.time()
        try:
            RESULTS.mkdir(parents=True, exist_ok=True)
            cola = cola_resumen()
            cur = None
            if state.get("current"):
                lv = _LIVE["d"] or {}
                cur = {"id": state["current"], "motor": state.get("current_motor"),
                       "modelo": state.get("current_modelo"),
                       "modelo_real": lv.get("modelo_real") if lv.get("task_id") == state["current"] else None,
                       "estado": lv.get("estado") if lv.get("task_id") == state["current"] else None}
            status = {
                "runner": f"growi-bridge/{VERSION}", "alive": True, "last_poll": _now_iso(),
                "tasks_done": state["tasks_done"], "current": cur,
                "paso": state.get("paso"), "claude": shutil.which("claude"), "pid": os.getpid(),
                "motores": engines_summary(), "guardrail": guardrail_level(),
                "esperando_aprobacion": sorted(p.name for p in WAITING.glob("*.task.json")),
                "cola_pendiente": cola["pendiente"], "proximo_reintento": cola["proximo_reintento"],
                "cola": cola["cuenta"], "cola_db": str(COLA_DB),
                "vivo": LIVE_FILE.name,
            }
            path = OUTBOX / "runner-status.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
            for i in range(5):
                try:
                    os.replace(tmp, path)
                    break
                except PermissionError:
                    time.sleep(0.1 * (i + 1))
        except OSError:
            pass
        except Exception as e:  # nunca tumbar al que llama
            log(f"runner: latido con error ({type(e).__name__}: {e})")


def _runner_pulse_loop(stop_event):
    """Hilo de pulso: mientras una tarea corre, el bucle principal espera al
    motor; este hilo sigue escribiendo el vivo (cada ~5 s) y el latido
    (cada 60 s), para que nada se congele."""
    while not stop_event.is_set():
        try:
            d = _LIVE["d"]
            if d is not None and d.get("estado") != "terminado":
                live_write()
            if state.get("current") and time.time() - _HB["t"] >= HEARTBEAT_SECONDS:
                runner_heartbeat()
        except Exception as e:
            log(f"runner (pulso) ERROR (se sigue): {type(e).__name__}: {e}")
        stop_event.wait(1)


def runner_loop(stop_event):
    for d in (TASKS, PROCESSING, DONE, RESULTS, WAITING):
        d.mkdir(parents=True, exist_ok=True)
    claude = shutil.which("claude")
    log(f"runner: arrancado (claude={claude or 'NO ENCONTRADO'})")
    try:
        rec, _av = cola_recuperar()
        cola_archivar()
        log(f"cola: {COLA_DB} lista ({len(rec)} recuperada(s) tras corte)")
    except Exception as e:
        log(f"cola ERROR al recuperar (el runner sigue): {type(e).__name__}: {e}")
    _eng, _err = load_engines()
    log("motores: " + ", ".join(f"{k} {'sí' if v['disponible'] else 'no'}"
                                for k, v in engines_summary().items())
        + (f" (AVISO: {_err})" if _err else ""))
    if not claude:
        log("runner AVISO: `claude` no esta en el PATH; las tareas fallaran con error.")
    threading.Thread(target=_runner_pulse_loop, args=(stop_event,), daemon=True).start()
    last_heartbeat = 0.0
    last_archive = time.time()
    while not stop_event.is_set():
        try:
            now = time.time()
            if now - max(last_heartbeat, _HB["t"]) >= HEARTBEAT_SECONDS:
                runner_heartbeat()
                last_heartbeat = now
            if now - last_archive >= 3600:
                cola_archivar()
                last_archive = now
            espera = cola_en_espera()
            candidates = []
            for p in TASKS.glob("*.task.json"):
                try:
                    if now - p.stat().st_mtime >= 2 and not _is_model_task(p):
                        _cola_ver(p)  # se apunta en cola.db antes de recogerla
                        if p.name not in espera:
                            candidates.append(p)
                except OSError:
                    continue
            # Las rondas de correccion van primero (son la misma tarea).
            candidates.sort(key=lambda p: (0 if _is_round_task(p) else 1, p.stat().st_mtime))
            if candidates:
                if process_one(candidates[0]):
                    runner_heartbeat()
                    last_heartbeat = time.time()
        except Exception as e:
            log(f"runner ERROR en el loop (se sigue): {type(e).__name__}: {e}")
        stop_event.wait(POLL_SECONDS)
    log("runner: parado")


def _is_round_task(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return isinstance(data, dict) and bool(data.get("ronda"))
    except Exception:
        return False


def _is_model_task(path):
    """True si el task es una accion de modelos (ollama_action). Esos van
    por su propio carril para no esperar detras de una tarea larga de Claude."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return isinstance(data, dict) and "ollama_action" in data
    except Exception:
        return False


def model_lane_loop(stop_event):
    """Carril de modelos: instala / borra / lista modelos de uno en uno,
    aunque Claude este ocupado con otra tarea."""
    while not stop_event.is_set():
        try:
            now = time.time()
            candidates = []
            for p in TASKS.glob("*.task.json"):
                try:
                    if now - p.stat().st_mtime >= 1 and _is_model_task(p):
                        _cola_ver(p)
                        candidates.append(p)
                except OSError:
                    continue
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime)
                process_one(candidates[0])
                continue
        except Exception as e:
            log(f"runner (modelos) ERROR en el loop (se sigue): {type(e).__name__}: {e}")
        stop_event.wait(2)


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
    threading.Thread(target=model_lane_loop, args=(_runner_stop,), daemon=True).start()
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
    'idle' = solo el personaje, con fondo transparente (sin cuadro
    blanco ni oscuro alrededor); 'sync'/'sync2' = distintivo verde
    GRANDE que pulsa mientras hay sincronizacion (transferencia en los
    ultimos 10 s) y sobresale de la esquina inferior derecha;
    'error' = distintivo rojo (el puente esta caido)."""
    try:
        from PIL import ImageDraw
        base = Image.open(TRAY_ICON if TRAY_ICON.is_file() else PHOTO).convert("RGBA")
    except Exception:
        return None
    # El personaje va a 56x56 centrado (margen de 4 px) para que el
    # distintivo tenga donde sobresalir sin taparlo entero. El tamano
    # es el mismo con y sin distintivo, asi el icono no "salta".
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    small = base.resize((56, 56), Image.LANCZOS)
    img.paste(small, (4, 4), small)
    if kind == "idle":
        return img
    d = ImageDraw.Draw(img)
    color = {"sync": "#34C759", "sync2": "#8BE0A4", "error": "#FF3B30"}[kind]
    # Distintivo grande (28 px) en la esquina inferior derecha,
    # centrado en (49, 49): se sale del personaje y llega al borde.
    d.ellipse([36, 36, 63, 63], fill=color, outline="white", width=3)
    return img


def make_switch(parent, initial, command, bg=None):
    """Interruptor estilo macOS (verde #34C759 encendido, gris claro
    apagado, perilla blanca). command(recibe True/False) se llama al
    cambiar. El estado visual se sincroniza desde refresh_ui con
    set_switch()."""
    bg = bg or THEME["bg"]
    c = tk.Canvas(parent, width=S(52), height=S(30), bg=bg, highlightthickness=0,
                  bd=0, takefocus=1, cursor="hand2")
    c._on = bool(initial)
    c._focus = False
    c._command = command
    c._t = 1.0 if c._on else 0.0  # 0 = apagado, 1 = encendido (animado)
    c._anim = None

    def _draw():
        t = c._t
        track = _lerp_color(_C("#E9E9EA"), THEME["green"], t)
        outline = _lerp_color("#8E8E93", "#248A3D", t)
        # Con el foco (Tab) el borde se vuelve azul y mas grueso.
        b = 2 if c._focus else 1
        if c._focus:
            outline = THEME["blue"]
        c.delete("all")
        # borde (pildora b px mas grande detras); se dibuja a 100 % y luego
        # se escala entero con SCALE.
        c.create_rectangle(15, 0, 37, 30, fill=outline, outline=outline)
        c.create_oval(0, 0, 30, 30, fill=outline, outline=outline)
        c.create_oval(22, 0, 52, 30, fill=outline, outline=outline)
        # interior
        c.create_rectangle(16, b, 36, 30 - b, fill=track, outline=track)
        c.create_oval(b, b, 30 - b, 30 - b, fill=track, outline=track)
        c.create_oval(22 + b, b, 52 - b, 30 - b, fill=track, outline=track)
        kx = 2 + 22 * t
        c.create_oval(kx + b - 1, 2 + b - 1, kx + 26 - b + 1, 28 - b + 1,
                      fill="white", outline="#8E8E93")
        if SCALE != 1.0:
            c.scale("all", 0, 0, SCALE, SCALE)

    def _animate_to(target):
        # Desliza la perilla en ~150 ms (6 pasos de 25 ms).
        if c._anim is not None:
            try:
                c.after_cancel(c._anim)
            except Exception:
                pass
            c._anim = None
        start = c._t
        if abs(target - start) < 0.01:
            c._t = target
            _draw()
            return

        def _step(n=0):
            k = (n + 1) / 6.0
            c._t = start + (target - start) * (1 - (1 - k) ** 3)  # ease-out
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
        return "break"

    def _focus(on):
        c._focus = on
        _draw()

    c.bind("<Button-1>", lambda e: (c.focus_set(), _toggle(e)))
    c.bind("<space>", _toggle)
    c.bind("<Return>", _toggle)
    c.bind("<FocusIn>", lambda e: _focus(True))
    c.bind("<FocusOut>", lambda e: _focus(False))
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
    # Anillo fijo (antes parpadeaba a 1 Hz). Con el foco (Tab) es azul.
    if getattr(c, "_focus", False):
        c.create_oval(4, 4, 166, 166, outline=THEME["blue"], width=S(3))
    if on:
        c.create_oval(8, 8, 162, 162, outline=THEME["green"], width=S(3))
        c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                      fill="#E5E5EA", outline="#E5E5EA")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=THEME["green"], outline="#2DB84C", width=S(2))
        sym = "white"
    else:
        c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                      fill="#E5E5EA", outline="#E5E5EA")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#E9E9EA", outline="#D2D2D7", width=S(2))
        sym = "#8E8E93"
    c.create_arc(cx - 26, cy - 26, cx + 26, cy + 26, start=300, extent=300,
                 style="arc", outline=sym, width=S(7))
    c.create_line(cx, cy - 34, cx, cy - 12, fill=sym, width=S(7), capstyle="round")
    if SCALE != 1.0:
        c.scale("all", 0, 0, SCALE, SCALE)


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
        fill = _lerp_color(_C("#E9E9EA"), THEME["green"], t)
        outline = _lerp_color(_C("#D2D2D7"), "#2DB84C", t)
        sym = _lerp_color("#8E8E93", "#FFFFFF", t)
        # onda expansiva que se desvanece (el color se acerca al fondo)
        wave_r = r + 8 + 12 * t
        wave_c = _lerp_color(THEME["green"], THEME["bg"], t)
        c.create_oval(cx - wave_r, cy - wave_r, cx + wave_r, cy + wave_r,
                      outline=wave_c, width=S(3))
    else:
        fill = _lerp_color(THEME["green"], _C("#E9E9EA"), t)
        outline = _lerp_color("#2DB84C", _C("#D2D2D7"), t)
        sym = _lerp_color("#FFFFFF", "#8E8E93", t)
    # sombra suave debajo del circulo
    c.create_oval(cx - r - 2, cy - r + 4, cx + r + 2, cy + r + 8,
                  fill="#E5E5EA", outline="#E5E5EA")
    c.create_oval(cx - r, cy - r, cx + r, cy + r,
                  fill=fill, outline=outline, width=S(2))
    # el simbolo se dibuja poco a poco (al apagar, se desdibuja)
    extent = 300 * t if on else 300 * (1 - t)
    if extent > 0:
        c.create_arc(cx - 26, cy - 26, cx + 26, cy + 26, start=300,
                     extent=extent, style="arc", outline=sym, width=S(7))
    line_len = 22 * t if on else 22 * (1 - t)
    if line_len > 0:
        c.create_line(cx, cy - 34, cx, cy - 34 + line_len, fill=sym, width=S(7),
                      capstyle="round")
    if SCALE != 1.0:
        c.scale("all", 0, 0, SCALE, SCALE)


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
        k = min(1.0, steps[0] / 10.0)
        t = 1 - (1 - k) ** 3  # ease-out, ~280 ms
        _draw_power_frame(t, on)
        if k < 1.0:
            _power_anim["job"] = _root.after(28, _step)
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
    return f"○ Sin actividad. Lo último: {arrow.lower()} {name}, hace {secs} s"


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
        pill += f", ahora {state['current']}"
    elif state["last_result"]:
        pill += f", la última {state['last_result']}"
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
        text=f"Versión {VERSION}\n"
        + ("Con permisos de administrador" if state["admin"] else "Sin permisos de administrador"))
    if state["update_available"]:
        w["update_label"].config(
            text=f"¡Hay una actualización! v{state['update_available']} disponible.")
        w["update_btn"].config(state="normal")
    elif state["update_checked"]:
        w["update_label"].config(text="Estás en la última versión.")
    if state["sharing"]:
        folder = Path(state.get("share_folder") or "").name
        w["share_status"].config(
            text=f"Compartiendo en la sesión {folder}: van "
                 f"{state.get('share_frame', 0)} fotogramas"
                 + (f", el último a las {str(state['last_frame'])[11:19]}"
                    if state["last_frame"] else ""))
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
    _refresh_banner()
    if _tick_n[0] % 2 == 0:
        try:
            _refresh_tasks_ui()
        except Exception:
            pass
    if _tick_n[0] % 5 == 0:
        _refresh_live_ui()  # consumo en vivo: cada ~5 s, igual que runner-live.json
    # Contadores de la barra lateral (Plain) y pagina Tareas, cada 10 s.
    if _tick_n[0] % 10 == 0:
        try:
            w["nav_count_carpetas"].config(text=str(len(load_folders())))
            w["nav_count_skills"].config(text=str(len(list_skills())))
            w["nav_count_apis"].config(text=str(len(load_apis())))
            if _mdl["installed"] is not None:
                w["nav_count_modelos"].config(text=str(len(_mdl["installed"])))
        except Exception:
            pass
        try:
            _refresh_channels()
        except Exception:
            pass
    # Distintivo de sincronizacion en el icono de la bandeja (como OneDrive).
    if _tray_icon is not None:
        try:
            _tray_tick()
        except Exception:
            pass
    if False:  # distintivo viejo (antes de Venezuela primero), ya no se usa
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
    if _tick_n[0] % 3 == 0:
        _refresh_conn_widgets()
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
    try:
        _models_poll()
    except Exception:
        pass
    try:
        _res_tick()
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
    log(f"boton grande: {'todo encendido' if on else 'todo apagado'}")
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
        # Ya no saluda por cada tarea: solo celebra los hitos (ver
        # _celebrate_milestone, que lo llama al aprobarse una tarea).
        _mascot["last_tasks"] = state["tasks_done"]
        if state.get("current"):
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
    return sw - (MASCOT_SIZE + S(20)), sh - (MASCOT_SIZE + S(20))



def show_mascot():
    if _root is None or _mascot["win"] is not None:
        return
    if not TRAY_OK or not PHOTO.is_file():
        log("mascota: falta la foto (growi.png)")
        return
    win = tk.Toplevel(_root)
    win.overrideredirect(True)
    win.configure(bg=MASCOT_MAGIC)  # todo pixel fuera de la imagen es magenta = transparente
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
    label = tk.Label(win, image=photo, bg=MASCOT_MAGIC, bd=0, highlightthickness=0)
    label.image = photo
    label.pack(fill="both", expand=True)
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
            win.geometry(f"{MASCOT_SIZE}x{MASCOT_SIZE}+{d[2] + dx}+{d[3] + dy}")

    def _release(e):
        d = _mascot["drag"]
        _mascot["drag"] = None
        if d and d[4]:
            # al soltar, la ventana vuelve al tamano de la imagen en el sitio soltado
            try:
                win.geometry(f"{MASCOT_SIZE}x{MASCOT_SIZE}+{win.winfo_x()}+{win.winfo_y()}")
            except Exception:
                pass
        if d and not d[4]:
            on_mascot_click()

    label.bind("<ButtonPress-1>", _press)
    label.bind("<B1-Motion>", _move)
    label.bind("<ButtonRelease-1>", _release)
    label.bind("<Button-3>", _mascot_menu)
    log("mascota: Growi está en la esquina inferior derecha")
    _mascot["last_tasks"] = state["tasks_done"]
    _root.after(120, _mascot_loop)
    _root.after(700, lambda: _mascot_play("wave"))  # saludo al arrancar


def _mascot_menu(event):
    """Clic derecho en la mascota: lo que se le puede pedir sin abrir la
    ventana."""
    menu = tk.Menu(_root, tearoff=0, font=(FONT, 10))
    menu.add_command(label="Escribirle a Growi", command=open_prompt_box)
    menu.add_command(label="Abrir Growi Bridge", command=show_window)
    menu.add_command(label="Buscar acciones", accelerator="Ctrl+K",
                     command=lambda: (show_window(), _open_palette()))
    menu.add_separator()
    menu.add_command(label="Ocultar la mascota", command=toggle_mascot)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


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
    x = max(0, _root.winfo_x() + S(100))
    y = max(0, _root.winfo_y() + S(100))
    box.geometry(f"{S(360)}x{S(190)}+{x}+{y}")
    tk.Label(box, text=f"'{name}' pesa {size_mb:.0f} MB.",
             font=(FONT, 11, "bold"), bg=THEME["bg"], fg=THEME["text"],
             wraplength=S(320), justify="left").pack(padx=16, pady=(14, 2))
    tk.Label(box, text="Copiarlo a Growi Bridge puede tardar un rato en "
             "sincronizarse. ¿Seguro que quieres copiarlo?",
             font=(FONT, 10), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=S(320), justify="left").pack(padx=16, pady=(0, 10))
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
    x = max(0, win.winfo_x() - S(220))
    y = max(0, win.winfo_y() - S(190))
    box.geometry(f"{S(380)}x{S(230)}+{x}+{y}")
    # Cabecera: avatar + saludo.
    head = tk.Frame(box, bg=THEME["bg"])
    head.pack(fill="x", padx=18, pady=(16, 4))
    try:
        img = Image.open(PHOTO).resize((S(40), S(40)), Image.LANCZOS)
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
    # Las conexiones por proveedor y el desplegable de motores siguen a apis.json.
    _refresh_api_connections()
    _refresh_engine_widgets()


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


def hide_to_tray(toast=False):
    """Minimiza la ventana (la mascota sigue visible en su esquina). El
    aviso de que sigue corriendo sale solo si lo pide la X con el ajuste
    «minimizar» (toast=True) y solo la primera vez; Ctrl+Alt+G nunca avisa."""
    if _root is None:
        return
    try:
        _root.iconify()
    except Exception:
        pass
    log("ventana minimizada (el programa sigue corriendo)")
    if not toast or _tray_icon is None:
        return
    s = load_settings()
    if s.get("close_toast_shown"):
        return
    s["close_toast_shown"] = True
    save_settings(s)
    try:
        _tray_icon.notify("Sigo en la bandeja. Salir: clic derecho", "Growi Bridge")
    except Exception:
        pass


CLOSE_MODES = (("ask", "Preguntarme"), ("minimize", "Minimizar a la bandeja"),
               ("quit", "Salir del todo"))


def _set_close_mode(mode):
    s = load_settings()
    if mode == "ask":
        s.pop("on_close", None)
    else:
        s["on_close"] = mode
    save_settings(s)
    var = _widgets.get("close_var")
    if var is not None and var.get() != mode:
        var.set(mode)
    log("ajustes: al cerrar la ventana -> " + dict(CLOSE_MODES)[mode].lower())


def _ask_close_mode():
    """Primera vez que se pulsa la X: pregunta que hacer y (si se deja
    marcado) lo recuerda. Devuelve 'minimize', 'quit' o None (cancelar)."""
    res = {"mode": None}
    box = tk.Toplevel(_root)
    box.title("Cerrar Growi Bridge")
    box.configure(bg=THEME["bg"])
    box.resizable(False, False)
    box.transient(_root)
    try:
        x = _root.winfo_x() + max(0, (_root.winfo_width() - S(420)) // 2)
        y = _root.winfo_y() + S(140)
        box.geometry(f"{S(420)}x{S(220)}+{x}+{y}")
    except Exception:
        pass
    tk.Label(box, text="¿Qué hago al cerrar la ventana?", font=(FONT, 13, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 4))
    tk.Label(box, text="Si me quedo en la bandeja sigo recibiendo tareas de Growi. "
             "Si salgo, se paran el puente y el runner.", font=(FONT, 10),
             bg=THEME["bg"], fg=THEME["muted"], wraplength=S(380),
             justify="left").pack(anchor="w", padx=20)
    remember = tk.BooleanVar(value=True)
    tk.Checkbutton(box, text="Recordar mi elección (se cambia en Ajustes)",
                   variable=remember, font=(FONT, 10), bg=THEME["bg"],
                   fg=THEME["text"], activebackground=THEME["bg"],
                   selectcolor="#FFFFFF").pack(anchor="w", padx=16, pady=(10, 6))
    row = tk.Frame(box, bg=THEME["bg"])
    row.pack(anchor="w", padx=20, pady=(4, 16))

    def _pick(mode):
        res["mode"] = mode
        if mode and remember.get():
            _set_close_mode(mode)
        box.destroy()

    first = ttk.Button(row, text="Minimizar a la bandeja", style="Accent.TButton",
                       command=lambda: _pick("minimize"))
    first.pack(side="left", padx=(0, 8))
    ttk.Button(row, text="Salir", command=lambda: _pick("quit")).pack(side="left", padx=(0, 8))
    ttk.Button(row, text="Cancelar", command=lambda: _pick(None)).pack(side="left")
    box.bind("<Escape>", lambda _e: _pick(None))
    box.protocol("WM_DELETE_WINDOW", lambda: _pick(None))
    first.focus_set()
    box.grab_set()
    _root.wait_window(box)
    return res["mode"]


def on_close_window():
    """La X de la ventana: hace lo que elegiste en Ajustes (minimizar a la
    bandeja o salir). Si aun no elegiste, lo pregunta una vez."""
    mode = load_settings().get("on_close")
    if mode not in ("minimize", "quit"):
        mode = _ask_close_mode()
    if mode == "quit":
        quit_app()
    elif mode == "minimize":
        hide_to_tray(toast=True)


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
    # Menu corto (reglas P0): Abrir, Paleta, Estado del proxy, Pausar
    # mascota, Salir. Lo demas (puente, runner, pantalla) sigue en la
    # ventana y en Ctrl+K.
    menu = pystray.Menu(
        pystray.MenuItem("Abrir Growi Bridge", lambda: _root.after(0, show_window), default=True),
        pystray.MenuItem("Paleta (Ctrl+K)", lambda: _tray_palette()),
        pystray.MenuItem(_tray_proxy_label, lambda: _tray_open_proxy()),
        pystray.MenuItem(_tray_mascot_label, lambda: _root.after(0, toggle_mascot)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", lambda: _root.after(0, quit_app)),
    )
    icon = pystray.Icon("GrowiBridge" + ("B" if LANE == "b" else ""), image, _tray_title(), menu)
    _patch_tray_clicks(icon)
    try:
        icon.run_detached()
    except AttributeError:
        threading.Thread(target=icon.run, daemon=True).start()
    return icon


# ================================================================ Venezuela primero
# Onboarding de 4 pasos, mapa de disponibilidad (availability.json), proxy
# central y visible (con cambio solo al modelo local si la nube cae), gasto
# visible en la bandeja (tres dineros separados) y tema oscuro siguiendo a
# Windows (Direccion Raycast de DESIGN.md).
AVAIL_FILE = APP_DIR / "availability.json"
_AV = {"rows": {}, "at": 0.0, "running": False, "first": True, "country_direct": "",
       "lock": threading.Lock(), "last_conn": None}
_SP = {"at": 0.0, "data": None, "running": False, "warned": set()}
_TOAST = {"ctx": None}
_OB = {"det": None, "frame": None}

# ---- tema oscuro (Raycast): se decide al arrancar, siguiendo a Windows
DARK_THEME = {
    "bg": "#1E1E20", "sidebar": "#252528", "card": "#2A2A2D", "field": "#1E1E20",
    "text": "#F2F2F7", "muted": "#AEAEB2", "line": "#3A3A3D",
    "green": "#34C759", "green_text": "#4CD964", "blue": "#4DA3FF",
    "orange": "#FF9500", "orange_text": "#FFB340", "red": "#FF6B6B",
}
# Colores fijos del tema claro -> su par oscuro (solo literales en mayusculas;
# los colores calculados por _lerp_color van en minusculas y no se tocan).
_DARK_MAP = {
    "#FFFFFF": "#1E1E20", "#F5F5F7": "#2A2A2D", "#1D1D1F": "#F2F2F7", "#5F5F63": "#AEAEB2",
    "#E5E5EA": "#3A3A3D", "#E8E8ED": "#3A3A3F", "#D2D2D7": "#4A4A4E", "#E9E9EA": "#48484C",
    "#0066CC": "#4DA3FF", "#1F7A33": "#4CD964", "#9A5200": "#FFB340", "#C81E1E": "#FF6B6B",
    "#DCEBFF": "#24364F", "#6E6E73": "#A1A1A6", "#FBECEC": "#3B2626", "#D8D8DD": "#505055",
    "#3A3A3C": "#D1D1D6", "#5A7086": "#8E9BAA",
}
_COLOR_OPTS = ("bg", "background", "fg", "foreground", "activebackground", "activeforeground",
               "highlightbackground", "highlightcolor", "selectbackground", "selectforeground",
               "insertbackground", "selectcolor", "disabledforeground", "fill", "outline",
               "troughcolor", "readonlybackground")
_THEME_STATE = {"dark": False}


def _system_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        v, _t = winreg.QueryValueEx(k, "AppsUseLightTheme")
        winreg.CloseKey(k)
        return int(v) == 0
    except Exception:
        return False


def _want_dark():
    forced = os.environ.get("GROWI_BRIDGE_THEME", "").strip().lower()
    if forced in ("dark", "oscuro"):
        return True
    if forced in ("light", "claro"):
        return False
    pref = load_settings().get("apariencia") or "sistema"
    if pref == "oscuro":
        return True
    if pref == "claro":
        return False
    return _system_dark()


def _fix_font(f):
    """Reglas P0: texto regular >= 12 px y en negrita >= 14 px (a 100 %)."""
    if isinstance(f, tuple) and len(f) >= 2 and isinstance(f[1], int) and f[1] > 0:
        st = " ".join(str(x) for x in f[2:]).lower()
        if "bold" in st and f[1] < 11:
            return (f[0], -S(14)) + tuple(f[2:])
        if f[1] < 9:
            return (f[0], 9) + tuple(f[2:])
    return f


def _filter_kw(cnf):
    if not isinstance(cnf, dict):
        return cnf
    dark = _THEME_STATE["dark"]
    for k, v in list(cnf.items()):
        if dark and k in _COLOR_OPTS and isinstance(v, str) and v in _DARK_MAP:
            cnf[k] = _DARK_MAP[v]
        elif k == "font":
            cnf[k] = _fix_font(v)
    return cnf


def _theme_init():
    """Antes de crear la ventana: decide claro u oscuro y pone el filtro de
    colores y tamanos minimos de letra en la frontera con Tk."""
    if not TK_OK or getattr(tk.BaseWidget, "_growi_theme", False):
        return
    if _want_dark():
        _THEME_STATE["dark"] = True
        THEME.update(DARK_THEME)
        globals()["PALETTE_RED"] = THEME["red"]
    orig_init = tk.BaseWidget.__init__
    orig_conf = tk.Misc._configure
    orig_create = tk.Canvas._create

    def __init__(self, master, widgetName, cnf={}, kw={}, extra=()):
        cnf = _filter_kw(dict(tk._cnfmerge((cnf, kw))) if (cnf or kw) else {})
        return orig_init(self, master, widgetName, cnf, {}, extra)

    def _configure(self, cmd, cnf, kw):
        if kw:
            kw = _filter_kw(dict(kw))
        if isinstance(cnf, dict) and cnf:
            cnf = _filter_kw(dict(cnf))
        return orig_conf(self, cmd, cnf, kw)

    def _create(self, itemType, args, kw):
        if kw:
            kw = _filter_kw(dict(kw))
        return orig_create(self, itemType, args, kw)

    tk.BaseWidget.__init__ = __init__
    tk.Misc._configure = _configure
    tk.Canvas._create = _create
    tk.BaseWidget._growi_theme = True


def _C(hexcolor):
    """Un color fijo del tema claro, en el tema que toca."""
    return _DARK_MAP.get(hexcolor, hexcolor) if _THEME_STATE["dark"] else hexcolor


def _theme_styles(style):
    """Estilos ttk (no pasan por el filtro): botones, campos, listas."""
    big = (FONT, -S(14), "bold")
    style.configure("Accent.TButton", font=big)
    style.configure("Treeview.Heading", font=(FONT, -S(14), "bold"))
    if not _THEME_STATE["dark"]:
        return
    T = THEME
    style.configure("TButton", background=T["card"], foreground=T["text"],
                    bordercolor="#4A4A4E", lightcolor=T["card"], darkcolor=T["card"])
    style.map("TButton", background=[("active", "#3A3A3F"), ("disabled", T["bg"])],
              foreground=[("disabled", "#8E8E93")])
    style.configure("Accent.TButton", background="#0A64C8", foreground="white")
    style.map("Accent.TButton", background=[("disabled", "#3A3A3F"), ("active", "#0A84FF")],
              foreground=[("disabled", "#B0B0B5")])
    style.configure("TEntry", fieldbackground=T["field"], foreground=T["text"],
                    insertcolor=T["text"], bordercolor="#4A4A4E")
    style.configure("TCombobox", fieldbackground=T["field"], foreground=T["text"],
                    background=T["card"], arrowcolor=T["text"], bordercolor="#4A4A4E")
    style.map("TCombobox", fieldbackground=[("readonly", T["field"])],
              selectbackground=[("readonly", T["field"])],
              selectforeground=[("readonly", T["text"])],
              foreground=[("readonly", T["text"])])
    style.configure("Treeview", background=T["field"], foreground=T["text"],
                    fieldbackground=T["field"])
    style.map("Treeview", background=[("selected", "#24364F")],
              foreground=[("selected", T["text"])])
    style.configure("Treeview.Heading", background=T["card"], foreground=T["muted"])
    style.configure("TCheckbutton", background=T["bg"], foreground=T["text"])
    for _sb in ("TScrollbar", "Vertical.TScrollbar"):
        style.configure(_sb, background="#3A3A3F", troughcolor=T["bg"], arrowcolor=T["muted"],
                        bordercolor=T["bg"], lightcolor="#3A3A3F", darkcolor="#3A3A3F")
    style.map("Vertical.TScrollbar", background=[("active", "#4A4A4E")])
    try:
        _root.option_add("*TCombobox*Listbox.background", T["field"])
        _root.option_add("*TCombobox*Listbox.foreground", T["text"])
        _root.option_add("*TCombobox*Listbox.selectBackground", "#24364F")
    except Exception:
        pass


def _dark_titlebar(win):
    """Barra de titulo oscura en Windows 11 (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    if not _THEME_STATE["dark"]:
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), 4)
    except Exception:
        pass


# ---- avisos (toasts): solo lo que importa, <50 letras, clic = su contexto
def toast(text, ctx=None):
    text = str(text)
    if len(text) > 49:
        text = text[:48].rstrip() + "…"
    _TOAST["ctx"] = ctx
    try:
        if _tray_icon is not None:
            _tray_icon.notify(text, "Growi Bridge")
    except Exception:
        pass


def _short(name, n=22):
    name = str(name or "")
    return name if len(name) <= n else name[:n - 1] + "…"


def _open_ctx(ctx):
    """Abre la ventana en el sitio exacto del aviso."""
    show_window()
    show = _widgets.get("show_page")
    if not show:
        return
    if not ctx:
        return
    kind = ctx[0]
    if kind == "tareas":
        show("tareas")
        tree = _widgets.get("tasks_tree")
        if tree is not None and len(ctx) > 1 and ctx[1] in _tasks_rows:
            try:
                tree.selection_set(ctx[1])
                tree.see(ctx[1])
            except Exception:
                pass
    elif kind in ("estado", "proxy", "mapa"):
        show("estado")
    elif kind == "gasto":
        show("tareas")
    elif kind == "modelos":
        show("modelos")


# ---- sondas de red (con y sin el proxy, nunca con el proxy de las variables)
def _probe(url, via_proxy=False, timeout=8, headers=None, max_body=600):
    """(codigo HTTP o None, cuerpo corto, ms, error legible)."""
    if via_proxy:
        purl = proxy_url()
        if not purl:
            return None, "", 0, "no hay proxy guardado"
        handler = urllib.request.ProxyHandler({"http": purl, "https": purl})
    else:
        handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(handler)
    req = urllib.request.Request(url, headers=dict({"User-Agent": "GrowiBridge"}, **(headers or {})))
    t0 = time.time()
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(max_body).decode("utf-8", "replace")
            return r.status, body, int((time.time() - t0) * 1000), ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read(max_body).decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, int((time.time() - t0) * 1000), ""
    except Exception as e:
        return None, "", int((time.time() - t0) * 1000), _net_reason(e)


def _net_reason(e):
    s = f"{type(e).__name__}: {e}"
    low = s.lower()
    if "407" in low or "proxy authentication" in low:
        return "el proxy rechazó tu usuario o clave"
    if "timed out" in low or "timeout" in low:
        return "no contesta (tiempo agotado)"
    if "getaddrinfo" in low or "name or service" in low or "11001" in low:
        return "no encuentro la dirección (¿sin internet?)"
    if "refused" in low or "10061" in low:
        return "rechaza la conexión"
    if "tunnel connection failed" in low:
        return "el proxy no deja pasar (" + s.split("Tunnel connection failed:")[-1].strip()[:40] + ")"
    if "10060" in low or "unreachable" in low:
        return "no se puede llegar"
    return s[:90]


def load_availability():
    try:
        d = json.loads(AVAIL_FILE.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("filas"), list):
            return d
    except (OSError, ValueError):
        pass
    return None


def _country_name(cfg, code):
    return (cfg.get("paises") or {}).get(code or "", code or "un país desconocido")


def _ip_country(cfg, via_proxy):
    for url in cfg.get("ip_info") or []:
        code, body, ms, err = _probe(url, via_proxy, timeout=cfg.get("timeout_s", 8))
        if code == 200:
            try:
                d = json.loads(body if body.strip().endswith("}") else body + "}")
            except ValueError:
                m = re.search(r'"country(?:_code)?"\s*:\s*"([A-Z]{2})"', body)
                d = {"country": m.group(1)} if m else {}
            c = d.get("country") or d.get("country_code") or ""
            if c:
                return c, d.get("ip") or "", ms, ""
        elif err:
            return "", "", ms, err
    return "", "", 0, "no supe el país"


def _row(fila, estado, frase, accion=None, ms=None, ruta=None, detalle=""):
    return {"id": fila["id"], "nombre": fila.get("nombre", fila["id"]), "estado": estado,
            "frase": frase, "como": fila.get("como", ""), "accion": accion, "ms": ms,
            "ruta": ruta, "detalle": detalle, "at": time.time()}


def _check_nube(cfg, fila):
    url = fila["url"]
    key = api_key_for(fila["clave"]) if fila.get("clave") in API_PROVIDERS else ""
    headers = {}
    if key and fila.get("clave_parametro"):
        url += ("&" if "?" in url else "?") + f"{fila['clave_parametro']}={key}"
    elif key:
        headers = _api_headers(fila["clave"], key)
    marks = [m.lower() for m in fila.get("bloqueo_marcas") or []]
    res, det = {}, []
    routes = [("directo", False)] + ([("proxy", True)] if proxy_url() else [])
    for name, via in routes:
        code, body, ms, err = _probe(url, via, timeout=cfg.get("timeout_s", 8), headers=headers)
        body_l = _scrub(body, key).lower()
        if err:
            res[name] = ("sin_respuesta", ms, err)
        elif any(m in body_l for m in marks):
            res[name] = ("bloqueado", ms, f"HTTP {code}")
        elif code in (fila.get("ok_codigos") or [200]):
            res[name] = ("ok", ms, f"HTTP {code}")
        elif not key and code in (fila.get("sin_clave_codigos") or []):
            res[name] = ("sin_clave", ms, f"HTTP {code}")
        else:
            res[name] = ("raro", ms, f"HTTP {code}")
        det.append(f"{name}: {res[name][0]} ({res[name][2]}, {ms} ms)")
    d, p = res.get("directo"), res.get("proxy")
    detalle = "; ".join(det)
    if d and d[0] == "ok":
        return _row(fila, "ok", fila.get("frase_ok", "Responde."), ("usar", "Usar"), d[1], "directo", detalle)
    if d and d[0] == "sin_clave":
        return _row(fila, "aviso", fila.get("frase_sin_clave", "Responde, falta tu clave."),
                    ("clave", "Poner clave"), d[1], "directo", detalle)
    if p and p[0] in ("ok", "sin_clave"):
        return _row(fila, "ok" if state.get("proxy_on") else "aviso",
                    fila.get("frase_solo_proxy", "Solo responde con el proxy."),
                    ("usar", "Usar"), p[1], "proxy", detalle)
    if any(x and x[0] == "bloqueado" for x in (d, p)):
        return _row(fila, "falla", fila.get("frase_bloqueado", "Bloqueado."), ("porque", "Ver por qué"),
                    None, None, detalle)
    why = (p or d)[2] if (p or d) else "sin datos"
    return _row(fila, "falla", f"No responde ({why}). La ruta que sí anda: el modelo local.",
                ("reintentar", "Reintentar"), None, None, detalle)


def _check_ollama(cfg, fila):
    code, body, ms, err = _probe(fila["url"], False, timeout=4, max_body=200000)
    if code == 200:
        try:
            models = [m.get("name") for m in json.loads(body).get("models") or []]
        except ValueError:
            models = []
        if models:
            names = ", ".join(friendly_model_name(m) for m in models[:2])
            return _row(fila, "ok", fila.get("frase_ok", "").format(n=len(models)) + f" ({names})",
                        ("usar", "Usar"), ms, "local", f"HTTP 200, {len(models)} modelos")
        return _row(fila, "aviso", fila.get("frase_sin_modelo", "Sin modelos."),
                    ("descargar", "Descargar modelo"), ms, "local", "HTTP 200, 0 modelos")
    return _row(fila, "falla", fila.get("frase_caido", "No responde."), ("reintentar", "Reintentar"),
                None, None, err or f"HTTP {code}")


def _check_proxy(cfg, fila):
    pc = proxy_config()
    if not pc.get("host") or not proxy_url():
        return _row(fila, "aviso", fila.get("frase_sin_proxy", "Sin proxy."), ("avanzado", "Ajustes"),
                    None, None, "no hay host ni clave guardados")
    t0 = time.time()
    try:
        socket.create_connection((pc["host"], int(pc["port"])), timeout=cfg.get("timeout_s", 8)).close()
    except Exception as e:
        motivo = f"no llego a {pc['host']}:{pc['port']} ({_net_reason(e)})"
        return _row(fila, "falla", fila.get("frase_caido", "{motivo}").format(motivo=motivo),
                    ("reintentar", "Reintentar"), None, None, motivo)
    tcp_ms = int((time.time() - t0) * 1000)
    code, ip, ms, err = _ip_country(cfg, True)
    if err or not code:
        motivo = err or "no supe por qué país sales"
        return _row(fila, "falla", fila.get("frase_caido", "{motivo}").format(motivo=motivo),
                    ("reintentar", "Reintentar"), None, None, f"TCP ok {tcp_ms} ms; {motivo}")
    pais = _country_name(cfg, code)
    _AV["country_proxy"] = code
    return _row(fila, "ok", fila.get("frase_ok", "Conectado.").format(pais=pais), ("probar", "Probar"),
                ms, "proxy", f"TCP {tcp_ms} ms; IP de salida {ip} ({code})")


def _check_internet(cfg, fila):
    best = None
    for url in fila.get("urls") or []:
        code, body, ms, err = _probe(url, False, timeout=cfg.get("timeout_s", 8))
        if code:
            best = (ms, url, code)
            break
    if not best:
        return _row(fila, "falla", fila.get("frase_caido", "Sin internet."), ("reintentar", "Reintentar"),
                    None, None, "ninguna página respondió")
    code, ip, _ms, _err = _ip_country(cfg, False)
    _AV["country_direct"] = code
    return _row(fila, "ok", fila.get("frase_ok", "Hay internet.").format(pais=_country_name(cfg, code)),
                ("reintentar", "Reintentar"), best[0], "directo", f"{best[1]}: HTTP {best[2]}")


_CHECKERS = {"nube": _check_nube, "ollama": _check_ollama, "proxy": _check_proxy,
             "internet": _check_internet}


def run_availability(only=None):
    """Comprueba de verdad cada fila de availability.json (en hilos)."""
    cfg = load_availability()
    if cfg is None:
        with _AV["lock"]:
            _AV["rows"] = {"_falta": {"id": "_falta", "nombre": "Mapa", "estado": "falla",
                                      "frase": "Falta availability.json junto al programa.",
                                      "como": "", "accion": None, "ms": None, "ruta": None,
                                      "detalle": "", "at": time.time()}}
        return
    filas = [f for f in cfg["filas"] if not only or f["id"] in only]
    out = {}

    def one(f):
        fn = _CHECKERS.get(f.get("tipo"))
        try:
            out[f["id"]] = fn(cfg, f) if fn else _row(f, "falla", "Tipo de fila desconocido.")
        except Exception as e:
            out[f["id"]] = _row(f, "falla", f"No pude comprobarlo ({type(e).__name__}).",
                                ("reintentar", "Reintentar"))
    ths = [threading.Thread(target=one, args=(f,), daemon=True) for f in filas]
    for t in ths:
        t.start()
    for t in ths:
        t.join(30)
    with _AV["lock"]:
        _AV["rows"].pop("_falta", None)
        _AV["rows"].update(out)
        _AV["at"] = time.time()
        _AV["order"] = [f["id"] for f in cfg["filas"]]
    log("disponibilidad: " + ", ".join(f"{k} {v['estado']}" for k, v in out.items()))


def start_availability(only=None, done=None):
    if _AV["running"]:
        return False
    _AV["running"] = True

    def _run():
        try:
            run_availability(only)
        finally:
            _AV["running"] = False
            _ui_call(_after_availability)
            if done:
                _ui_call(done)
    threading.Thread(target=_run, daemon=True).start()
    _render_avail()
    return True


def _availability_loop():
    time.sleep(3)
    while True:
        start_availability()
        cfg = load_availability() or {}
        time.sleep(max(2, int(cfg.get("cada_min") or 10)) * 60)


def conn_state():
    """conectado (la nube responde por la ruta en uso) / local (solo el
    modelo local) / sin (nada) / None (aun sin comprobar)."""
    rows = _AV["rows"]
    if not rows or "claude" not in rows:
        return None
    c, o = rows.get("claude") or {}, rows.get("ollama") or {}
    route_ok = c.get("estado") in ("ok", "aviso") and (
        c.get("ruta") == "directo" or (c.get("ruta") == "proxy" and state.get("proxy_on")))
    if route_ok:
        return "conectado"
    if o.get("estado") == "ok":
        return "local"
    return "sin"


def conn_text():
    st = conn_state()
    p = (_AV["rows"].get("proxy") or {})
    if st is None:
        return "○ Comprobando la conexión…"
    if st == "conectado":
        if state.get("proxy_on") and p.get("estado") == "ok":
            pais = _country_name(load_availability() or {}, _AV.get("country_proxy"))
            return f"● Conectado — sales por {pais}"
        return "● Conectado"
    if st == "local":
        return "● Solo local (sin nube)"
    return "● Sin conexión"


def _conn_color():
    return {"conectado": THEME["green_text"], "local": THEME["orange_text"],
            "sin": THEME["red"]}.get(conn_state(), THEME["muted"])


def _after_availability():
    st = conn_state()
    prev = _AV.get("last_conn")
    _AV["last_conn"] = st
    if st == "local" and prev != "local":
        state["nube_caida"] = True
        log("conexión: sin nube; las preguntas de la app van al modelo local")
        toast("Sin nube: uso el modelo local", ("estado",))
    elif st == "sin" and prev not in ("sin", None):
        state["nube_caida"] = True
        toast("Sin conexión: ni nube ni modelo local", ("estado",))
    elif st == "conectado":
        if state.get("nube_caida"):
            log("conexión: la nube volvió")
        state["nube_caida"] = False
    _render_avail()
    _refresh_conn_widgets()


# ---- proxy: probar, modos, exportar
def proxy_test_ui(btn=None, label=None, done=None):
    """Boton «Probar proxy» / «Conectar»: prueba el proxy y Claude por el proxy."""
    if btn is not None:
        btn.config(state="disabled")
    if label is not None:
        label.config(text="⠋ Probando el proxy…", fg=THEME["muted"])

    def _fin():
        if btn is not None:
            try:
                btn.config(state="normal")
            except Exception:
                pass
        if label is not None:
            try:
                label.config(text=_proxy_result_text(), fg=_proxy_result_color())
            except Exception:
                pass
        if done:
            done()
    if not start_availability(only=("proxy", "claude", "ollama"), done=_fin):
        _root.after(500, lambda: proxy_test_ui(btn, label, done))


def _proxy_result_text():
    p = _AV["rows"].get("proxy") or {}
    if not p:
        return "Sin comprobar todavía."
    if p.get("estado") == "ok":
        ms = f" ({p['ms']} ms)" if p.get("ms") else ""
        return "✓ " + p["frase"] + ms
    o = _AV["rows"].get("ollama") or {}
    tail = "" if o.get("estado") == "ok" else " El modelo local tampoco responde."
    return ("✗ " if p.get("estado") == "falla" else "! ") + p.get("frase", "") + tail


def _proxy_result_color():
    e = (_AV["rows"].get("proxy") or {}).get("estado")
    return {"ok": THEME["green_text"], "aviso": THEME["orange_text"]}.get(e, THEME["red"])


def _system_proxy():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        on = winreg.QueryValueEx(k, "ProxyEnable")[0]
        srv = winreg.QueryValueEx(k, "ProxyServer")[0] if on else ""
        winreg.CloseKey(k)
    except Exception:
        return ""
    if not srv:
        return ""
    m = re.search(r"https=([^;]+)", srv) or re.search(r"http=([^;]+)", srv)
    srv = m.group(1) if m else srv.split(";")[0]
    return srv if "://" in srv else "http://" + srv


def set_proxy_mode(mode):
    """vps (tu proxy) / sistema (el de Windows) / ninguno."""
    s = load_settings()
    s["proxy_mode"] = mode
    save_settings(s)
    if mode == "vps":
        ok, msg = set_proxy(True)
    elif mode == "ninguno":
        ok, msg = set_proxy(False)
    else:
        url = _system_proxy()
        if not url:
            ok, msg = False, "Windows no tiene un proxy puesto"
        else:
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE)
                for n in ("HTTPS_PROXY", "HTTP_PROXY"):
                    winreg.SetValueEx(key, n, 0, winreg.REG_SZ, url)
                winreg.CloseKey(key)
                os.environ["HTTPS_PROXY"] = os.environ["HTTP_PROXY"] = url
                _broadcast_env_change()
                state["proxy_on"] = True
                ok, msg = True, "uso el proxy de Windows"
            except OSError as e:
                ok, msg = False, f"no se pudo escribir en el registro: {e}"
    log(f"proxy: modo {mode}: {msg}")
    return ok, msg


def export_conversations():
    """Respaldo: conversaciones de Claude Code, historial de motores,
    resultados del runner y mensajes, en un .zip donde tu elijas."""
    default = f"growi-conversaciones-{datetime.now().strftime('%Y%m%d-%H%M')}.zip"
    docs = HOME_DIR / "Documents"
    path = filedialog.asksaveasfilename(
        title="Exportar mis conversaciones", defaultextension=".zip", initialfile=default,
        initialdir=str(docs if docs.is_dir() else HOME_DIR), filetypes=[("Archivo zip", "*.zip")])
    if not path:
        return
    lbl = _widgets.get("px_export_status")
    if lbl is not None:
        lbl.config(text="⠋ Exportando… (puede tardar un poco)", fg=THEME["muted"])
    sources = [(HOME_DIR / ".claude" / "projects", "claude-code"), (SESSIONS_DIR, "motores"),
               (RESULTS, "resultados"), (MESSAGES, "mensajes")]

    def _run():
        import zipfile
        n = 0
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for base, arc in sources:
                    if not base.is_dir():
                        continue
                    for f in base.rglob("*"):
                        if f.is_file() and f.suffix.lower() in (".jsonl", ".json", ".txt", ".md"):
                            try:
                                z.write(f, f"{arc}/{f.relative_to(base)}")
                                n += 1
                            except OSError:
                                pass
            msg, ok = f"✓ {n} archivos guardados en {Path(path).name}", True
        except Exception as e:
            msg, ok = f"✗ No se pudo exportar: {e}", False
        log(f"exportar: {msg}")
        if lbl is not None:
            _ui_call(lambda: lbl.config(text=msg, fg=THEME["green_text"] if ok else THEME["red"]))
    threading.Thread(target=_run, daemon=True).start()


# ---- gasto: tres dineros separados ($ real / $ equivalente Max / $0 local)
def _claude_plan():
    """max / pro / api / None. Solo lee el tipo de plan, nunca el token."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "api"
    try:
        d = json.loads((HOME_DIR / ".claude" / ".credentials.json").read_text(encoding="utf-8"))
        sub = ((d.get("claudeAiOauth") or {}).get("subscriptionType") or "").lower()
        return sub or None
    except (OSError, ValueError):
        return None


def _money_kind(d, plan):
    motor = str(d.get("motor") or "")
    model = str(d.get("model") or d.get("modelo") or "")
    if motor in ("llama", "ollama") or model.startswith("ollama:"):
        return "local"
    if motor == "api" or model.startswith("api:"):
        return "real"
    if motor in ("", "claude"):
        return "real" if plan == "api" else "equiv"
    return "otro"


_LIMIT_RE = re.compile(r"(usage limit|limit reached|5-hour limit|weekly limit|rate limit|"
                       r"l[ií]mite de uso)", re.I)


def spend_summary():
    plan = _claude_plan()
    today = datetime.now().astimezone().date().isoformat()
    cwd_of = {}
    for f in RESULTS.glob("*.orquestacion.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            cwd = ((d.get("plan") or {}).get("cwd")) or ""
            for t in [d.get("raiz")] + list(d.get("tareas") or []):
                if t and cwd:
                    cwd_of[t] = cwd
        except Exception:
            pass
    for f in list(DONE.glob("*.task.json"))[-500:]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("cwd"):
                cwd_of.setdefault(str(d.get("id") or f.stem), d["cwd"])
        except Exception:
            pass
    out = {"plan": plan, "hoy": {"real": 0.0, "equiv": 0.0, "local": 0, "real_sin_precio": 0},
           "total": {"real": 0.0, "equiv": 0.0, "local": 0}, "por_tarea": {}, "por_proyecto": {},
           "por_motor": {}, "limite": None}
    for pattern in ("*.result.json", "*.revision.json"):
        for f in RESULTS.glob(pattern):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict) or d.get("ollama_action"):
                continue
            kind = _money_kind(d, plan)
            cost = d.get("cost_usd") if isinstance(d.get("cost_usd"), (int, float)) else None
            when = str(d.get("finished_at") or d.get("revisado_at") or "")
            tid = str(d.get("raiz") or d.get("id") or f.stem.split(".")[0])
            is_today = when[:10] == today
            if kind == "local":
                out["total"]["local"] += 1
                if is_today and pattern == "*.result.json":
                    out["hoy"]["local"] += 1
            elif kind in ("real", "equiv") and cost is not None:
                out["total"][kind] += cost
                if is_today:
                    out["hoy"][kind] += cost
            elif kind == "real" and is_today:
                out["hoy"]["real_sin_precio"] += 1
            txt = f"{d.get('error') or ''} {str(d.get('result') or '')[:400]}"
            if d.get("status") != "ok" and _LIMIT_RE.search(txt):
                if not out["limite"] or when > out["limite"]["at"]:
                    out["limite"] = {"at": when, "tarea": tid, "texto": _LIMIT_RE.search(txt).group(0)}
            proj = Path(cwd_of.get(tid) or cwd_of.get(str(d.get("id"))) or str(INBOX)).name or "Inbox"
            motor = MOTOR_CORTO.get(d.get("motor") or "claude", d.get("motor") or "Claude")
            for bucket, k in (("por_tarea", tid), ("por_proyecto", proj), ("por_motor", motor)):
                b = out[bucket].setdefault(k, {"real": 0.0, "equiv": 0.0, "local": 0, "n": 0})
                b["n"] += 1 if pattern == "*.result.json" else 0
                if kind == "local":
                    b["local"] += 1
                elif cost is not None and kind in ("real", "equiv"):
                    b[kind] += cost
    out["cuota"] = max_quota()
    return out


def max_quota():
    """Cuota de Max (5 h, semana, Opus). Anthropic no publica una forma
    oficial de leerla, asi que no se inventa: 'disponible' es False."""
    return {"disponible": False,
            "motivo": "Anthropic no publica cuánto te queda de Max; no lo invento."}


def start_spend(force=False):
    if _SP["running"] or (not force and time.time() - _SP["at"] < 300):
        return
    _SP["running"] = True

    def _run():
        try:
            data = spend_summary()
            _SP.update(data=data, at=time.time(), error="")
        except Exception as e:
            _SP["error"] = f"{type(e).__name__}: {e}"
            log(f"gasto: no se pudo calcular ({_SP['error']})")
        finally:
            _SP["running"] = False
            _ui_call(_after_spend)
    threading.Thread(target=_run, daemon=True).start()


def _spend_loop():
    time.sleep(5)
    while True:
        start_spend(force=True)
        time.sleep(300)


def spend_lines():
    """Las 3 lineas del tooltip de la bandeja."""
    d = _SP.get("data")
    if not d:
        return ["Gasto: calculando…", "Max: cuota no disponible", "Local $0"]
    h = d["hoy"]
    stale = " (desactualizado)" if time.time() - _SP["at"] > 600 else ""
    l1 = f"Hoy ${h['real']:.2f} real / ${h['equiv']:.2f} equivalente Max"
    q = d.get("cuota") or {}
    if q.get("disponible"):
        l2 = (f"Max 5h {q['h5']:.0f}% · Semana {q['semana']:.0f}% · Opus {q['opus']:.0f}%"
              f" — reinicio {q.get('reinicio', '?')}")
    elif d.get("limite") and d["limite"]["at"][:10] == datetime.now().date().isoformat():
        l2 = f"Max: tope alcanzado a las {d['limite']['at'][11:16]}"
    else:
        l2 = "Max: cuota no disponible"
    l3 = f"Local $0 · {h['local']} tareas{stale}"
    return [l1, l2, l3]


def _quota_pct():
    q = ((_SP.get("data") or {}).get("cuota") or {})
    if not q.get("disponible"):
        return None
    return max(q.get("h5", 0), q.get("semana", 0), q.get("opus", 0))


def _after_spend():
    pct = _quota_pct()
    if pct is not None:
        q = _SP["data"]["cuota"]
        for lim in (90, 75):
            key = f"{q.get('reinicio')}:{lim}"
            if pct >= lim and key not in _SP["warned"]:
                _SP["warned"].add(key)
                toast(f"Max al {pct:.0f}%: pasa lo nuevo a local", ("gasto",))
                break
    _update_tray_title()
    _render_spend()
    _tray_state[0] = None  # redibujar el numero


def _tray_title():
    """Tooltip de la bandeja: las lineas de gasto; en el carril B, primero
    «Growi Bridge — carril B» para distinguirlo del A."""
    lines = list(spend_lines())
    if LANE == "b":
        lines.insert(0, "Growi Bridge — carril B")
    return "\n".join(lines)[:127]


def _update_tray_title():
    if _tray_icon is None:
        return
    try:
        _tray_icon.title = _tray_title()
    except Exception:
        pass


def _fmt_money(b):
    parts = []
    if b.get("real"):
        parts.append(f"${b['real']:.2f} real")
    if b.get("equiv"):
        parts.append(f"${b['equiv']:.2f} eq. Max")
    if b.get("local"):
        parts.append(f"$0 local ({b['local']})")
    return ", ".join(parts) or "$0"


def _render_spend():
    w = _widgets
    d = _SP.get("data")
    if w.get("sp_real") is None:
        return
    if not d:
        w["sp_real"].config(text="⠋")
        return
    h = d["hoy"]
    w["sp_real"].config(text=f"${h['real']:.2f}")
    w["sp_real_sub"].config(text="con tu clave" + (f"; {h['real_sin_precio']} sin precio"
                                                   if h["real_sin_precio"] else ""))
    w["sp_equiv"].config(text=f"${h['equiv']:.2f}")
    w["sp_equiv_sub"].config(text="no se cobra aparte (va en tu Max)" if d["plan"] == "max"
                             else "lo que costaría por API")
    w["sp_local"].config(text="$0")
    w["sp_local_sub"].config(text=f"{h['local']} tareas hoy en tu PC")
    q = d.get("cuota") or {}
    pct = _quota_pct()
    w["sp_quota"].config(text=f"{pct:.0f}%" if pct is not None else "no disponible")
    lim = d.get("limite")
    w["sp_quota_sub"].config(text=(f"Tope visto a las {lim['at'][11:16]} ({lim['tarea']})" if lim
                                   else q.get("motivo", "")))
    stale = time.time() - _SP["at"] > 600
    w["sp_when"].config(text=("Desactualizado: " if stale else "Actualizado a las ")
                        + datetime.fromtimestamp(_SP["at"]).strftime("%H:%M")
                        + ". Se recalcula cada 5 min.")
    tree = w.get("sp_tree")
    if tree is None:
        return
    view = w["sp_view"].get()
    bucket = {"tarea": "por_tarea", "proyecto": "por_proyecto", "motor": "por_motor"}[view]
    for it in tree.get_children():
        tree.delete(it)
    items = sorted(d[bucket].items(), key=lambda kv: -(kv[1]["real"] + kv[1]["equiv"] + kv[1]["local"] * 1e-3))
    for name, b in items[:30]:
        tree.insert("", "end", values=(name, f"${b['real']:.2f}", f"${b['equiv']:.2f}",
                                       str(b["local"]), str(b["n"])))


def _build_spend_card(tab):
    card = _card(tab, "Gasto",
                 "Tres dineros que nunca se mezclan: lo que pagas de verdad con tu clave, lo que "
                 "costaría por API lo que hiciste con Max (no se cobra aparte) y lo local ($0).")
    _widgets["sp_card"] = card
    grid = tk.Frame(card, bg=THEME["card"])
    grid.pack(fill="x", padx=16, pady=(0, 6))
    for i, (key, label) in enumerate((("sp_real", "Real hoy"), ("sp_equiv", "Equivalente Max hoy"),
                                      ("sp_local", "Local"), ("sp_quota", "Cuota de Max"))):
        cell = tk.Frame(grid, bg=THEME["bg"], padx=S(12), pady=S(10))
        cell.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 8, 0),
                  pady=(0 if i < 2 else 8, 0))
        grid.columnconfigure(i % 2, weight=1, uniform="sp")
        tk.Label(cell, text=label, font=(FONT, 9), bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w")
        _widgets[key] = tk.Label(cell, text="⠋", font=(FONT, 17, "bold"), bg=THEME["bg"],
                                 fg=THEME["text"])
        _widgets[key].pack(anchor="w")
        _widgets[key + "_sub"] = tk.Label(cell, text="", font=(FONT, 9), bg=THEME["bg"],
                                          fg=THEME["muted"], wraplength=S(250), justify="left")
        _widgets[key + "_sub"].pack(anchor="w")
    seg = tk.Frame(card, bg=THEME["card"])
    seg.pack(fill="x", padx=16, pady=(6, 2))
    _widgets["sp_view"] = tk.StringVar(value="tarea")
    for k, lab in (("tarea", "Por tarea"), ("proyecto", "Por proyecto"), ("motor", "Por motor")):
        tk.Radiobutton(seg, text=lab, value=k, variable=_widgets["sp_view"], indicatoron=0,
                       command=_render_spend, font=(FONT, 10), bg=THEME["card"], fg=THEME["text"],
                       selectcolor="#E8E8ED", activebackground="#E8E8ED", bd=0, padx=S(10), pady=S(3),
                       highlightthickness=S(2), highlightbackground=THEME["card"],
                       highlightcolor=THEME["blue"], cursor="hand2").pack(side="left", padx=(0, 4))
    tree = ttk.Treeview(card, columns=("que", "real", "equiv", "local", "n"), show="headings",
                        height=5, selectmode="browse")
    for col, txt, wd, st in (("que", "Qué", 220, True), ("real", "Real", 80, False),
                             ("equiv", "Equivalente Max", 130, False), ("local", "Local", 70, False),
                             ("n", "Tareas", 70, False)):
        tree.heading(col, text=txt, anchor="w")
        tree.column(col, width=S(wd), minwidth=S(50), stretch=st, anchor="w")
    tree.pack(fill="x", padx=16, pady=4)
    _widgets["sp_tree"] = tree
    _widgets["sp_when"] = tk.Label(card, text="", font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"])
    _widgets["sp_when"].pack(anchor="w", padx=16, pady=(0, 12))
    _render_spend()


# ---- mapa de disponibilidad (pestana Estado)
_AV_ICON = {"ok": ("✓", "green_text"), "aviso": ("!", "orange_text"), "falla": ("✗", "red")}


def _avail_action(rid, act):
    show = _widgets.get("show_page")
    row = _AV["rows"].get(rid) or {}
    if act in ("reintentar", "probar"):
        start_availability(only=(rid,) if rid not in ("proxy",) else ("proxy", "claude"))
    elif act == "descargar" and show:
        show("modelos")
    elif act == "clave" and show:
        show("apis")
    elif act == "avanzado":
        _toggle_px_advanced(True)
    elif act == "porque":
        messagebox.showinfo(f"{row.get('nombre')}: por qué",
                            f"{row.get('frase')}\n\nCómo lo sé: {row.get('como')}\n"
                            f"Lo que vi: {row.get('detalle') or '—'}\n\n"
                            "La ruta que sí anda: el modelo local (Ollama), gratis y en tu PC.")
    elif act == "usar":
        _use_engine_for(rid)


def _use_engine_for(rid):
    s = load_settings()
    if rid == "claude":
        if (_AV["rows"].get("claude") or {}).get("ruta") == "proxy" and not state.get("proxy_on"):
            set_proxy_mode("vps")
        s["default_engine"] = "sonnet"
    elif rid in ("chatgpt", "gemini"):
        prov = "openai" if rid == "chatgpt" else "gemini"
        if not api_key_for(prov):
            messagebox.showinfo("Falta tu clave", "Pon tu clave en APIs y vuelve a pulsar Usar.")
            _widgets["show_page"]("apis")
            return
        s["default_engine"] = f"api:{prov}:{api_model_for(prov)}"
    elif rid == "ollama":
        s["default_engine"] = "ollama:" + (default_ollama_model() or OLLAMA_MODEL)
    else:
        return
    save_settings(s)
    _refresh_engine_widgets()
    log(f"disponibilidad: ahora responde {s['default_engine']}")
    lbl = _widgets.get("av_status")
    if lbl is not None:
        lbl.config(text=f"✓ Listo: ahora te responde {_row_name(rid)}.", fg=THEME["green_text"])


def _row_name(rid):
    return (_AV["rows"].get(rid) or {}).get("nombre", rid)


def _render_avail():
    box = _widgets.get("av_box")
    if box is None:
        return
    _clear(box)
    cbg = THEME["card"]
    cfg = load_availability() or {"filas": []}
    order = [f["id"] for f in cfg.get("filas", [])] or list(_AV["rows"])
    for rid in order + [k for k in _AV["rows"] if k not in order]:
        r = _AV["rows"].get(rid)
        fila = next((f for f in cfg.get("filas", []) if f["id"] == rid), {"nombre": rid})
        row = tk.Frame(box, bg=cbg)
        row.pack(fill="x", padx=16, pady=4)
        if r is None:
            ic, col, frase = "⠋", "muted", "Comprobando…" if _AV["running"] else "Sin comprobar."
        else:
            ic, col = _AV_ICON.get(r["estado"], ("?", "muted"))
            frase = r["frase"]
        tk.Label(row, text=ic, font=(FONT, 12, "bold"), bg=cbg, fg=THEME[col], width=2).pack(
            side="left", anchor="n")
        left = tk.Frame(row, bg=cbg)
        left.pack(side="left", fill="x", expand=True)
        top = tk.Frame(left, bg=cbg)
        top.pack(fill="x")
        tk.Label(top, text=fila.get("nombre", rid), font=(FONT, 11, "bold"), bg=cbg,
                 fg=THEME["text"]).pack(side="left")
        if r and r.get("ms"):
            tk.Label(top, text=f"{r['ms']} ms" + (f", {r['ruta']}" if r.get("ruta") else ""),
                     font=(FONT, 9), bg="#E8E8ED", fg=THEME["text"], padx=S(6)).pack(side="left", padx=8)
        tk.Label(left, text=frase, font=(FONT, 10), bg=cbg, fg=THEME["text"], wraplength=S(470),
                 justify="left", anchor="w").pack(fill="x", anchor="w")
        tk.Label(left, text="Cómo lo sé: " + fila.get("como", ""), font=(FONT, 9), bg=cbg,
                 fg=THEME["muted"], wraplength=S(470), justify="left", anchor="w").pack(fill="x", anchor="w")
        if r and r.get("accion"):
            act, lab = r["accion"]
            style = "Accent.TButton" if act == "usar" and r["estado"] == "ok" else "TButton"
            ttk.Button(row, text=lab, style=style,
                       command=lambda i=rid, a=act: _avail_action(i, a)).pack(side="right", anchor="n")
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)
    when = _widgets.get("av_when")
    if when is not None:
        if _AV["running"]:
            when.config(text="⠋ Comprobando de verdad cada servicio…")
        elif _AV["at"]:
            cada = (cfg.get("cada_min") or 10)
            when.config(text=f"Comprobado a las {datetime.fromtimestamp(_AV['at']).strftime('%H:%M:%S')}. "
                             f"Se repite al arrancar y cada {cada} min.")
    btn = _widgets.get("av_btn")
    if btn is not None:
        btn.config(state="disabled" if _AV["running"] else "normal")


def _spin_avail(n=0):
    """Spinner visible mientras se comprueba (esperas > 300 ms)."""
    when = _widgets.get("av_when")
    if when is None or _root is None:
        return
    if _AV["running"]:
        when.config(text=f"{_SPIN[n % len(_SPIN)]} Comprobando de verdad cada servicio…")
        _root.after(120, lambda: _spin_avail(n + 1))


def _recheck_ui():
    if start_availability():
        _spin_avail()


def _build_avail_card(tab):
    card = _card(tab, "Mapa de disponibilidad",
                 "Qué responde desde aquí, comprobado de verdad por la app (con y sin el proxy). "
                 "Si algo falla, te digo la ruta que sí anda.")
    head = tk.Frame(card, bg=THEME["card"])
    head.pack(fill="x", padx=16, pady=(0, 4))
    _widgets["av_when"] = tk.Label(head, text="", font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"])
    _widgets["av_when"].pack(side="left")
    _widgets["av_btn"] = ttk.Button(head, text="Volver a comprobar", command=_recheck_ui)
    _widgets["av_btn"].pack(side="right")
    _widgets["av_box"] = tk.Frame(card, bg=THEME["card"])
    _widgets["av_box"].pack(fill="x")
    _widgets["av_status"] = tk.Label(card, text="", font=(FONT, 9), bg=THEME["card"],
                                     fg=THEME["green_text"])
    _widgets["av_status"].pack(anchor="w", padx=16, pady=(4, 12))
    _render_avail()


def _toggle_px_advanced(force=None):
    box, btn = _widgets.get("px_adv"), _widgets.get("px_adv_btn")
    if box is None:
        return
    show = (not box.winfo_ismapped()) if force is None else force
    if show:
        box.pack(fill="x", before=_widgets["px_adv_anchor"])
        btn.config(text="Ocultar ajustes avanzados")
    else:
        box.pack_forget()
        btn.config(text="Ajustes avanzados")


def _refresh_conn_widgets():
    txt, col = conn_text(), _conn_color()
    for key in ("conn_chip", "px_state"):
        lbl = _widgets.get(key)
        if lbl is not None:
            try:
                lbl.config(text=txt, fg=col)
            except Exception:
                pass
    lbl = _widgets.get("px_result")
    if lbl is not None and _AV["rows"].get("proxy"):
        lbl.config(text=_proxy_result_text(), fg=_proxy_result_color())
    b = _widgets.get("cloud_banner")
    if b is not None:
        down = conn_state() in ("local", "sin")
        if down and not b.winfo_ismapped():
            b.pack(fill="x", padx=20, pady=(12, 0))
        elif not down and b.winfo_ismapped():
            b.pack_forget()
            b.master.configure(height=1)
        if down:
            _widgets["cloud_banner_txt"].config(
                text="Sin conexión con la nube: trabajando con el modelo local, calidad menor."
                if conn_state() == "local" else
                "Sin conexión: ni la nube ni el modelo local responden. Mira el mapa en Estado.")


def local_fallback_model(model):
    """Si la nube cayo, lo que pide la app va al modelo local (aviso claro)."""
    if not state.get("nube_caida") or conn_state() != "local":
        return model, False
    if model.startswith("ollama:") or model in ("motor:llama", "motor:ollama"):
        return model, False
    return "ollama:" + (default_ollama_model() or OLLAMA_MODEL), True


# ---- bandeja: icono con distintivo de conexion y numero de cuota
def _tray_kind():
    if state["bridge"] != "corriendo":
        base = "sin"
    else:
        base = {"conectado": "ok", "local": "local", "sin": "sin"}.get(conn_state(), "idle")
    sync = False
    if TRANSFERS:
        try:
            sync = (datetime.now().astimezone() - datetime.fromisoformat(TRANSFERS[-1][3])
                    ).total_seconds() < 10
        except Exception:
            pass
    pct = _quota_pct()
    pulse = "2" if sync and _tick_n[0] % 2 else ""
    return f"{base}{pulse}|{'' if pct is None else int(pct)}"


def _tray_image2(kind):
    """Personaje + distintivo (verde conectado, ambar solo local, rojo sin
    conexion) + el % de Max que mas aprieta, si se puede leer."""
    try:
        from PIL import ImageDraw, ImageFont
        base = Image.open(TRAY_ICON if TRAY_ICON.is_file() else PHOTO).convert("RGBA")
    except Exception:
        return None
    state_k, pct = kind.split("|")
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    small = base.resize((56, 56), Image.LANCZOS)
    img.paste(small, (4, 4), small)
    d = ImageDraw.Draw(img)
    colors = {"ok": "#34C759", "ok2": "#8BE0A4", "local": "#FF9500", "local2": "#FFC266",
              "sin": "#FF3B30", "sin2": "#FF8A80"}
    if state_k in colors:
        d.ellipse([36, 36, 63, 63], fill=colors[state_k], outline="white", width=3)
    if pct:
        p = int(pct)
        fill = "#34C759" if p < 75 else "#FF9500" if p < 90 else "#FF3B30"
        try:
            font = ImageFont.truetype("segoeuib.ttf", 26)
        except Exception:
            font = None
        d.rounded_rectangle([0, 0, 40, 30], radius=8, fill=fill, outline="white", width=2)
        d.text((20, 15), str(min(p, 99)), fill="white", anchor="mm", font=font)
    return img


def _tray_tick():
    if _tray_icon is None:
        return
    kind = _tray_kind()
    if kind != _tray_state[0]:
        _tray_state[0] = kind
        img = _tray_image2(kind)
        if img is not None:
            _tray_icon.icon = img


def _patch_tray_clicks(icon):
    """Clic = desglose del gasto en Tareas; doble clic = abrir la ventana;
    clic en un aviso = su contexto exacto."""
    try:
        from pystray._util import win32 as pw
    except Exception:
        return
    orig = icon._message_handlers.get(pw.WM_NOTIFY)
    if orig is None:
        return
    pend = {"t": None}

    def _single():
        pend["t"] = None
        if _root is not None:
            _root.after(0, lambda: _open_ctx(("gasto",)))

    def handler(wparam, lparam):
        if lparam == 0x0203:  # WM_LBUTTONDBLCLK
            if pend["t"]:
                pend["t"].cancel()
                pend["t"] = None
            if _root is not None:
                _root.after(0, show_window)
            return 0
        if lparam == 0x0202:  # WM_LBUTTONUP
            if pend["t"]:
                return 0
            try:
                import ctypes
                ms = ctypes.windll.user32.GetDoubleClickTime()
            except Exception:
                ms = 400
            pend["t"] = threading.Timer(ms / 1000.0, _single)
            pend["t"].start()
            return 0
        if lparam == 0x0405:  # NIN_BALLOONUSERCLICK
            ctx = _TOAST.get("ctx")
            if _root is not None:
                _root.after(0, lambda: _open_ctx(ctx))
            return 0
        return orig(wparam, lparam)
    icon._message_handlers[pw.WM_NOTIFY] = handler


def _tray_proxy_label(_item=None):
    return "Estado del proxy: " + conn_text().lstrip("●○ ").strip()


def _tray_open_proxy():
    if _root is not None:
        _root.after(0, lambda: (_open_ctx(("estado",)), proxy_test_ui(
            _widgets.get("px_test_btn"), _widgets.get("px_result"))))


def _tray_palette():
    if _root is not None:
        _root.after(0, lambda: (show_window(), _open_palette()))


def _tray_mascot_label(_item=None):
    return "Pausar mascota" if state["mascot"] else "Mostrar mascota"


# ---- onboarding (4 pasos)
OB_ASSISTANTS = (
    ("muse", "Muse", "Tu asistente de siempre: te habla por WhatsApp y el chat, y usa este PC por el puente."),
    ("claude", "Claude Code", "Trabaja en tus carpetas desde este PC. El más listo; va por internet."),
    ("grok", "Grok", "El modelo de xAI, por internet, con tu clave."),
    ("dot", "Dot", "Tu asistente Dot: te contesta por el puente, como Muse."),
    ("codex", "Codex", "El agente de OpenAI: trabaja en tus carpetas desde este PC."),
    ("otro", "Otro", "Elige tú cuál responde de los que hay en este PC."),
)
OB_ENGINE = {"claude": "sonnet", "codex": "motor:codex", "grok": "api:xai:grok-4"}
OB_KEY_URL = {"anthropic": "https://console.anthropic.com/settings/keys",
              "openai": "https://platform.openai.com/api-keys",
              "xai": "https://console.x.ai", "gemini": "https://aistudio.google.com/apikey"}
OB_LEVELS = (("mirar", "Solo mirar", "Lee tus archivos, pero no cambia ni crea nada."),
             ("cambiar", "Mirar y cambiar", "Lee y cambia archivos; solo pregunta lo delicado."),
             ("preguntar", "Preguntarme siempre", "Antes de cambiar, borrar o enviar algo, te pregunta."))


def onboarding_needed():
    if os.environ.get("GROWI_BRIDGE_ONBOARDING") == "0":
        return False
    return not load_settings().get("onboarding_done")


def _cli_version(name):
    exe = shutil.which(name)
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=12,
                           creationflags=_NO_WINDOW, stdin=subprocess.DEVNULL)
        m = re.search(r"\d+\.\d+(?:\.\d+)?", (r.stdout or "") + (r.stderr or ""))
        return m.group(0) if m else "instalado"
    except Exception:
        return "instalado"


def onboarding_detect():
    """En silencio, sin bloquear: que hay instalado, Ollama, sesion, carpetas."""
    det = {"cli": {}, "ollama_models": None, "claude_plan": _claude_plan(), "folders": []}
    ths = []
    for n in ("claude", "codex", "ollama", "gemini"):
        def one(n=n):
            det["cli"][n] = _cli_version(n)
        ths.append(threading.Thread(target=one, daemon=True))
    for t in ths:
        t.start()
    code, body, _ms, _e = _probe("http://127.0.0.1:11434/api/tags", False, timeout=3, max_body=200000)
    if code == 200:
        try:
            det["ollama_models"] = [m.get("name") for m in json.loads(body).get("models") or []]
        except ValueError:
            det["ollama_models"] = []
    cands = list(load_folders())
    for p in (HOME_DIR / "Documents", HOME_DIR / "Desktop", HOME_DIR / "Downloads", INBOX):
        if p.is_dir() and str(p) not in cands:
            cands.append(str(p))
    det["folders"] = [p for p in cands if Path(p).is_dir()]
    for t in ths:
        t.join(15)
    log("configuración inicial: encontré " + ", ".join(
        f"{k} {v}" for k, v in det["cli"].items() if v) + f"; Ollama {len(det['ollama_models'] or [])} modelos")
    return det


def _ob_preselect(det):
    cli = det.get("cli") or {}
    if cli.get("claude"):
        return "claude"
    if cli.get("codex"):
        return "codex"
    return "muse"


def open_onboarding(root=None):
    """Pantalla completa sobre la ventana: 4 pasos, «Saltar por ahora» en
    todos. Se guarda todo en settings.json."""
    root = root or _root
    if _OB.get("frame") is not None:
        try:
            _OB["frame"].destroy()
        except Exception:
            pass
    bg, cbg, T = THEME["bg"], THEME["card"], THEME
    ov = tk.Frame(root, bg=bg)
    ov.place(relx=0, rely=0, relwidth=1, relheight=1)
    ov.lift()
    _OB.update(frame=ov, step=0, choice=tk.StringVar(value="claude"), other=tk.StringVar(),
               level=tk.StringVar(value="preguntar"), folder_vars={}, det=_OB.get("det"))
    col = tk.Frame(ov, bg=bg)
    col.place(relx=0.5, rely=0, anchor="n", relheight=1, width=min(S(680), max(S(480), root.winfo_width() - S(40))))
    _OB["col"] = col
    prog = tk.Canvas(col, height=S(6), bg=bg, highlightthickness=0, bd=0)
    prog.pack(fill="x", pady=(S(20), 0))
    _OB["prog"] = prog
    _OB["kicker"] = tk.Label(col, text="", font=(FONT, 10), bg=bg, fg=T["muted"])
    _OB["kicker"].pack(anchor="w", pady=(12, 0))
    _OB["title"] = tk.Label(col, text="", font=(FONT, 22, "bold"), bg=bg, fg=T["text"],
                            justify="left", anchor="w")
    _OB["title"].pack(anchor="w", fill="x")
    _OB["sub"] = tk.Label(col, text="", font=(FONT, 11), bg=bg, fg=T["muted"], justify="left",
                          anchor="w", wraplength=S(620))
    _OB["sub"].pack(anchor="w", fill="x", pady=(2, 10))
    foot = tk.Frame(col, bg=bg)
    foot.pack(side="bottom", fill="x", pady=(8, S(18)))
    tk.Frame(col, bg=T["line"], height=S(1)).pack(side="bottom", fill="x")
    _OB["skip"] = ttk.Button(foot, text="Saltar por ahora", command=lambda: _ob_next(skip=True))
    _OB["skip"].pack(side="left")
    _OB["next"] = ttk.Button(foot, text="Siguiente", style="Accent.TButton", command=_ob_next)
    _OB["next"].pack(side="right")
    _OB["back"] = ttk.Button(foot, text="Atrás", command=_ob_back)
    _OB["back"].pack(side="right", padx=(0, 8))
    body_holder = tk.Frame(col, bg=bg)
    body_holder.pack(fill="both", expand=True)
    _OB["body"] = _scrollable(body_holder)
    ov.bind_all("<Escape>", lambda _e: _ob_next(skip=True) if _OB.get("frame") else None)
    if _OB.get("det") is None:
        def _det():
            d = onboarding_detect()
            _OB["det"] = d
            _ui_call(lambda: (_OB["choice"].set(_ob_preselect(d)), _ob_render()))
        threading.Thread(target=_det, daemon=True).start()
    else:
        _OB["choice"].set(_ob_preselect(_OB["det"]))
    _ob_render()
    _OB["next"].focus_set()


def _ob_render():
    if _OB.get("frame") is None:
        return
    step = _OB["step"]
    T, bg, cbg = THEME, THEME["bg"], THEME["card"]
    prog = _OB["prog"]
    prog.delete("all")
    prog.update_idletasks()
    wd = max(prog.winfo_width(), S(400))
    seg = (wd - S(18)) / 4
    for i in range(4):
        x = i * (seg + S(6))
        prog.create_rectangle(x, 0, x + seg, S(6), fill=T["blue"] if i <= step else _C("#E5E5EA"),
                              outline="")
    titles = ("¿Quién te ayuda?", "Conectar", "Tus carpetas", "Comprobación")
    subs = ("Elige tu asistente principal: es el que te responde en la paleta (Ctrl+K) y en el chat. "
            "Los demás quedan como ayudantes para tareas concretas.",
            "Inicia sesión o pon tu clave, y conecta la salida a internet. Si no tienes la clave "
            "ahora, lo haces más tarde: nada se bloquea.",
            "Elige qué carpetas puede ver tu asistente y qué puede hacer en ellas.",
            "Pruebo de verdad que todo anda. Luego, a hablar.")
    _OB["kicker"].config(text=f"Paso {step + 1} de 4")
    _OB["title"].config(text=titles[step])
    _OB["sub"].config(text=subs[step], fg=T["muted"])
    _OB["back"].config(state="normal" if step else "disabled")
    _OB["next"].config(text="Empezar a hablar" if step == 3 else "Siguiente")
    _OB["skip"].config(text="Lo haré más tarde" if step == 1 else "Saltar por ahora")
    body = _OB["body"]
    _clear(body)
    det = _OB.get("det")
    if step == 0:
        if det is None:
            tk.Label(body, text="⠋ Buscando lo que ya tienes en este PC…", font=(FONT, 10), bg=bg,
                     fg=T["muted"]).pack(anchor="w", pady=4)
        else:
            cli = det["cli"]
            names = {"claude": "Claude Code", "codex": "Codex", "ollama": "Ollama", "gemini": "Gemini"}
            found = [f"{names[k]} {v}" for k, v in cli.items() if v]
            if det.get("ollama_models"):
                found.append(f"{len(det['ollama_models'])} modelo(s) en tu PC")
            if det.get("claude_plan"):
                found.append(f"sesión de Claude ({det['claude_plan'].capitalize()})")
            tk.Label(body, text="Encontré en este PC: " + (", ".join(found) if found else "nada todavía"),
                     font=(FONT, 10), bg=bg, fg=T["text"], wraplength=S(620), justify="left").pack(
                anchor="w", pady=(0, 8))
        card = tk.Frame(body, bg=cbg)
        card.pack(fill="x")
        for k, name, desc in OB_ASSISTANTS:
            row = tk.Frame(card, bg=cbg)
            row.pack(fill="x", padx=12, pady=4)
            tk.Radiobutton(row, text=name, value=k, variable=_OB["choice"], font=(FONT, 11, "bold"),
                           bg=cbg, fg=T["text"], activebackground=cbg, selectcolor="#FFFFFF", bd=0,
                           highlightthickness=S(2), highlightbackground=cbg,
                           highlightcolor=T["blue"], anchor="w",
                           command=_ob_render).pack(anchor="w")
            v = (det or {}).get("cli", {}).get(k if k != "claude" else "claude") if k in ("claude", "codex") else None
            extra = f"  ✓ Instalado ({v})" if v else ""
            tk.Label(row, text=desc + extra, font=(FONT, 9), bg=cbg, fg=T["muted"], wraplength=S(560),
                     justify="left").pack(anchor="w", padx=(S(24), 0))
            if k == "otro" and _OB["choice"].get() == "otro":
                cb = ttk.Combobox(row, textvariable=_OB["other"], width=36, state="readonly",
                                  values=[c[0] for c in engine_choices()])
                cb.pack(anchor="w", padx=(S(24), 0), pady=4)
                if not _OB["other"].get():
                    cb.current(0)
            tk.Frame(card, bg=T["line"], height=S(1)).pack(fill="x", padx=12)
    elif step == 1:
        ch = _OB["choice"].get()
        card = tk.Frame(body, bg=cbg)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Tu asistente", font=SECTION_FONT, bg=cbg, fg=T["text"]).pack(
            anchor="w", padx=16, pady=(12, 2))
        prov = {"claude": "anthropic", "codex": "openai", "grok": "xai"}.get(ch)
        if ch in ("muse", "dot"):
            on = state.get("bridge") == "corriendo"
            tk.Label(card, text=(f"✓ Se conecta por el puente, que está encendido (puerto {BRIDGE_PORT})." if on else
                                 "! El puente está apagado: enciéndelo en Estado para que te alcance."),
                     font=(FONT, 10), bg=cbg, fg=T["green_text"] if on else T["orange_text"],
                     wraplength=S(600), justify="left").pack(anchor="w", padx=16, pady=(0, 12))
        else:
            plan = (det or {}).get("claude_plan")
            if ch == "claude" and plan:
                tk.Label(card, text=f"✓ Ya iniciaste sesión en Claude (plan {plan.capitalize()}).",
                         font=(FONT, 10), bg=cbg, fg=T["green_text"]).pack(anchor="w", padx=16)
            elif ch in ("claude", "codex"):
                ttk.Button(card, text="Iniciar sesión en el navegador", style="Accent.TButton",
                           command=lambda c=ch: _ob_login(c)).pack(anchor="w", padx=16, pady=(0, 4))
            if prov:
                r = tk.Frame(card, bg=cbg)
                r.pack(fill="x", padx=16, pady=(6, 0))
                tk.Label(r, text="O usa tu clave:", font=(FONT, 10), bg=cbg, fg=T["text"]).pack(side="left")
                ent = ttk.Entry(r, width=30, show="•", font=(FONT, 10))
                ent.pack(side="left", padx=8)
                if api_key_for(prov):
                    ent.insert(0, api_key_for(prov))
                _OB["key_entry"], _OB["key_prov"] = ent, prov
                tk.Button(card, text="¿Dónde consigo mi clave?", font=(FONT, 10), bg=cbg, fg=T["blue"],
                          activebackground=cbg, activeforeground=T["blue"], bd=0, cursor="hand2",
                          highlightthickness=S(2), highlightcolor=T["blue"], highlightbackground=cbg,
                          command=lambda p=prov: _ob_open_url(OB_KEY_URL.get(p))).pack(anchor="w", padx=12, pady=(4, 0))
            else:
                _OB["key_entry"] = None
            tk.Frame(card, bg=cbg, height=S(10)).pack()
        card2 = tk.Frame(body, bg=cbg)
        card2.pack(fill="x")
        tk.Label(card2, text="Salida a internet", font=SECTION_FONT, bg=cbg, fg=T["text"]).pack(
            anchor="w", padx=16, pady=(12, 2))
        tk.Label(card2, text="Desde Venezuela, Claude y ChatGPT solo responden por tu proxy. Un clic y "
                 "lo pruebo con los datos que ya tienes guardados.", font=(FONT, 9), bg=cbg,
                 fg=T["muted"], wraplength=S(600), justify="left").pack(anchor="w", padx=16)
        r = tk.Frame(card2, bg=cbg)
        r.pack(fill="x", padx=16, pady=(8, 4))
        btn = ttk.Button(r, text="Conectar", style="Accent.TButton")
        btn.pack(side="left")
        res = tk.Label(card2, text=_proxy_result_text() if _AV["rows"].get("proxy") else "",
                       font=(FONT, 10, "bold"), bg=cbg, fg=_proxy_result_color(), wraplength=S(600),
                       justify="left")
        res.pack(anchor="w", padx=16, pady=(4, 12))
        btn.config(command=lambda: _ob_connect(btn, res))
    elif step == 2:
        card = tk.Frame(body, bg=cbg)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text="Qué carpetas ve", font=SECTION_FONT, bg=cbg, fg=T["text"]).pack(
            anchor="w", padx=16, pady=(12, 4))
        current = set(load_folders())
        folders = (det or {}).get("folders") or list(current)
        for p in folders + [p for p in _OB["folder_vars"] if p not in folders]:
            var = _OB["folder_vars"].setdefault(p, tk.BooleanVar(value=p in current))
            tk.Checkbutton(card, text=p, variable=var, font=(FONT, 10), bg=cbg, fg=T["text"],
                           activebackground=cbg, selectcolor="#FFFFFF", bd=0, anchor="w",
                           highlightthickness=S(2), highlightbackground=cbg,
                           highlightcolor=T["blue"]).pack(anchor="w", padx=12)
        ttk.Button(card, text="Añadir otra carpeta", command=_ob_add_folder).pack(anchor="w", padx=16, pady=(6, 12))
        card2 = tk.Frame(body, bg=cbg)
        card2.pack(fill="x")
        tk.Label(card2, text="Qué puede hacer en ellas", font=SECTION_FONT, bg=cbg, fg=T["text"]).pack(
            anchor="w", padx=16, pady=(12, 4))
        for k, lab, expl in OB_LEVELS:
            row = tk.Frame(card2, bg=cbg)
            row.pack(fill="x", padx=12, pady=3)
            tk.Radiobutton(row, text=lab, value=k, variable=_OB["level"], font=(FONT, 11, "bold"),
                           bg=cbg, fg=T["text"], activebackground=cbg, selectcolor="#FFFFFF", bd=0,
                           highlightthickness=S(2), highlightbackground=cbg,
                           highlightcolor=T["blue"], anchor="w").pack(anchor="w")
            tk.Label(row, text=expl, font=(FONT, 9), bg=cbg, fg=T["muted"]).pack(anchor="w", padx=(S(24), 0))
        tk.Frame(card2, bg=cbg, height=S(10)).pack()
    else:
        card = tk.Frame(body, bg=cbg)
        card.pack(fill="x", pady=(0, 8))
        _OB["checks"] = {}
        for k, lab in (("proxy", "Proxy"), ("motor", "Tu asistente"), ("carpetas", "Carpetas")):
            row = tk.Frame(card, bg=cbg)
            row.pack(fill="x", padx=16, pady=6)
            ic = tk.Label(row, text="⠋", font=(FONT, 13, "bold"), bg=cbg, fg=T["muted"], width=2)
            ic.pack(side="left", anchor="n")
            left = tk.Frame(row, bg=cbg)
            left.pack(side="left", fill="x", expand=True)
            tk.Label(left, text=lab, font=(FONT, 11, "bold"), bg=cbg, fg=T["text"]).pack(anchor="w")
            msg = tk.Label(left, text="Probando…", font=(FONT, 10), bg=cbg, fg=T["muted"],
                           wraplength=S(540), justify="left")
            msg.pack(anchor="w")
            _OB["checks"][k] = (ic, msg)
            tk.Frame(card, bg=T["line"], height=S(1)).pack(fill="x", padx=16)
        ttk.Button(card, text="Volver a probar", command=_ob_run_checks).pack(anchor="w", padx=16, pady=10)
        ex = tk.Frame(body, bg=cbg)
        ex.pack(fill="x")
        tk.Label(ex, text="Tu primera prueba", font=SECTION_FONT, bg=cbg, fg=T["text"]).pack(
            anchor="w", padx=16, pady=(12, 2))
        tk.Label(ex, text=f"Pulsa «Empezar a hablar» y envía: «{_ob_example()}»", font=(FONT, 10),
                 bg=cbg, fg=T["text"], wraplength=S(600), justify="left").pack(anchor="w", padx=16, pady=(0, 12))
        _ob_run_checks()


def _ob_example():
    return "Dime qué archivos hay en mi Inbox y resúmeme el más reciente en 3 líneas"


def _ob_open_url(url):
    if url:
        import webbrowser
        webbrowser.open(url)


def _ob_login(which):
    """Abre una consola con el programa para iniciar sesion en el navegador."""
    exe = shutil.which(which)
    if not exe:
        messagebox.showinfo("Iniciar sesión", f"No encuentro {which} en este PC. Puedes usar tu clave.")
        return
    args = [exe] if which == "claude" else [exe, "login"]
    try:
        subprocess.Popen(["cmd", "/k"] + args, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
        log(f"configuración inicial: abrí el inicio de sesión de {which}")
    except Exception as e:
        messagebox.showerror("Iniciar sesión", f"No pude abrirlo: {e}")


def _ob_connect(btn, res):
    def done():
        p = _AV["rows"].get("proxy") or {}
        if p.get("estado") == "ok" and not state.get("proxy_on"):
            set_proxy_mode("vps")
        res.config(text=_proxy_result_text(), fg=_proxy_result_color())
    proxy_test_ui(btn, res, done)


def _ob_add_folder():
    p = filedialog.askdirectory(title="Elige una carpeta")
    if p:
        p = str(Path(p))
        _OB["folder_vars"][p] = tk.BooleanVar(value=True)
        _ob_render()


def _ob_save_step(step):
    s = load_settings()
    if step == 0:
        ch = _OB["choice"].get()
        s["assistant"] = ch
        s["assistant_name"] = dict((k, n) for k, n, _d in OB_ASSISTANTS)[ch]
        if ch == "otro":
            lab = _OB["other"].get()
            model = dict((l, m) for l, m, _d in engine_choices()).get(lab)
            if model:
                s["default_engine"] = model
                s["assistant_name"] = lab
        elif ch in OB_ENGINE:
            s["default_engine"] = OB_ENGINE[ch]
        log(f"configuración inicial: asistente principal {s['assistant_name']}")
    elif step == 1:
        ent = _OB.get("key_entry")
        try:
            key = ent.get().strip() if ent is not None and ent.winfo_exists() else ""
        except Exception:
            key = ""
        prov = _OB.get("key_prov")
        if key and prov and key != api_key_for(prov):
            apis = [a for a in load_apis() if a.get("provider") != prov]
            apis.append({"name": API_PROVIDERS[prov]["label"], "provider": prov, "key": key})
            save_apis(apis)
            log(f"configuración inicial: clave de {API_PROVIDERS[prov]['label']} guardada (solo en este PC)")
    elif step == 2:
        roots = [p for p, v in _OB["folder_vars"].items() if v.get()]
        if roots:
            save_folders(roots)
        lvl = _OB["level"].get()
        s = load_settings()
        s["folder_access"] = lvl
        s["guardrail"] = {"mirar": "siempre", "cambiar": "delicado", "preguntar": "siempre"}[lvl]
        off = set(s.get("disabled_abilities") or [])
        for t in ("tool:Write", "tool:Edit"):
            (off.add if lvl == "mirar" else off.discard)(t)
        s["disabled_abilities"] = sorted(off)
        log(f"configuración inicial: {len(roots)} carpetas, nivel «{dict((k, l) for k, l, _e in OB_LEVELS)[lvl]}»")
    save_settings(s)


def _ob_next(skip=False):
    if _OB.get("frame") is None:
        return
    step = _OB["step"]
    if not skip:
        try:
            _ob_save_step(step)
        except Exception as e:
            log(f"configuración inicial: no se pudo guardar el paso {step + 1} ({e})")
    if step >= 3:
        _ob_finish(start=not skip)
        return
    _OB["step"] = step + 1
    _ob_render()


def _ob_back():
    if _OB.get("frame") is not None and _OB["step"] > 0:
        _OB["step"] -= 1
        _ob_render()


def _ob_finish(start=True):
    s = load_settings()
    s["onboarding_done"] = True
    s["onboarding_at"] = _now_iso()
    save_settings(s)
    log("configuración inicial: terminada" + ("" if start else " (saltada)"))
    try:
        _OB["frame"].destroy()
    except Exception:
        pass
    _OB["frame"] = None
    _scroll_canvases[:] = [c for c in _scroll_canvases if c.winfo_exists()]
    _refresh_engine_widgets()
    refresh_folders_ui()
    if start:
        show = _widgets.get("show_page")
        if show:
            show("tareas")
        box = _widgets.get("ask_text")
        if box is not None:
            box.delete("1.0", "end")
            box.insert("1.0", _ob_example())
            box.focus_set()
        st = _widgets.get("ask_status")
        if st is not None:
            st.config(text="Pulsa Enviar para tu primera prueba.", fg=THEME["blue"])


def _ob_set(k, ok, text):
    ic, msg = (_OB.get("checks") or {}).get(k, (None, None))
    if ic is None:
        return
    try:
        ic.config(text="✓" if ok else "✗", fg=THEME["green_text"] if ok else THEME["red"])
        msg.config(text=text, fg=THEME["text"])
    except Exception:
        pass


def _ob_run_checks():
    for k, (ic, msg) in (_OB.get("checks") or {}).items():
        ic.config(text="⠋", fg=THEME["muted"])
        msg.config(text="Probando…", fg=THEME["muted"])

    def _proxy_done():
        p = _AV["rows"].get("proxy") or {}
        _ob_set("proxy", p.get("estado") == "ok", _proxy_result_text().lstrip("✓✗! "))
    proxy_test_ui(None, None, _proxy_done)

    def _motor():
        s = load_settings()
        ch = s.get("assistant") or "claude"
        model = str(s.get("default_engine") or "sonnet")
        if ch in ("muse", "dot"):
            ok = state.get("bridge") == "corriendo"
            txt = ("El puente está encendido: tu asistente te alcanza." if ok
                   else "El puente está apagado: enciéndelo en Estado.")
        elif model.startswith("ollama:"):
            code, body, ms, err = _probe("http://127.0.0.1:11434/api/tags", False, timeout=4)
            ok = code == 200
            txt = f"El modelo local responde ({ms} ms), gratis." if ok else f"Ollama no responde ({err})."
        elif model.startswith("api:"):
            prov = model.split(":")[1]
            if prov in API_PROVIDERS and api_key_for(prov):
                ok, why = test_api(prov)
                txt = "Tu clave funciona." if ok else f"La clave no funcionó: {why}"
            else:
                ok, txt = False, "Falta tu clave: ponla en APIs (no bloquea nada)."
        else:
            which = "codex" if model == "motor:codex" else "claude"
            v = _cli_version(which)
            plan = _claude_plan() if which == "claude" else None
            ok = bool(v) and (which != "claude" or bool(plan))
            txt = (f"{'Claude Code' if which == 'claude' else 'Codex'} {v} listo"
                   + (f", con sesión {plan.capitalize()}." if plan else ".") if ok else
                   f"No encuentro {which} o falta iniciar sesión.")
            if ok and which == "claude" and conn_state() == "local":
                ok, txt = False, txt + " Pero ahora no llega a la nube: uso el modelo local."
        _ui_call(lambda: _ob_set("motor", ok, txt))

    def _carpetas():
        roots = load_folders()
        bad = [r for r in roots if not os.access(r, os.R_OK)]
        ok = bool(roots) and not bad
        lvl = dict((k, l) for k, l, _e in OB_LEVELS).get(load_settings().get("folder_access") or "preguntar")
        txt = (f"Veo {len(roots)} carpeta(s), con «{lvl}»." if ok else
               ("No puedo leer: " + ", ".join(bad)) if bad else "No elegiste ninguna carpeta.")
        _ui_call(lambda: _ob_set("carpetas", ok, txt))
    threading.Thread(target=_motor, daemon=True).start()
    threading.Thread(target=_carpetas, daemon=True).start()


def maybe_onboarding():
    if onboarding_needed():
        open_onboarding()


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

    # Un solo manejador para todas las paginas: mueve la que se esta viendo
    # (antes cada pagina pisaba al anterior y solo la ultima hacia scroll).
    _scroll_canvases.append(canvas)

    def _on_wheel(e):
        for c in _scroll_canvases:
            try:
                if c.winfo_ismapped():
                    c.yview_scroll(-1 if e.delta > 0 else 1, "units")
                    break
            except Exception:
                pass

    canvas.bind_all("<MouseWheel>", _on_wheel)
    return inner


_scroll_canvases = []


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


def _notify_task(title, msg, ctx=None):
    """Aviso de Windows (via pystray): corto (<50 letras) y con su contexto."""
    toast(msg, ctx or ("tareas",))


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
            action = d.get("ollama_action")
            if action == "list":
                continue
            if action in ("pull", "rm"):
                what = "instalado" if action == "pull" else "borrado"
                ok = d.get("status") == "ok"
                _notify_task("Growi Bridge",
                             f"Modelo {_short(friendly_model_name(d.get('model') or ''), 26)} "
                             f"{what if ok else 'con error'}", ("modelos",))
                continue
            # Las tareas normales avisan una sola vez, al final de su
            # orquestacion (abajo), no por cada ronda.
    except Exception:
        pass
    try:
        _watch_families()
    except Exception:
        pass


_seen_fam = {}
_fam_init = [False]


def _watch_families():
    """Un solo toast por tarea cuando queda aprobada / necesita decision /
    fallida / sin revision (y uno cuando espera tu aprobacion)."""
    first = not _fam_init[0]
    _fam_init[0] = True
    for f in RESULTS.glob("*.orquestacion.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        raiz, estado = d.get("raiz"), d.get("estado")
        key = (raiz, estado)
        if key in _seen_fam:
            continue
        _seen_fam[key] = True
        if first or estado not in FINAL_STATES + ("esperando_aprobacion",) or estado == "rechazada":
            continue
        cost = d.get("costo_usd")
        cost_txt = f" (${cost:.2f})" if isinstance(cost, (int, float)) else ""
        motor = _motor_txt(d.get("motor"), d)
        full = {
            "aprobada": f"Tarea aprobada: {raiz}, con {motor}{cost_txt}",
            "necesita_decision": f"Necesita tu decisión: {raiz} ({d.get('ronda')} rondas sin aprobar){cost_txt}",
            "fallida": f"Tarea fallida: {raiz}. {str(d.get('reporte') or '')[:90]}",
            "sin_revision": f"Terminó sin revisión: {raiz}, con {motor}{cost_txt}",
            "esperando_aprobacion": f"Growi espera tu aprobación: {raiz} (mira Tareas)",
        }[estado]
        msg = {
            "aprobada": f"Tarea lista: {_short(raiz, 32)}",
            "necesita_decision": f"Decide tú: {_short(raiz, 36)}",
            "fallida": f"Tarea fallida: {_short(raiz, 32)}",
            "sin_revision": f"Terminó sin revisión: {_short(raiz, 26)}",
            "esperando_aprobacion": f"Espera tu sí: {_short(raiz, 34)}",
        }[estado]
        _notify_task("Growi Bridge", msg, ("tareas", raiz))
        log(f"aviso: {full}")
        if estado == "aprobada":
            _celebrate_milestone()


MILESTONES = (1, 10, 25, 50, 100)


def _celebrate_milestone():
    """Cuenta las tareas aprobadas (en settings) y la mascota celebra solo
    los hitos: la primera, la 10, 25, 50, 100 y luego cada 100."""
    s = load_settings()
    n = int(s.get("aprobadas_total") or 0) + 1
    s["aprobadas_total"] = n
    save_settings(s)
    if n in MILESTONES or (n > 100 and n % 100 == 0):
        log(f"mascota: hito, {n} tareas aprobadas")
        try:
            _mascot_play("wave")
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


def _window_dpi(root):
    """DPI del monitor donde esta la ventana (GetDpiForWindow; con varios
    monitores cada uno tiene el suyo). GROWI_BRIDGE_DPI lo fija a mano,
    solo para probar 125 % / 150 % en un monitor a 100 %."""
    forced = os.environ.get("GROWI_BRIDGE_DPI", "").strip()
    if forced.isdigit() and 48 <= int(forced) <= 480:
        return int(forced)
    try:
        import ctypes
        user32 = ctypes.windll.user32
        root.update_idletasks()
        hwnd = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()  # GA_ROOT
        dpi = user32.GetDpiForWindow(hwnd)
        if not dpi:
            dpi = user32.GetDpiForSystem()
        return int(dpi) or 96
    except Exception:
        try:  # mismo factor que usa Tk para las fuentes: winfo_fpixels('1i')
            return int(round(root.winfo_fpixels("1i"))) or 96
        except Exception:
            return 96


def _scale_pads(kw):
    for k in ("padx", "pady", "ipadx", "ipady"):
        v = kw.get(k)
        if isinstance(v, int):
            kw[k] = S(v)
        elif isinstance(v, tuple):
            kw[k] = tuple(S(x) if isinstance(x, int) else x for x in v)


def _install_pad_scaling():
    """Los padx/pady/ipadx/ipady de pack() y grid() estan en pixeles a
    100 %: se escalan solos con SCALE (asi ningun margen queda fijo)."""
    if getattr(tk.Pack, "_growi_scaled", False):
        return
    orig_pack, orig_grid = tk.Pack.pack_configure, tk.Grid.grid_configure

    def pack_configure(self, cnf={}, **kw):
        if isinstance(cnf, dict) and cnf:
            kw = {**cnf, **kw}
            cnf = {}
        _scale_pads(kw)
        return orig_pack(self, cnf, **kw)

    def grid_configure(self, cnf={}, **kw):
        if isinstance(cnf, dict) and cnf:
            kw = {**cnf, **kw}
            cnf = {}
        _scale_pads(kw)
        return orig_grid(self, cnf, **kw)

    tk.Pack.pack_configure = tk.Pack.pack = pack_configure
    tk.Grid.grid_configure = tk.Grid.grid = grid_configure
    tk.Pack._growi_scaled = True


def _dpi_scaling(root):
    """Escala la interfaz al DPI de la ventana: las fuentes (tk scaling) y
    toda la geometria fija (SCALE = dpi / 96, ver S())."""
    global SCALE, MASCOT_SIZE
    dpi = _window_dpi(root)
    SCALE = dpi / 96
    try:
        root.tk.call("tk", "scaling", dpi / 72)
    except Exception:
        pass
    MASCOT_SIZE = S(128)
    _install_pad_scaling()
    log(f"DPI de la ventana: {dpi} ({round(SCALE * 100)} % de escalado)")


_PALETTE_CMDS = []
_tasks_fp = [None]
# Motores del desplegable (nombre normal -> model del task). Se rehace solo
# con los modelos instalados (accion list del runner) y las APIs con clave.
_ASK_ENGINES = {
    "Claude Sonnet": "sonnet", "Claude Opus": "opus", "Claude Haiku": "haiku",
}


def toggle_window():
    """Muestra u oculta la ventana (la usa el atajo global Ctrl+Alt+G)."""
    if _root is None:
        return
    try:
        if _root.state() == "iconic" or not _root.winfo_viewable():
            show_window()
        else:
            hide_to_tray(toast=False)
    except Exception:
        show_window()


# ---------------------------------------------------------------- paleta Ctrl+K
# Cada accion: id, label, keys (alias en espanol para la busqueda), fn,
# chip (atajo global, si lo tiene), danger (destructiva: se ve en rojo y
# con aviso) y more (acciones secundarias: lista de (texto, fn)).
_palette = {"win": None}
_PALETTE_FAVS_DEFAULT = ("pedir", "ir_tareas", "power")
PALETTE_RED = THEME["red"]


def _norm(text):
    """Minusculas y sin tildes, para comparar lo que se escribe."""
    t = unicodedata.normalize("NFKD", str(text).lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def _fuzzy_score(q, text):
    """Busqueda difusa: las letras de q aparecen en text en ese orden, no
    hace falta que esten juntas («md» encuentra «Modelos»). Puntua mas los
    inicios de palabra y las letras seguidas. None si no coincide."""
    if not q:
        return 0.0
    if q in text:
        start = text.startswith(q) or (" " + q) in text
        return 20.0 + (10.0 if start else 0.0) - len(text) * 0.05
    score, pos, prev = 0.0, 0, -2
    for ch in q:
        j = text.find(ch, pos)
        if j < 0:
            return None
        if j == prev + 1:
            score += 3
        if j == 0 or text[j - 1] in " /:-(":
            score += 5
        score -= min(j - pos, 10) * 0.2
        prev, pos = j, j + 1
    return score - len(text) * 0.05


def _palette_prefs():
    s = load_settings()
    favs = s.get("palette_favs")
    if not isinstance(favs, list):
        favs = list(_PALETTE_FAVS_DEFAULT)
    use = s.get("palette_use") if isinstance(s.get("palette_use"), dict) else {}
    return favs, use


def _palette_count(cid):
    s = load_settings()
    use = s.get("palette_use") if isinstance(s.get("palette_use"), dict) else {}
    use[cid] = int(use.get(cid, 0)) + 1
    s["palette_use"] = use
    save_settings(s)


def _palette_toggle_fav(cid):
    s = load_settings()
    favs = s.get("palette_favs")
    if not isinstance(favs, list):
        favs = list(_PALETTE_FAVS_DEFAULT)
    if cid in favs:
        favs.remove(cid)
    else:
        favs.append(cid)
    s["palette_favs"] = favs
    save_settings(s)


def _palette_sections(q):
    """Lo que muestra la paleta. Vacia: favoritos, frecuentes y el resto.
    Con texto: los resultados de la busqueda difusa, del mejor al peor."""
    favs, use = _palette_prefs()
    toks = _norm(q).split()
    if not toks:
        by_id = {c["id"]: c for c in _PALETTE_CMDS}
        fav = [by_id[i] for i in favs if i in by_id]
        fav_ids = {c["id"] for c in fav}
        freq = sorted((c for c in _PALETTE_CMDS
                       if int(use.get(c["id"], 0)) > 0 and c["id"] not in fav_ids),
                      key=lambda c: -int(use.get(c["id"], 0)))[:4]
        seen = fav_ids | {c["id"] for c in freq}
        rest = [c for c in _PALETTE_CMDS if c["id"] not in seen]
        return [("Favoritos", fav), ("Frecuentes", freq), ("Todas las acciones", rest)]
    scored = []
    for c in _PALETTE_CMDS:
        total = 0.0
        for tok in toks:
            best = None
            for text, bonus in ((_norm(c["label"]), 2.0), (_norm(c["keys"]), 0.0)):
                sc = _fuzzy_score(tok, text)
                if sc is not None and (best is None or sc + bonus > best):
                    best = sc + bonus
            if best is None:
                break
            total += best
        else:
            scored.append((total + min(int(use.get(c["id"], 0)), 10) * 0.1, c))
    scored.sort(key=lambda x: -x[0])
    return [("Resultados", [c for _s, c in scored[:12]])]


def _palette_ask_ai(q):
    """Nada coincide: la frase se manda como tarea a la IA (el motor
    elegido en Tareas), igual que el boton Enviar."""
    box, show = _widgets.get("ask_text"), _widgets.get("show_page")
    if box is None or show is None:
        return
    if load_settings().get("assistant") in ("muse", "dot"):
        # El asistente principal vive al otro lado del puente: la frase le
        # llega como mensaje (igual que la cajita de la mascota).
        MESSAGES.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt"
        (MESSAGES / name).write_text(q, encoding="utf-8")
        log(f"paleta: mensaje enviado a tu asistente ({name})")
        toast("Enviado: te responde en el chat", ("tareas",))
        return
    show("tareas")
    box.delete("1.0", "end")
    box.insert("1.0", q)
    _send_ask()


def _on_ctrl_k(_e=None):
    """Ctrl+K: abre la paleta. Si ya esta abierta no abre otra: con el foco
    en ella muestra las acciones secundarias de la fila elegida; si no,
    la trae al frente."""
    pal = _palette.get("win")
    try:
        alive = pal is not None and pal.winfo_exists()
    except Exception:
        alive = False
    if not alive:
        _open_palette()
        return "break"
    try:
        focus = pal.focus_get()
    except Exception:
        focus = None
    if focus is not None and str(focus).startswith(str(pal)):
        _palette["more"]()
    else:
        pal.deiconify()
        pal.lift()
        _palette["entry"].focus_set()
    return "break"


def _open_palette():
    """Paleta de comandos estilo Raycast (Ctrl+K). Nunca hay dos: si ya
    esta abierta, la trae al frente."""
    if _root is None or not _PALETTE_CMDS:
        return
    old = _palette.get("win")
    try:
        if old is not None and old.winfo_exists():
            old.deiconify()
            old.lift()
            _palette["entry"].focus_set()
            return
    except Exception:
        pass
    pal = tk.Toplevel(_root)
    _palette["win"] = pal
    pal.title("Buscar acciones")
    pal.attributes("-topmost", True)
    pal.configure(bg=THEME["bg"])
    pal.resizable(False, False)
    W, H = S(580), S(440)
    try:
        x = _root.winfo_x() + max(0, (_root.winfo_width() - W) // 2)
        y = _root.winfo_y() + S(70)
        pal.geometry(f"{W}x{H}+{x}+{y}")
    except Exception:
        pal.geometry(f"{W}x{H}")
    # Campo con borde azul (el foco esta aqui al abrir).
    field = tk.Frame(pal, bg=THEME["blue"], padx=S(2), pady=S(2))
    field.pack(fill="x", padx=12, pady=(12, 4))
    entry = tk.Entry(field, font=(FONT, 12), bg="#FFFFFF", fg=THEME["text"],
                     insertbackground=THEME["text"], borderwidth=0,
                     highlightthickness=0)
    entry.pack(fill="x", ipady=7, ipadx=6)
    _palette["entry"] = entry
    hint = tk.Label(pal, text="Escribe aunque sea a medias: «md» encuentra Modelos.",
                    font=(FONT, 9), bg=THEME["bg"], fg=THEME["muted"], anchor="w")
    hint.pack(fill="x", padx=14, pady=(0, 4))
    foot = tk.Label(pal, text="", font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
                    anchor="w", padx=S(12), pady=S(6))
    foot.pack(side="bottom", fill="x")
    holder = tk.Frame(pal, bg=THEME["bg"])
    holder.pack(fill="both", expand=True, padx=12, pady=(0, 8))
    canvas = tk.Canvas(holder, bg=THEME["bg"], highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=THEME["bg"])
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    st = {"items": [], "rows": [], "sel": 0, "mode": "main", "cmd": None, "q": ""}
    SEL_BG = "#E8E8ED"

    def _paint():
        for i, (row, parts, item) in enumerate(st["rows"]):
            on = i == st["sel"]
            bg = SEL_BG if on else THEME["bg"]
            row.config(bg=bg)
            for w_ in parts:
                w_.config(bg=bg)
            row._bar.config(bg=THEME["blue"] if on else bg)
            if row._enter is not None:
                row._enter.config(text="Enter" if on else "",
                                  bg="#D2D2D7" if on else bg)

    def _see():
        if not st["rows"]:
            return
        row = st["rows"][st["sel"]][0]
        pal.update_idletasks()
        total = max(1, inner.winfo_height())
        top, bottom = canvas.yview()
        y0, y1 = row.winfo_y() / total, (row.winfo_y() + row.winfo_height()) / total
        if y0 < top:
            canvas.yview_moveto(y0)
        elif y1 > bottom:
            canvas.yview_moveto(max(0.0, y1 - (bottom - top)))

    def _add_header(text):
        tk.Label(inner, text=text, font=(FONT, 9, "bold"), bg=THEME["bg"],
                 fg=THEME["muted"], anchor="w").pack(fill="x", padx=8, pady=(8, 2))

    def _add_row(item, chip=None):
        idx = len(st["rows"])
        danger = bool(item.get("danger"))
        fg = PALETTE_RED if danger else THEME["text"]
        row = tk.Frame(inner, bg=THEME["bg"], cursor="hand2")
        row.pack(fill="x")
        bar = tk.Frame(row, bg=THEME["bg"], width=S(3))
        bar.pack(side="left", fill="y")
        # Lo destructivo: rojo y con el simbolo de aviso (nunca solo color).
        text = ("⚠ " if danger else "") + item["label"]
        lab = tk.Label(row, text=text, font=(FONT, 11), bg=THEME["bg"], fg=fg, anchor="w")
        lab.pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=5)
        parts = [lab]
        if chip:
            c = tk.Label(row, text=chip, font=(FONT, 9), bg="#E8E8ED", fg=THEME["text"],
                         padx=S(6), pady=S(1))
            c.pack(side="right", padx=(0, 8))
        if danger:
            warn = tk.Label(row, text="pide confirmación", font=(FONT, 9),
                            bg=THEME["bg"], fg=PALETTE_RED)
            warn.pack(side="right", padx=(0, 8))
            parts.append(warn)
        enter = tk.Label(row, text="", font=(FONT, 9), bg=THEME["bg"], fg=THEME["text"],
                         padx=S(6), pady=S(1))
        enter.pack(side="right", padx=(0, 6))
        row._bar, row._enter = bar, enter
        for w_ in (row, lab, *parts[1:]):
            w_.bind("<Button-1>", lambda _e, i=idx: (_select(i), _run()))
            w_.bind("<Motion>", lambda _e, i=idx: st["sel"] != i and _select(i, see=False))
        st["rows"].append((row, parts, item))

    def _render():
        for child in inner.winfo_children():
            child.destroy()
        st["rows"], st["sel"] = [], 0
        if st["mode"] == "more":
            c = st["cmd"]
            favs, _use = _palette_prefs()
            _add_header(f"Más acciones para «{c['label']}»")
            _add_row({"label": "Ejecutar", "fn": c["fn"], "id": c["id"],
                      "danger": c.get("danger")}, chip="Enter")
            _add_row({"label": "Quitar de favoritos" if c["id"] in favs
                      else "Añadir a favoritos",
                      "fn": lambda cid=c["id"]: _palette_toggle_fav(cid), "keep": True})
            for lab, fn, *dz in c.get("more") or []:
                _add_row({"label": lab, "fn": fn, "danger": bool(dz and dz[0])})
            foot.config(text="Enter para elegir. Esc para volver a la lista.")
        else:
            q = entry.get().strip()
            n = 0
            for title, items in _palette_sections(q):
                if not items:
                    continue
                _add_header(title)
                for c in items:
                    n += 1
                    chip = c.get("chip") or (f"Alt+{n}" if n <= 9 else None)
                    _add_row(c, chip=chip)
            if not st["rows"] and q:
                _add_header("Nada coincide")
                _add_row({"id": "_ia", "label": f"Pedírselo a la IA: «{q[:60]}»",
                          "fn": lambda q=q: _palette_ask_ai(q)}, chip="Enter")
            foot.config(text="Enter para ejecutar. Ctrl+K para más acciones. "
                             "Esc para cerrar.")
        _paint()
        canvas.yview_moveto(0)

    def _select(i, see=True):
        if not st["rows"]:
            return
        st["sel"] = max(0, min(i, len(st["rows"]) - 1))
        _paint()
        if see:
            _see()

    def _run(_e=None):
        if not st["rows"]:
            return "break"
        item = st["rows"][st["sel"]][2]
        if item.get("keep"):
            item["fn"]()
            st["mode"] = "main"
            _render()
            return "break"
        cid = item.get("id") or (st["cmd"] or {}).get("id")
        pal.destroy()
        if cid and cid != "_ia":
            _palette_count(cid)
        try:
            item["fn"]()
        except Exception as e:
            log(f"paleta: no se pudo ejecutar ({e})")
        return "break"

    def _more():
        if st["mode"] == "more" or not st["rows"]:
            return
        item = st["rows"][st["sel"]][2]
        if not item.get("id") or item["id"] == "_ia":
            return
        st["mode"], st["cmd"] = "more", item
        _render()

    def _esc(_e=None):
        if st["mode"] == "more":
            st["mode"] = "main"
            _render()
        else:
            pal.destroy()
        return "break"

    def _alt(n):
        # Alt+N ejecuta la fila N de la lista (los chips lo dicen).
        k = 0
        for i, (_row, _parts, item) in enumerate(st["rows"]):
            if not item.get("id") or item["id"] == "_ia":
                continue
            k += 1
            if k == n:
                _select(i)
                return _run()
        return "break"

    def _wheel(e):
        canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        return "break"

    def _gone(e):
        if e.widget is pal:
            _palette["win"] = None

    _palette["more"] = _more
    def _on_type(_e=None):
        # Solo filtra si el texto cambio (flechas, Enter, Ctrl+K o Alt+N no).
        q = entry.get()
        if q == st["q"]:
            return
        st["q"] = q
        st["mode"] = "main"
        _render()

    entry.bind("<KeyRelease>", _on_type)
    entry.bind("<Down>", lambda _e: (_select(st["sel"] + 1), "break")[1])
    entry.bind("<Up>", lambda _e: (_select(st["sel"] - 1), "break")[1])
    entry.bind("<Return>", _run)
    pal.bind("<Escape>", _esc)
    pal.bind("<MouseWheel>", _wheel)
    pal.bind("<Destroy>", _gone)
    for _n in range(1, 10):
        pal.bind(f"<Alt-Key-{_n}>", lambda _e, n=_n: _alt(n))

    _render()
    entry.focus_set()


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
    if model.startswith("ollama:") and not valid_model_name(model.split(":", 1)[1]):
        model = "sonnet"
    model, fell = local_fallback_model(model)
    if fell:
        engine = "el modelo local (sin nube, calidad menor)"
    crit_box = w.get("ask_criterios")
    criterios = []
    if crit_box is not None:
        criterios = [c.strip(" -•\t") for c in crit_box.get("1.0", "end").splitlines()
                     if c.strip(" -•\t")]
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
    if model == "motor:auto":
        # Elige el runner; los permisos quedan por si elige Claude.
        data.pop("model")
        data["motor"] = AUTO
    elif model.startswith("motor:"):
        data.pop("model")
        data["motor"] = model.split(":", 1)[1]
        if data["motor"] != "claude":
            data.pop("allowed_tools")
        if data["motor"] not in ("claude", "codex"):
            data.pop("permission_mode")
    if criterios:
        data["criterios"] = criterios
    (TASKS / f"{task_id}.task.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"tareas: '{task_id}' enviado al runner ({engine})")
    text.delete("1.0", "end")
    if crit_box is not None:
        crit_box.delete("1.0", "end")
    if w.get("ask_status") is not None:
        w["ask_status"].config(text=f"✓ Enviado al runner ({engine})")
        _ask_spinner(task_id, engine)


_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_ask_spin = {"id": None, "job": None}


def _ask_spinner(task_id, engine, n=0, started=False, t0=None):
    """Fila de estado bajo «Enviar» mientras la tarea espera o trabaja: un
    spinner y lo que pasa (en cola, trabajando, terminada). Se para sola."""
    lbl = _widgets.get("ask_status")
    if lbl is None or _root is None:
        return
    if _ask_spin["id"] not in (None, task_id) and n == 0 and _ask_spin["job"]:
        try:
            _root.after_cancel(_ask_spin["job"])
        except Exception:
            pass
    _ask_spin["id"] = task_id
    t0 = t0 or time.time()
    cur = state.get("current") or ""
    working = task_id in cur
    started = started or working
    secs = int(time.time() - t0)
    g = _SPIN[n % len(_SPIN)]
    if working:
        lbl.config(text=f"{g} Trabajando en {task_id} con {engine}, lleva "
                        f"{secs // 60}:{secs % 60:02d}", fg=THEME["blue"])
    elif started:
        lbl.config(text=f"✓ {task_id} terminó. Mira su revisión en la lista de arriba.",
                   fg=THEME["green_text"])
        _ask_spin.update(id=None, job=None)
        return
    elif secs > 7200:
        _ask_spin.update(id=None, job=None)
        return
    else:
        why = "" if state.get("runner") == "corriendo" else " (el runner está apagado)"
        lbl.config(text=f"{g} En cola: {task_id}, esperando a que empiece{why}",
                   fg=THEME["muted"])
    _ask_spin["job"] = _root.after(
        120, lambda: _ask_spinner(task_id, engine, n + 1, started, t0))


ESTADOS_UI = dict(ESTADOS, terminada="terminada")
MOTOR_CORTO = {"claude": "Claude", "llama": "Hermes directo", "ollama": "Ollama",
               "codex": "Codex", "meshy": "Meshy", "api": "API", "modelos": "Modelos",
               "auto": "Automático"}


def _motor_txt(motor, fam=None):
    """Columna Motor: 'Auto → Sonnet' si lo eligio el modo Automatico."""
    el = (fam or {}).get("motor_elegido")
    if el:
        return f"Auto → {auto_label(el)}"
    return MOTOR_CORTO.get(motor, motor)
_tasks_rows = {}
_approvals_fp = [None]


def _task_rows():
    """Una fila por tarea original (sus rondas van dentro de la misma fila),
    mas las pendientes y las de antes de la orquestacion. Tambien el costo
    del dia y el total (resultados + revisiones)."""
    rows, fams, covered = [], {}, set()
    archivadas = cola_archivadas()
    for f in RESULTS.glob("*.orquestacion.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("raiz"):
            fams[d["raiz"]] = d
    for raiz, d in fams.items():
        covered.update(d.get("tareas") or [])
        covered.add(raiz)
        if raiz in archivadas:  # +30 dias: no se ve, pero sus archivos siguen ahi
            continue
        rows.append({"id": raiz, "estado": d.get("estado") or "pendiente",
                     "motor": d.get("motor") or "claude", "ronda": d.get("ronda") or 0,
                     "costo": d.get("costo_usd"), "rev": d.get("ultima_revision") or {},
                     "fam": d, "t": d.get("actualizado") or ""})
    for p in TASKS.glob("*.task.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict) or "ollama_action" in data:
            continue
        tid = str(data.get("id") or p.stem)
        if (data.get("raiz") or tid) in fams or tid in covered:
            continue
        motor = data.get("motor") or ("ollama" if str(data.get("model") or "").startswith("ollama:")
                                      else "claude")
        rows.append({"id": tid, "estado": "pendiente", "motor": motor, "ronda": 0, "costo": None,
                     "rev": {}, "fam": {"encargo": data.get("prompt"),
                                        "criterios": data.get("criterios") or []},
                     "t": datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")})
    total = today_total = 0.0
    today = datetime.now().astimezone().date().isoformat()
    res_idx = {}  # id -> (duracion, tokens entrada, tokens salida, modelo real)
    for pattern in ("*.result.json", "*.revision.json"):
        for f in RESULTS.glob(pattern):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            if pattern == "*.result.json":
                uso = d.get("uso") if isinstance(d.get("uso"), dict) else {}
                res_idx[str(d.get("id") or f.stem.split(".")[0])] = (
                    d.get("duration_s"), uso.get("tokens_in"), uso.get("tokens_out"),
                    uso.get("modelo_real") or d.get("modelo"))
            cost = d.get("cost_usd")
            if isinstance(cost, (int, float)):
                total += cost
                if (d.get("finished_at") or d.get("revisado_at") or "")[:10] == today:
                    today_total += cost
            if pattern != "*.result.json" or d.get("ollama_action") == "list":
                continue
            tid = d.get("id", f.stem)
            if tid in covered or d.get("raiz") in fams:
                continue
            model_action = bool(d.get("ollama_action"))
            estado = ("fallida" if d.get("status") != "ok"
                      else "terminada" if model_action else "sin_revision")
            rows.append({"id": tid, "estado": estado,
                         "motor": "modelos" if model_action else (d.get("motor") or "claude"),
                         "ronda": None, "costo": cost, "rev": {},
                         "fam": {"viejo": True, "reporte": d.get("error") or "",
                                 "motor_elegido": d.get("motor_elegido"),
                                 "motivo_eleccion": d.get("motivo_eleccion"),
                                 "resultado": (d.get("result") or "")[:400]},
                         "t": d.get("finished_at") or ""})
    for r in rows:
        ids = list(dict.fromkeys([r["id"]] + list((r["fam"] or {}).get("tareas") or [])))
        got = [res_idx[i] for i in ids if i in res_idx]
        durs = [g[0] for g in got if isinstance(g[0], (int, float))]
        tins = [g[1] for g in got if isinstance(g[1], int)]
        touts = [g[2] for g in got if isinstance(g[2], int)]
        r["dur"] = sum(durs) if durs else None
        r["tin"] = sum(tins) if tins else None
        r["tout"] = sum(touts) if touts else None
        r["modelo"] = next((g[3] for g in reversed(got) if g[3]), None) or (r["fam"] or {}).get("modelo")
    rows.sort(key=lambda r: r["t"], reverse=True)
    return rows, today_total, total


def _cost_cell(r):
    """Costo de una fila sin mezclar dineros: real, equivalente Max o local."""
    motor = str(r.get("motor") or "claude")
    if motor in ("llama", "ollama"):
        return "$0 local"
    if not isinstance(r.get("costo"), (int, float)):
        return "—"
    if motor == "api" or (motor == "claude" and _claude_plan() == "api"):
        return f"${r['costo']:.2f}"
    if motor == "claude":
        return f"${r['costo']:.2f} eq."
    return f"${r['costo']:.2f}"


# ---- consumo en vivo en la pestana Tareas (lee runner-live.json, no calcula)
_live_ui = {"fp": None}


def _model_label(m):
    """'claude-sonnet-5-5' -> 'Claude Sonnet 5.5'; lo demas tal cual."""
    m = str(m or "").split("/")[-1]
    mm = re.fullmatch(r"claude-([a-z]+)-(\d+)-(\d+)(?:-\d{8})?", m)
    if mm:
        return f"Claude {mm.group(1).capitalize()} {mm.group(2)}.{mm.group(3)}"
    return m or "—"


def _fmt_tok(n):
    if not isinstance(n, (int, float)):
        return "—"
    n = int(n)
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{n / 1e3:.1f} k" if n >= 1000 else str(n)


def _fmt_secs(s):
    if not isinstance(s, (int, float)):
        return "—"
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _money_txt(cost, kind, estimado=False, corto=False):
    """Un dinero con su etiqueta: nunca se mezclan. corto = como la columna
    Costo de siempre ('eq.')."""
    if kind == "local":
        return "$0 local"
    if not isinstance(cost, (int, float)):
        return "sin precio" if kind == "real" else "—"
    pre = "~" if estimado else ""
    return f"{pre}${cost:.2f}" + ((" eq." if corto else " eq. Max") if kind == "equiv"
                                  else "" if corto and kind == "real" else " real" if kind == "real" else "")


def _motor_modelo(motor_txt, mod):
    """'Claude' + 'claude-sonnet-5-5' -> 'Claude Sonnet 5.5' (sin repetir)."""
    if not mod or str(mod).startswith("@"):
        return motor_txt
    ml = _model_label(mod)
    return ml if ml.lower().startswith(motor_txt.lower()) else f"{motor_txt} / {ml}"


def _live_values(lv, corto=False):
    """Lo que la fila viva muestra (estado, motor/modelo, tiempo, tokens, costo)."""
    kind = lv.get("dinero") or "equiv"
    mod = lv.get("modelo_real") or lv.get("modelo")
    mtxt = _motor_modelo(MOTOR_CORTO.get(lv.get("motor"), lv.get("motor") or "—"), mod)
    sin = lv.get("modo_vivo") == "sin vivo"
    if lv.get("modo_vivo") == "esperando" and not lv.get("tokens_in") and not lv.get("tokens_out"):
        toks = "esperando al motor"
    elif sin and not lv.get("tokens_in") and not lv.get("tokens_out"):
        toks = "sin vivo"
    else:
        toks = f"{_fmt_tok(lv.get('tokens_in'))} / {_fmt_tok(lv.get('tokens_out'))}"
    if isinstance(lv.get("cost_usd_final"), (int, float)):
        cost = _money_txt(lv["cost_usd_final"], kind, corto=corto)
    elif sin and kind != "local":
        cost = "sin vivo"
    else:
        cost = _money_txt(lv.get("cost_usd_estimado"), kind, estimado=True, corto=corto)
    rev = lv.get("revision") or {}
    if lv.get("estado") == "revisando" and rev:
        rtxt = MOTOR_CORTO.get(rev.get("motor"), rev.get("motor") or "")
        c = rev.get("cost_usd_final") if isinstance(rev.get("cost_usd_final"), (int, float)) \
            else rev.get("cost_usd_estimado")
        rv = f"revisando con {rtxt}: {_fmt_tok(rev.get('tokens_in'))} / {_fmt_tok(rev.get('tokens_out'))}, " \
             + _money_txt(c, rev.get("dinero") or kind, estimado=not isinstance(rev.get("cost_usd_final"), (int, float)))
    else:
        rv = "—"
    return {"estado": lv.get("estado") or "en curso", "motor": mtxt,
            "tiempo": _fmt_secs(lv.get("elapsed_s")), "tokens": toks, "costo": cost, "revision": rv}


def _live_active():
    lv = read_live()
    if not lv:
        return None
    if lv.get("estado") == "terminado":
        try:  # se ve unos segundos mas, hasta que la fila normal tenga los datos
            age = time.time() - datetime.fromisoformat(str(lv.get("actualizado"))).timestamp()
        except (TypeError, ValueError):
            age = 999
        return lv if age < 20 else None
    return lv


def _apply_live_to_tree():
    tree = _widgets.get("tasks_tree")
    lv = _live_active()
    lbl = _widgets.get("live_line")
    if lbl is not None:
        if lv:
            v = _live_values(lv)
            extra = (f" {lv['nota']}." if lv.get("nota") else "")
            lbl.config(text=(f"En vivo: {lv.get('task_id')}, {v['estado']}, {v['motor']}, "
                             f"lleva {v['tiempo']}. Tokens entrada / salida: {v['tokens']}. "
                             f"Hasta ahora: {v['costo']}"
                             + (" (estimado a precio de lista; al terminar vale el que reporta Claude)"
                                if v["costo"].startswith("~") else "") + "." + extra),
                       fg=THEME["blue"] if lv.get("estado") != "terminado" else THEME["muted"])
        else:
            lbl.config(text="En vivo: no hay ninguna tarea corriendo.", fg=THEME["muted"])
    if tree is None or not lv:
        return
    iid = lv.get("raiz") or lv.get("task_id")
    if not iid or not tree.exists(iid):
        return
    v = _live_values(lv, corto=True)
    cur = list(tree.item(iid, "values"))
    if len(cur) < 8:
        return
    cur[1], cur[2], cur[4], cur[5], cur[6] = v["estado"], v["motor"], v["tiempo"], v["tokens"], v["costo"]
    if v["revision"] != "—":
        cur[7] = v["revision"]
    tree.item(iid, values=cur, tags=("en_curso" if lv.get("estado") != "terminado" else
                                     (tree.item(iid, "tags") or ("",))[0],))


def day_by_model(day=None):
    """Total del dia por dinero y modelo, sumando los .result.json terminados
    (y las revisiones, aparte). {(dinero, modelo): {...}}."""
    plan = _claude_plan()
    day = day or datetime.now().astimezone().date().isoformat()
    out = {}

    def add(kind, model, n, tin, tout, cost, rev=False):
        b = out.setdefault((kind, model, rev), {"n": 0, "tin": 0, "tout": 0, "cost": 0.0,
                                                "sin_precio": 0, "sin_tokens": 0})
        b["n"] += n
        if tin is None and tout is None:
            b["sin_tokens"] += n
        else:
            b["tin"] += int(tin or 0)
            b["tout"] += int(tout or 0)
        if kind == "local":
            return
        if isinstance(cost, (int, float)):
            b["cost"] += cost
        elif n:
            b["sin_precio"] += n

    for pattern in ("*.result.json", "*.revision.json"):
        for f in RESULTS.glob(pattern):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict) or d.get("ollama_action"):
                continue
            rev = pattern == "*.revision.json"
            if str(d.get("finished_at") or d.get("revisado_at") or "")[:10] != day:
                continue
            if rev:
                op = d.get("opinion_modelo") if isinstance(d.get("opinion_modelo"), dict) else {}
                mid = op.get("motor")
                if not mid:  # revision por reglas o por archivos: no gasta nada
                    continue
                rk = _money_kind({"motor": mid}, plan)
                c = d.get("cost_usd") if isinstance(d.get("cost_usd"), (int, float)) else None
                add(rk, op.get("modelo") or mid, 1, None, None, 0.0 if rk == "local" else c, rev=True)
                continue
            if d.get("estado") == "rechazada" or (not d.get("duration_s") and d.get("cost_usd") is None
                                                  and not d.get("uso")):
                continue  # no llego a correr: no consumio nada
            kind = _money_kind(d, plan)
            cost = d.get("cost_usd") if isinstance(d.get("cost_usd"), (int, float)) else None
            uso = d.get("uso") if isinstance(d.get("uso"), dict) else {}
            por = uso.get("por_modelo") if isinstance(uso.get("por_modelo"), dict) else {}
            if por:
                main = uso.get("modelo_real") or next(iter(por))
                for m, b in por.items():
                    c = b.get("cost_usd")
                    if c is None and len(por) == 1:
                        c = cost
                    add(kind, m, 1 if m == main else 0, b.get("tokens_in"), b.get("tokens_out"), c)
            else:
                m = (uso.get("modelo_real") or d.get("modelo") or d.get("model")
                     or ("Claude (sin detalle de modelo)" if (d.get("motor") or "claude") == "claude"
                         else MOTOR_CORTO.get(d.get("motor"), d.get("motor") or "—")))
                add(kind, m, 1, uso.get("tokens_in") if uso else None,
                    uso.get("tokens_out") if uso else None, cost)
    return out


_DINERO_TXT = (("real", "$ real (APIs con tu clave)"),
               ("equiv", "$ equivalente Max (sesión Max, a precio de lista; no se cobra aparte)"),
               ("local", "$0 local (tu PC)"),
               ("otro", "Otros (cobra otro plan)"))


def _render_day_models(force=False):
    tree = _widgets.get("dm_tree")
    if tree is None:
        return
    fp = (_tasks_fp[0], datetime.now().date().isoformat())
    if fp == _live_ui["fp"] and not force:
        return
    _live_ui["fp"] = fp
    data = day_by_model()
    for it in tree.get_children():
        tree.delete(it)
    totals = {}
    for kind, head in _DINERO_TXT:
        items = sorted(((k, b) for k, b in data.items() if k[0] == kind),
                       key=lambda kb: -(kb[1]["cost"] + kb[1]["tout"] * 1e-9))
        if not items:
            continue
        tot = sum(b["cost"] for _, b in items)
        totals[kind] = tot
        tree.insert("", "end", tags=("head",), values=(
            head, sum(b["n"] for _, b in items), "", "",
            "$0" if kind == "local" else f"${tot:.2f}"))
        for (_, model, rev), b in items:
            name = _model_label(model) + (" (revisiones)" if rev else "")
            toks_ok = b["n"] > b["sin_tokens"] or b["tin"] or b["tout"]
            cost = ("$0" if kind == "local" else f"${b['cost']:.2f}"
                    + (f" (+{b['sin_precio']} sin precio)" if b["sin_precio"] else ""))
            tree.insert("", "end", values=(
                "    " + name, b["n"],
                _fmt_tok(b["tin"]) if toks_ok else "—", _fmt_tok(b["tout"]) if toks_ok else "—", cost))
    if not tree.get_children():
        tree.insert("", "end", values=("Hoy no ha terminado ninguna tarea todavía.", "", "", "", ""))
    lbl = _widgets.get("dm_note")
    if lbl is not None:
        parts = [f"real ${totals.get('real', 0):.2f}", f"equivalente Max ${totals.get('equiv', 0):.2f}",
                 "local $0"]
        lbl.config(text="Hoy, solo lo terminado: " + "; ".join(parts) + ". Es lo acumulado: Max no "
                        "publica cuánto te queda, así que aquí no se muestra ninguna cuota. Las tareas "
                        "viejas sin detalle de tokens salen con «—».")


def _build_live_card(tab, before=None):
    card = tk.Frame(tab, bg=THEME["card"])
    card.pack(fill="x", padx=20, pady=(4, 8), before=before)
    tk.Label(card, text="Consumo de hoy por modelo", font=SECTION_FONT, bg=THEME["card"],
             fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    tree = ttk.Treeview(card, columns=("que", "n", "ent", "sal", "costo"), show="headings",
                        height=6, selectmode="none")
    for col, txt, wd, st in (("que", "Modelo", 300, True), ("n", "Tareas", 60, False),
                             ("ent", "Entrada", 80, False), ("sal", "Salida", 80, False),
                             ("costo", "Costo", 130, False)):
        tree.heading(col, text=txt, anchor="w")
        tree.column(col, width=S(wd), minwidth=S(40), stretch=st, anchor="w")
    tree.tag_configure("head", font=(FONT, 10, "bold"))
    tree.pack(fill="x", padx=16, pady=4)
    _widgets["dm_tree"] = tree
    _widgets["dm_note"] = tk.Label(card, text="", font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
                                   wraplength=S(620), justify="left")
    _widgets["dm_note"].pack(anchor="w", padx=16, pady=(0, 12))
    _render_day_models(force=True)


def _refresh_live_ui():
    try:
        _apply_live_to_tree()
        _render_day_models()
    except Exception as e:
        log(f"tareas: vivo no se pudo dibujar ({type(e).__name__}: {e})")


def _rev_summary(row):
    rv = row["rev"] or {}
    if rv.get("aprobado") is True:
        return "Sí"
    if rv.get("aprobado") is False:
        return "No: " + "; ".join(rv.get("que_falta") or [])[:90]
    return "sin revisión" if row["estado"] == "sin_revision" else "—"


def _task_detail_text(row):
    d = row["fam"] or {}
    rv = row["rev"] or {}
    head = [row["id"], ESTADOS_UI.get(row["estado"], row["estado"]),
            _motor_txt(row["motor"], d)]
    if row["ronda"] is not None:
        head.append(f"ronda {row['ronda']}/{MAX_ROUNDS}")
    if isinstance(row["costo"], (int, float)):
        head.append(_cost_cell(row) + (" (equivalente: no se cobra aparte en Max)"
                                       if _cost_cell(row).endswith("eq.") else ""))
    if d.get("fase"):
        head.append(str(d["fase"]))
    lines = [", ".join(head)]
    if d.get("motor_elegido"):
        lines.append(f"Quién respondió: {auto_label(d['motor_elegido'])}, elegido por el modo "
                     f"Automático. Por qué: {d.get('motivo_eleccion') or '—'}")
    if d.get("encargo"):
        lines.append("Encargo: " + re.sub(r"\s+", " ", str(d["encargo"]))[:300])
    if d.get("criterios"):
        lines.append("Criterios:")
        lines += [f"   – {c}" for c in d["criterios"]]
    if rv:
        lines.append(f"Revisión ({rv.get('motor') or '—'}): "
                     + ("aprobada" if rv.get("aprobado") else "no aprobada" if rv.get("aprobado") is False
                        else "sin revisión"))
        if rv.get("que_falta"):
            lines.append("Qué falta:")
            lines += [f"   – {x}" for x in rv["que_falta"]]
        if rv.get("evidencia"):
            lines.append("Evidencia:")
            lines += [f"   – {x}" for x in rv["evidencia"][:6]]
    if d.get("resultado"):
        lines.append("Resultado: " + re.sub(r"\s+", " ", d["resultado"])[:300])
    if d.get("reporte"):
        lines.append("Reporte: " + str(d["reporte"]))
    if d.get("siguiente"):
        lines.append(f"Siguiente: {d['siguiente']}")
    if row["estado"] == "esperando_reintento" and d.get("proximo_reintento"):
        lines.append(f"Próximo reintento: {str(d['proximo_reintento'])[11:19]} (reintento "
                     f"{d.get('reintentos')}/{MAX_RETRIES}). Motivo: "
                     + str(d.get("motivo_reintento") or "")[:200])
    elif d.get("reintentos"):
        lines.append(f"Reintentos por errores pasajeros: {d['reintentos']}")
    if d.get("recuperada_tras_corte"):
        lines.append("Recuperada tras corte" + (f": {d['nota_cola']}" if d.get("nota_cola") else ""))
    return "\n".join(lines)


def _estado_txt(r):
    """Texto de la columna Estado (con la hora del proximo reintento)."""
    d = r["fam"] or {}
    if r["estado"] == "esperando_reintento" and d.get("proximo_reintento"):
        return f"reintento {str(d['proximo_reintento'])[11:19]}"
    if r["estado"] == "pendiente" and d.get("recuperada_tras_corte"):
        return "en cola (tras corte)"
    return ESTADOS_UI.get(r["estado"], r["estado"])


def _show_task_detail(_e=None):
    tree, lbl = _widgets.get("tasks_tree"), _widgets.get("tasks_detail")
    if tree is None or lbl is None:
        return
    sel = tree.selection()
    row = _tasks_rows.get(sel[0]) if sel else None
    lbl.config(text=_task_detail_text(row) if row else
               "Elige una tarea de la lista para ver su revisión y su reporte.")


def _requeue_ui():
    """Boton «Volver a la cola»: repite una tarea fallida, huerfana tras un
    corte o que necesita tu decision (su ultimo task)."""
    tree = _widgets.get("tasks_tree")
    sel = tree.selection() if tree is not None else ()
    row = _tasks_rows.get(sel[0]) if sel else None
    if not row:
        messagebox.showinfo("Tareas", "Elige primero una tarea de la lista.")
        return
    fam = row["fam"] or {}
    ids = [fam.get("ultimo_resultado"), *reversed(fam.get("tareas") or []), row["id"]]
    msg = "esa tarea no está en la cola"
    for tid in dict.fromkeys(x for x in ids if x):
        ok, msg = cola_reencolar(tid)
        if ok:
            if load_family(row["id"]):
                _family_update(row["id"], estado="pendiente", en_curso=None,
                               nota_cola="la volviste a encolar")
            break
        if msg.startswith("ya está"):
            break
    messagebox.showinfo("Tareas", f"{row['id']}: {msg}")
    _tasks_fp[0] = None
    _refresh_tasks_ui()


def _approve_ui(raiz, ok):
    fn = approve_waiting if ok else reject_waiting
    done, msg = fn(raiz)
    if not done:
        messagebox.showinfo("Tareas", msg)
    _tasks_fp[0] = None
    _approvals_fp[0] = None
    _refresh_tasks_ui()


def _render_approvals(rows):
    """Tarjeta «Esperan tu aprobación»: el plan de cada tarea que quiere
    borrar, publicar, gastar o enviar algo, con Aprobar / Rechazar."""
    box = _widgets.get("approvals_box")
    if box is None:
        return
    waiting = [r for r in rows if r["estado"] == "esperando_aprobacion"]
    fp = tuple((r["id"], r["t"]) for r in waiting)
    if fp == _approvals_fp[0]:
        return
    _approvals_fp[0] = fp
    _clear(box)
    if not waiting:
        box.pack_forget()
        return
    box.pack(fill="x", padx=20, pady=(0, 8), before=_widgets["tasks_tree"])
    tk.Label(box, text="Esperan tu aprobación", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    for r in waiting:
        plan = (r["fam"] or {}).get("plan") or {}
        acc = plan.get("acciones") or {}
        quiere = ", ".join(f"{k} ({', '.join(v.get('palabras') or [])})" for k, v in acc.items())
        row = tk.Frame(box, bg=THEME["card"])
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text=f"{r['id']} quiere {quiere}", font=(FONT, 10, "bold"),
                 bg=THEME["card"], fg=THEME["text"], wraplength=S(600), justify="left").pack(anchor="w")
        perms = plan.get("permisos") or {}
        tk.Label(row, text=(f"Motor: {_motor_txt(plan.get('motor'), plan)}   "
                            f"Carpeta: {plan.get('cwd')}   "
                            f"Permisos: {perms.get('permission_mode') or 'los normales'}"),
                 font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"], wraplength=S(600),
                 justify="left").pack(anchor="w")
        tk.Label(row, text="Plan: " + re.sub(r"\s+", " ", plan.get("prompt") or "")[:500],
                 font=(FONT, 9), bg=THEME["card"], fg=THEME["text"], wraplength=S(600),
                 justify="left").pack(anchor="w", pady=(2, 4))
        brow = tk.Frame(row, bg=THEME["card"])
        brow.pack(anchor="w")
        ttk.Button(brow, text="Aprobar", style="Accent.TButton",
                   command=lambda x=r["id"]: _approve_ui(x, True)).pack(side="left", padx=(0, 8))
        ttk.Button(brow, text="Rechazar",
                   command=lambda x=r["id"]: _approve_ui(x, False)).pack(side="left")
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)
    tk.Frame(box, bg=THEME["card"], height=S(8)).pack()


def _refresh_tasks_ui():
    """Pagina Tareas: estado, motor, ronda, costo acumulado y revision de
    cada tarea. Solo re-dibuja si algo cambio."""
    w = _widgets
    tree = w.get("tasks_tree")
    if tree is None:
        return
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        files = list(RESULTS.glob("*.json"))
        fp = (len(files), max((f.stat().st_mtime for f in files), default=0),
              tuple(sorted(p.name for p in TASKS.glob("*.task.json"))),
              tuple(sorted(p.name for p in WAITING.glob("*.task.json"))))
        if fp == _tasks_fp[0]:
            return
        _tasks_fp[0] = fp
        rows, today_total, total = _task_rows()
        sel = tree.selection()
        keep = sel[0] if sel else None
        for item in tree.get_children():
            tree.delete(item)
        _tasks_rows.clear()
        for r in rows[:40]:
            iid = r["id"]
            _tasks_rows[iid] = r
            mod = r.get("modelo")
            tree.insert("", "end", iid=iid, tags=(r["estado"],), values=(
                r["id"], _estado_txt(r),
                _motor_modelo(_motor_txt(r["motor"], r["fam"]), mod),
                f"{r['ronda']}/{MAX_ROUNDS}" if r["ronda"] is not None else "—",
                _fmt_secs(r.get("dur")),
                (f"{_fmt_tok(r['tin'])} / {_fmt_tok(r['tout'])}"
                 if r.get("tin") is not None or r.get("tout") is not None else "—"),
                _cost_cell(r),
                _rev_summary(r)))
        if keep and keep in _tasks_rows:
            tree.selection_set(keep)
        _apply_live_to_tree()  # la fila en curso, con los numeros del vivo
        _show_task_detail()
        _render_approvals(rows)
        if w.get("tasks_summary") is not None:
            waiting = sum(1 for r in rows if r["estado"] == "esperando_aprobacion")
            cola = cola_resumen()
            w["tasks_summary"].config(
                text=f"{len(rows)} tareas. El gasto, separado en real, equivalente Max y local, "
                     "va en la tarjeta Gasto."
                     + (f" {waiting} esperan tu aprobación." if waiting else "")
                     + (f" En cola: {cola['pendiente']}." if cola["pendiente"] else "")
                     + (f" Próximo reintento a las {cola['proximo_reintento'][11:19]}."
                        if cola["proximo_reintento"] else ""))
        if w.get("nav_count_tareas") is not None:
            w["nav_count_tareas"].config(text=str(len(rows)))
    except Exception as e:
        log(f"tareas: no se pudo actualizar la lista ({type(e).__name__}: {e})")


_banner = {"id": None, "t0": 0.0, "shown": False}


def _refresh_banner():
    """Banner mientras un motor trabaja: paso actual + boton Parar."""
    b = _widgets.get("banner")
    if b is None:
        return
    cur, paso = state.get("current"), state.get("paso")
    if cur and paso:
        if _banner["id"] != cur:
            _banner.update(id=cur, t0=time.time())
        secs = int(time.time() - _banner["t0"])
        _widgets["banner_title"].config(text=paso)
        _widgets["banner_sub"].config(
            text=f"Tarea {cur}, lleva {secs // 60}:{secs % 60:02d}. Parar mata el proceso del motor.")
        if not _banner["shown"]:
            b.pack(fill="x", padx=20, pady=(12, 0))
            _banner["shown"] = True
    elif _banner["shown"]:
        b.pack_forget()
        # Tk no encoge el contenedor al quitarle su unico hijo: se fuerza.
        b.master.configure(height=1)
        _banner.update(shown=False, id=None)


def _on_stop_click():
    cur = state.get("current")
    if not cur:
        messagebox.showinfo("Parar", "No hay ninguna tarea corriendo.")
        return
    if not messagebox.askyesno("Parar", f"¿Parar {cur}?\n\nSe mata el proceso del motor y no se "
                                        "crean más rondas de corrección."):
        return
    threading.Thread(target=stop_current_task, daemon=True).start()


def _on_guardrail(level):
    var = _widgets.get("guardrail_var")
    prev = guardrail_level()
    if level == prev:
        return
    if level == "nunca":
        ok = messagebox.askyesno(
            "Hazlo sin preguntar",
            "Con esto Growi podrá borrar, publicar, gastar dinero y enviar mensajes "
            "sin enseñarte el plan antes.\n\n¿Seguro que quieres quitar la pregunta?",
            icon="warning", default="no")
        if ok:
            from tkinter import simpledialog
            typed = simpledialog.askstring(
                "Confirmación doble", "Para confirmarlo, escribe: sin preguntar", parent=_root)
            ok = _norm(typed or "").strip() == "sin preguntar"
            if not ok and typed is not None:
                messagebox.showinfo("Hazlo sin preguntar", "No coincide; se queda como estaba.")
        if not ok:
            if var is not None:
                var.set(prev)
            return
    s = load_settings()
    s["guardrail"] = level
    save_settings(s)
    log("ajustes: permisos -> " + next(l for k, l, _x in GUARDRAIL_LEVELS if k == level))


# ---------------------------------------------------------------- pestana Modelos (UI)
_mdl = {"installed": None, "specs": None, "detecting": False, "pending": {},
        "list_req": None, "list_err": "", "last_list_ask": 0.0,
        "api_status": {}, "show_ids": False}
FIT_COLORS = {"green": "#34C759", "orange": "#FF9500", "red": "#FF3B30",
              "gray": "#C7C7CC"}
CHANNELS = (
    ("whatsapp", "WhatsApp", "Te escribe por WhatsApp a través de tu asistente."),
    ("chat", "El chat de Muse", "Te contesta en el chat; los archivos llegan por el puente."),
    ("mascota", "La cajita de la mascota", "Haz clic en la mascota y escríbele."),
)


_UI_Q = queue.Queue()


def _ui_call(fn):
    """Pasa una funcion al hilo de la ventana (desde un hilo de fondo): va a
    una cola que _tick vacia cada segundo (tkinter no es seguro entre hilos)."""
    _UI_Q.put(fn)


def _drain_ui_queue():
    for _ in range(50):
        try:
            fn = _UI_Q.get_nowait()
        except queue.Empty:
            return
        try:
            fn()
        except Exception as e:
            log(f"ventana: error en una actualizacion ({type(e).__name__}: {e})")


def _write_model_task(action, model=None, timeout_min=None):
    """La ventana pide las acciones de modelos igual que el asistente: con
    un task en runner-tasks/ que el runner ejecuta."""
    TASKS.mkdir(parents=True, exist_ok=True)
    tid = f"app-{action}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}"
    data = {"id": tid, "ollama_action": action}
    if model:
        data["model"] = model
    if timeout_min:
        data["timeout_min"] = timeout_min
    tmp = TASKS / f"{tid}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, TASKS / f"{tid}.task.json")
    _mdl["pending"][tid] = {"action": action, "model": model, "t0": time.time(),
                            "timeout": (timeout_min or 5) * 60}
    return tid


def request_models_list(force=False):
    """Pide la lista de modelos instalados (accion list del runner). Si el
    runner esta apagado, la lee directamente para que la ventana no quede
    vacia."""
    if _mdl["list_req"] and not force:
        return
    _mdl["last_list_ask"] = time.time()
    if state["runner"] == "corriendo":
        _mdl["list_req"] = _write_model_task("list")
        return
    _mdl["list_req"] = "directo"

    def _run():
        ok, out, err = run_model_action("list", timeout_s=60)
        _ui_call(lambda: _apply_models_list(ok, out, err))

    threading.Thread(target=_run, daemon=True).start()


def _apply_models_list(ok, out, err):
    _mdl["list_req"] = None
    if ok:
        _mdl["installed"] = parse_ollama_list(out)
        _mdl["list_err"] = ""
    else:
        _mdl["list_err"] = err or "no pude leer tus modelos"
        if _mdl["installed"] is None:
            _mdl["installed"] = []
    cnt = _widgets.get("nav_count_modelos")
    if cnt is not None:
        cnt.config(text=str(len(_mdl["installed"] or [])))
    _refresh_engine_widgets()
    _render_models()


def _humanize_pull_line(line):
    """'pulling 6a07…:  45% ▕██ ▏ 2.1 GB/4.7 GB' -> 'descargando 45 % (2.1 GB de 4.7 GB)'."""
    low = line.lower()
    pct = re.search(r"(\d{1,3})%", line)
    sizes = re.search(r"([\d.]+\s*[KMGT]?B)\s*/\s*([\d.]+\s*[KMGT]?B)", line)
    if pct:
        txt = f"descargando {pct.group(1)} %"
        return txt + (f" ({sizes.group(1)} de {sizes.group(2)})" if sizes else "")
    if "manifest" in low and "pulling" in low:
        return "preparando…"
    if "verifying" in low:
        return "comprobando la descarga…"
    if "writing" in low:
        return "guardando…"
    if "success" in low:
        return "listo"
    if "pulling" in low:
        return "descargando…"
    return line[:80]


def _set_models_progress(text, ok=None):
    lbl = _widgets.get("mdl_progress")
    if lbl is None:
        return
    color = THEME["muted"] if ok is None else (THEME["green_text"] if ok else THEME["red"])
    lbl.config(text=text, fg=color)


def _models_poll():
    """Cada segundo: progreso de lo que se esta instalando y resultados de
    las acciones de modelos que pidio la ventana."""
    _drain_ui_queue()
    for tid, info in list(_mdl["pending"].items()):
        job = MODEL_JOBS.get(tid)
        if info["action"] == "pull" and job and job.get("line"):
            _set_models_progress(
                f"Instalando {friendly_model_name(info['model'] or '')}: "
                f"{_humanize_pull_line(job['line'])}")
        rp = RESULTS / f"{tid}.result.json"
        if not rp.is_file():
            if time.time() - info["t0"] > info["timeout"] + 180:
                _mdl["pending"].pop(tid, None)
                if _mdl["list_req"] == tid:
                    _mdl["list_req"] = None
                _set_models_progress("El runner no respondió. ¿Está encendido en Estado?", False)
                _render_models()
            continue
        try:
            d = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # todavia se esta escribiendo
        _mdl["pending"].pop(tid, None)
        MODEL_JOBS.pop(tid, None)
        ok = d.get("status") == "ok"
        if info["action"] == "list":
            # Consulta interna de la ventana: no se guarda en el historial.
            _rm_quiet(rp)
            _rm_quiet(DONE / f"{tid}.task.json")
            _apply_models_list(ok, d.get("result", ""), d.get("error"))
            continue
        name = friendly_model_name(info["model"] or "")
        if info["action"] == "pull":
            msg = (f"Listo: {name} quedó instalado y comprobado." if ok
                   else f"No se pudo instalar {name}: {d.get('error')}")
        else:
            msg = (f"{name} se borró de tu PC." if ok
                   else f"No se pudo borrar {name}: {d.get('error')}")
        log(f"modelos: {msg}")
        _set_models_progress(msg, ok)
        request_models_list(force=True)
        _render_models()


def start_pc_check():
    """Boton Comprobar mi PC: detecta GPU, RAM, CPU, disco y Ollama en un
    hilo (la ventana no se congela) y recalcula el semaforo."""
    if _mdl["detecting"]:
        return
    _mdl["detecting"] = True
    log("modelos: comprobando tu PC (GPU, memoria, procesador, disco)")
    _render_models()

    def _run():
        try:
            specs = detect_pc_specs()
        except Exception as e:
            specs = None
            log(f"modelos: no se pudo comprobar el PC ({type(e).__name__}: {e})")

        def _done():
            _mdl["detecting"] = False
            if specs:
                _mdl["specs"] = specs
                log(f"modelos: tu PC: {pc_specs_summary(specs)}")
            _render_models()

        _ui_call(_done)

    threading.Thread(target=_run, daemon=True).start()


def _on_models_open():
    """Al abrir la pestana: la primera vez comprueba el PC sola, y pide la
    lista de modelos si aun no la hay."""
    if _mdl["specs"] is None and not _mdl["detecting"] and not PC_SPECS_FILE.is_file():
        start_pc_check()
    if _mdl["installed"] is None and not _mdl["list_req"]:
        request_models_list()


def _fit_dot(parent, color, bg):
    c = tk.Canvas(parent, width=S(14), height=S(14), bg=bg, highlightthickness=0, bd=0)
    c.create_oval(S(2), S(2), S(12), S(12), fill=FIT_COLORS[color], outline=FIT_COLORS[color])
    return c


def _clear(frame):
    for child in frame.winfo_children():
        child.destroy()


def _runner_needed():
    if state["runner"] == "corriendo":
        return True
    messagebox.showinfo("Modelos", "Enciende el runner (pestaña Estado) para instalar "
                        "o borrar modelos: la ventana se lo pide a él, igual que tu asistente.")
    return False


def _set_default_model(name):
    s = load_settings()
    s["ollama_model"] = name
    if str(s.get("default_engine") or "").startswith("ollama:"):
        s["default_engine"] = "ollama:" + name
    save_settings(s)
    log(f"modelos: {friendly_model_name(name)} es ahora el modelo de tu PC por defecto")
    _refresh_engine_widgets()
    _render_models()


def _remove_model_ui(name, size):
    if not _runner_needed():
        return
    if not messagebox.askyesno(
            "Borrar modelo",
            f"¿Borrar {friendly_model_name(name)} de tu PC?\n\nLibera {size} de disco. "
            "Puedes volver a instalarlo cuando quieras."):
        return
    tid = _write_model_task("rm", name, timeout_min=5)
    log(f"modelos: borrado de {name} pedido al runner ({tid})")
    _set_models_progress(f"Borrando {friendly_model_name(name)}…")
    _render_models()


def _install_model_ui(entry):
    """Antes de instalar: tamaño, VRAM libre de ahora (nvidia-smi) y
    confirmacion si va justo. Los rojos no llegan aqui (boton apagado)."""
    if not _runner_needed():
        return
    color, _reason = model_fit(entry["vram_gb"], entry["size_gb"], _mdl["specs"])
    if color == "red":
        return
    _set_models_progress(f"Mirando la memoria libre para {entry['name']}…")

    def _check():
        free = gpu_free_vram_gb()
        _ui_call(lambda: _confirm(free))

    def _confirm(free):
        msg = (f"{entry['name']} ocupa {_gb(entry['size_gb'])} GB en tu disco y necesita "
               f"unos {_gb(entry['vram_gb'])} GB de VRAM (memoria de video) para funcionar.")
        if free is not None:
            msg += f"\n\nAhora mismo tienes {_gb(free)} GB de VRAM libre."
            if entry["vram_gb"] > free:
                msg += (" No cabe en la que está libre ahora (otras apps la están usando): "
                        "se instala igual, pero irá lento hasta que cierres algo.")
        if color == "orange":
            msg = "Este modelo va justo en tu PC, ¿seguro?\n\n" + msg
        elif color == "gray":
            msg += "\n\nAún no comprobé tu PC: pulsa Comprobar mi PC para saber si cabe."
        if not messagebox.askyesno("Instalar modelo", msg + "\n\n¿Instalar ahora?"):
            _set_models_progress("")
            return
        tid = _write_model_task("pull", entry["id"], timeout_min=MAX_TIMEOUT_MIN)
        log(f"modelos: instalación de {entry['id']} ({_gb(entry['size_gb'])} GB) "
            f"pedida al runner ({tid})")
        _set_models_progress(f"Instalando {entry['name']}: preparando…")
        _render_models()

    threading.Thread(target=_check, daemon=True).start()


def _render_models():
    """Redibuja el resumen del PC, la lista de instalados y la libreria con
    su semaforo."""
    w = _widgets
    if w.get("mdl_library_box") is None:
        return
    specs = _mdl["specs"]
    bg = THEME["card"]
    if _mdl["detecting"]:
        w["mdl_specs"].config(text="Comprobando tu PC…")
    else:
        w["mdl_specs"].config(text=pc_specs_summary(specs))
    detail = "Pulsa Comprobar mi PC: mira tu tarjeta de video, memoria y disco para decirte qué modelos caben."
    if specs:
        cpu = specs.get("cpu") or {}
        cores = f" ({cpu['cores']} núcleos)" if cpu.get("cores") else ""
        free = (specs.get("gpu") or {}).get("vram_free_gb")
        detail = (f"Procesador: {cpu.get('name') or 'desconocido'}{cores}. "
                  + (f"VRAM libre al comprobar: {_gb(free)} GB. " if free is not None else "")
                  + (f"RAM libre: {_gb(specs['ram_free_gb'])} GB. " if specs.get("ram_free_gb") else "")
                  + (f"Ollama {specs['ollama_version']}." if specs.get("ollama_version")
                     else "Ollama no está instalado (hace falta para los modelos de tu PC; es gratis).")
                  + f" Comprobado el {str(specs.get('detected_at', ''))[:16].replace('T', ' a las ')}.")
    w["mdl_specs_detail"].config(text=detail)
    w["mdl_check_btn"].config(state="disabled" if _mdl["detecting"] else "normal")

    catalog = load_catalog()
    installed = _mdl["installed"]
    default = default_ollama_model()
    pending = {(i["action"], i["model"]) for i in _mdl["pending"].values()}

    box = w["mdl_installed_box"]
    _clear(box)
    if installed is None:
        tk.Label(box, text="Leyendo tus modelos…", font=(FONT, 10), bg=bg,
                 fg=THEME["muted"]).pack(anchor="w", padx=16, pady=6)
    elif not installed:
        tk.Label(box, text=(f"No pude leer tus modelos: {_mdl['list_err']}" if _mdl["list_err"]
                            else "Todavía no tienes modelos en tu PC. Elige uno de la librería."),
                 font=(FONT, 10), bg=bg, fg=THEME["muted"], wraplength=S(560),
                 justify="left").pack(anchor="w", padx=16, pady=6)
    for m in installed or []:
        cat = next((c for c in catalog if _same_model(c["id"], m["name"])), None)
        vram = cat["vram_gb"] if cat else round((m["size_gb"] or 0) * 1.15, 1)
        color, reason = model_fit(vram, m["size_gb"], specs, installed=True)
        row = tk.Frame(box, bg=bg)
        row.pack(fill="x", padx=16, pady=6)
        _fit_dot(row, color, bg).pack(side="left", padx=(0, 10), anchor="n", pady=4)
        mid = tk.Frame(row, bg=bg)
        mid.pack(side="left", fill="x", expand=True)
        tk.Label(mid, text=friendly_model_name(m["name"], catalog), font=(FONT, 10, "bold"),
                 bg=bg, fg=THEME["text"]).pack(anchor="w")
        tk.Label(mid, text=f"{m['size']} en disco, instalado {m['modified']}".strip(", "),
                 font=(FONT, 9), bg=bg, fg=THEME["muted"]).pack(anchor="w")
        tk.Label(mid, text=reason, font=(FONT, 9), bg=bg,
                 fg=THEME["red"] if color == "red" else THEME["muted"]).pack(anchor="w")
        if color == "red":
            tk.Label(mid, text="Aviso: con tu PC de ahora no cabe. Puede ir muy lento o "
                     "fallar; libera memoria de video o bórralo.", font=(FONT, 9), bg=bg,
                     fg=THEME["red"], wraplength=S(380), justify="left").pack(anchor="w")
        right = tk.Frame(row, bg=bg)
        right.pack(side="right")
        if _same_model(m["name"], default):
            tk.Label(right, text="Por defecto", font=(FONT, 9, "bold"), bg="#E8E8ED",
                     fg=THEME["blue"], padx=S(8), pady=S(3)).pack(side="left", padx=4)
        else:
            ttk.Button(right, text="Usar por defecto",
                       command=lambda n=m["name"]: _set_default_model(n)).pack(side="left", padx=4)
        busy = ("rm", m["name"]) in pending
        ttk.Button(right, text="Borrando…" if busy else "Borrar",
                   state="disabled" if busy else "normal",
                   command=lambda n=m["name"], s=m["size"]: _remove_model_ui(n, s)).pack(side="left")
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)

    box = w["mdl_library_box"]
    _clear(box)
    if not catalog:
        tk.Label(box, text="No encuentro la librería (models-catalog.json junto al programa).",
                 font=(FONT, 10), bg=bg, fg=THEME["muted"]).pack(anchor="w", padx=16, pady=6)
    for c in catalog:
        is_inst = bool(installed) and any(_same_model(c["id"], m["name"]) for m in installed)
        color, reason = model_fit(c["vram_gb"], c["size_gb"], specs, installed=is_inst)
        row = tk.Frame(box, bg=bg)
        row.pack(fill="x", padx=16, pady=6)
        _fit_dot(row, color, bg).pack(side="left", padx=(0, 10), anchor="n", pady=4)
        mid = tk.Frame(row, bg=bg)
        mid.pack(side="left", fill="x", expand=True)
        tk.Label(mid, text=c["name"], font=(FONT, 10, "bold"), bg=bg,
                 fg=THEME["text"]).pack(anchor="w")
        if c["use"]:
            tk.Label(mid, text=c["use"], font=(FONT, 9), bg=bg, fg=THEME["text"],
                     wraplength=S(420), justify="left").pack(anchor="w")
        tk.Label(mid, text=f"{_gb(c['size_gb'])} GB en disco, necesita ~{_gb(c['vram_gb'])} GB de VRAM",
                 font=(FONT, 9), bg=bg, fg=THEME["muted"]).pack(anchor="w")
        tk.Label(mid, text=reason, font=(FONT, 9), bg=bg,
                 fg=THEME["red"] if color == "red" else THEME["muted"]).pack(anchor="w")
        right = tk.Frame(row, bg=bg)
        right.pack(side="right")
        if is_inst:
            tk.Label(right, text="Instalado", font=(FONT, 9, "bold"), bg=bg,
                     fg=THEME["green_text"]).pack(side="left", padx=4)
        elif ("pull", c["id"]) in pending:
            ttk.Button(right, text="Instalando…", state="disabled").pack(side="left")
        else:
            ttk.Button(right, text="Instalar", style="Accent.TButton",
                       state="disabled" if color == "red" else "normal",
                       command=lambda e=c: _install_model_ui(e)).pack(side="left")
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)


def engine_choices():
    """(nombre normal, model del task, frase simple) de quien puede responder."""
    out = [(AUTO_LABEL, "motor:auto",
            "Automático: según lo que pidas, elige el más barato que lo hace bien (Hermes en tu "
            "PC para lo simple, Sonnet para código, Opus para lo grande). Siempre verás quién "
            "respondió y por qué."),
           ("Claude Sonnet", "sonnet", "Claude: el más listo, va por internet."),
           ("Claude Opus", "opus", "Claude Opus: el más potente, para trabajos grandes; va por internet."),
           ("Claude Haiku", "haiku", "Claude Haiku: el más rápido de Claude; va por internet.")]
    llama = get_engine("llama")
    if llama and _llama_installed(llama)[0]:
        out.append(("Local Hermes 3 directo $0", "motor:llama",
                    "Hermes 3 en tu PC, directo (llama.cpp): gratis, privado y rápido."))
    codex = get_engine("codex")
    if codex and _resolve_binary(codex):
        out.append(("Codex (por internet)", "motor:codex",
                    "Codex de OpenAI: otro agente que trabaja en tus carpetas; va por internet."))
    catalog = load_catalog()
    default = default_ollama_model()
    names = [m["name"] for m in (_mdl["installed"] or [])]
    if _mdl["installed"] is None and default:
        names = [default]
    names.sort(key=lambda n: 0 if _same_model(n, default) else 1)
    labels = {o[0] for o in out}
    for n in names:
        fn = friendly_model_name(n, catalog)
        label = f"{fn} (en tu PC)"
        if label in labels:
            label = f"{fn} ({n})"
        labels.add(label)
        out.append((label, "ollama:" + n, f"{fn}: corre en tu PC, gratis y privado."))
    for p in API_ORDER:
        if api_key_for(p):
            lab = API_PROVIDERS[p]["label"]
            out.append((f"{lab} (por internet)", f"api:{p}:{api_model_for(p)}",
                        f"{lab}: otro modelo por internet, con tu clave."))
    return out


def _default_engine_label(choices):
    s = load_settings()
    want = "motor:auto" if s.get("motor") == AUTO else str(s.get("default_engine") or "sonnet")
    return next((l for l, m, _d in choices if m == want), "Claude Sonnet")


def _refresh_engine_widgets():
    choices = engine_choices()
    _ASK_ENGINES.clear()
    _ASK_ENGINES.update({l: m for l, m, _d in choices})
    labels = [c[0] for c in choices]
    default_label = _default_engine_label(choices)
    for key in ("ask_engine", "mdl_engine"):
        cb = _widgets.get(key)
        if cb is None:
            continue
        cb.config(values=labels)
        if cb.get() not in labels:
            cb.set(default_label)
    _update_engine_desc()


def _update_engine_desc():
    cb = _widgets.get("mdl_engine")
    lbl = _widgets.get("mdl_engine_desc")
    if cb is None or lbl is None:
        return
    label = cb.get()
    choice = next((c for c in engine_choices() if c[0] == label), None)
    text = choice[2] if choice else ""
    if choice and _mdl["show_ids"]:
        text += f"\nNombre exacto: {choice[1]}"
    lbl.config(text=text)


def _on_engine_pick(_e=None):
    cb = _widgets.get("mdl_engine")
    label = cb.get() if cb is not None else ""
    model = _ASK_ENGINES.get(label)
    if not model:
        return
    s = load_settings()
    if model == "motor:auto":
        # El motor fijo de antes se queda en default_engine por si se vuelve a manual.
        s["motor"] = AUTO
    else:
        s.pop("motor", None)
        s["default_engine"] = model
    if model.startswith("ollama:"):
        s["ollama_model"] = model.split(":", 1)[1]
    save_settings(s)
    ask = _widgets.get("ask_engine")
    if ask is not None:
        ask.set(label)
    log(f"modelos: ahora responde {label}")
    _update_engine_desc()
    _render_models()


def _toggle_ability(key, name, on):
    s = load_settings()
    off = set(s.get("disabled_abilities") or [])
    if on:
        off.discard(key)
    else:
        off.add(key)
    s["disabled_abilities"] = sorted(off)
    save_settings(s)
    log(f"habilidades: '{name}' {'encendida' if on else 'apagada'}")


def _render_abilities():
    box = _widgets.get("mdl_abilities_box")
    if box is None:
        return
    _clear(box)
    bg = THEME["card"]
    for a in list_abilities():
        row = tk.Frame(box, bg=bg)
        row.pack(fill="x", padx=16, pady=5)
        left = tk.Frame(row, bg=bg)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=a["name"], font=(FONT, 10, "bold"), bg=bg,
                 fg=THEME["text"]).pack(anchor="w")
        tk.Label(left, text=a["desc"], font=(FONT, 9), bg=bg,
                 fg=THEME["muted"]).pack(anchor="w")
        make_switch(row, a["on"], lambda on, k=a["key"], n=a["name"]: _toggle_ability(k, n, on),
                    bg=bg).pack(side="right")
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)


def _refresh_channels():
    bg = THEME["card"]
    for key, _name, _desc in CHANNELS:
        dot = _widgets.get(f"chan_{key}_dot")
        txt = _widgets.get(f"chan_{key}_state")
        if dot is None or txt is None:
            continue
        if key == "mascota":
            on = bool(state.get("mascot"))
            msg = "Conectada" if on else "Apagada: enciéndela abajo en la barra lateral"
        else:
            on = state.get("bridge") == "corriendo"
            msg = "Conectado por el puente" if on else "Sin conexión: el puente está apagado"
        color = FIT_COLORS["green"] if on else FIT_COLORS["gray"]
        dot.delete("all")
        dot.create_oval(S(2), S(2), S(12), S(12), fill=color, outline=color)
        txt.config(text=msg, fg=THEME["green_text"] if on else THEME["muted"], bg=bg)


def _render_rules():
    box = _widgets.get("mdl_rules_box")
    if box is None:
        return
    _clear(box)
    bg = THEME["card"]
    rules = load_rules()
    if not rules:
        tk.Label(box, text="Sin reglas. Escribe una abajo.", font=(FONT, 10), bg=bg,
                 fg=THEME["muted"]).pack(anchor="w", padx=16, pady=6)
    for i, r in enumerate(rules):
        row = tk.Frame(box, bg=bg)
        row.pack(fill="x", padx=16, pady=5)
        tk.Label(row, text=r["text"], font=(FONT, 10), bg=bg, fg=THEME["text"],
                 wraplength=S(420), justify="left", anchor="w").pack(
            side="left", fill="x", expand=True, anchor="w")
        make_switch(row, r["on"], lambda on, i=i: _toggle_rule(i, on), bg=bg).pack(side="right")
        ttk.Button(row, text="Quitar", command=lambda i=i: _remove_rule(i)).pack(side="right", padx=8)
        tk.Frame(box, bg=THEME["line"], height=S(1)).pack(fill="x", padx=16)


def _toggle_rule(i, on):
    rules = load_rules()
    if 0 <= i < len(rules):
        rules[i]["on"] = on
        save_rules(rules)
        log(f"reglas: '{rules[i]['text']}' {'activada' if on else 'desactivada'}")


def _remove_rule(i):
    rules = load_rules()
    if 0 <= i < len(rules):
        gone = rules.pop(i)
        save_rules(rules)
        log(f"reglas: quitada '{gone['text']}'")
    _render_rules()


def _add_rule():
    ent = _widgets.get("mdl_rule_entry")
    if ent is None:
        return
    text = ent.get().strip()[:300]
    if not text:
        return
    rules = load_rules()
    rules.append({"text": text, "on": True})
    save_rules(rules)
    ent.delete(0, "end")
    log(f"reglas: añadida '{text}'")
    _render_rules()


def _card(parent, title, expl=None):
    card = tk.Frame(parent, bg=THEME["card"])
    card.pack(fill="x", padx=20, pady=8)
    tk.Label(card, text=title, font=SECTION_FONT, bg=THEME["card"],
             fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    if expl:
        tk.Label(card, text=expl, font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
                 wraplength=S(600), justify="left").pack(anchor="w", padx=16, pady=(0, 6))
    return card


def _build_models_page(tab):
    bg, cbg = THEME["bg"], THEME["card"]
    tk.Label(tab, text="Modelos", font=(FONT, 22, "bold"), bg=bg,
             fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab, text="Growi Bridge junta lo mejor de Ollama (modelos en tu PC) y OpenClaw "
             "(un agente que usa herramientas y te habla por varios canales), sin que "
             "tengas que configurar nada de eso.",
             font=(FONT, 11), bg=bg, fg=THEME["muted"], wraplength=S(600),
             justify="left").pack(anchor="w", padx=20, pady=(0, 10))

    # Tu PC (Comprobar mi PC)
    card = _card(tab, "Tu PC")
    row = tk.Frame(card, bg=cbg)
    row.pack(fill="x", padx=16, pady=(0, 2))
    _widgets["mdl_specs"] = tk.Label(row, text="", font=(FONT, 11, "bold"), bg=cbg,
                                     fg=THEME["text"], wraplength=S(440), justify="left")
    _widgets["mdl_specs"].pack(side="left", anchor="w")
    _widgets["mdl_check_btn"] = ttk.Button(row, text="Comprobar mi PC", style="Accent.TButton",
                                           command=start_pc_check)
    _widgets["mdl_check_btn"].pack(side="right")
    _widgets["mdl_specs_detail"] = tk.Label(card, text="", font=(FONT, 9), bg=cbg,
                                            fg=THEME["muted"], wraplength=S(600), justify="left")
    _widgets["mdl_specs_detail"].pack(anchor="w", padx=16, pady=(2, 14))

    # Quien responde
    card = _card(tab, "Quién responde",
                 "Elige quién te contesta cuando le pides algo desde la app.")
    row = tk.Frame(card, bg=cbg)
    row.pack(fill="x", padx=16)
    _widgets["mdl_engine"] = ttk.Combobox(row, width=34, font=(FONT, 10), state="readonly")
    _widgets["mdl_engine"].pack(side="left")
    _widgets["mdl_engine"].bind("<<ComboboxSelected>>", _on_engine_pick)

    def _toggle_ids():
        _mdl["show_ids"] = not _mdl["show_ids"]
        _update_engine_desc()

    tk.Button(row, text="Ver nombre exacto", font=(FONT, 9), bg=cbg, fg=THEME["blue"],
              activebackground=cbg, activeforeground=THEME["blue"], bd=0, cursor="hand2",
              command=_toggle_ids).pack(side="left", padx=10)
    _widgets["mdl_engine_desc"] = tk.Label(card, text="", font=(FONT, 10), bg=cbg,
                                           fg=THEME["text"], justify="left")
    _widgets["mdl_engine_desc"].pack(anchor="w", padx=16, pady=(6, 14))

    # En tu PC (instalados)
    card = _card(tab, "En tu PC")
    row = tk.Frame(card, bg=cbg)
    row.pack(fill="x", padx=16)
    _widgets["mdl_progress"] = tk.Label(row, text="", font=(FONT, 9, "bold"), bg=cbg,
                                        fg=THEME["muted"], wraplength=S(460), justify="left")
    _widgets["mdl_progress"].pack(side="left", anchor="w")
    ttk.Button(row, text="Actualizar", command=lambda: request_models_list(force=True)).pack(side="right")
    _widgets["mdl_installed_box"] = tk.Frame(card, bg=cbg)
    _widgets["mdl_installed_box"].pack(fill="x", pady=(4, 12))

    # Libreria
    card = _card(tab, "Librería",
                 "Modelos gratis para tu PC. El color dice si caben: verde, holgado; "
                 "naranja, va justo; rojo, no cabe (no se ofrece instalarlo).")
    _widgets["mdl_library_box"] = tk.Frame(card, bg=cbg)
    _widgets["mdl_library_box"].pack(fill="x", pady=(0, 12))

    # Que puede hacer (habilidades)
    card = _card(tab, "Qué puede hacer",
                 "Las habilidades de tu asistente. Si apagas una, deja de usarla en las tareas.")
    _widgets["mdl_abilities_box"] = tk.Frame(card, bg=cbg)
    _widgets["mdl_abilities_box"].pack(fill="x", pady=(0, 12))

    # Donde te habla (canales, solo lectura)
    card = _card(tab, "Dónde te habla")
    for key, name, desc in CHANNELS:
        row = tk.Frame(card, bg=cbg)
        row.pack(fill="x", padx=16, pady=5)
        dot = tk.Canvas(row, width=S(14), height=S(14), bg=cbg, highlightthickness=0, bd=0)
        dot.pack(side="left", padx=(0, 10), anchor="n", pady=4)
        left = tk.Frame(row, bg=cbg)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=name, font=(FONT, 10, "bold"), bg=cbg, fg=THEME["text"]).pack(anchor="w")
        tk.Label(left, text=desc, font=(FONT, 9), bg=cbg, fg=THEME["muted"]).pack(anchor="w")
        st = tk.Label(row, text="", font=(FONT, 9), bg=cbg)
        st.pack(side="right")
        _widgets[f"chan_{key}_dot"] = dot
        _widgets[f"chan_{key}_state"] = st
    tk.Frame(card, bg=cbg, height=S(8)).pack()

    # Reglas
    card = _card(tab, "Reglas",
                 "Lo que tu asistente cumple siempre, sin que tengas que repetirlo. "
                 "Se le dicen al principio de cada tarea.")
    _widgets["mdl_rules_box"] = tk.Frame(card, bg=cbg)
    _widgets["mdl_rules_box"].pack(fill="x")
    row = tk.Frame(card, bg=cbg)
    row.pack(fill="x", padx=16, pady=(8, 14))
    _widgets["mdl_rule_entry"] = ttk.Entry(row, width=48, font=(FONT, 10))
    _widgets["mdl_rule_entry"].pack(side="left", padx=(0, 8))
    _widgets["mdl_rule_entry"].bind("<Return>", lambda _e: _add_rule())
    ttk.Button(row, text="Añadir regla", style="Accent.TButton", command=_add_rule).pack(side="left")

    _mdl["specs"] = load_pc_specs()
    _render_models()
    _render_abilities()
    _render_rules()
    _refresh_channels()


# --- APIs: conexiones por proveedor (amplia la pestana APIs)
def _build_api_connections(tab):
    card = _card(tab, "Conexiones",
                 "Pon la clave de cada servicio y pulsa Probar: hace una consulta mínima y "
                 "gratis para ver si funciona. La clave nunca se muestra entera ni se "
                 "escribe en el registro.")
    cbg = THEME["card"]
    for p in API_ORDER:
        row = tk.Frame(card, bg=cbg)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text=API_PROVIDERS[p]["label"], font=(FONT, 10, "bold"), bg=cbg,
                 fg=THEME["text"], width=13, anchor="w").pack(side="left")
        mask = tk.Label(row, text="", font=(FONT, 9), bg=cbg, fg=THEME["muted"],
                        width=10, anchor="w")
        mask.pack(side="left")
        ent = ttk.Entry(row, width=22, font=(FONT, 10), show="•")
        ent.pack(side="left", padx=(4, 6))
        ttk.Button(row, text="Guardar", command=lambda p=p: _save_api_conn(p)).pack(side="left")
        ttk.Button(row, text="Probar", command=lambda p=p: _test_api_ui(p)).pack(side="left", padx=4)
        st = tk.Label(row, text="", font=(FONT, 9), bg=cbg, fg=THEME["muted"], anchor="w")
        st.pack(side="left", padx=(6, 0))
        _widgets[f"apic_{p}_mask"] = mask
        _widgets[f"apic_{p}_entry"] = ent
        _widgets[f"apic_{p}_status"] = st
    tk.Frame(card, bg=cbg, height=S(8)).pack()
    saved = load_settings().get("api_status") or {}
    for p, v in saved.items():
        if isinstance(v, dict):
            _mdl["api_status"][p] = (bool(v.get("ok")), str(v.get("msg", "")))
    _refresh_api_connections()


def _refresh_api_connections():
    for p in API_ORDER:
        mask = _widgets.get(f"apic_{p}_mask")
        st = _widgets.get(f"apic_{p}_status")
        if mask is None or st is None:
            continue
        key = api_key_for(p)
        mask.config(text=("••••" + key[-4:]) if len(key) > 4 else ("••••" if key else "sin clave"))
        res = _mdl["api_status"].get(p)
        if not key:
            st.config(text="", fg=THEME["muted"])
        elif res is None:
            st.config(text="Sin probar", fg=THEME["muted"])
        elif res[0]:
            st.config(text="Conectada", fg=THEME["green_text"])
        else:
            st.config(text=f"Falló: {res[1]}", fg=THEME["red"])


def _save_api_conn(p):
    ent = _widgets.get(f"apic_{p}_entry")
    key = ent.get().strip() if ent is not None else ""
    if not key:
        messagebox.showwarning("APIs", "Pega la clave primero.")
        return
    info = API_PROVIDERS[p]
    apis = [a for a in load_apis()
            if not (a.get("provider") == p
                    or str(a.get("name", "")).strip().lower() in info["aliases"])]
    apis.append({"name": info["label"], "key": key, "provider": p})
    save_apis(apis)
    ent.delete(0, "end")
    _mdl["api_status"].pop(p, None)
    log(f"APIs: clave de {info['label']} guardada (solo en este PC)")
    refresh_apis_ui()


def _test_api_ui(p):
    st = _widgets.get(f"apic_{p}_status")
    label = API_PROVIDERS[p]["label"]
    if not api_key_for(p):
        if st is not None:
            st.config(text="Falta la clave", fg=THEME["red"])
        return
    if st is not None:
        st.config(text="Probando…", fg=THEME["muted"])

    def _run():
        ok, msg = test_api(p)
        log(f"APIs: prueba de {label}: {'conectada' if ok else 'falló (' + msg + ')'}")

        def _done():
            _mdl["api_status"][p] = (ok, msg)
            s = load_settings()
            s.setdefault("api_status", {})[p] = {"ok": ok, "msg": msg, "at": _now_iso()}
            save_settings(s)
            _refresh_api_connections()

        _ui_call(_done)

    threading.Thread(target=_run, daemon=True).start()


# --- Recursos: cuanto del PC se usa y que proceso lo usa, con lo de Growi
# primero (no es un clon del Administrador de tareas). Lee en un hilo aparte
# cada 2 s y solo mientras la pestana esta abierta; al salir se pausa.
RES_INTERVAL_S = 2.0
# Procesos de Windows que la app NUNCA cierra: cerrarlos cuelga o reinicia el
# PC, o tumba el escritorio. (wininit va de mas: matarlo es pantallazo azul.)
CRITICAL_PROCS = {"system", "system idle process", "csrss", "smss", "winlogon", "services",
                  "lsass", "svchost", "explorer", "registry", "fontdrvhost", "dwm", "wininit"}
# Lo que Growi orquesta: (texto en el nombre del proceso, como se llama).
GROWI_PROCS = (("llama-server", "Hermes directo (llama-server)"), ("ollama", "Ollama"),
               ("claude", "Claude"), ("codex", "Codex"), ("meshy", "Meshy"))
# python/node: se mira la linea de comandos (que programa estan corriendo).
GROWI_SCRIPTS = (("growi-bridge.py", "Growi Bridge"),
                 ("browser-server.py", "Navegador (browser-server)"),
                 ("claude", "Claude"), ("codex", "Codex"), ("meshy", "Meshy"))
_SCRIPT_HOSTS = {"python", "pythonw", "py", "node"}
_RES = {"thread": None, "wake": threading.Event(), "page": False, "active": False,
        "data": None, "all": False, "query": "", "sort": ("cpu", True), "sel": None,
        "psutil": None, "installing": False, "install_tried": False, "install_err": "",
        "cpu_prev": None, "status": ("", None)}


def _res_psutil():
    """psutil si esta instalado; si no, None (y se usa tasklist)."""
    if _RES["psutil"] is None:
        try:
            import psutil
            _RES["psutil"] = psutil
        except ImportError:
            _RES["psutil"] = False
    return _RES["psutil"] or None


def _res_install_psutil():
    """Sin psutil: lo instala con pip (solo ese paquete, nada mas). Si no se
    puede, la pestana sigue con tasklist y lo dice."""
    _RES["installing"] = True
    py = Path(sys.executable)
    if py.name.lower() == "pythonw.exe" and (py.parent / "python.exe").is_file():
        py = py.parent / "python.exe"
    log("recursos: falta psutil; lo instalo con pip (solo psutil)")
    err = ""
    try:
        p = subprocess.run([str(py), "-m", "pip", "install", "--quiet", "psutil"],
                           capture_output=True, text=True, timeout=300,
                           creationflags=_NO_WINDOW)
        ok = p.returncode == 0
        err = (p.stderr or p.stdout or "").strip()[-300:]
    except Exception as e:
        ok, err = False, f"{type(e).__name__}: {e}"
    if ok:
        try:
            import importlib
            import site
            importlib.invalidate_caches()
            try:
                site.addsitedir(site.getusersitepackages())
            except Exception:
                pass
            import psutil
            _RES["psutil"] = psutil
            log(f"recursos: psutil {psutil.__version__} instalado")
        except ImportError as e:
            ok, err = False, str(e)
    if not ok:
        _RES["install_err"] = err or "pip falló"
        log(f"recursos: no se pudo instalar psutil ({_RES['install_err']}); uso tasklist")
    _RES["installing"] = False
    _RES["install_tried"] = True


def _nvidia_smi():
    smi = shutil.which("nvidia-smi")
    if not smi:
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        smi = str(cand) if cand.is_file() else None
    return smi


def _res_gpu():
    """(datos, motivo). Sin GPU NVIDIA o si nvidia-smi no responde: (None,
    motivo). Nunca se inventa un numero."""
    smi = _nvidia_smi()
    if not smi:
        return None, "No encuentro nvidia-smi."
    try:
        p = subprocess.run([smi, "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5, creationflags=_NO_WINDOW)
        line = next((l for l in (p.stdout or "").splitlines() if l.strip()), "")
        name, util, used, total = [x.strip() for x in line.split(",")[:4]]
        return {"name": name, "util": float(util), "used_gb": float(used) / 1024,
                "total_gb": float(total) / 1024}, ""
    except subprocess.TimeoutExpired:
        return None, "nvidia-smi no respondió."
    except Exception:
        return None, "nvidia-smi no dio datos."


def _res_gpu_kick():
    """nvidia-smi va en su propio hilo (tarda ~0,7 s, mas si la GPU del
    portatil estaba dormida): asi nunca retrasa la CPU, la RAM ni la lista."""
    if _RES.get("gpu_busy"):
        return
    _RES["gpu_busy"] = True

    def run():
        try:
            _RES["gpu_last"] = _res_gpu()
        except Exception:
            _RES["gpu_last"] = (None, "nvidia-smi no dio datos.")
        finally:
            _RES["gpu_busy"] = False

    threading.Thread(target=run, daemon=True).start()


def _res_cpu_fallback():
    """CPU total sin psutil (GetSystemTimes, entre dos lecturas)."""
    import ctypes
    from ctypes import wintypes
    idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern),
                                                 ctypes.byref(user)):
        return None

    def v(ft):
        return (ft.dwHighDateTime << 32) | ft.dwLowDateTime

    cur = (v(idle), v(kern), v(user))
    prev, _RES["cpu_prev"] = _RES["cpu_prev"], cur
    if not prev:
        return None
    total = (cur[1] - prev[1]) + (cur[2] - prev[2])  # kernel ya incluye idle
    if total <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (total - (cur[0] - prev[0])) / total))


def _res_mem_fallback():
    import ctypes

    class _MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    st = _MEM()
    st.dwLength = ctypes.sizeof(_MEM)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullTotalPhys - st.ullAvailPhys, st.ullTotalPhys


def _res_stem(name):
    n = str(name or "").lower()
    return n[:-4] if n.endswith(".exe") else n


def _res_is_critical(name, pid):
    return pid in (0, 4) or _res_stem(name) in CRITICAL_PROCS


_RES_TIMES = {}  # (pid, hora de creacion) -> tiempo de CPU acumulado (100 ns)
_RES_TIMES_AT = [0.0]


def _res_snapshot():
    """CPU y RAM de TODOS los procesos con una sola llamada a Windows
    (NtQuerySystemInformation, lo mismo que usa el Administrador de tareas).
    psutil, sin permisos de administrador, hace esa misma consulta una vez
    por cada proceso protegido: ~1 s por lectura y la ventana se traba.
    Devuelve {pid: fila} (nombre, padre, hora de creacion, cpu %, MB de
    memoria privada activa) o None."""
    import ctypes
    from ctypes import wintypes

    class _US(ctypes.Structure):
        _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT),
                    ("Buffer", ctypes.c_void_p)]

    class _SPI(ctypes.Structure):
        _fields_ = [("NextEntryOffset", ctypes.c_ulong), ("NumberOfThreads", ctypes.c_ulong),
                    ("WorkingSetPrivateSize", ctypes.c_longlong),
                    ("HardFaultCount", ctypes.c_ulong),
                    ("NumberOfThreadsHighWatermark", ctypes.c_ulong),
                    ("CycleTime", ctypes.c_ulonglong), ("CreateTime", ctypes.c_longlong),
                    ("UserTime", ctypes.c_longlong), ("KernelTime", ctypes.c_longlong),
                    ("ImageName", _US), ("BasePriority", ctypes.c_long),
                    ("UniqueProcessId", ctypes.c_void_p),
                    ("InheritedFromUniqueProcessId", ctypes.c_void_p)]

    nt = ctypes.windll.ntdll
    size = 1 << 20
    for _ in range(6):
        buf = ctypes.create_string_buffer(size)
        need = ctypes.c_ulong(0)
        st = nt.NtQuerySystemInformation(5, buf, size, ctypes.byref(need)) & 0xFFFFFFFF
        if st == 0:
            break
        if st != 0xC0000004:  # STATUS_INFO_LENGTH_MISMATCH: buffer mas grande
            return None
        size = max(size * 2, need.value + 65536)
    else:
        return None
    now = time.time()
    dt = now - _RES_TIMES_AT[0] if _RES_TIMES_AT[0] else 0.0
    ncpu = os.cpu_count() or 1
    base, off, out, times = ctypes.addressof(buf), 0, {}, {}
    while True:
        e = _SPI.from_address(base + off)
        pid = e.UniqueProcessId or 0
        key = (pid, e.CreateTime)
        tot = e.UserTime + e.KernelTime
        times[key] = tot
        prev = _RES_TIMES.get(key)
        cpu = None
        if prev is not None and dt > 0:
            cpu = max(0.0, min(100.0, (tot - prev) / (dt * 1e7) / ncpu * 100))
        if e.ImageName.Buffer and e.ImageName.Length:
            name = ctypes.wstring_at(e.ImageName.Buffer, e.ImageName.Length // 2)
        else:
            name = "System Idle Process" if pid == 0 else "?"
        out[pid] = {"pid": pid, "ppid": e.InheritedFromUniqueProcessId or 0, "name": name,
                    "cpu": cpu, "ram": e.WorkingSetPrivateSize / 1048576,
                    # FILETIME (100 ns desde 1601) -> segundos unix, como psutil
                    "ct": e.CreateTime / 1e7 - 11644473600 if e.CreateTime else 0.0}
        if not e.NextEntryOffset:
            break
        off += e.NextEntryOffset
    _RES_TIMES.clear()
    _RES_TIMES.update(times)
    _RES_TIMES_AT[0] = now
    return out


def _res_procs_psutil(ps):
    # Todos los procesos de una vez con _res_snapshot; psutil queda para la
    # linea de comandos (python/node) y para comprobar antes de cerrar. Si la
    # consulta fallara, psutil proceso a proceso (mas lento, pero en este
    # hilo, no en el de la ventana).
    try:
        snap = _res_snapshot()
    except Exception:
        snap = None
    _RES["snapshot"] = snap is not None
    if snap is not None:
        return snap
    ncpu = ps.cpu_count() or 1
    rows = {}
    for p in ps.process_iter(["pid", "ppid", "name", "create_time", "memory_info",
                              "cpu_percent"]):
        i = p.info
        mi = i.get("memory_info")
        rows[i["pid"]] = {"pid": i["pid"], "ppid": i.get("ppid") or 0,
                          "name": i.get("name") or "?",
                          # psutil da hasta 100 x nucleos; el Administrador de
                          # tareas lo reparte entre todos (0-100 %).
                          "cpu": (i.get("cpu_percent") or 0.0) / ncpu,
                          "ram": (mi.rss / 1048576) if mi else None,
                          "ct": i.get("create_time") or 0.0}
    return rows


def _res_cmdline(pid):
    ps = _res_psutil()
    if ps is None:
        return ""
    try:
        return " ".join(ps.Process(pid).cmdline()).lower()
    except Exception:
        return ""


def _res_procs_tasklist():
    import csv
    import io
    p = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, timeout=10,
                       creationflags=_NO_WINDOW)
    text = p.stdout.decode("oem", errors="replace")
    rows = {}
    for rec in csv.reader(io.StringIO(text)):
        if len(rec) < 5 or not rec[1].isdigit():
            continue
        pid = int(rec[1])
        kb = re.sub(r"\D", "", rec[4])
        rows[pid] = {"pid": pid, "ppid": None, "name": rec[0], "cpu": None,
                     "ram": int(kb) / 1024 if kb else None, "ct": None}
    return rows


def _res_launched(rows):
    """{pid: quien lo lanzo} de lo que lanzo la app y sigue vivo (mismo
    programa: Windows reutiliza los PID, asi que la hora tiene que cuadrar)."""
    out = {}
    for pid, (who, t) in list(_LAUNCHED.items()):
        r = rows.get(pid)
        if r is not None and (not r["ct"] or abs(r["ct"] - t) < 10):
            out[pid] = who
    return out


def _res_classify(rows):
    """Marca lo que es de Growi: la app, lo que lanzo (runner, Modelos), sus
    hijos y los motores que orquesta (claude, ollama, llama-server, codex,
    meshy, browser-server). kind: app / growi / otro."""
    me = os.getpid()
    apps = {me}
    what = {}
    launched = _res_launched(rows)
    for pid, r in rows.items():
        stem = _res_stem(r["name"])
        label = None
        if stem in _SCRIPT_HOSTS:
            cmd = _res_cmdline(pid)
            label = next((lab for key, lab in GROWI_SCRIPTS if key in cmd), None)
            if label == "Growi Bridge":
                apps.add(pid)
        else:
            label = next((lab for key, lab in GROWI_PROCS if key in stem), None)
        if label:
            what[pid] = label

    def ancestor(pid):
        """El primer antepasado que es de Growi (app, lanzado o motor)."""
        r, seen = rows.get(pid), 0
        while r is not None and r["ppid"] and seen < 12:
            par = rows.get(r["ppid"])
            # Windows reutiliza los PID: el padre tiene que ser mas viejo.
            if par is None or (par["ct"] and r["ct"] and par["ct"] > r["ct"] + 1):
                return None
            if par["pid"] in apps or par["pid"] in launched or par["pid"] in what:
                return par
            r, seen = par, seen + 1
        return None

    for pid, r in rows.items():
        r["crit"] = _res_is_critical(r["name"], pid)
        if pid in apps:
            r["kind"] = "app"
            r["origin"] = "Growi Bridge, esta ventana" if pid == me else "Growi Bridge (otra copia)"
            continue
        if pid in launched:
            r["kind"], r["origin"] = "growi", launched[pid]
            continue
        par = None if r["crit"] else ancestor(pid)
        if par is not None:
            r["kind"] = "growi"
            if par["pid"] in launched:
                r["origin"] = launched[par["pid"]]
            elif par["pid"] in apps:
                r["origin"] = "lo abrió Growi Bridge"
            else:
                r["origin"] = f"lo abrió {par['name']} (PID {par['pid']}), {what[par['pid']]}"
        elif pid in what:
            r["kind"], r["origin"] = "growi", f"{what[pid]}, abierto fuera de Growi"
        else:
            r["kind"], r["origin"] = "otro", ""
    return rows


def _res_sample():
    """Una lectura completa (en el hilo de Recursos, nunca en el de la
    ventana)."""
    ps = _res_psutil()
    if ps is None and not _RES["install_tried"] and not _RES["installing"]:
        _res_install_psutil()
        ps = _res_psutil()
    d = {"ts": time.time()}
    _res_gpu_kick()
    if ps is not None:
        d["tool"] = f"psutil {ps.__version__}"
        d["cpu"] = ps.cpu_percent(interval=None)
        vm = ps.virtual_memory()
        d["ram_used"], d["ram_total"] = vm.total - vm.available, vm.total
        d["ncpu"] = ps.cpu_count()
        rows = _res_procs_psutil(ps)
    else:
        d["tool"] = "tasklist"
        d["cpu"] = _res_cpu_fallback()
        d["ram_used"], d["ram_total"] = _res_mem_fallback()
        d["ncpu"] = os.cpu_count()
        rows = _res_procs_tasklist()
    t_end = time.time() + 1.0
    while _RES.get("gpu_busy") and time.time() < t_end:
        time.sleep(0.05)
    # Sin respuesta todavia: "Leyendo la GPU…" (nunca "sin GPU" ni un numero).
    d["gpu"], d["gpu_why"] = _RES.get("gpu_last") or (None, None)
    drive =(os.environ.get("SystemDrive") or "C:") + "\\"
    try:
        du = shutil.disk_usage(drive)
        d["disk"] = (drive[:2], du.free, du.total)
    except OSError:
        d["disk"] = None
    d["procs"] = list(_res_classify(rows).values())
    return d


def _res_loop():
    while True:
        if not _RES["active"]:
            _RES["wake"].wait()
            _RES["wake"].clear()
            continue
        t0 = time.time()
        try:
            data = _res_sample()
        except Exception as e:
            data = {"error": f"{type(e).__name__}: {e}"}
        _ui_call(lambda d=data: _res_apply(d))
        _RES["wake"].wait(max(0.2, RES_INTERVAL_S - (time.time() - t0)))
        _RES["wake"].clear()


def _res_tick():
    """Desde _tick (cada segundo): la lectura corre solo con la pestana a la
    vista; minimizada o en otra pestana, se pausa."""
    on = _RES["page"]
    if on and _root is not None:
        try:
            on = _root.state() not in ("iconic", "withdrawn")
        except Exception:
            pass
    if on and not _RES["active"]:
        _RES["active"] = True
        if _RES["thread"] is None:
            _RES["thread"] = threading.Thread(target=_res_loop, daemon=True)
            _RES["thread"].start()
        _RES["wake"].set()
    elif not on:
        _RES["active"] = False
    # Contador de la barra lateral: el % de CPU (lectura instantanea, sin
    # procesos). Con la pestana abierta lo pone la lectura completa.
    if not _RES["active"] and _tick_n[0] % 2 == 0:
        ps = _res_psutil()
        try:
            cpu = ps.cpu_percent(interval=None) if ps is not None else _res_cpu_fallback()
        except Exception:
            cpu = None
        _res_set_counter(cpu)


def _res_set_counter(cpu):
    w = _widgets.get("nav_count_recursos")
    if w is not None:
        w.config(text="" if cpu is None else f"{cpu:.0f} %")


def _res_refresh_now():
    _RES["wake"].set()
    _res_set_status("Actualizando…", None)


def _res_set_status(text, ok):
    _RES["status"] = (text, ok)
    w = _widgets.get("res_status")
    if w is not None:
        color = {True: THEME["green_text"], False: THEME["red"]}.get(ok, THEME["muted"])
        w.config(text=text, fg=color)


def _res_bar(canvas, pct):
    canvas.delete("all")
    wd = max(canvas.winfo_width(), S(40))
    h = S(4)
    canvas.create_rectangle(0, 0, wd, h, fill="#E5E5EA", width=0)
    if pct is None:
        return
    pct = max(0.0, min(100.0, pct))
    color = THEME["blue"] if pct < 80 else (FIT_COLORS["orange"] if pct < 95 else FIT_COLORS["red"])
    if pct > 0:
        canvas.create_rectangle(0, 0, max(S(2), wd * pct / 100), h, fill=color, width=0)


def _res_card_set(key, value, sub, pct):
    _widgets[f"res_{key}_val"].config(text=value)
    _widgets[f"res_{key}_sub"].config(text=sub)
    _res_bar(_widgets[f"res_{key}_bar"], pct)


def _res_apply(d):
    if _widgets.get("res_tree") is None:
        return
    if d.get("error"):
        _res_set_status(f"No pude leer los recursos: {d['error']}", False)
        return
    _RES["data"] = d
    gb = 1024 ** 3
    cpu = d.get("cpu")
    _res_card_set("cpu", "—" if cpu is None else f"{cpu:.0f} %",
                  f"{d.get('ncpu') or '?'} núcleos lógicos", cpu)
    _res_set_counter(cpu)
    used, total = d["ram_used"] / gb, d["ram_total"] / gb
    _res_card_set("ram", f"{_gb(used)} GB", f"de {_gb(total)} GB ({used / total * 100:.0f} %)",
                  used / total * 100)
    g = d.get("gpu")
    if g:
        _res_card_set("gpu", f"{g['util']:.0f} %",
                      f"VRAM {_gb(g['used_gb'])} de {_gb(g['total_gb'])} GB", g["util"])
    elif d.get("gpu_why") is None:
        _res_card_set("gpu", "—", "Leyendo la GPU…", None)
    else:
        _res_card_set("gpu", "sin GPU NVIDIA", d["gpu_why"], None)
    if d.get("disk"):
        drv, free, tot = d["disk"]
        _res_card_set("disk", f"{_gb(free / gb)} GB", f"libres de {_gb(tot / gb)} GB en {drv}",
                      (tot - free) / tot * 100)
    else:
        _res_card_set("disk", "—", "No pude leer el disco.", None)
    if d["tool"] == "tasklist":
        why = (" (instalando psutil…)" if _RES["installing"] else
               f" porque no se pudo instalar psutil: {_RES['install_err'][:120]}"
               if _RES["install_tried"] else "")
        tool = (f"Sin psutil: la lista sale de tasklist, sin CPU por proceso{why}. "
                "Se actualiza cada 2 s mientras esta pestaña está abierta.")
    else:
        ram = ("RAM de cada proceso: memoria privada activa, la misma que el "
               "Administrador de tareas. " if _RES.get("snapshot") else "")
        tool = (f"Datos de {d['tool']}. {ram}Se actualiza cada 2 s mientras esta pestaña "
                "está abierta; en otra pestaña se pausa.")
    _widgets["res_tool"].config(text=tool)
    if _RES["status"][0] in ("Actualizando…", "Leyendo los procesos…"):
        _res_set_status("", None)
    _res_render_table()


def _res_visible_rows():
    d = _RES["data"]
    if not d:
        return []
    rows = d["procs"] if _RES["all"] else [r for r in d["procs"] if r["kind"] != "otro"]
    q = _norm(_RES["query"]).strip()
    if q:
        rows = [r for r in rows if q in _norm(r["name"]) or q == str(r["pid"])]
    key, desc = _RES["sort"]
    if key == "cpu" and d["tool"] == "tasklist":
        key = "ram"  # sin CPU por proceso: se ordena por RAM
    if key in ("name", "origin"):
        rows.sort(key=lambda r: _norm(r.get(key) or ""), reverse=desc)
    else:
        rows.sort(key=lambda r: (r.get(key) is not None, r.get(key) or 0), reverse=desc)
    return rows


def _res_fmt_cpu(v):
    return "—" if v is None else f"{v:.1f}"


def _res_render_table():
    tree = _widgets["res_tree"]
    d = _RES["data"]
    rows = _res_visible_rows()
    want = [str(r["pid"]) for r in rows]
    have = set(tree.get_children())
    for iid in have - set(want):
        tree.delete(iid)
    for r in rows:
        iid = str(r["pid"])
        vals = (r["name"], r["pid"], _res_fmt_cpu(r["cpu"]),
                "—" if r["ram"] is None else f"{r['ram']:,.0f}".replace(",", "."),
                r["origin"])
        tags = (r["kind"],) + (("crit",) if r["crit"] else ())
        if iid in have:
            tree.item(iid, values=vals, tags=tags)
        else:
            tree.insert("", "end", iid=iid, values=vals, tags=tags)
    tree.set_children("", *want)
    # Resumen de lo de Growi.
    mine = [r for r in d["procs"] if r["kind"] != "otro"]
    ram = sum(r["ram"] or 0 for r in mine) / 1024
    cpu = sum(r["cpu"] or 0 for r in mine)
    if _RES["all"]:
        txt = (f"{len(d['procs'])} procesos en el PC; {len(mine)} son de Growi "
               "(lo dice la columna Lanzado por).")
    else:
        cpu_txt = "" if d["tool"] == "tasklist" else f"{cpu:.0f} % de CPU y "
        txt = (f"Growi tiene {len(mine)} procesos andando: {cpu_txt}{_gb(ram)} GB de RAM.")
    if _RES["query"].strip():
        txt += f" Con «{_RES['query'].strip()}» se ven {len(rows)}."
    _widgets["res_summary"].config(text=txt)
    key, desc = _RES["sort"]
    for col, lab in _RES_COLS:
        arrow = (" ▼" if desc else " ▲") if col == key else ""
        tree.heading(col, text=lab + arrow)
    sel = _RES["sel"]
    if sel is not None and str(sel) in want:
        if tree.selection() != (str(sel),):
            tree.selection_set(str(sel))
    elif sel is not None:
        _RES["sel"] = None
    _res_update_actions()


_RES_COLS = (("name", "Nombre"), ("pid", "PID"), ("cpu", "CPU %"), ("ram", "RAM (MB)"),
             ("origin", "Lanzado por"))


def _res_row(pid):
    d = _RES["data"]
    if not d or pid is None:
        return None
    return next((r for r in d["procs"] if r["pid"] == pid), None)


def _res_on_select(_e=None):
    sel = _widgets["res_tree"].selection()
    _RES["sel"] = int(sel[0]) if sel else None
    _res_update_actions()


def _res_block_reason(r):
    if _res_stem(r["name"]) == "explorer":
        return ("Bloqueado: explorer.exe es el escritorio de Windows (barra de tareas y "
                "carpetas). No se puede cerrar desde la app.")
    return (f"Bloqueado: {r['name']} es un proceso crítico de Windows; cerrarlo puede "
            "colgar o reiniciar el PC. No se puede cerrar desde la app.")


def _res_update_actions():
    r = _res_row(_RES["sel"])
    btn, title, why = _widgets["res_kill_btn"], _widgets["res_sel"], _widgets["res_why"]
    if r is None:
        title.config(text="Elige un proceso de la lista")
        why.config(text="Con el proceso elegido: Supr lo cierra (siempre pide confirmación).",
                   fg=THEME["muted"])
        btn.state(["disabled"])
        return
    title.config(text=f"{r['name']}, PID {r['pid']}")
    if r["crit"]:
        btn.state(["disabled"])
        why.config(text=_res_block_reason(r), fg=THEME["orange_text"])
    else:
        btn.state(["!disabled"])
        if r["kind"] == "app":
            why.config(text="Es Growi Bridge: si lo cierras, mueren el puente y el runner.",
                       fg=THEME["orange_text"])
        else:
            why.config(text=r["origin"] or "No es de Growi.", fg=THEME["muted"])


def _res_close_selected(_e=None):
    r = _res_row(_RES["sel"])
    if r is None:
        messagebox.showinfo("Cerrar proceso", "Elige primero un proceso de la lista.")
        return
    name, pid = r["name"], r["pid"]
    if r["crit"]:
        messagebox.showwarning("Cerrar proceso", _res_block_reason(r))
        return
    if r["kind"] == "app":
        este = " (esta misma ventana)" if pid == os.getpid() else ""
        if not messagebox.askyesno(
                "Cerrar Growi Bridge",
                f"{name} con PID {pid} es Growi Bridge{este}.\n\nSi lo cierras, mueren el "
                "puente y el runner: Growi deja de poder mandarte tareas hasta que vuelvas "
                "a abrir la app.\n\n¿Seguir?", icon="warning", default="no"):
            return
        if not messagebox.askyesno(
                "Confirmar otra vez",
                f"Última confirmación: ¿cerrar {name} con PID {pid}? Se paran el puente y "
                "el runner.", icon="warning", default="no"):
            return
    else:
        quien = f"\n\nLanzado por: {r['origin']}." if r["origin"] else ""
        if not messagebox.askyesno(
                "Cerrar proceso",
                f"¿Cerrar {name} con PID {pid}?{quien}\n\nSe cierra a la fuerza: lo que no "
                "esté guardado en ese programa se pierde.", icon="warning", default="no"):
            return
    _res_set_status(f"Cerrando {name} (PID {pid})…", None)
    threading.Thread(target=_res_kill, args=(pid, name, r.get("ct")), daemon=True).start()


def _res_alive(pid, ct):
    ps = _res_psutil()
    if ps is not None:
        try:
            p = ps.Process(pid)
            return not ct or abs(p.create_time() - ct) < 1
        except Exception:
            return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, timeout=10, creationflags=_NO_WINDOW)
        return f'"{pid}"' in out.stdout.decode("oem", errors="replace")
    except Exception:
        return False


def _res_kill(pid, name, ct):
    """taskkill en un hilo; luego comprueba de verdad que el proceso murio."""
    def done(text, ok):
        log(f"recursos: {text}")
        _ui_call(lambda: _res_set_status(text, ok))
        _RES["wake"].set()  # releer ya, sin pisar el mensaje

    if _res_is_critical(name, pid):  # segunda barrera, por si acaso
        done(f"no cerré {name} (PID {pid}): es un proceso crítico de Windows", False)
        return
    ps = _res_psutil()
    if ps is not None:
        try:  # el PID tiene que seguir siendo el mismo programa
            p = ps.Process(pid)
            if p.name() != name or (ct and abs(p.create_time() - ct) >= 1):
                done(f"no cerré nada: el PID {pid} ya es otro programa ({p.name()})", False)
                return
        except Exception:
            done(f"{name} (PID {pid}) ya no estaba abierto", True)
            return
    log(f"recursos: cerrando {name} (PID {pid}) con taskkill")
    try:
        out = subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                             timeout=15, creationflags=_NO_WINDOW)
        msg = (out.stdout + out.stderr).decode("oem", errors="replace").strip()
    except Exception as e:
        out, msg = None, f"{type(e).__name__}: {e}"
    for _ in range(15):
        if not _res_alive(pid, ct):
            done(f"✓ {name} (PID {pid}) cerrado.", True)
            return
        time.sleep(0.2)
    why = msg.splitlines()[-1] if msg else "sigue abierto"
    done(f"No se pudo cerrar {name} (PID {pid}): {why}", False)


def _res_open():
    _RES["page"] = True
    if _RES["data"] is None:
        _res_set_status("Leyendo los procesos…", None)
    _res_tick()
    _RES["wake"].set()


def _build_resources_page(tab):
    bg, cbg = THEME["bg"], THEME["card"]
    tk.Label(tab, text="Recursos", font=(FONT, 22, "bold"), bg=bg,
             fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab, text="Cuánto del PC se está usando y qué lo usa. Primero, lo que Growi "
             "tiene andando.", font=(FONT, 11), bg=bg, fg=THEME["muted"], wraplength=S(600),
             justify="left").pack(anchor="w", padx=20, pady=(0, 10))

    # Resumen vivo: cuatro tarjetas (numero grande + barra fina).
    cards = tk.Frame(tab, bg=bg)
    cards.pack(fill="x", padx=20, pady=(0, 8))
    for i, (key, title) in enumerate((("cpu", "CPU"), ("ram", "RAM"), ("gpu", "GPU"),
                                      ("disk", "Disco libre"))):
        cards.grid_columnconfigure(i, weight=1, uniform="res")
        c = tk.Frame(cards, bg=cbg)
        c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 0 if i == 3 else 4))
        tk.Label(c, text=title, font=(FONT, 9), bg=cbg, fg=THEME["muted"]).pack(
            anchor="w", padx=12, pady=(10, 0))
        _widgets[f"res_{key}_val"] = tk.Label(c, text="—", font=(FONT, 17, "bold"), bg=cbg,
                                              fg=THEME["text"], anchor="w")
        _widgets[f"res_{key}_val"].pack(fill="x", padx=12)
        sub = tk.Label(c, text="", font=(FONT, 9), bg=cbg, fg=THEME["muted"], anchor="w",
                       justify="left", wraplength=S(150))
        sub.pack(fill="x", padx=12)
        # El texto pequeno se parte al ancho real de la tarjeta (no se corta).
        c.bind("<Configure>", lambda e, lab=sub: lab.config(wraplength=max(S(60), e.width - S(26))))
        _widgets[f"res_{key}_sub"] = sub
        # width pequeno: un Canvas pide 10 cm por defecto y ensanchaba la pagina.
        bar = tk.Canvas(c, width=S(40), height=S(4), bg=cbg, highlightthickness=0, bd=0)
        bar.pack(fill="x", padx=12, pady=(6, 12))
        _widgets[f"res_{key}_bar"] = bar

    # Mis procesos (Raycast: buscador arriba, lista limpia, barra de acciones
    # abajo con el elegido y su atajo).
    card = tk.Frame(tab, bg=cbg)
    card.pack(fill="x", padx=20, pady=8)
    head = tk.Frame(card, bg=cbg)
    head.pack(fill="x", padx=16, pady=(12, 2))
    _widgets["res_title"] = tk.Label(head, text="Mis procesos", font=SECTION_FONT, bg=cbg,
                                     fg=THEME["text"])
    _widgets["res_title"].pack(side="left")
    ttk.Button(head, text="Actualizar", command=_res_refresh_now).pack(side="right")

    def _toggle_all(on):
        _RES["all"] = on
        _widgets["res_title"].config(text="Todos los procesos" if on else "Mis procesos")
        if _RES["data"]:
            _res_render_table()

    sw = make_switch(head, False, _toggle_all, bg=cbg)
    sw.pack(side="right", padx=(0, 12))
    tk.Label(head, text="Ver todos los procesos", font=(FONT, 10), bg=cbg,
             fg=THEME["text"]).pack(side="right", padx=(0, 8))
    _widgets["res_all_sw"] = sw
    _widgets["res_summary"] = tk.Label(card, text="", font=(FONT, 9), bg=cbg,
                                       fg=THEME["muted"], anchor="w", justify="left",
                                       wraplength=S(640))
    _widgets["res_summary"].pack(fill="x", padx=16, pady=(0, 6))

    srow = tk.Frame(card, bg=cbg)
    srow.pack(fill="x", padx=16, pady=(0, 6))
    hint = "Buscar proceso por nombre o PID"
    # El filtro sigue al texto (escribir, pegar con el raton, borrar...).
    var = tk.StringVar()
    ent = tk.Entry(srow, textvariable=var, font=(FONT, 11), bg="#FFFFFF", fg=THEME["muted"],
                   relief="flat", highlightthickness=S(1), highlightbackground="#D2D2D7",
                   highlightcolor=THEME["blue"], insertbackground=THEME["text"])
    ent._hint = True
    ent.insert(0, hint)
    ent.pack(fill="x", ipady=S(5))

    def _focus_in(_e):
        if ent._hint:
            ent._hint = False
            ent.delete(0, "end")
            ent.config(fg=THEME["text"])

    def _focus_out(_e):
        if not ent.get():
            ent._hint = True
            ent.insert(0, hint)
            ent.config(fg=THEME["muted"])

    def _typed(*_a):
        q = "" if ent._hint else var.get()
        if q != _RES["query"]:
            _RES["query"] = q
            if _RES["data"]:
                _res_render_table()

    ent.bind("<FocusIn>", _focus_in)
    ent.bind("<FocusOut>", _focus_out)
    var.trace_add("write", _typed)
    ent.bind("<Down>", lambda _e: (tree.focus_set(), tree.get_children() and not tree.selection()
                                   and tree.selection_set(tree.get_children()[0])))
    ent.bind("<F5>", lambda _e: _res_refresh_now())
    _widgets["res_search"] = ent

    style = ttk.Style()
    style.configure("Res.Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                    foreground=THEME["text"], borderwidth=0, font=(FONT, 10),
                    rowheight=S(28))
    style.map("Res.Treeview", background=[("selected", "#DCEBFF")],
              foreground=[("selected", THEME["text"])])
    tbox = tk.Frame(card, bg="#FFFFFF")
    tbox.pack(fill="x", padx=16)
    tree = ttk.Treeview(tbox, columns=[c for c, _l in _RES_COLS], show="headings", height=11,
                        selectmode="browse", style="Res.Treeview")
    for col, lab in _RES_COLS:
        num = col in ("pid", "cpu", "ram")
        tree.heading(col, text=lab, anchor="e" if num else "w",
                     command=lambda c=col: _res_sort(c))
    tree.column("name", width=S(170), minwidth=S(90), stretch=False, anchor="w")
    tree.column("pid", width=S(64), minwidth=S(50), stretch=False, anchor="e")
    tree.column("cpu", width=S(64), minwidth=S(50), stretch=False, anchor="e")
    tree.column("ram", width=S(80), minwidth=S(60), stretch=False, anchor="e")
    tree.column("origin", width=S(260), minwidth=S(120), stretch=True, anchor="w")
    tree.tag_configure("app", font=(FONT, 10, "bold"))
    tree.tag_configure("crit", foreground=THEME["muted"])
    ysb = ttk.Scrollbar(tbox, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=ysb.set)
    ysb.pack(side="right", fill="y")
    tree.pack(side="left", fill="x", expand=True)
    tree.bind("<<TreeviewSelect>>", _res_on_select)
    tree.bind("<Delete>", _res_close_selected)
    tree.bind("<F5>", lambda _e: _res_refresh_now())
    # La rueda mueve la lista (no la pagina) cuando el raton esta encima.
    tree.bind("<MouseWheel>", lambda e: (tree.yview_scroll(-1 if e.delta > 0 else 1, "units"),
                                         "break")[1])
    _widgets["res_tree"] = tree

    act = tk.Frame(card, bg=cbg)
    act.pack(fill="x", padx=16, pady=(8, 12))
    left = tk.Frame(act, bg=cbg)
    left.pack(side="left", fill="x", expand=True)
    _widgets["res_sel"] = tk.Label(left, text="", font=(FONT, 10, "bold"), bg=cbg,
                                   fg=THEME["text"], anchor="w")
    _widgets["res_sel"].pack(fill="x")
    _widgets["res_why"] = tk.Label(left, text="", font=(FONT, 9), bg=cbg, fg=THEME["muted"],
                                   anchor="w", justify="left", wraplength=S(430))
    _widgets["res_why"].pack(fill="x")
    tk.Label(act, text="Supr", font=(FONT, 9), bg="#E8E8ED", fg=THEME["text"],
             padx=S(6), pady=S(1)).pack(side="right", padx=(8, 0))
    style.configure("Danger.TButton", foreground=THEME["red"], font=(FONT, 10, "bold"))
    style.map("Danger.TButton", foreground=[("disabled", "#8E8E93")],
              background=[("disabled", "#F5F5F7"), ("active", "#FBECEC")])
    _widgets["res_kill_btn"] = ttk.Button(act, text="Cerrar proceso", style="Danger.TButton",
                                          command=_res_close_selected)
    _widgets["res_kill_btn"].pack(side="right")
    _widgets["res_status"] = tk.Label(card, text="", font=(FONT, 9, "bold"), bg=cbg,
                                      fg=THEME["muted"], anchor="w")
    _widgets["res_status"].pack(fill="x", padx=16, pady=(0, 12))
    _widgets["res_tool"] = tk.Label(tab, text="", font=(FONT, 9), bg=bg, fg=THEME["muted"],
                                    anchor="w", justify="left", wraplength=S(640))
    _widgets["res_tool"].pack(fill="x", padx=20, pady=(0, 16))
    _res_update_actions()


def _res_sort(col):
    key, desc = _RES["sort"]
    _RES["sort"] = (col, not desc if key == col else col in ("cpu", "ram", "pid"))
    if _RES["data"]:
        _res_render_table()


def _build_ajustes_tk(tab_aj):
    """Pagina Ajustes clasica (tkinter), tal cual estaba antes del piloto.
    Es la que sale si CustomTkinter no esta o el piloto esta apagado."""
    tk.Label(tab_aj, text="Ajustes", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab_aj, text="Todo lo de la app en un solo sitio.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    aj = tk.Frame(tab_aj, bg=THEME["card"])
    aj.pack(fill="x", padx=20, pady=8)
    tk.Label(aj, text="General", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))

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
        sep = tk.Frame(aj, bg=THEME["line"], height=S(1))
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

    crow = tk.Frame(aj, bg=THEME["card"])
    crow.pack(fill="x", padx=16, pady=(5, 12))
    tk.Label(crow, text="Al cerrar la ventana", font=(FONT, 10, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w")
    tk.Label(crow, text="Qué hace la X: quedarse en la bandeja (sigue recibiendo tareas) "
             "o salir del todo.", font=(FONT, 9), bg=THEME["card"],
             fg=THEME["muted"]).pack(anchor="w")
    _close_now = load_settings().get("on_close")
    _widgets["close_var"] = tk.StringVar(
        value=_close_now if _close_now in ("minimize", "quit") else "ask")
    _crow_opts = tk.Frame(crow, bg=THEME["card"])
    _crow_opts.pack(anchor="w", pady=(4, 0))
    for _k, _lab in CLOSE_MODES:
        tk.Radiobutton(_crow_opts, text=_lab, value=_k, variable=_widgets["close_var"],
                       command=lambda k=_k: _set_close_mode(k), font=(FONT, 10),
                       bg=THEME["card"], fg=THEME["text"], activebackground=THEME["card"],
                       selectcolor="#FFFFFF", bd=0, highlightthickness=S(2),
                       highlightbackground=THEME["card"], highlightcolor=THEME["blue"],
                       anchor="w").pack(side="left", padx=(0, 14))

    ob = _card(tab_aj, "Configuración inicial",
               "Los 4 pasos del principio: asistente, conectar, carpetas y comprobación.")
    obr = tk.Frame(ob, bg=THEME["card"])
    obr.pack(fill="x", padx=16, pady=(0, 6))
    ttk.Button(obr, text="Volver a hacer la configuración inicial",
               command=open_onboarding).pack(side="left")
    tk.Label(ob, text="Apariencia (se aplica al volver a abrir la app)", font=(FONT, 10, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(6, 0))
    _widgets["apariencia"] = tk.StringVar(value=load_settings().get("apariencia") or "sistema")
    aprow = tk.Frame(ob, bg=THEME["card"])
    aprow.pack(anchor="w", padx=12, pady=(2, 12))

    def _set_apariencia(v):
        s = load_settings()
        s["apariencia"] = v
        save_settings(s)
        log(f"ajustes: apariencia {v} (al volver a abrir la app)")
    for _k, _lab in (("sistema", "Como Windows"), ("claro", "Clara"), ("oscuro", "Oscura")):
        tk.Radiobutton(aprow, text=_lab, value=_k, variable=_widgets["apariencia"],
                       command=lambda k=_k: _set_apariencia(k), font=(FONT, 10),
                       bg=THEME["card"], fg=THEME["text"], activebackground=THEME["card"],
                       selectcolor="#FFFFFF", bd=0, highlightthickness=S(2),
                       highlightbackground=THEME["card"], highlightcolor=THEME["blue"],
                       anchor="w").pack(side="left", padx=(0, 14))

    gr = tk.Frame(tab_aj, bg=THEME["card"])
    gr.pack(fill="x", padx=20, pady=8)
    tk.Label(gr, text="Permisos", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(gr, text="Antes de borrar, publicar, gastar o enviar algo, Growi te enseña el "
             "plan en Tareas y espera tu sí.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"], wraplength=S(600),
             justify="left").pack(anchor="w", padx=16, pady=(0, 6))
    _widgets["guardrail_var"] = tk.StringVar(value=guardrail_level())
    for _k, _lab, _expl in GUARDRAIL_LEVELS:
        _row = tk.Frame(gr, bg=THEME["card"])
        _row.pack(fill="x", padx=16, pady=3)
        tk.Radiobutton(_row, text=_lab, value=_k, variable=_widgets["guardrail_var"],
                       command=lambda k=_k: _on_guardrail(k), font=(FONT, 10, "bold"),
                       bg=THEME["card"], fg=THEME["text"], activebackground=THEME["card"],
                       selectcolor="#FFFFFF", bd=0, highlightthickness=S(2),
                       highlightbackground=THEME["card"], highlightcolor=THEME["blue"],
                       anchor="w").pack(anchor="w")
        tk.Label(_row, text=_expl, font=(FONT, 9), bg=THEME["card"],
                 fg=THEME["muted"]).pack(anchor="w", padx=(24, 0))
    tk.Frame(gr, bg=THEME["card"], height=S(8)).pack()

    pc = tk.Frame(tab_aj, bg=THEME["card"])
    pc.pack(fill="x", padx=20, pady=8)
    tk.Label(pc, text="Este PC", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
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


# ---------------------------------------------------------------- piloto CustomTkinter (Ajustes)
# PILOTO (antes de la cadena Fase A; ver share\outbox\ESTADO-PILOTO-CUSTOMTKINTER.md):
# SOLO la pagina Ajustes se dibuja con CustomTkinter. Si customtkinter no se
# puede importar (o falla al dibujar), o si GROWI_BRIDGE_CTK=0 o settings.json
# trae "piloto_ctk": false, sale la pagina clasica de tkinter
# (_build_ajustes_tk), que se queda tal cual. Mismo comportamiento en las dos:
# los mismos interruptores, opciones y botones llaman a las mismas funciones.
# Quitar el piloto: "piloto_ctk": false en settings.json (o borrar este bloque
# y dejar en build_gui la llamada directa a _build_ajustes_tk).
_AJ_KEYS = ("autoupd_sw", "autostart_sw", "keepawake_sw", "close_var", "apariencia",
            "guardrail_var", "update_label", "update_btn")


def _ctk_wanted():
    if os.environ.get("GROWI_BRIDGE_CTK", "").strip() == "0":
        return False
    return load_settings().get("piloto_ctk", True) is not False


def _build_ajustes(tab_aj):
    """Pagina Ajustes: CustomTkinter (piloto) o, si no se puede, la clasica."""
    if _ctk_wanted():
        t0 = time.perf_counter()
        try:
            ver = _build_ajustes_ctk(tab_aj)
            _widgets["ajustes_ctk"] = True
            log(f"ajustes: pagina con CustomTkinter {ver} "
                f"({(time.perf_counter() - t0) * 1000:.0f} ms, importacion incluida)")
            return
        except Exception as e:
            log(f"ajustes: CustomTkinter no disponible ({type(e).__name__}: {e}); "
                "se usa la pagina clasica")
            for ch in tab_aj.winfo_children():
                try:
                    ch.destroy()
                except Exception:
                    pass
            for k in _AJ_KEYS:
                _widgets.pop(k, None)
    _widgets["ajustes_ctk"] = False
    _build_ajustes_tk(tab_aj)


def _build_ajustes_ctk(tab_aj):
    import customtkinter as ctk
    # La app ya fija su DPI (SCALE, ver _dpi_scaling): CustomTkinter usa el
    # mismo factor en vez de leer el monitor por su cuenta.
    ctk.deactivate_automatic_dpi_awareness()
    ctk.set_widget_scaling(SCALE)
    dark = _THEME_STATE["dark"]
    ctk.set_appearance_mode("dark" if dark else "light")
    T = THEME
    # Colores: los tokens de THEME; los fijos van en minusculas para que el
    # filtro de tema (_DARK_MAP, solo mayusculas) no los vuelva a cambiar.
    seg_bg = "#3a3a3f" if dark else "#e8e8ed"
    seg_sel = "#5a5a5f" if dark else "#ffffff"
    seg_hover = "#4a4a4e" if dark else "#dcdce1"
    accent = "#0a64c8" if dark else "#0066cc"
    accent_hover = "#0a84ff" if dark else "#0057b0"
    off_track = "#48484c" if dark else "#e9e9ea"

    def F(px, w=None):
        # Segoe UI Semibold es la variante semibold real de Windows.
        if w == "semibold":
            return ctk.CTkFont(family="Segoe UI Semibold", size=px)
        return ctk.CTkFont(family=FONT, size=px, weight=w or "normal")

    class _Label(ctk.CTkLabel):
        def config(self, **kw):  # refresh_ui usa .config()
            if "fg" in kw:
                kw["text_color"] = kw.pop("fg")
            return self.configure(**kw)

    class _Button(ctk.CTkButton):
        _accent = None

        def config(self, **kw):
            return self.configure(**kw)

        def configure(self, require_redraw=False, **kw):
            if "state" in kw and self._accent:
                on = kw["state"] == "normal"
                kw.setdefault("fg_color", self._accent if on else seg_bg)
            return super().configure(require_redraw, **kw)

    class _Switch(ctk.CTkSwitch):
        # Lo que esperan set_switch() y la paleta del interruptor clasico.
        @property
        def _on(self):
            return bool(self.get())

        @_on.setter
        def _on(self, v):  # set_switch() asigna _on y luego lo vuelve a leer
            (self.select if v else self.deselect)()

        def _animate_to(self, t):
            (self.select if t >= 0.5 else self.deselect)()

        def event_generate(self, seq, *a, **kw):
            if seq == "<Button-1>":
                self.toggle()
                return None
            return super().event_generate(seq, *a, **kw)

    # El texto se parte al ancho que hay (a 150 % nada se sale de su caja).
    # Una sola pasada agrupada tras los cambios de tamano: re-partir en cada
    # <Configure> redibujaba las esquinas de CTk cientos de veces (~1 s).
    _wraps = []
    _wrap_job = [None]

    def _rewrap():
        _wrap_job[0] = None
        for label, frame in _wraps:
            try:
                w = max(80, int(frame.winfo_width() / SCALE) - 4)
                if abs(label.cget("wraplength") - w) > 2:
                    label.configure(wraplength=w)
            except Exception:
                pass

    def _wrap_soon(_e=None):
        if _wrap_job[0] is None:
            _wrap_job[0] = tab_aj.after(60, _rewrap)

    def wrap_to(label, frame):
        _wraps.append((label, frame))
        frame.bind("<Configure>", _wrap_soon, add=True)

    def text_block(parent, title, expl, title_font=None):
        if title:
            _Label(parent, text=title, font=title_font or F(14, "semibold"),
                   text_color=T["text"], anchor="w", justify="left",
                   height=1).pack(anchor="w", fill="x")
        if expl:
            ex = _Label(parent, text=expl, font=F(13), text_color=T["muted"],
                        anchor="w", justify="left", height=1)
            ex.pack(anchor="w", fill="x", pady=(2, 0))
            wrap_to(ex, parent)

    def section(title):
        # Etiqueta de seccion fuera de la tarjeta, en formato oracion y
        # apagada (Raycast: "Categories", "All Extensions").
        _Label(tab_aj, text=title, font=F(15, "semibold"), text_color=T["muted"],
               anchor="w", height=1).pack(anchor="w", padx=22, pady=(16, 6))
        card = ctk.CTkFrame(tab_aj, fg_color=T["card"], corner_radius=10,
                            border_width=1, border_color=T["line"])
        card.pack(fill="x", padx=20)
        card._rows = 0
        return card

    def row(card):
        if card._rows:
            tk.Frame(card, bg=T["line"], height=S(1)).pack(fill="x", padx=16)
        card._rows += 1
        r = ctk.CTkFrame(card, fg_color="transparent")
        r.pack(fill="x", padx=16, pady=12)
        return r

    def button(parent, text, command, danger=False):
        return _Button(parent, text=text, command=command, font=F(13),
                       corner_radius=8, height=32, width=0, border_spacing=10,
                       fg_color=seg_bg, hover_color=seg_hover,
                       text_color=T["red"] if danger else T["text"],
                       text_color_disabled=T["muted"])

    def segmented(parent, var, options, on_pick):
        # Control segmentado en pildora; var guarda la clave (como antes).
        labels = dict(options)
        keys = {v: k for k, v in options}
        seg = ctk.CTkSegmentedButton(
            parent, values=[l for _k, l in options], font=F(13), height=30,
            corner_radius=8, border_width=2, fg_color=seg_bg,
            selected_color=seg_sel, selected_hover_color=seg_sel,
            unselected_color=seg_bg, unselected_hover_color=seg_hover,
            text_color=T["text"], command=lambda lab: on_pick(keys[lab]))
        seg.set(labels.get(var.get(), ""))
        var.trace_add("write", lambda *_a: seg.set(labels.get(var.get(), "")))
        return seg

    def setting_switch(card, label, expl, initial, on_change):
        r = row(card)
        sw = _Switch(r, text="", width=46, switch_width=46, switch_height=26,
                     corner_radius=13, button_length=0, border_width=1,
                     border_color="#8e8e93",  # mismo borde que el interruptor clasico
                     fg_color=off_track, progress_color=T["green"],
                     button_color="#ffffff", button_hover_color="#f2f2f7",
                     command=lambda: on_change(bool(sw.get())))
        if initial:
            sw.select()
        sw.pack(side="right", padx=(16, 0))
        # Teclado (Tab + Espacio/Intro), como el interruptor clasico.
        try:
            sw._canvas.configure(takefocus=1)
            sw._canvas.bind("<space>", lambda _e: sw.toggle())
            sw._canvas.bind("<Return>", lambda _e: sw.toggle())
            # Con el foco el borde se vuelve azul y mas grueso (como el clasico).
            sw._canvas.bind("<FocusIn>", lambda _e: sw.configure(
                border_color=T["blue"], border_width=2), add=True)
            sw._canvas.bind("<FocusOut>", lambda _e: sw.configure(
                border_color="#8e8e93", border_width=1), add=True)
        except Exception:
            pass
        left = ctk.CTkFrame(r, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        text_block(left, label, expl)
        return sw

    # ---- cabecera
    _Label(tab_aj, text="Ajustes", font=F(29, "bold"), text_color=T["text"],
           anchor="w").pack(anchor="w", padx=20, pady=(18, 0))
    _Label(tab_aj, text="Todo lo de la app en un solo sitio.", font=F(15),
           text_color=T["muted"], anchor="w", height=1).pack(anchor="w", padx=20, pady=(0, 2))

    # ---- General (mismos manejadores que la pagina clasica)
    gen = section("General")

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

    def _sw_keepawake(on):
        state["keep_awake"] = on
        s = load_settings()
        s["keep_awake"] = on
        save_settings(s)
        log(f"ajustes: no suspender mientras trabaja {'activado' if on else 'desactivado'}")

    _widgets["autoupd_sw"] = setting_switch(
        gen, "Actualización automática",
        "Se actualiza sola desde GitHub cuando hay una versión nueva.",
        state.get("auto_update", False), _sw_autoupd)
    _widgets["autostart_sw"] = setting_switch(
        gen, "Iniciar al encender la PC", "Arranca sola con Windows al iniciar sesión.",
        state.get("autostart", False), _sw_autostart)
    _widgets["keepawake_sw"] = setting_switch(
        gen, "No suspender mientras trabaja",
        "La PC no se duerme mientras Claude corre una tarea.",
        state.get("keep_awake", True), _sw_keepawake)

    r = row(gen)
    text_block(r, "Al cerrar la ventana",
               "Qué hace la X: quedarse en la bandeja (sigue recibiendo tareas) "
               "o salir del todo.")
    _close_now = load_settings().get("on_close")
    _widgets["close_var"] = tk.StringVar(
        value=_close_now if _close_now in ("minimize", "quit") else "ask")
    segmented(r, _widgets["close_var"], CLOSE_MODES, _set_close_mode).pack(
        anchor="w", pady=(10, 0))

    # ---- Configuracion inicial y apariencia
    ob = section("Configuración inicial")
    r = row(ob)
    text_block(r, None,
               "Los 4 pasos del principio: asistente, conectar, carpetas y comprobación.")
    button(r, "Volver a hacer la configuración inicial", open_onboarding).pack(
        anchor="w", pady=(10, 0))
    r = row(ob)
    text_block(r, "Apariencia", "Se aplica al volver a abrir la app.")
    _widgets["apariencia"] = tk.StringVar(value=load_settings().get("apariencia") or "sistema")

    def _set_apariencia(v):
        _widgets["apariencia"].set(v)
        s = load_settings()
        s["apariencia"] = v
        save_settings(s)
        log(f"ajustes: apariencia {v} (al volver a abrir la app)")
    segmented(r, _widgets["apariencia"],
              (("sistema", "Como Windows"), ("claro", "Clara"), ("oscuro", "Oscura")),
              _set_apariencia).pack(anchor="w", pady=(10, 0))

    # ---- Permisos (una opcion por fila, explicacion debajo: BFF)
    gr = section("Permisos")
    r = row(gr)
    text_block(r, None, "Antes de borrar, publicar, gastar o enviar algo, Growi te enseña "
                        "el plan en Tareas y espera tu sí.")
    _widgets["guardrail_var"] = tk.StringVar(value=guardrail_level())
    for _k, _lab, _expl in GUARDRAIL_LEVELS:
        r = row(gr)
        ctk.CTkRadioButton(r, text=_lab, value=_k, variable=_widgets["guardrail_var"],
                           command=lambda k=_k: _on_guardrail(k), font=F(14, "semibold"),
                           text_color=T["text"], fg_color=accent, hover_color=accent_hover,
                           border_color=T["muted"], radiobutton_width=18,
                           radiobutton_height=18, border_width_unchecked=2,
                           border_width_checked=5).pack(anchor="w")
        sub = ctk.CTkFrame(r, fg_color="transparent")
        sub.pack(fill="x", padx=(28, 0))
        text_block(sub, None, _expl)

    # ---- Este PC (confirmacion y 60 s de margen: _pc_confirm, igual que antes)
    pc = section("Este PC")
    r = row(pc)
    text_block(r, None, "Apagar o reiniciar este PC. Te pide confirmación y tienes "
                        "60 segundos para cancelarlo.")
    prow = ctk.CTkFrame(r, fg_color="transparent")
    prow.pack(anchor="w", pady=(10, 0))
    _widgets["aj_pc_off"] = button(prow, "Apagar PC", lambda: _pc_confirm("shutdown"),
                                   danger=True)
    _widgets["aj_pc_off"].pack(side="left", padx=(0, 8))
    _widgets["aj_pc_restart"] = button(prow, "Reiniciar PC", lambda: _pc_confirm("restart"),
                                       danger=True)
    _widgets["aj_pc_restart"].pack(side="left", padx=(0, 8))
    _widgets["aj_pc_cancel"] = button(prow, "Cancelar apagado", pc_abort)
    _widgets["aj_pc_cancel"].pack(side="left")

    # ---- Carpetas y version
    up = section("Carpetas y actualizaciones")
    r = row(up)
    text_block(r, None, f"Versión {VERSION}.")
    brow = ctk.CTkFrame(r, fg_color="transparent")
    brow.pack(anchor="w", pady=(10, 0))
    for i, (txt, cmd) in enumerate((("Abrir Inbox", lambda: open_folder(INBOX)),
                                    ("Abrir Outbox", lambda: open_folder(OUTBOX)),
                                    ("Buscar actualizaciones", check_updates_ui),
                                    ("Salir", quit_app))):
        button(brow, txt, cmd).pack(side="left", padx=(0 if i == 0 else 8, 0))
    _widgets["update_label"] = _Label(r, text="", font=F(13), text_color=T["green_text"],
                                      anchor="w", height=1)
    _widgets["update_label"].pack(anchor="w", pady=(8, 0))
    ub = _Button(r, text="Actualizar ahora", command=do_update_ui, font=F(14, "semibold"),
                 corner_radius=8, height=32, width=0, border_spacing=10,
                 fg_color=seg_bg, hover_color=accent_hover, text_color="#ffffff",
                 text_color_disabled=T["muted"])
    ub._accent = accent
    ub.configure(state="disabled")
    ub.pack(anchor="w", pady=(6, 0))
    _widgets["update_btn"] = ub
    tk.Frame(tab_aj, bg=T["bg"], height=S(20)).pack()
    return ctk.__version__


def build_gui():
    global _root, _PALETTE_CMDS
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        state["dnd"] = True
    except ImportError:
        root = tk.Tk()
        state["dnd"] = False
    _root = root
    # El icono va lo primero, antes de _dpi_scaling (su update_idletasks ya
    # muestra la ventana): asi nunca se ve la pluma de Tk, ni un instante.
    try:
        if ICO.is_file():
            root.iconbitmap(default=str(ICO))
            root.iconbitmap(str(ICO))
        else:
            log(f"icono: falta {ICO}; la barra de tareas mostrara la pluma de Tk")
    except Exception as e:
        log(f"icono: iconbitmap fallo ({type(e).__name__}: {e}); "
            "la barra de tareas mostrara la pluma de Tk")
    _dpi_scaling(root)
    _set_taskbar_props(root)
    root.title("Growi Bridge" + (" — carril B" if LANE == "b" else ""))
    # Tamano a 100 % por SCALE, sin pasarse de la pantalla (a 150 % en un
    # portatil de 1080 px la ventana entera no cabria).
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{min(S(940), sw - 40)}x{min(S(680), sh - 80)}")
    root.minsize(min(S(820), sw - 40), min(S(560), sh - 80))
    root.configure(bg=THEME["bg"])
    root.protocol("WM_DELETE_WINDOW", on_close_window)
    cfg = proxy_config()

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TButton", background="#FFFFFF", foreground=THEME["text"],
                    borderwidth=1, relief="solid",
                    padding=(S(12), S(6)), font=(FONT, 10))
    style.map("TButton", background=[("active", "#F5F5F7")])
    style.configure("Accent.TButton", background=THEME["blue"], foreground="white",
                    borderwidth=0, padding=(S(12), S(6)), font=(FONT, 10, "bold"))
    style.map("Accent.TButton", background=[("disabled", "#E8E8ED"), ("active", "#0055AA")],
              foreground=[("disabled", "#6E6E73")])
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=THEME["text"],
                    borderwidth=1, relief="solid", insertcolor=THEME["text"])
    try:  # bordercolor no existe en todos los Tk; si falla, se sigue sin el
        style.configure("TButton", bordercolor="#D2D2D7")
        style.configure("TEntry", bordercolor="#D2D2D7")
    except Exception:
        pass
    style.configure("TCombobox", fieldbackground="#FFFFFF", foreground=THEME["text"])
    style.map("TCombobox", fieldbackground=[("readonly", "#FFFFFF")],
              selectbackground=[("readonly", "#FFFFFF")],
              selectforeground=[("readonly", THEME["text"])])
    style.configure("Treeview", background="#FFFFFF", foreground=THEME["text"],
                    fieldbackground="#FFFFFF", borderwidth=0, font=(FONT, 10),
                    rowheight=S(24))
    style.configure("Treeview.Heading", background="#F5F5F7",
                    foreground=THEME["muted"], font=(FONT, 10, "bold"))
    style.configure("TCheckbutton", background=THEME["bg"], foreground=THEME["text"],
                    font=(FONT, 10))
    _theme_styles(style)
    _dark_titlebar(root)

    # ---------------- barra lateral (Superlist / Plain)
    sidebar = tk.Frame(root, bg=THEME["sidebar"], width=S(220))
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)
    head = tk.Frame(sidebar, bg=THEME["sidebar"])
    head.pack(fill="x", padx=16, pady=(16, 8))
    photo = None
    if TRAY_OK and HEADER_PHOTO.is_file():
        try:
            img = Image.open(HEADER_PHOTO).resize((S(64), S(64)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            # La foto es solo para la barra lateral: nunca como icono de la
            # ventana (iconphoto taparia growi.ico en la barra de tareas).
            tk.Label(head, image=photo, bg=THEME["sidebar"]).pack(anchor="w")
            head.image = photo
        except Exception as e:
            log(f"encabezado: {type(e).__name__}: {e}")
    tk.Label(head, text="Growi Bridge", font=(FONT, 15, "bold"),
             bg=THEME["sidebar"], fg=THEME["text"]).pack(anchor="w", pady=(8, 0))
    _widgets["admin_text"] = tk.Label(head, text="", font=(FONT, 9), justify="left",
                                      bg=THEME["sidebar"], fg=THEME["muted"])
    _widgets["admin_text"].pack(anchor="w")
    _widgets["conn_chip"] = tk.Label(head, text=conn_text(), font=(FONT, 10, "bold"),
                                     bg=THEME["sidebar"], fg=_conn_color(), cursor="hand2",
                                     anchor="w", justify="left", wraplength=S(190))
    _widgets["conn_chip"].pack(anchor="w", pady=(6, 0))
    _widgets["conn_chip"].bind("<Button-1>", lambda _e: _widgets["show_page"]("estado"))

    # ---------------- contenido (una pagina por seccion, con scroll)
    content = tk.Frame(root, bg=THEME["bg"])
    content.pack(side="right", fill="both", expand=True)
    # Banner mientras un motor trabaja (visible en todas las paginas).
    banner_slot = tk.Frame(content, bg=THEME["bg"])
    banner_slot.pack(side="top", fill="x")
    banner = tk.Frame(banner_slot, bg=THEME["card"])
    tk.Frame(banner, bg=THEME["blue"], width=S(3)).pack(side="left", fill="y")
    btxt = tk.Frame(banner, bg=THEME["card"])
    btxt.pack(side="left", fill="x", expand=True, padx=12, pady=8)
    _widgets["banner_title"] = tk.Label(btxt, text="", font=(FONT, 10, "bold"),
                                        bg=THEME["card"], fg=THEME["text"], anchor="w")
    _widgets["banner_title"].pack(fill="x")
    _widgets["banner_sub"] = tk.Label(btxt, text="", font=(FONT, 9),
                                      bg=THEME["card"], fg=THEME["muted"], anchor="w")
    _widgets["banner_sub"].pack(fill="x")
    ttk.Button(banner, text="Parar", command=_on_stop_click).pack(side="right", padx=12)
    _widgets["banner"] = banner
    cloud = tk.Frame(banner_slot, bg=THEME["card"])
    tk.Frame(cloud, bg=THEME["orange"], width=S(3)).pack(side="left", fill="y")
    _widgets["cloud_banner_txt"] = tk.Label(cloud, text="", font=(FONT, 10, "bold"),
                                            bg=THEME["card"], fg=THEME["text"], anchor="w",
                                            justify="left", wraplength=S(520))
    _widgets["cloud_banner_txt"].pack(side="left", fill="x", expand=True, padx=12, pady=8)
    ttk.Button(cloud, text="Ver el mapa", command=lambda: _widgets["show_page"]("estado")).pack(
        side="right", padx=12)
    _widgets["cloud_banner"] = cloud
    pages = {}
    for name in ("estado", "carpetas", "skills", "pantalla", "apis", "modelos",
                 "tareas", "recursos", "ajustes", "registro"):
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
        if name == "modelos":
            _on_models_open()
        if name == "tareas":
            _tasks_fp[0] = None
            _refresh_tasks_ui()
        # Recursos: la lectura corre solo con la pestana abierta.
        if name == "recursos":
            _res_open()
        else:
            _RES["page"] = False
            _RES["active"] = False

    _widgets["show_page"] = _show_page
    _nav_btns = {}
    nav = tk.Frame(sidebar, bg=THEME["sidebar"])
    nav.pack(fill="x", padx=8, pady=8)
    for name, label in (("estado", "Estado"), ("carpetas", "Carpetas"),
                        ("skills", "Skills"), ("pantalla", "Pantalla"),
                        ("apis", "APIs"), ("modelos", "Modelos"), ("tareas", "Tareas"),
                        ("recursos", "Recursos"), ("ajustes", "Ajustes"),
                        ("registro", "Registro")):
        row = tk.Frame(nav, bg=THEME["sidebar"])
        row.pack(fill="x", pady=1)
        bar = tk.Frame(row, bg=THEME["sidebar"], width=S(3))
        bar.pack(side="left", fill="y")
        btn = tk.Button(row, text="  " + label, font=(FONT, 11),
                        bg=THEME["sidebar"], fg=THEME["text"], bd=0,
                        activebackground="#E8E8ED", anchor="w",
                        highlightthickness=S(2), highlightcolor=THEME["blue"],
                        highlightbackground=THEME["sidebar"], cursor="hand2",
                        pady=0, command=lambda n=name: _show_page(n))
        btn.bind("<Return>", lambda _e, n=name: _show_page(n))
        btn.pack(side="left", fill="x", expand=True, ipady=2)
        btn._bar = bar
        _nav_btns[name] = btn
        if name in ("carpetas", "skills", "apis", "modelos", "tareas", "recursos"):
            cnt = tk.Label(row, text="", font=(FONT, 10),
                           bg=THEME["sidebar"], fg=THEME["muted"])
            cnt.pack(side="right", padx=(0, 10))
            _widgets[f"nav_count_{name}"] = cnt

    krow = tk.Frame(sidebar, bg=THEME["sidebar"], cursor="hand2")
    krow.pack(fill="x", padx=18, pady=(0, 4))
    _kl = tk.Label(krow, text="Buscar acciones", font=(FONT, 10),
                   bg=THEME["sidebar"], fg=THEME["muted"], cursor="hand2")
    _kl.pack(side="left")
    _kc = tk.Label(krow, text="Ctrl+K", font=(FONT, 9), bg="#E8E8ED",
                   fg=THEME["text"], padx=S(6), pady=S(1), cursor="hand2")
    _kc.pack(side="right")
    for _w in (krow, _kl, _kc):
        _w.bind("<Button-1>", lambda _e: _open_palette())

    # Pie de la barra lateral: la mascota siempre a la vista (Superlist /
    # Plain ponen el avatar abajo). El interruptor enciende o apaga a Growi.
    foot = tk.Frame(sidebar, bg=THEME["sidebar"])
    foot.pack(side="bottom", fill="x", padx=16, pady=14, before=nav)
    tk.Frame(foot, bg=THEME["line"], height=S(1)).pack(fill="x", pady=(0, 10))
    frow = tk.Frame(foot, bg=THEME["sidebar"])
    frow.pack(fill="x")
    mini = None
    if TRAY_OK and PHOTO.is_file():
        try:
            img = Image.open(PHOTO).resize((S(40), S(40)), Image.LANCZOS)
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
    tk.Label(tab, text="El puente, el runner y el proxy, de un vistazo.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"]).pack(
        anchor="w", padx=20, pady=(0, 10))

    power = tk.Frame(tab, bg=THEME["bg"])
    power.pack(pady=4)
    canvas = tk.Canvas(power, width=S(170), height=S(170), bg=THEME["bg"],
                       highlightthickness=0, takefocus=1, cursor="hand2")
    canvas.pack()
    canvas._focus = False

    def _power_focus(on):
        canvas._focus = on
        draw_power()

    canvas.bind("<Button-1>", lambda e: (canvas.focus_set(), on_power_click()))
    canvas.bind("<space>", lambda e: on_power_click())
    canvas.bind("<Return>", lambda e: on_power_click())
    canvas.bind("<FocusIn>", lambda e: _power_focus(True))
    canvas.bind("<FocusOut>", lambda e: _power_focus(False))
    _widgets["power_canvas"] = canvas
    _widgets["power_label"] = tk.Label(power, text="Todo apagado",
                                       font=(FONT, 13, "bold"),
                                       bg=THEME["bg"], fg=THEME["muted"])
    _widgets["power_label"].pack()

    status = tk.Frame(tab, bg=THEME["card"])
    status.pack(fill="x", padx=20, pady=8)
    tk.Label(status, text="Servicios", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))

    def _service_row(key, label, on_switch):
        row = tk.Frame(status, bg=THEME["card"])
        row.pack(fill="x", padx=16, pady=5)
        dot = tk.Label(row, text="●", font=(FONT, 13), bg=THEME["card"])
        dot.pack(side="left", padx=(0, 8))
        tk.Label(row, text=label, font=(FONT, 10, "bold"),
                 bg=THEME["card"], fg=THEME["text"]).pack(side="left")
        pill = tk.Label(row, text="", font=(FONT, 9), bg="#E8E8ED",
                        fg=THEME["text"], padx=S(8), pady=S(2))
        pill.pack(side="left", padx=(10, 0))
        sw = make_switch(row, False, on_switch, bg=THEME["card"])
        sw.pack(side="right")
        _widgets[f"{key}_dot"] = dot
        _widgets[f"{key}_pill"] = pill
        _widgets[f"{key}_sw"] = sw
        sep = tk.Frame(status, bg=THEME["line"], height=S(1))
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

    _build_avail_card(tab)

    px = tk.Frame(tab, bg=THEME["card"])
    px.pack(fill="x", padx=20, pady=8)
    tk.Label(px, text="Proxy", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    _widgets["px_state"] = tk.Label(px, text=conn_text(), font=(FONT, 11, "bold"),
                                    bg=THEME["card"], fg=_conn_color())
    _widgets["px_state"].pack(anchor="w", padx=16)
    tk.Label(px, text="El proxy te conecta; tu cuenta puede ser suspendida si el proveedor detecta "
             "la región. La vía sin ese riesgo es la API con clave propia o un modelo local.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"], wraplength=S(600),
             justify="left").pack(anchor="w", padx=16, pady=(2, 6))
    pxb = tk.Frame(px, bg=THEME["card"])
    pxb.pack(fill="x", padx=16, pady=(0, 4))
    _widgets["px_test_btn"] = ttk.Button(pxb, text="Probar proxy", style="Accent.TButton")
    _widgets["px_test_btn"].pack(side="left", padx=(0, 8))
    _widgets["px_test_btn"].config(command=lambda: proxy_test_ui(_widgets["px_test_btn"],
                                                                 _widgets["px_result"]))
    ttk.Button(pxb, text="Exportar mis conversaciones",
               command=export_conversations).pack(side="left", padx=(0, 8))
    _widgets["px_adv_btn"] = ttk.Button(pxb, text="Ajustes avanzados",
                                        command=_toggle_px_advanced)
    _widgets["px_adv_btn"].pack(side="left")
    _widgets["px_result"] = tk.Label(px, text="", font=(FONT, 10), bg=THEME["card"],
                                     fg=THEME["muted"], wraplength=S(600), justify="left")
    _widgets["px_result"].pack(anchor="w", padx=16, pady=(2, 0))
    _widgets["px_export_status"] = tk.Label(px, text="", font=(FONT, 9), bg=THEME["card"],
                                            fg=THEME["muted"], wraplength=S(600), justify="left")
    _widgets["px_export_status"].pack(anchor="w", padx=16)
    adv = tk.Frame(px, bg=THEME["card"])
    _widgets["px_adv"] = adv
    _widgets["px_adv_anchor"] = tk.Frame(px, bg=THEME["card"], height=S(10))
    _widgets["px_adv_anchor"].pack(fill="x")
    tk.Label(adv, text="Cada quien usa el suyo. Encendido, Claude sale por el proxy.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"]).pack(
        anchor="w", padx=16, pady=(6, 4))
    _widgets["px_mode"] = tk.StringVar(value=load_settings().get("proxy_mode") or "vps")
    mrow = tk.Frame(adv, bg=THEME["card"])
    mrow.pack(fill="x", padx=12, pady=(0, 4))

    def _pick_px_mode(k):
        ok, msg = set_proxy_mode(k)
        if not ok:
            messagebox.showinfo("Proxy", msg)
    for _k, _lab in (("vps", "Mi proxy"), ("sistema", "Usar proxy del sistema"),
                     ("ninguno", "Sin proxy")):
        tk.Radiobutton(mrow, text=_lab, value=_k, variable=_widgets["px_mode"],
                       command=lambda k=_k: _pick_px_mode(k),
                       font=(FONT, 10), bg=THEME["card"], fg=THEME["text"],
                       activebackground=THEME["card"], selectcolor="#FFFFFF", bd=0,
                       highlightthickness=S(2), highlightbackground=THEME["card"],
                       highlightcolor=THEME["blue"]).pack(side="left", padx=(0, 12))
    grid = tk.Frame(adv, bg=THEME["card"])
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
    prow = tk.Frame(adv, bg=THEME["card"])
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
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
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
    tree.column("skill", width=S(150))
    tree.column("descripcion", width=S(420))
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
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
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
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(4, 2))
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
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    _build_api_connections(tab5)
    tk.Label(tab5, text="Todas las claves", font=SECTION_FONT, bg=THEME["bg"],
             fg=THEME["text"]).pack(anchor="w", padx=20, pady=(10, 0))
    tree = ttk.Treeview(tab5, columns=("api", "clave"), show="headings", height=6)
    tree.heading("api", text="API")
    tree.heading("clave", text="Clave")
    tree.column("api", width=S(170))
    tree.column("clave", width=S(420))
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

    # ================= pagina Modelos
    _build_models_page(pages["modelos"])

    # ================= pagina Tareas
    tabt = pages["tareas"]
    tk.Label(tabt, text="Tareas", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tabt, text="Cada tarea se revisa sola al terminar. Si falta algo, Growi lo "
             "corrige hasta 3 veces; si aun asi no queda, te pide que decidas tú.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    _widgets["tasks_summary"] = tk.Label(tabt, text="", font=(FONT, 11, "bold"),
                                         bg=THEME["bg"], fg=THEME["text"])
    _widgets["tasks_summary"].pack(anchor="w", padx=20, pady=(0, 6))
    _build_spend_card(tabt)
    _widgets["approvals_box"] = tk.Frame(tabt, bg=THEME["card"])
    tree = ttk.Treeview(tabt, columns=("tarea", "estado", "motor", "ronda", "tiempo", "tokens",
                                       "costo", "revision"),
                        show="headings", height=9, selectmode="browse")
    for _col, _txt, _w, _st in (("tarea", "Tarea", 145, False), ("estado", "Estado", 95, False),
                                ("motor", "Motor / modelo", 175, False), ("ronda", "Ronda", 58, False),
                                ("tiempo", "Tiempo", 62, False),
                                ("tokens", "Tokens ent. / sal.", 125, False),
                                ("costo", "Costo", 95, False), ("revision", "Revisión", 140, True)):
        tree.heading(_col, text=_txt, anchor="w")
        tree.column(_col, width=S(_w), minwidth=S(40), stretch=_st, anchor="w")
    tree.tag_configure("aprobada", foreground=THEME["green_text"])
    tree.tag_configure("fallida", foreground=THEME["red"])
    tree.tag_configure("necesita_decision", foreground=THEME["orange_text"])
    tree.tag_configure("esperando_aprobacion", foreground=THEME["orange_text"])
    tree.tag_configure("en_curso", foreground=THEME["blue"])
    tree.tag_configure("revisando", foreground=THEME["blue"])
    tree.tag_configure("esperando_reintento", foreground=THEME["orange_text"])
    tree.bind("<<TreeviewSelect>>", _show_task_detail)
    tree.pack(fill="x", padx=20, pady=4)
    _widgets["tasks_tree"] = tree
    # Fila viva: la de la tarea en curso se actualiza cada ~5 s desde
    # runner-live.json (lo que el runner va leyendo del motor).
    _widgets["live_line"] = tk.Label(tabt, text="", font=(FONT, 9), bg=THEME["bg"],
                                     fg=THEME["muted"], wraplength=S(640), justify="left")
    _widgets["live_line"].pack(anchor="w", padx=20, pady=(0, 4))
    _build_live_card(tabt)
    det = tk.Frame(tabt, bg=THEME["card"])
    det.pack(fill="x", padx=20, pady=(4, 8))
    tk.Label(det, text="Detalle", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    _widgets["tasks_detail"] = tk.Label(det, text="", font=(FONT, 9), bg=THEME["card"],
                                        fg=THEME["text"], wraplength=S(640), justify="left",
                                        anchor="w")
    _widgets["tasks_detail"].pack(fill="x", padx=16, pady=(0, 6))
    det_btns = tk.Frame(det, bg=THEME["card"])
    det_btns.pack(anchor="w", padx=16, pady=(0, 12))
    ttk.Button(det_btns, text="Abrir resultados",
               command=lambda: open_folder(RESULTS)).pack(side="left", padx=(0, 8))
    ttk.Button(det_btns, text="Volver a la cola", command=_requeue_ui).pack(side="left")
    ask = tk.Frame(tabt, bg=THEME["card"])
    ask.pack(fill="x", padx=20, pady=8)
    tk.Label(ask, text="Pedirle algo", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(ask, text="Escribe la tarea y elige el motor. Claude hace el trabajo pesado; "
             "Hermes 3 corre en local, gratis, para lo rápido.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
             wraplength=S(560), justify="left").pack(anchor="w", padx=16, pady=(0, 6))
    _widgets["ask_text"] = tk.Text(ask, height=3, font=(FONT, 10), bg="#FFFFFF",
                                   fg=THEME["text"], insertbackground=THEME["text"],
                                   borderwidth=0, highlightthickness=0)
    _widgets["ask_text"].pack(fill="x", padx=16, pady=4)
    tk.Label(ask, text="Para darla por buena (opcional, una frase por línea): p. ej. "
             "\"el archivo notas.txt existe y tiene más de 20 líneas\"",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"],
             wraplength=S(560), justify="left").pack(anchor="w", padx=16, pady=(4, 0))
    _widgets["ask_criterios"] = tk.Text(ask, height=2, font=(FONT, 10), bg="#FFFFFF",
                                        fg=THEME["text"], insertbackground=THEME["text"],
                                        borderwidth=0, highlightthickness=0)
    _widgets["ask_criterios"].pack(fill="x", padx=16, pady=4)
    arow = tk.Frame(ask, bg=THEME["card"])
    arow.pack(fill="x", padx=16, pady=(0, 12))
    def _engines_open():
        # Al abrir el desplegable: pedirle al runner la lista de modelos
        # instalados (accion list), como mucho cada 30 s.
        if time.time() - _mdl["last_list_ask"] > 30:
            request_models_list()
        _refresh_engine_widgets()

    _widgets["ask_engine"] = ttk.Combobox(arow, width=30, font=(FONT, 10),
                                          state="readonly", postcommand=_engines_open,
                                          values=list(_ASK_ENGINES))
    _widgets["ask_engine"].set(_default_engine_label(engine_choices()))
    _widgets["ask_engine"].pack(side="left", padx=(0, 8))
    ttk.Button(arow, text="Enviar", style="Accent.TButton",
               command=_send_ask).pack(side="left")
    _widgets["ask_status"] = tk.Label(ask, text="", font=(FONT, 9),
                                      bg=THEME["card"], fg=THEME["green_text"])
    _widgets["ask_status"].pack(anchor="w", padx=16, pady=(0, 12))

    # ================= pagina Recursos
    _build_resources_page(pages["recursos"])

    # ================= pagina Ajustes (piloto CustomTkinter; si no, la clasica)
    _build_ajustes(pages["ajustes"])


    # ================= pagina Registro
    tab_reg = pages["registro"]
    tk.Label(tab_reg, text="Registro", font=(FONT, 22, "bold"),
             bg=THEME["bg"], fg=THEME["text"]).pack(anchor="w", padx=20, pady=(18, 2))
    tk.Label(tab_reg, text="Todo lo que la app ha hecho, en orden.",
             font=(FONT, 11), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=S(600), justify="left").pack(anchor="w", padx=20, pady=(0, 10))
    log_box = tk.Frame(tab_reg, bg=THEME["card"])
    log_box.pack(fill="both", expand=True, padx=20, pady=(4, 16))
    tk.Label(log_box, text="Lo más reciente, abajo", font=SECTION_FONT,
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=16, pady=(12, 2))
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

    def _confirm_quit():
        if messagebox.askyesno("Salir de Growi Bridge",
                               "¿Salir del todo? Se paran el puente y el runner, y "
                               "Growi deja de poder mandarte tareas.",
                               icon="warning", default="no"):
            quit_app()

    def _copy(text):
        root.clipboard_clear()
        root.clipboard_append(text)
        log(f"copiado: {text}")

    def C(cid, label, keys, fn, chip=None, danger=False, more=None):
        return {"id": cid, "label": label, "keys": keys, "fn": fn, "chip": chip,
                "danger": danger, "more": more or []}

    _PALETTE_CMDS.clear()
    _page_alias = {
        "estado": "inicio servicios puente runner proxy encender",
        "carpetas": "carpetas directorios folders permisos rutas",
        "skills": "habilidades skills claude",
        "pantalla": "compartir pantalla captura screen",
        "apis": "claves api keys tokens conexiones",
        "modelos": "modelos ia llm ollama local hermes quien responde",
        "tareas": "tareas cola trabajos encargos pedidos",
        "ajustes": "ajustes configuracion opciones preferencias",
        "registro": "registro log historial actividad",
        "recursos": "recursos cpu ram gpu vram disco memoria procesos monitor cerrar matar",
    }
    for _i, (_n, _l) in enumerate((("estado", "Estado"), ("carpetas", "Carpetas"),
                                   ("skills", "Skills"), ("pantalla", "Pantalla"),
                                   ("apis", "APIs"), ("modelos", "Modelos"),
                                   ("tareas", "Tareas"), ("ajustes", "Ajustes"),
                                   ("registro", "Registro")), start=1):
        _PALETTE_CMDS.append(C(f"ir_{_n}", f"Ir a {_l}", "ir pagina " + _page_alias[_n],
                               lambda n=_n: (show_window(), _show_page(n)),
                               chip=f"Ctrl+{_i}"))
        root.bind_all(f"<Control-Key-{_i}>", lambda _e, n=_n: _show_page(n))
    # Recursos va con Ctrl+0 (Ctrl+1..9 se quedan como estaban).
    _PALETTE_CMDS.append(C("ir_recursos", "Ir a Recursos", "ir pagina " + _page_alias["recursos"],
                           lambda: (show_window(), _show_page("recursos")), chip="Ctrl+0"))
    root.bind_all("<Control-Key-0>", lambda _e: _show_page("recursos"))
    _PALETTE_CMDS += [
        C("pedir", "Pedirle algo a Claude", "pedir preguntar tarea encargo claude ia escribir",
          lambda: (show_window(), _show_page("tareas"), _widgets["ask_text"].focus_set())),
        C("power", "Encender o apagar todo", "power todo encender apagar boton grande",
          on_power_click),
        C("pc_check", "Comprobar mi PC", "comprobar pc gpu vram memoria modelos tarjeta",
          lambda: (_show_page("modelos"), start_pc_check())),
        C("mdl_list", "Actualizar la lista de modelos", "modelos ollama lista instalados refrescar",
          lambda: (_show_page("modelos"), request_models_list(force=True))),
        C("bridge", "Encender o apagar el puente", "puente bridge servidor",
          lambda: _sw_click("bridge_sw"),
          more=[("Encender el puente", start_bridge), ("Apagar el puente", stop_bridge, True)]),
        C("runner", "Encender o apagar el runner", "runner ejecutor tareas",
          lambda: _sw_click("runner_sw"),
          more=[("Encender el runner", start_runner), ("Apagar el runner", stop_runner, True)]),
        C("proxy", "Encender o apagar el proxy", "proxy red internet salida",
          lambda: _sw_click("proxy_sw"),
          more=[("Ir a la configuración del proxy", lambda: _show_page("estado"))]),
        C("mascota", "Mostrar u ocultar la mascota", "mascota growi personaje", toggle_mascot,
          more=[("Escribirle a Growi", open_prompt_box)]),
        C("aprobar", "Ver tareas que esperan tu aprobación", "aprobar aprobacion permisos plan",
          lambda: _show_page("tareas")),
        C("reencolar", "Volver a encolar la tarea elegida", "reintentar repetir encolar cola corte",
          lambda: (_show_page("tareas"), _requeue_ui())),
        C("inbox", "Abrir el Inbox", "abrir inbox carpeta entrada", lambda: open_folder(INBOX),
          more=[("Copiar la ruta del Inbox", lambda: _copy(str(INBOX)))]),
        C("outbox", "Abrir el Outbox", "abrir outbox carpeta salida", lambda: open_folder(OUTBOX),
          more=[("Copiar la ruta del Outbox", lambda: _copy(str(OUTBOX)))]),
        C("update", "Buscar actualizaciones", "actualizar update version nueva", check_updates_ui),
        C("ventana", "Mostrar u ocultar la ventana", "ventana mostrar ocultar minimizar",
          toggle_window, chip="Ctrl+Alt+G"),
        C("cerrar_modo", "Elegir qué hace la X al cerrar", "cerrar x minimizar bandeja salir ajuste",
          lambda: _show_page("ajustes")),
        C("parar", "Parar la tarea en curso", "parar detener stop tarea motor matar",
          _on_stop_click, danger=True),
        C("apagar_pc", "Apagar el PC", "apagar pc shutdown equipo ordenador",
          lambda: _pc_confirm("shutdown"), danger=True,
          more=[("Cancelar un apagado pendiente", pc_abort)]),
        C("reiniciar_pc", "Reiniciar el PC", "reiniciar pc restart equipo ordenador",
          lambda: _pc_confirm("restart"), danger=True,
          more=[("Cancelar un reinicio pendiente", pc_abort)]),
        C("salir", "Salir de Growi Bridge", "salir cerrar quitar terminar exit",
          _confirm_quit, danger=True),
        C("disponibilidad", "Volver a comprobar la disponibilidad",
          "mapa disponibilidad claude chatgpt gemini ollama internet comprobar venezuela",
          lambda: (show_window(), _show_page("estado"), _recheck_ui())),
        C("probar_proxy", "Probar el proxy", "proxy probar conectar vps eeuu salida",
          lambda: (show_window(), _show_page("estado"),
                   proxy_test_ui(_widgets["px_test_btn"], _widgets["px_result"]))),
        C("gasto", "Ver el gasto", "gasto dinero costo cuota max equivalente local",
          lambda: _open_ctx(("gasto",))),
        C("exportar", "Exportar mis conversaciones", "exportar respaldo copia conversaciones",
          export_conversations),
        C("inicial", "Volver a hacer la configuración inicial",
          "configuracion inicial bienvenida asistente pasos onboarding", open_onboarding),
    ]
    root.bind_all("<Control-k>", _on_ctrl_k)
    root.bind_all("<Control-K>", _on_ctrl_k)

    _refresh_engine_widgets()
    _show_page("estado")
    # Alto minimo = lo que pide la barra lateral entera (cabecera, las 10
    # secciones, Buscar acciones y el pie): con 560 fijo, Registro y Buscar
    # acciones quedaban tapados al achicar la ventana.
    root.update_idletasks()

    def _sidebar_need():
        root.update_idletasks()
        return sum(w.winfo_reqheight() for w in (head, nav, krow, foot)) + S(16 + 8 + 16 + 4 + 28)

    need = _sidebar_need()
    # Pantalla baja (p. ej. 150 % en 1080 px): las filas de navegacion se
    # compactan para que las 10 secciones quepan sin cortarse (barra de
    # titulo y de tareas incluidas). A 100 % no cambia nada.
    if need > sh - 80 - S(60):
        for _b in _nav_btns.values():
            _b.pack_configure(ipady=0)
            _b.master.pack_configure(pady=0)
        need = _sidebar_need()
    root.minsize(min(S(820), sw - 40), min(max(S(560), need), sh - 80))
    return root

def show_error_dialog(summary, details):
    """Muestra una ventana con el error y el motivo, y un botón para copiarlo.

    Se usa cuando algo falla (por ejemplo, al arrancar la app): en vez de
    cerrarse en silencio, Growi Bridge explica qué pasó y deja copiar el
    error completo para pasárselo a quien lo arregla. Crea su propia ventana,
    así funciona aunque la ventana principal no haya llegado a abrirse.
    """
    if not TK_OK:
        print(f"ERROR: {summary}\n{details}")
        return
    try:
        dlg = tk.Tk()
    except Exception:
        print(f"ERROR: {summary}\n{details}")
        return
    try:
        dlg.iconbitmap(default=str(ICO))
    except Exception as e:
        log(f"icono: el dialogo de error no pudo cargar {ICO.name} ({type(e).__name__}: {e})")
    dlg.title("Growi Bridge — Error")
    dlg.geometry(f"{S(580)}x{S(440)}")
    dlg.minsize(S(480), S(360))
    dlg.configure(bg="#FFFFFF")
    try:
        dlg.attributes("-topmost", True)
    except Exception:
        pass
    # Centrar en la pantalla.
    try:
        dlg.update_idletasks()
        sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
        x, y = (sw - S(580)) // 2, (sh - S(440)) // 2
        dlg.geometry(f"{S(580)}x{S(440)}+{x}+{y}")
    except Exception:
        pass

    head = tk.Label(dlg, text="Hubo un error", font=("Segoe UI", 18, "bold"),
                    bg="#FFFFFF", fg="#1D1D1F", anchor="w")
    head.pack(fill="x", padx=20, pady=(18, 2))
    sub = tk.Label(dlg, text=summary, font=("Segoe UI", 11),
                   bg="#FFFFFF", fg="#3A3A3C", anchor="w", justify="left",
                   wraplength=S(540))
    sub.pack(fill="x", padx=20, pady=(0, 12))

    frame = tk.Frame(dlg, bg="#FFFFFF")
    frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))
    scroll = tk.Scrollbar(frame)
    scroll.pack(side="right", fill="y")
    txt = tk.Text(frame, font=("Consolas", 10), bg="#F5F5F7", fg="#1D1D1F",
                  relief="flat", padx=10, pady=10, wrap="none",
                  yscrollcommand=scroll.set)
    txt.pack(side="left", fill="both", expand=True)
    scroll.config(command=txt.yview)
    txt.insert("1.0", details)
    txt.config(state="disabled")

    btns = tk.Frame(dlg, bg="#FFFFFF")
    btns.pack(fill="x", padx=20, pady=(0, 18))
    copy_btn = tk.Button(btns, text="Copiar error", font=("Segoe UI", 11, "bold"),
                         bg="#0066CC", fg="#FFFFFF", activebackground="#0055AA",
                         activeforeground="#FFFFFF", relief="flat",
                         padx=16, pady=8, cursor="hand2")
    copy_btn.pack(side="left")

    def _copy():
        try:
            dlg.clipboard_clear()
            dlg.clipboard_append(details)
            dlg.update()
        except Exception:
            pass
        copy_btn.config(text="Copiado ✓")
        dlg.after(2000, lambda: copy_btn.config(text="Copiar error"))

    copy_btn.config(command=_copy)
    close_btn = tk.Button(btns, text="Cerrar", font=("Segoe UI", 11),
                          bg="#E8E8ED", fg="#1D1D1F", activebackground="#D8D8DD",
                          relief="flat", padx=16, pady=8, cursor="hand2",
                          command=dlg.destroy)
    close_btn.pack(side="left", padx=(10, 0))
    dlg.mainloop()


# Un AppUserModelID por carril: cada carril tiene su boton en la barra de
# tareas. El ID de antes ("leandrogzn98-hash.GrowiBridge", sin carril) ya no
# se usa: Windows le dejo pegada la pluma de Tk a su boton y no la suelta
# mientras quede viva una ventana con ese ID (los dos carriles se turnan, asi
# que el boton nunca se cerraba). Ver share/outbox/ESTADO-ICONO-BARRA.md.
APP_USER_MODEL_ID = "leandrogzn98-hash.GrowiBridge.Carril" + LANE.upper()
_instance_mutex = None


def _set_app_user_model_id():
    """Para que Windows agrupe la ventana bajo Growi y no bajo pythonw.exe.
    Va antes de crear cualquier ventana (incluido el aviso de doble copia)."""
    try:
        import ctypes
        hr = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        if hr != 0:
            log(f"icono: SetCurrentProcessExplicitAppUserModelID devolvio 0x{hr & 0xffffffff:08x}")
    except Exception as e:
        log(f"icono: no se pudo fijar el AppUserModelID ({e})")


def _set_taskbar_props(win):
    """Propiedades de la ventana para la barra de tareas (IPropertyStore):
    el mismo AppUserModelID, el icono sacado de growi.ico (no del de Tk) y
    el nombre «Growi Bridge» en vez de «Python». Si falla, queda en el log."""
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort),
                        ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]

        class _PKEY(ctypes.Structure):
            _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_ulong)]

        class _PROPVARIANT(ctypes.Structure):
            _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort),
                        ("r3", ctypes.c_ushort), ("p", ctypes.c_void_p), ("p2", ctypes.c_void_p)]

        def guid(text):
            u = uuid.UUID(text)
            return _GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))

        win.update_idletasks()
        user32 = ctypes.windll.user32
        user32.GetAncestor.restype = wintypes.HWND
        hwnd = user32.GetAncestor(win.winfo_id(), 2) or win.winfo_id()  # GA_ROOT
        pyw = Path(sys.executable).with_name("pythonw.exe")
        exe = pyw if pyw.is_file() else Path(sys.executable)
        name = "Growi Bridge" + (" — carril B" if LANE == "b" else "")
        values = [(5, APP_USER_MODEL_ID),                            # AppUserModel.ID
                  (2, f'"{exe}" "{APP_DIR / "growi-bridge.py"}"'),   # RelaunchCommand
                  (3, f"{ICO},0"),                                   # RelaunchIconResource
                  (4, name)]                                         # RelaunchDisplayNameResource
        shell32 = ctypes.windll.shell32
        shell32.SHGetPropertyStoreForWindow.argtypes = [
            wintypes.HWND, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
        store = ctypes.c_void_p()
        hr = shell32.SHGetPropertyStoreForWindow(
            hwnd, ctypes.byref(guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")), ctypes.byref(store))
        if hr != 0 or not store:
            raise OSError(f"SHGetPropertyStoreForWindow 0x{hr & 0xffffffff:08x}")
        vtbl = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0],
                           ctypes.POINTER(ctypes.c_void_p))
        set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PKEY),
                                       ctypes.POINTER(_PROPVARIANT))(vtbl[6])
        commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[7])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        keep = []
        try:
            for pid, text in values:
                buf = ctypes.create_unicode_buffer(text)
                keep.append(buf)
                pv = _PROPVARIANT(vt=31, p=ctypes.cast(buf, ctypes.c_void_p))  # VT_LPWSTR
                hr = set_value(store, ctypes.byref(_PKEY(guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), pid)),
                               ctypes.byref(pv))
                if hr != 0:
                    raise OSError(f"SetValue({pid}) 0x{hr & 0xffffffff:08x}")
            commit(store)
        finally:
            release(store)
    except Exception as e:
        log(f"icono: no se pudieron fijar las propiedades de la barra de tareas ({type(e).__name__}: {e})")


def _single_instance_ok():
    """Mutex de Windows: True si somos la unica instancia. Si ya hay otra
    viva devuelve False y no se toca nada (ni la otra, ni la cola)."""
    global _instance_mutex
    try:
        import ctypes
        name = os.environ.get("GROWI_BRIDGE_MUTEX") or (
            "Local\\GrowiBridgeInstanciaUnica" + ("-carrilB" if LANE == "b" else ""))
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = ctypes.c_void_p
        h = k32.CreateMutexW(None, False, name)
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return False
        _instance_mutex = h
    except Exception as e:
        log(f"instancia unica: no se pudo comprobar ({e})")
    return True


def main():
    _set_app_user_model_id()
    if not _single_instance_ok():
        log("Growi Bridge ya esta corriendo: esta copia se cierra sin tocar nada")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Growi Bridge ya está corriendo.",
                                             "Growi Bridge", 0x40)
        except Exception:
            pass
        return 0
    if not TK_OK:
        print("ERROR: tkinter no esta disponible en este Python.")
        print("Reinstala Python marcando la opcion Tcl/Tk, o corre los programas por separado.")
        return 2
    _dpi_awareness()
    state["admin"] = is_admin()
    state["proxy_configured"] = bool(proxy_config().get("password"))
    state["proxy_on"] = "HTTPS_PROXY" in os.environ
    settings = load_settings()
    state["mascot"] = bool(settings.get("mascot", False)) and LANE == "a"  # B: sin mascota
    state["keep_awake"] = bool(settings.get("keep_awake", True))
    state["auto_update"] = bool(settings.get("auto_update", False))
    state["autostart"] = autostart_enabled()
    if settings.get("guardrail") not in ("siempre", "delicado", "nunca"):
        settings["guardrail"] = "siempre"
        save_settings(settings)

    def _uncaught(exc_type, exc_value, exc_tb):
        # Red de seguridad: si algo falla fuera del arranque (por ejemplo, en
        # un callback de la ventana), mostrar el diálogo en vez de morir en
        # silencio. No se dispara para KeyboardInterrupt.
        if exc_type is KeyboardInterrupt:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        err = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log(f"error no controlado: {err}")
        except Exception:
            pass
        try:
            show_error_dialog(
                "Growi Bridge encontró un error mientras trabajaba. Este es el motivo:",
                err.strip())
        except Exception:
            pass

    sys.excepthook = _uncaught
    _theme_init()

    try:
        root = build_gui()
    except Exception:
        err = traceback.format_exc()
        traceback.print_exc()
        log(f"no se pudo crear la ventana: {err}")
        show_error_dialog(
            "Growi Bridge no pudo arrancar. Este es el motivo:",
            err.strip())
        return 2
    global _tray_icon
    _tray_icon = build_tray()
    log(f"Growi Bridge v{VERSION} arrancado (carril {LANE.upper()}, puerto {BRIDGE_PORT}). "
        f"Administrador: {'sí' if state['admin'] else 'no'}.")
    set_power(True)
    # Lista de modelos instalados (accion list del runner) para la pestana
    # Modelos, el contador y el desplegable de Tareas.
    if LANE == "a":  # el carril B no toca modelos locales
        root.after(2500, request_models_list)
    if state["mascot"]:
        try:
            show_mascot()
        except Exception as e:
            log(f"mascota: no se pudo mostrar ({e})")
    # Atajo global Ctrl+Alt+G para mostrar/ocultar la ventana (estilo Raycast).
    # Solo el carril A: dos copias con el mismo atajo se pisarian.
    try:
        if LANE == "b":
            raise RuntimeError("carril B")
        import keyboard
        keyboard.add_hotkey("ctrl+alt+g", lambda: _root.after(0, toggle_window))
        log("atajo global Ctrl+Alt+G activo")
    except Exception as e:
        log(f"atajo global no disponible ({type(e).__name__})")
    if LANE == "a":  # el carril B no se actualiza solo: su codigo lo mueve la VM a mano
        threading.Thread(target=_auto_update_check, daemon=True).start()
        threading.Thread(target=_auto_update_loop, daemon=True).start()
    # Venezuela primero: mapa de disponibilidad (al arrancar y cada X min)
    # y gasto (cada 5 min); la configuracion inicial solo la primera vez.
    threading.Thread(target=_availability_loop, daemon=True).start()
    threading.Thread(target=_spend_loop, daemon=True).start()
    if LANE == "a":  # el carril B es una copia de fondo: sin asistente inicial
        root.after(400, maybe_onboarding)
    root.after(1000, _tick)
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
