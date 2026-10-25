#!/usr/bin/env python3
"""Growi Bridge v2.0 — puente + runner + proxy + pantalla + mascota en uno (Windows).

Un solo proceso, una sola ventana con pestanas, un solo icono en la bandeja
(la foto de Growi). Reemplaza al servidor viejo (pc-server.py) y al runner.

Pestanas:
  Estado    — boton grande de encendido, estado de puente/runner/proxy,
              indicador de sincronizacion (que se descarga/carga), registro.
  Carpetas  — que carpetas puede ver Claude Code (Growi tambien las puede
              modificar). Por defecto: el Inbox del puente + tu carpeta
              principal (C:\\Users\\forte).
  Skills    — las skills instaladas de Claude Code (~/.claude/skills/).
  Pantalla  — compartir pantalla con Growi (fotogramas comprimidos, solo
              cuando tu lo activas; Growi mira un fotograma cuando hace falta).

Extras:
  - Mascota: Growi en la esquina inferior derecha; clic para saludar y
    escribirle un mensaje rapido (llega a Growi por el puente).
  - Proxy: boton para encender/apagar el proxy (host/puerto/usuario/clave
    configurables; cada quien usa los suyos).
  - Actualizaciones: busca nuevas versiones en GitHub y se actualiza solo.
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
import time
import traceback
import urllib.request
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = "2.1"
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
PROXY_FILE = APP_DIR / "proxy.json"
FOLDERS_FILE = APP_DIR / "folders.json"
SETTINGS_FILE = APP_DIR / "settings.json"
BRIDGE_PORT = 8787
HOME_DIR = Path.home()

# Tema v2.1 (ver DESIGN.md): consola nocturna, texto crema, un solo acento.
FONT = "Segoe UI"
THEME = {
    "bg": "#0B1B2B", "card": "#12283C", "field": "#0A1622",
    "text": "#F5F1E8", "muted": "#9AB0C2", "line": "#1E3A52",
    "green": "#2FD9A6", "orange": "#FA5102", "red": "#E5484D",
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
    "sharing": False, "last_frame": "",
    "mascot": False,
    "update_available": "", "update_checked": False,
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


# ---------------------------------------------------------------- carpetas
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
def _version_tuple(v):
    parts = []
    for p in str(v).strip().lstrip("v").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_update_available():
    """Compara con VERSION en GitHub (raw). Devuelve la version nueva o ''."""
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/VERSION"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrowiBridge"})
        with urllib.request.urlopen(req, timeout=15) as r:
            remote = r.read().decode("utf-8", errors="replace").strip()
        if remote and _version_tuple(remote) > _version_tuple(VERSION):
            return remote
    except Exception as e:
        log(f"actualizaciones: no se pudo comprobar ({type(e).__name__})")
    return ""


def download_update(version):
    """Baja growi-bridge.py nuevo y deja el actualizador listo. True/False."""
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/growi-bridge.py"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrowiBridge"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if b"Growi Bridge" not in data[:2000] or len(data) < 10000:
            return False
        (APP_DIR / "growi-bridge.py.new").write_bytes(data)
        updater = APP_DIR / "actualizar.bat"
        updater.write_text(
            "@echo off\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            "move /y \"growi-bridge.py.new\" \"growi-bridge.py\"\r\n"
            "start /b pythonw growi-bridge.py\r\n"
            "del \"%~f0\"\r\n", encoding="utf-8")
        return True
    except Exception as e:
        log(f"actualizaciones: fallo la descarga ({e})")
        return False

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
            model not in ALLOWED_MODELS and not model.startswith("claude-")
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


def run_task(task):
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
def _capture_frame():
    """Un fotograma comprimido a share/outbox/screens/latest.jpg."""
    try:
        from PIL import ImageGrab
    except ImportError:
        return None
    SCREENS.mkdir(parents=True, exist_ok=True)
    try:
        img = ImageGrab.grab()
    except Exception as e:
        log(f"pantalla: no se pudo capturar ({e})")
        return None
    if img.width > 1280:
        img = img.resize((1280, int(img.height * 1280 / img.width)))
    path = SCREENS / "latest.jpg"
    img.convert("RGB").save(path, "JPEG", quality=45)
    info = {"at": _now_iso(), "size": path.stat().st_size,
            "w": img.width, "h": img.height}
    (SCREENS / "status.json").write_text(json.dumps(info), encoding="utf-8")
    state["last_frame"] = info["at"]
    return info


def screen_loop(stop_event, interval_s):
    log(f"pantalla: compartiendo (fotograma cada {interval_s}s, JPEG 45, max 1280px)")
    count = 0
    while not stop_event.is_set():
        info = _capture_frame()
        if info:
            count += 1
            if count % 6 == 1:
                log(f"pantalla: fotograma {count} ({info['size'] // 1024} KB)")
        stop_event.wait(interval_s)
    log("pantalla: compartiendo detenido")


def start_sharing(interval_s=10):
    global _share_stop, _share_thread
    if _share_thread and _share_thread.is_alive():
        return False
    _share_stop = threading.Event()
    _share_thread = threading.Thread(target=screen_loop, args=(_share_stop, interval_s), daemon=True)
    _share_thread.start()
    state["sharing"] = True
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
    c = _widgets.get("power_canvas")
    if c is None:
        return
    c.delete("all")
    on = state["power"]
    cx, cy, r = 85, 85, 62
    if on:
        ring = THEME["green"] if _pulse[0] else "#7DE8C3"
        c.create_oval(8, 8, 162, 162, outline=ring, width=3)
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=THEME["green"], outline="#25B98C", width=2)
        sym = THEME["bg"]
    else:
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#22384E", outline="#33475C", width=2)
        sym = "#5A7086"
    c.create_arc(cx - 26, cy - 26, cx + 26, cy + 26, start=300, extent=300,
                 style="arc", outline=sym, width=7)
    c.create_line(cx, cy - 34, cx, cy - 12, fill=sym, width=7, capstyle="round")


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
    dot, color = _dot(state["bridge"])
    w["bridge_dot"].config(text=dot, fg=color)
    w["bridge_text"].config(
        text=f"Puente — {state['bridge']}" + (f" (puerto {BRIDGE_PORT})" if state["bridge"] == "corriendo" else "")
        + (f" — {state['bridge_err']}" if state["bridge_err"] else ""))
    dot, color = _dot(state["runner"])
    w["runner_dot"].config(text=dot, fg=color)
    extra = f" — tareas: {state['tasks_done']}"
    if state["current"]:
        extra += f" · ahora: {state['current']}"
    if state["last_result"]:
        extra += f" · último: {state['last_result']}"
    w["runner_text"].config(text=f"Runner — {state['runner']}{extra}")
    cfg = proxy_config()
    dot, color = ("●", THEME["green"]) if state["proxy_on"] else ("●", "#5A7086")
    w["proxy_dot"].config(text=dot, fg=color)
    w["proxy_text"].config(
        text=f"Proxy — {'ENCENDIDO' if state['proxy_on'] else 'apagado'}"
        + (f" ({cfg['host']}:{cfg['port']})" if cfg["host"] else "")
        + ("" if state["proxy_configured"] else " — falta configurar"))
    w["proxy_btn"].config(text="Apagar proxy" if state["proxy_on"] else "Encender proxy")
    w["power_label"].config(
        text="Todo encendido" if state["power"] else "Todo apagado",
        fg=THEME["green"] if state["power"] else THEME["muted"])
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
        w["share_status"].config(
            text=f"Compartiendo pantalla · último fotograma: {state['last_frame'] or '—'}")
        w["share_btn"].config(text="Dejar de compartir pantalla")
    else:
        w["share_status"].config(text="Pantalla no compartida")
        w["share_btn"].config(text="Compartir pantalla")
    try:
        w["mascot_var"].set(state["mascot"])
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
    if _root is not None:
        try:
            _root.after(1000, _tick)
        except Exception:
            pass


def on_power_click():
    on = set_power(not state["power"])
    log(f"boton grande: {'todo ENCENDIDO' if on else 'todo APAGADO'}")


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
_mascot = {"win": None, "label": None, "frames": [], "animating": False,
           "drag": None, "bob": 0}


def _mascot_frames():
    if _mascot["frames"]:
        return _mascot["frames"]
    frames = []
    try:
        for p in sorted(MASCOT_DIR.glob("wave-*.png")):
            img = Image.open(p)
            frames.append(ImageTk.PhotoImage(img))
    except Exception:
        frames = []
    _mascot["frames"] = frames
    return frames


def _mascot_pos():
    sw = _root.winfo_screenwidth()
    sh = _root.winfo_screenheight()
    return sw - 180, sh - 200


def show_mascot():
    if _root is None or _mascot["win"] is not None:
        return
    if not TRAY_OK or not PHOTO.is_file():
        log("mascota: falta la foto (growi.png)")
        return
    win = tk.Toplevel(_root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    x, y = _mascot_pos()
    win.geometry(f"160x160+{x}+{y}")
    try:
        img = Image.open(PHOTO).resize((160, 160), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
    except Exception:
        win.destroy()
        return
    label = tk.Label(win, image=photo, bg=THEME["bg"], bd=0)
    label.image = photo
    label.pack()
    win._photo = photo
    _mascot["win"] = win
    _mascot["label"] = label

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
            win.geometry(f"160x160+{d[2] + dx}+{d[3] + dy}")

    def _release(e):
        d = _mascot["drag"]
        _mascot["drag"] = None
        if d and not d[4]:
            on_mascot_click()

    label.bind("<ButtonPress-1>", _press)
    label.bind("<B1-Motion>", _move)
    label.bind("<ButtonRelease-1>", _release)
    log("mascota: Growi está en la esquina inferior derecha")
    _mascot_bob()


def _mascot_bob():
    win = _mascot["win"]
    if win is None or _mascot["animating"]:
        return
    try:
        _mascot["bob"] = 1 - _mascot["bob"]
        y = win.winfo_y() + (-3 if _mascot["bob"] else 3)
        win.geometry(f"160x160+{win.winfo_x()}+{y}")
    except Exception:
        return
    try:
        _root.after(2500, _mascot_bob)
    except Exception:
        pass


def on_mascot_click():
    win = _mascot["win"]
    label = _mascot["label"]
    if win is None or label is None or _mascot["animating"]:
        return
    frames = _mascot_frames()
    if frames:
        _mascot["animating"] = True
        seq = frames * 2
        idx = [0]

        def _step():
            if idx[0] >= len(seq):
                label.config(image=win._photo)
                _mascot["animating"] = False
                return
            label.config(image=seq[idx[0]])
            idx[0] += 1
            _root.after(120, _step)
        _step()
    open_prompt_box()


def open_prompt_box():
    win = _mascot["win"]
    if win is None:
        return
    box = tk.Toplevel(_root)
    box.title("Escríbeme")
    box.attributes("-topmost", True)
    box.configure(bg=THEME["bg"])
    x = max(0, win.winfo_x() - 140)
    y = max(0, win.winfo_y() - 130)
    box.geometry(f"300x130+{x}+{y}")
    tk.Label(box, text="¡Hola! ¿Qué necesitas?",
             font=(FONT, 11, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack(pady=(10, 2))
    entry = tk.Entry(box, width=36, font=(FONT, 10), bg=THEME["field"],
                     fg=THEME["text"], insertbackground=THEME["text"], borderwidth=0)
    entry.pack(padx=10, pady=4)
    entry.focus_set()
    status = tk.Label(box, text="", font=(FONT, 9), fg=THEME["green"], bg=THEME["bg"])
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
    row.pack(pady=4)
    tk.Button(row, text="Enviar a Growi", command=_send,
              bg=THEME["green"], fg=THEME["bg"], borderwidth=0,
              font=(FONT, 10)).pack(side="left", padx=4)
    tk.Button(row, text="Cerrar", command=box.destroy,
              bg=THEME["card"], fg=THEME["text"], borderwidth=0,
              font=(FONT, 10)).pack(side="left", padx=4)


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
def build_gui():
    global _root
    root = tk.Tk()
    _root = root
    root.title("Growi Bridge")
    root.geometry("560x860")
    root.minsize(520, 720)
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
    style.configure("TNotebook", background=THEME["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=THEME["card"], foreground=THEME["muted"],
                    padding=(14, 8), font=(FONT, 10))
    style.map("TNotebook.Tab", background=[("selected", "#1B3A55")],
              foreground=[("selected", THEME["text"])])
    style.configure("TButton", background=THEME["card"], foreground=THEME["text"],
                    borderwidth=0, padding=(10, 6), font=(FONT, 10))
    style.map("TButton", background=[("active", "#1B3A55")])
    style.configure("Accent.TButton", background=THEME["green"], foreground=THEME["bg"])
    style.map("Accent.TButton", background=[("active", "#25B98C")])
    style.configure("TEntry", fieldbackground=THEME["field"], foreground=THEME["text"],
                    borderwidth=0, insertcolor=THEME["text"])
    style.configure("TCombobox", fieldbackground=THEME["field"], foreground=THEME["text"])
    style.configure("Treeview", background=THEME["card"], foreground=THEME["text"],
                    fieldbackground=THEME["card"], borderwidth=0, font=(FONT, 10))
    style.configure("Treeview.Heading", background=THEME["field"], foreground=THEME["muted"],
                    font=(FONT, 10, "bold"))
    style.configure("TCheckbutton", background=THEME["bg"], foreground=THEME["text"],
                    font=(FONT, 10))

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    # ---------------- pestana Estado
    tab = tk.Frame(nb, bg=THEME["bg"])
    nb.add(tab, text="  Estado  ")
    header = tk.Frame(tab, bg=THEME["card"], highlightbackground=THEME["line"],
                      highlightthickness=1)
    header.pack(fill="x", padx=12, pady=(12, 8))
    photo = None
    if TRAY_OK and HEADER_PHOTO.is_file():
        try:
            img = Image.open(HEADER_PHOTO).resize((96, 96), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            tk.Label(header, image=photo, bg=THEME["card"]).pack(
                side="left", padx=14, pady=12)
            header.image = photo
            root.iconphoto(True, photo)
        except Exception:
            pass
    tk.Label(header, text="Growi Bridge", font=(FONT, 20, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", pady=(12, 0))
    tk.Label(header, text="Puente · Runner · Proxy · Pantalla · Mascota",
             font=(FONT, 11), bg=THEME["card"], fg=THEME["muted"]).pack(anchor="w")
    _widgets["admin_text"] = tk.Label(header, text="", font=(FONT, 9),
                                      bg=THEME["card"], fg=THEME["muted"])
    _widgets["admin_text"].pack(anchor="w", pady=(0, 12))

    power = tk.Frame(tab, bg=THEME["bg"])
    power.pack(pady=6)
    canvas = tk.Canvas(power, width=170, height=170, bg=THEME["bg"],
                       highlightthickness=0)
    canvas.pack()
    canvas.bind("<Button-1>", lambda e: on_power_click())
    _widgets["power_canvas"] = canvas
    _widgets["power_label"] = tk.Label(power, text="Todo apagado",
                                       font=(FONT, 13, "bold"),
                                       bg=THEME["bg"], fg=THEME["muted"])
    _widgets["power_label"].pack()

    status = tk.Frame(tab, bg=THEME["card"], highlightbackground=THEME["line"],
                      highlightthickness=1)
    status.pack(fill="x", padx=12, pady=8)
    tk.Label(status, text="Estado", font=(FONT, 11, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(10, 2))
    for key, label in (("bridge", "Puente"), ("runner", "Runner"), ("proxy", "Proxy")):
        row = tk.Frame(status, bg=THEME["card"])
        row.pack(fill="x", padx=14, pady=5)
        dot = tk.Label(row, text="●", font=(FONT, 13), bg=THEME["card"])
        dot.pack(side="left", padx=(0, 8))
        tk.Label(row, text=label, font=(FONT, 10, "bold"),
                 bg=THEME["card"], fg=THEME["text"]).pack(side="left")
        txt = tk.Label(row, text="", font=(FONT, 10), bg=THEME["card"],
                       fg=THEME["muted"], anchor="w")
        txt.pack(side="left", padx=(6, 0))
        _widgets[f"{key}_dot"] = dot
        _widgets[f"{key}_text"] = txt
        sep = tk.Frame(status, bg=THEME["line"], height=1)
        sep.pack(fill="x", padx=14)
    sync = tk.Label(status, text="", font=(FONT, 10, "bold"), bg=THEME["card"],
                    fg=THEME["green"], anchor="w")
    sync.pack(fill="x", padx=14, pady=(8, 12))
    _widgets["sync_text"] = sync

    px = tk.Frame(tab, bg=THEME["card"], highlightbackground=THEME["line"],
                  highlightthickness=1)
    px.pack(fill="x", padx=12, pady=8)
    tk.Label(px, text="Proxy", font=(FONT, 11, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(10, 2))
    tk.Label(px, text="Cada quien usa el suyo. Encendido, Claude sale por el proxy.",
             font=(FONT, 9), bg=THEME["card"], fg=THEME["muted"]).pack(
        anchor="w", padx=14, pady=(0, 8))
    grid = tk.Frame(px, bg=THEME["card"])
    grid.pack(fill="x", padx=14)
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
    prow.pack(fill="x", padx=14, pady=(8, 12))
    ttk.Button(prow, text="Guardar", style="Accent.TButton",
               command=save_proxy_from_ui).pack(side="left", padx=(0, 8))
    _widgets["proxy_btn"] = ttk.Button(prow, text="Encender proxy", command=toggle_proxy)
    _widgets["proxy_btn"].pack(side="left")

    opts = tk.Frame(tab, bg=THEME["bg"])
    opts.pack(fill="x", padx=12, pady=2)
    mascot_var = tk.BooleanVar(value=state["mascot"])
    _widgets["mascot_var"] = mascot_var
    ttk.Checkbutton(opts, text="Mascota en la esquina inferior derecha",
                    variable=mascot_var, command=toggle_mascot,
                    style="TCheckbutton").pack(anchor="w")

    btns = tk.Frame(tab, bg=THEME["bg"])
    btns.pack(fill="x", padx=12, pady=8)
    ttk.Button(btns, text="Abrir Inbox",
               command=lambda: open_folder(INBOX)).grid(row=0, column=0, padx=2, pady=2)
    ttk.Button(btns, text="Abrir Outbox",
               command=lambda: open_folder(OUTBOX)).grid(row=0, column=1, padx=2, pady=2)
    ttk.Button(btns, text="Buscar actualizaciones",
               command=check_updates_ui).grid(row=0, column=2, padx=2, pady=2)
    ttk.Button(btns, text="Salir", command=quit_app).grid(row=0, column=3, padx=2, pady=2)
    _widgets["update_label"] = tk.Label(tab, text="", font=(FONT, 9),
                                        bg=THEME["bg"], fg=THEME["green"])
    _widgets["update_label"].pack(anchor="w", padx=14)
    _widgets["update_btn"] = ttk.Button(tab, text="Actualizar ahora", state="disabled",
                                        command=do_update_ui)
    _widgets["update_btn"].pack(anchor="w", padx=12, pady=2)

    log_box = tk.Frame(tab, bg=THEME["card"], highlightbackground=THEME["line"],
                       highlightthickness=1)
    log_box.pack(fill="both", expand=True, padx=12, pady=(4, 12))
    tk.Label(log_box, text="Registro", font=(FONT, 11, "bold"),
             bg=THEME["card"], fg=THEME["text"]).pack(anchor="w", padx=14, pady=(10, 2))
    text = scrolledtext.ScrolledText(log_box, height=8, font=("Consolas", 9),
                                     bg=THEME["field"], fg="#9FD8B4",
                                     insertbackground=THEME["text"],
                                     state="disabled", borderwidth=0)
    text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    _widgets["log"] = text

    # ---------------- pestana Carpetas
    tab2 = tk.Frame(nb, bg=THEME["bg"])
    nb.add(tab2, text="  Carpetas  ")
    tk.Label(tab2, text="Carpetas que Claude Code puede ver",
             font=(FONT, 13, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack(
        anchor="w", padx=14, pady=(12, 2))
    tk.Label(tab2, text="Claude Code solo trabaja dentro de estas carpetas. "
             "Growi también puede modificar esta lista pidiéndole a Claude "
             "que edite folders.json.",
             font=(FONT, 10), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=500, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
    lb = tk.Listbox(tab2, height=10, font=(FONT, 10), bg=THEME["card"],
                    fg=THEME["text"], selectbackground=THEME["green"],
                    selectforeground=THEME["bg"], borderwidth=0,
                    highlightthickness=0)
    lb.pack(fill="both", expand=True, padx=14, pady=4)
    _widgets["folders_list"] = lb
    brow = tk.Frame(tab2, bg=THEME["bg"])
    brow.pack(fill="x", padx=14, pady=(4, 12))
    ttk.Button(brow, text="Añadir carpeta", command=add_folder_ui).pack(side="left", padx=2)
    ttk.Button(brow, text="Quitar seleccionada", command=remove_folder_ui).pack(side="left", padx=2)
    ttk.Button(brow, text="Restablecer", command=reset_folders_ui).pack(side="left", padx=2)
    refresh_folders_ui()

    # ---------------- pestana Skills
    tab3 = tk.Frame(nb, bg=THEME["bg"])
    nb.add(tab3, text="  Skills  ")
    tk.Label(tab3, text="Skills instaladas de Claude Code",
             font=(FONT, 13, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack(
        anchor="w", padx=14, pady=(12, 2))
    tk.Label(tab3, text=f"Carpeta: {HOME_DIR / '.claude' / 'skills'}",
             font=(FONT, 9), bg=THEME["bg"], fg=THEME["muted"]).pack(anchor="w", padx=14)
    _widgets["skills_count"] = tk.Label(tab3, text="", font=(FONT, 10),
                                        bg=THEME["bg"], fg=THEME["muted"])
    _widgets["skills_count"].pack(anchor="w", padx=14, pady=(4, 0))
    tree = ttk.Treeview(tab3, columns=("skill", "descripcion"), show="headings", height=14)
    tree.heading("skill", text="Skill")
    tree.heading("descripcion", text="Descripción")
    tree.column("skill", width=150)
    tree.column("descripcion", width=360)
    tree.pack(fill="both", expand=True, padx=14, pady=6)
    _widgets["skills_tree"] = tree
    ttk.Button(tab3, text="Actualizar lista", command=refresh_skills_ui).pack(
        anchor="w", padx=14, pady=(0, 12))
    refresh_skills_ui()

    # ---------------- pestana Pantalla
    tab4 = tk.Frame(nb, bg=THEME["bg"])
    nb.add(tab4, text="  Pantalla  ")
    tk.Label(tab4, text="Compartir pantalla con Growi",
             font=(FONT, 13, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack(
        anchor="w", padx=14, pady=(12, 2))
    tk.Label(tab4, text="Cuando lo activas, la app manda un fotograma comprimido "
             "(JPEG, max 1280px) cada pocos segundos al outbox, y Growi lo puede "
             "ver por el puente. Growi solo mira un fotograma cuando se lo pides "
             "o cuando hace falta para ayudarte: no es video en vivo y no gasta "
             "muchos tokens. Puedes pararlo cuando quieras.",
             font=(FONT, 10), bg=THEME["bg"], fg=THEME["muted"],
             wraplength=500, justify="left").pack(anchor="w", padx=14, pady=(0, 10))
    _widgets["share_btn"] = ttk.Button(tab4, text="Compartir pantalla",
                                       style="Accent.TButton",
                                       command=lambda: stop_sharing() if state["sharing"]
                                       else start_sharing(int(_widgets["share_interval"].get().split()[0])))
    _widgets["share_btn"].pack(anchor="w", padx=14, pady=4)
    irow = tk.Frame(tab4, bg=THEME["bg"])
    irow.pack(anchor="w", padx=14, pady=4)
    tk.Label(irow, text="Fotograma cada:", font=(FONT, 10), bg=THEME["bg"],
             fg=THEME["text"]).pack(side="left")
    _widgets["share_interval"] = ttk.Combobox(irow, values=["5 s", "10 s", "30 s"],
                                              width=6, state="readonly")
    _widgets["share_interval"].set("10 s")
    _widgets["share_interval"].pack(side="left", padx=6)
    _widgets["share_status"] = tk.Label(tab4, text="Pantalla no compartida",
                                        font=(FONT, 10, "bold"),
                                        bg=THEME["bg"], fg=THEME["green"])
    _widgets["share_status"].pack(anchor="w", padx=14, pady=8)
    return root


def main():
    if not TK_OK:
        print("ERROR: tkinter no esta disponible en este Python.")
        print("Reinstala Python marcando la opcion Tcl/Tk, o corre los programas por separado.")
        return 2
    state["admin"] = is_admin()
    state["proxy_configured"] = bool(proxy_config().get("password"))
    state["proxy_on"] = "HTTPS_PROXY" in os.environ
    settings = load_settings()
    state["mascot"] = bool(settings.get("mascot", False))
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
    threading.Thread(target=_auto_update_check, daemon=True).start()
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
