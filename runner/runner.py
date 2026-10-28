#!/usr/bin/env python3
"""Growi Runner v1.0 — corre Claude Code headless con las tareas que Growi manda por el puente.

Como funciona (webhook por archivos, sin exponer nada nuevo a internet):
  1. Growi sube <id>.task.json a share\\inbox\\runner-tasks\\ con un `put` directo
     del puente. Ese `put` ES el disparo: llega en segundos.
  2. Este programa lo detecta (sondeo cada 5 s), lo mueve a processing/ y corre:
       claude -p "<prompt>" --output-format json
     en la carpeta de trabajo indicada, sin ventana y sin que nadie intervenga.
  3. Escribe <id>.result.json en share\\outbox\\runner-results\\ y el puente lo
     devuelve a la VM en el siguiente sync (<= 2 min; Growi puede sondearlo antes).

Limites de seguridad (a proposito, angostos):
  - Solo ejecuta `claude -p ...`. NUNCA ejecuta shell directo con nada del task.
  - El cwd tiene que existir y estar dentro de share\\inbox.
  - Una tarea a la vez, con timeout (por defecto 30 min, max 120).
  - Las tareas solo llegan por el puente, que exige el secreto compartido.
  - Todo queda registrado: task en done/, resultado en outbox, log en runner.log.

Uso:
  - Probar en ventana visible:  doble clic a iniciar-runner.bat
  - Arranque automatico al iniciar sesion: doble clic a instalar-runner.bat
  - Parar: Ctrl+C en la ventana, o `schtasks /delete /tn GrowiRunner /f`
    (y cerrar el proceso pythonw si corre oculto).

Requisitos: Python 3 en el PATH y `claude` en el PATH (Claude Code con la
suscripcion Max de Leandro; hereda HTTPS_PROXY del usuario -> sale por el
proxy del VPS, sin Avast).
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

VERSION = "growi-runner/1.2"

HERE = Path(__file__).resolve().parent
# El runner vive en share\inbox\runner\ -> el share es dos niveles arriba.
SHARE = HERE.parent.parent
INBOX = SHARE / "inbox"
OUTBOX = SHARE / "outbox"
TASKS = INBOX / "runner-tasks"
PROCESSING = TASKS / "processing"
DONE = TASKS / "done"
RESULTS = OUTBOX / "runner-results"
LOG = HERE / "runner.log"
LIVE_FILE = OUTBOX / "runner-live.json"
STATUS_FILE = OUTBOX / "runner-status.json"


# Lanzamiento oculto (t-checkpoint-ronda-030 §6): pythonw no tiene consola, y
# claude.exe sin flags abriria una ventana negra que parpadea. Igual que la app:
# CREATE_NO_WINDOW (0x08000000) + STARTUPINFO SW_HIDE; nunca se reintenta visible.
OCULTO_TXT = "CREATE_NO_WINDOW (0x08000000) + STARTUPINFO SW_HIDE"


def _oculto():
    kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kw["startupinfo"] = si
    return kw


POLL_SECONDS = 5
HEARTBEAT_SECONDS = 60
# Sin una sola linea de stdout/stderr en este tiempo, el intento se da por
# colgado y se mata (arbol completo). Es inactividad, no duracion: el limite
# total sigue siendo timeout_min. Solo para pruebas: GROWI_NO_PROGRESS_S.
NO_PROGRESS_TIMEOUT_S = 300
NO_PROGRESS_TXT = "lanzamiento sin progreso en 5 min"
LIVE_SECONDS = 5
# Precio de lista ($ por millon de tokens) solo para el ESTIMADO en vivo; el
# costo que vale es el que Claude reporta al final (total_cost_usd). Calibrado
# el 25 oct 2026 contra el costo real de Claude Code. Modelo sin precio aqui
# -> el vivo dice 'sin precio' (no se inventa).
# (entrada, salida, lectura de cache, escritura de cache 1 h); 5 min = 1,25 x entrada.
PRICES = {"haiku": (0.10, 0.50, 0.01, 0.20), "sonnet": (2.0, 10.0, 0.10, 4.0),
          "opus": (4.0, 20.0, 0.20, 8.0)}
MAX_PROMPT_CHARS = 100_000
DEFAULT_TIMEOUT_MIN = 30
MAX_TIMEOUT_MIN = 120
MAX_RESULT_CHARS = 20_000
MAX_STDERR_CHARS = 2_000
ALLOWED_MODELS = {"sonnet", "opus", "haiku"}
SAFE_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def no_progress_s():
    try:
        v = int(os.environ.get("GROWI_NO_PROGRESS_S") or NO_PROGRESS_TIMEOUT_S)
        return v if v > 0 else NO_PROGRESS_TIMEOUT_S
    except ValueError:
        return NO_PROGRESS_TIMEOUT_S


def log(msg):
    line = f"{now_iso()} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def safe_id(task_id):
    return (
        isinstance(task_id, str)
        and 1 <= len(task_id) <= 80
        and all(c in SAFE_ID_CHARS for c in task_id)
        and ".." not in task_id
    )


def validate_task(data):
    """Devuelve (task_normalizada, error). La task es solo texto + parametros."""
    if not isinstance(data, dict):
        return None, "el task.json no es un objeto JSON"
    task_id = data.get("id")
    if not safe_id(task_id):
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
    try:
        inside = os.path.commonpath([str(cwd), str(INBOX.resolve())]) == str(
            INBOX.resolve()
        )
    except ValueError:
        inside = False
    if not inside:
        return None, f"cwd fuera del area permitida (share\\inbox): {cwd}"
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
        "acceptEdits",
        "plan",
        "default",
        "bypassPermissions",
    ):
        return None, f"permission_mode no permitido: {permission_mode}"
    session_id = data.get("session_id")
    if session_id is not None and not safe_id(session_id):
        return None, f"session_id invalido: {session_id}"
    try:
        timeout_min = int(data.get("timeout_min") or DEFAULT_TIMEOUT_MIN)
    except (TypeError, ValueError):
        return None, "timeout_min debe ser un numero"
    timeout_min = max(1, min(MAX_TIMEOUT_MIN, timeout_min))
    return {
        "id": task_id,
        "prompt": prompt,
        "cwd": str(cwd),
        "model": model,
        "allowed_tools": allowed_tools,
        "permission_mode": permission_mode,
        "session_id": session_id,
        "timeout_min": timeout_min,
    }, None


# ---- consumo en vivo (runner-live.json) y latido que no se congela
_LOCK = threading.RLock()
_LIVE = {"d": None, "t0": 0.0, "written": 0.0, "msgs": {}}
_CUR = {"task": None, "tasks_done": 0, "hb": 0.0, "act": 0.0}


def touch():
    """Hubo actividad del motor (una linea de stdout/stderr o un evento)."""
    _CUR["act"] = time.time()


def _kill_tree(proc):
    """Mata el intento entero: claude lanza node y este sus hijos. Con
    psutil, hijos primero y luego el padre; sin psutil, taskkill /T /F."""
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        try:
            parent = psutil.Process(proc.pid)
            kids = parent.children(recursive=True)
            for k in kids:
                try:
                    k.kill()
                except psutil.Error:
                    pass
            parent.kill()
            psutil.wait_procs(kids + [parent], timeout=10)
        except psutil.Error:
            pass
    else:
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15, **_oculto())
        except Exception:
            pass
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(10)
    except Exception:
        pass


def _wait_watch(proc, task, result):
    """Espera al proceso vigilando dos limites: inactividad (no_progress_s
    sin ninguna linea) y el total de la tarea (timeout_min). Devuelve el
    codigo de salida, o None si hubo que matarlo (result ya dice por que)."""
    deadline = time.time() + task["timeout_min"] * 60
    limit = no_progress_s()
    while True:
        try:
            return proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        now = time.time()
        idle = now - _CUR["act"]
        if idle >= limit:
            _kill_tree(proc)
            result["status"] = "error"
            result["error"] = NO_PROGRESS_TXT
            log(f"[{task['id']}] {NO_PROGRESS_TXT}: {idle:.0f} s sin una linea de salida "
                f"(limite {limit} s); se mato el arbol de procesos del pid {proc.pid}")
            return None
        if now >= deadline:
            _kill_tree(proc)
            result["status"] = "timeout"
            result["error"] = f"timeout de {task['timeout_min']} min"
            log(f"[{task['id']}] timeout de {task['timeout_min']} min; se mato el arbol de procesos del pid {proc.pid}")
            return None


def _stderr_reader(pipe, buf):
    """Lee stderr linea a linea: cada linea cuenta como actividad."""
    try:
        for raw in pipe:
            touch()
            buf.append(raw.decode("utf-8", "replace"))
    except (OSError, ValueError):
        pass


def _atomic_write(path, data):
    tmp = path.with_suffix(".tmp")
    try:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        for i in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:  # alguien lo esta leyendo en ese instante
                time.sleep(0.1 * (i + 1))
    except OSError:
        pass


def _usage_norm(us):
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
    out = {k: max(prev.get(k, 0), u.get(k, 0)) for k in ("input", "cache_read", "output")}
    total = max(prev["cache_5m"] + prev["cache_1h"], u["cache_5m"] + u["cache_1h"])
    src = u if u.get("_split") else prev if prev.get("_split") else None
    c1h = min(src["cache_1h"], total) if src else 0
    out.update(cache_1h=c1h, cache_5m=total - c1h, _split=bool(src))
    return out


def _estimate(model, u):
    fam = next((f for f in PRICES if f in str(model or "").lower()), None)
    if fam is None:
        return None
    pin, pout, pcr, p1h = (x / 1e6 for x in PRICES[fam])
    return (u["input"] * pin + u["output"] * pout + u["cache_read"] * pcr
            + u["cache_1h"] * p1h + u["cache_5m"] * pin * 1.25)


def live_start(task):
    with _LOCK:
        _LIVE.update(t0=time.time(), written=0.0, msgs={}, d={
            "task_id": task["id"], "raiz": task["id"], "motor": "claude", "modelo": task.get("model"),
            "modelo_real": None, "estado": "en curso", "started_at": now_iso(), "elapsed_s": 0,
            "tokens_in": 0, "tokens_out": 0, "cost_usd_estimado": None, "cost_usd_final": None,
            "ronda": 0, "tarea_padre": None, "dinero": "equiv", "modo_vivo": "esperando",
            "por_modelo": {}, "revision": None, "nota": None})
    live_write(force=True)


def live_msg(key, model, u):
    """Uso de un mensaje (el mismo mensaje puede llegar varias veces: se
    queda el mayor de cada campo) y totales recalculados."""
    with _LOCK:
        d = _LIVE["d"]
        if d is None:
            return
        prev = _LIVE["msgs"].get(key)
        if prev:
            model = model or prev[0]
            u = _merge_usage(prev[1], u)
        _LIVE["msgs"][key] = (model, u)
        tin = tout = 0
        cost, sin_precio, por = 0.0, False, {}
        for m, uu in _LIVE["msgs"].values():
            ti = uu["input"] + uu["cache_5m"] + uu["cache_1h"] + uu["cache_read"]
            tin, tout = tin + ti, tout + uu["output"]
            c = _estimate(m, uu)
            b = por.setdefault(m or "?", {"tokens_in": 0, "tokens_out": 0, "cost_usd_estimado": 0.0})
            b["tokens_in"] += ti
            b["tokens_out"] += uu["output"]
            if c is None:
                sin_precio, b["cost_usd_estimado"] = True, None
            else:
                cost += c
                if b["cost_usd_estimado"] is not None:
                    b["cost_usd_estimado"] = round(b["cost_usd_estimado"] + c, 6)
        d.update(tokens_in=tin, tokens_out=tout, por_modelo=por, modo_vivo="en vivo",
                 cost_usd_estimado=None if sin_precio else round(cost, 6))
        if model:
            d["modelo_real"] = model
    live_write()


def live_set(**kw):
    with _LOCK:
        if _LIVE["d"] is not None:
            _LIVE["d"].update(kw)
    live_write(force=True)


def live_write(force=False):
    with _LOCK:
        d = _LIVE["d"]
        if d is None or (not force and time.time() - _LIVE["written"] < LIVE_SECONDS):
            return
        if d["estado"] != "terminado":
            d["elapsed_s"] = round(time.time() - _LIVE["t0"], 1)
        d["actualizado"] = now_iso()
        _LIVE["written"] = time.time()
        snap = dict(d)
    _atomic_write(LIVE_FILE, snap)


def _pulse():
    """Mientras una tarea corre, el bucle principal espera a Claude; este
    hilo sigue escribiendo el vivo (~5 s) y el latido (60 s)."""
    while True:
        try:
            d = _LIVE["d"]
            if d is not None and d.get("estado") != "terminado":
                live_write()
            if _CUR["task"] and time.time() - _CUR["hb"] >= HEARTBEAT_SECONDS:
                heartbeat(_CUR["tasks_done"], _CUR["task"])
        except Exception as e:
            log(f"pulso: {type(e).__name__}: {e}")
        time.sleep(1)


# Ruta absoluta de Claude Code (t-runner-path-045): el comando pelado depende del
# PATH del proceso, y un proceso elevado relanzado desde una terminal vieja
# hereda un PATH sin .localin. Primero la ruta conocida; el PATH es respaldo.
CLAUDE_ABS = Path(os.environ.get("USERPROFILE") or Path.home()) / ".local" / "bin" / "claude.exe"


def claude_exe():
    """(ruta, origen): 'ruta absoluta' | 'PATH' | None si no hay claude."""
    if CLAUDE_ABS.is_file():
        return str(CLAUDE_ABS), "ruta absoluta"
    w = shutil.which("claude")
    return (w, "PATH") if w else (None, None)


def _build_cmd(task, fmt):
    exe, origen = claude_exe()
    if exe is None:
        raise FileNotFoundError("claude")
    if not _CUR.get("claude_logged") == origen:
        _CUR["claude_logged"] = origen
        log(f"claude se lanza por {origen}: {exe}")
    cmd = [exe, "-p", task["prompt"]] + fmt
    if task["model"]:
        cmd += ["--model", task["model"]]
    if task["allowed_tools"]:
        cmd += ["--allowedTools", task["allowed_tools"]]
    if task["permission_mode"]:
        cmd += ["--permission-mode", task["permission_mode"]]
    if task.get("session_id"):
        cmd += ["--resume", task["session_id"]]
    return cmd


def _fill_from_final(result, data, rc):
    """Mismos campos que con --output-format json."""
    result["result"] = str(data.get("result", ""))[:MAX_RESULT_CHARS]
    result["cost_usd"] = data.get("total_cost_usd")
    result["num_turns"] = data.get("num_turns")
    result["session_id"] = data.get("session_id")
    result["status"] = "error" if data.get("is_error") or rc != 0 else "ok"
    if data.get("is_error"):
        result["error"] = "claude reporto is_error=true"
    u = _usage_norm(data.get("usage"))
    tin = u["input"] + u["cache_5m"] + u["cache_1h"] + u["cache_read"]
    por = {m: {"tokens_in": int(mu.get("inputTokens") or 0) + int(mu.get("cacheReadInputTokens") or 0)
               + int(mu.get("cacheCreationInputTokens") or 0), "tokens_out": int(mu.get("outputTokens") or 0),
               "cost_usd": mu.get("costUSD")}
           for m, mu in (data.get("modelUsage") or {}).items() if isinstance(mu, dict)}
    if tin or u["output"]:
        live_set(tokens_in=tin, tokens_out=u["output"], **({"por_modelo": por} if por else {}))


def _run_stream(task, result):
    """claude con --output-format stream-json; un hilo lector suma el uso de
    cada mensaje segun llega y marca la actividad. Devuelve False si no llego
    ni un evento (esta version de claude no entiende stream-json): el que
    llama lo repite con json. Si se mato por inactividad, no se repite."""
    cmd = _build_cmd(task, ["--output-format", "stream-json", "--verbose", "--include-partial-messages"])
    st = {"final": None, "events": 0, "uso": False, "model_of": {}, "text": "", "raw": deque(maxlen=60)}
    errbuf = deque(maxlen=400)
    touch()
    proc = subprocess.Popen(cmd, cwd=task["cwd"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, **_oculto())
    log(f"[{task['id']}] claude lanzado oculto ({OCULTO_TXT}), pid {proc.pid}")

    def reader():
        try:
            for raw in proc.stdout:
                touch()
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
                t = ev.get("type")
                if t == "stream_event":
                    e = ev.get("event") or {}
                    key = ev.get("api_message_id") or (e.get("message") or {}).get("id")
                    if e.get("type") == "message_start":
                        m = e.get("message") or {}
                        st["model_of"][key] = m.get("model")
                        if isinstance(m.get("usage"), dict):
                            st["uso"] = True
                            live_msg(key, m.get("model"), _usage_norm(m["usage"]))
                    elif e.get("type") == "message_delta" and isinstance(e.get("usage"), dict):
                        st["uso"] = True
                        live_msg(key, st["model_of"].get(key), _usage_norm(e["usage"]))
                elif t == "assistant":
                    m = ev.get("message") or {}
                    if isinstance(m.get("usage"), dict):
                        st["uso"] = True
                        live_msg(m.get("id"), m.get("model"), _usage_norm(m["usage"]))
                    for b in m.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "text":
                            st["text"] = b.get("text") or st["text"]
                elif t == "result":
                    st["final"] = ev
        except (OSError, ValueError):
            pass

    th = threading.Thread(target=reader, daemon=True)
    th_err = threading.Thread(target=_stderr_reader, args=(proc.stderr, errbuf), daemon=True)
    th.start()
    th_err.start()
    rc = _wait_watch(proc, task, result)
    th.join(15)
    th_err.join(15)
    result["stderr"] = "".join(errbuf)[-MAX_STDERR_CHARS:]
    result["exit_code"] = rc
    if not st["uso"]:
        live_set(modo_vivo="sin vivo", nota="claude no reportó uso mientras corría (sin vivo)")
    tail = st["text"] or "\n".join(st["raw"])
    if rc is None:  # matado por inactividad o por el timeout total
        result["result"] = tail[-MAX_RESULT_CHARS:]
        return True
    if st["final"] is None:
        if st["events"] == 0:
            return False
        result["result"] = tail[:MAX_RESULT_CHARS]
        result["error"] = f"claude salio con codigo {rc} sin el mensaje final"
        return True
    _fill_from_final(result, st["final"], rc)
    return True


def _run_plain(task, result):
    """Como siempre: --output-format json. Ya no es un subprocess.run
    bloqueante: dos hilos leen stdout/stderr segun llega (cada linea es
    actividad) y el mismo vigilante de inactividad y timeout total."""
    outbuf, errbuf = [], deque(maxlen=400)
    touch()
    proc = subprocess.Popen(
        _build_cmd(task, ["--output-format", "json"]), cwd=task["cwd"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, **_oculto())
    log(f"[{task['id']}] claude lanzado oculto ({OCULTO_TXT}), pid {proc.pid}")

    def reader():
        try:
            for raw in proc.stdout:
                touch()
                outbuf.append(raw)
        except (OSError, ValueError):
            pass

    th = threading.Thread(target=reader, daemon=True)
    th_err = threading.Thread(target=_stderr_reader, args=(proc.stderr, errbuf), daemon=True)
    th.start()
    th_err.start()
    rc = _wait_watch(proc, task, result)
    th.join(15)
    th_err.join(15)
    result["exit_code"] = rc
    result["stderr"] = "".join(errbuf)[-MAX_STDERR_CHARS:]
    stdout = b"".join(outbuf).decode("utf-8", "replace")
    if rc is None:  # matado por inactividad o por el timeout total
        result["result"] = stdout[-MAX_RESULT_CHARS:]
        return
    try:
        data = json.loads(stdout)
        if not isinstance(data, dict):
            raise ValueError
        _fill_from_final(result, data, rc)
    except ValueError:
        result["result"] = stdout[:MAX_RESULT_CHARS]
        result["status"] = "ok" if rc == 0 else "error"
        if rc != 0:
            result["error"] = f"claude salio con codigo {rc} y salida no-JSON"

def run_task(task):
    """Corre claude -p. Devuelve el dict de resultado (mismos campos que v1.1)."""
    started = now_iso()
    t0 = time.time()
    log(f"[{task['id']}] corriendo claude -p en {task['cwd']} (timeout {task['timeout_min']} min)")
    result = {
        "runner": VERSION,
        "id": task["id"],
        "status": "error",
        "started_at": started,
        "finished_at": None,
        "duration_s": None,
        "exit_code": None,
        "result": "",
        "cost_usd": None,
        "num_turns": None,
        "session_id": None,
        "stderr": "",
        "error": None,
    }
    live_start(task)
    try:
        if not _run_stream(task, result):
            log(f"[{task['id']}] claude no dio salida en vivo (stream-json); lo corro como antes (json)")
            live_set(modo_vivo="sin vivo", nota="claude no dio salida en vivo; se corrió sin vivo")
            result.update(status="error", error=None, result="", exit_code=None, stderr="")
            _run_plain(task, result)
    except FileNotFoundError:
        result["error"] = "claude no esta en el PATH de este usuario"
    except subprocess.TimeoutExpired as e:
        result["status"] = "timeout"
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        result["result"] = str(out)[-MAX_RESULT_CHARS:]
        result["error"] = f"timeout de {task['timeout_min']} min"
    except Exception as e:  # nunca tumbar el loop por una tarea
        result["error"] = f"{type(e).__name__}: {e}"
    result["finished_at"] = now_iso()
    result["duration_s"] = round(time.time() - t0, 1)
    live_set(estado="terminado",
             cost_usd_final=result["cost_usd"] if isinstance(result["cost_usd"], (int, float)) else None)
    return result


def write_result(result):
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{result['id']}.result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return path


def process_one(task_file):
    """Procesa un task.json. Devuelve True si se proceso (ok o con error)."""
    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"[{task_file.name}] JSON invalido ({e}); se archiva sin correr")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_file), str(DONE / task_file.name))
        write_result({
            "runner": VERSION,
            "id": task_file.stem,
            "status": "error",
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "duration_s": 0,
            "exit_code": None,
            "result": "",
            "cost_usd": None,
            "num_turns": None,
            "stderr": "",
            "error": f"JSON invalido: {e}",
        })
        return True
    task, error = validate_task(data)
    task_id = data.get("id") if isinstance(data.get("id"), str) else task_file.stem
    if error:
        log(f"[{task_id}] rechazado: {error}")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(task_file), str(DONE / task_file.name))
        write_result({
            "runner": VERSION,
            "id": task_id,
            "status": "error",
            "started_at": now_iso(),
            "finished_at": now_iso(),
            "duration_s": 0,
            "exit_code": None,
            "result": "",
            "cost_usd": None,
            "num_turns": None,
            "stderr": "",
            "error": error,
        })
        return True
    PROCESSING.mkdir(parents=True, exist_ok=True)
    DONE.mkdir(parents=True, exist_ok=True)
    processing_path = PROCESSING / task_file.name
    try:
        shutil.move(str(task_file), str(processing_path))
    except OSError as e:
        log(f"[{task['id']}] no se pudo mover a processing: {e}")
        return False
    _CUR["task"] = {"id": task["id"], "motor": "claude", "modelo": task["model"],
                    "started_at": now_iso()}
    touch()
    heartbeat(_CUR["tasks_done"], _CUR["task"])
    try:
        result = run_task(task)
    finally:
        _CUR["task"] = None
    try:
        write_result(result)
        log(f"[{task['id']}] terminado: status={result['status']} duracion={result['duration_s']}s costo={result['cost_usd']}"
            + (f" error={result['error']}" if result.get("error") else ""))
    except OSError as e:
        log(f"[{task['id']}] no se pudo escribir el resultado: {e}")
    try:
        shutil.move(str(processing_path), str(DONE / task_file.name))
    except OSError as e:
        log(f"[{task['id']}] no se pudo archivar el task: {e}")
    return True


def heartbeat(tasks_done, current):
    """runner-status.json. 'current' = la tarea en curso (id, motor, modelo,
    started_at, last_activity, idle_s) o null. Mientras corre una tarea lo
    escribe el hilo de pulso cada 60 s: un last_poll viejo ya no significa
    'Claude trabajando', es un problema; un idle_s que crece, tampoco."""
    _CUR["hb"] = time.time()
    if current:
        act = _CUR["act"] or _CUR["hb"]
        current = dict(current, last_activity=_iso(act), idle_s=round(_CUR["hb"] - act))
    status = {
        "runner": VERSION,
        "alive": True,
        "last_poll": now_iso(),
        "tasks_done": tasks_done,
        "current": current,
        "claude": claude_exe()[0],
        "claude_origen": claude_exe()[1],
        "pid": os.getpid(),
        "vivo": LIVE_FILE.name,
    }
    _atomic_write(STATUS_FILE, status)


def main():
    if HERE.name != "runner" or HERE.parent.name != "inbox":
        print("ERROR: el runner debe vivir en share\\inbox\\runner\\")
        print(f"Esta en: {HERE}")
        sys.exit(2)
    for d in (TASKS, PROCESSING, DONE, RESULTS):
        d.mkdir(parents=True, exist_ok=True)
    claude, origen = claude_exe()
    log(f"Growi Runner {VERSION} arrancado. python={sys.version.split()[0]} claude={claude or 'NO ENCONTRADO'} ({origen or 'ni ruta absoluta ni PATH'})")
    log(f"tasks en: {TASKS}")
    log(f"resultados en: {RESULTS}")
    if not claude:
        log("AVISO: `claude` no esta en el PATH; las tareas fallaran con error hasta que este instalado.")
    tasks_done = 0
    last_heartbeat = 0.0
    threading.Thread(target=_pulse, daemon=True).start()
    while True:
        try:
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                heartbeat(tasks_done, None)
                last_heartbeat = now
            candidates = []
            for p in TASKS.glob("*.task.json"):
                try:
                    # Esperar 2 s por si el puente aun esta escribiendo el archivo.
                    if now - p.stat().st_mtime >= 2:
                        candidates.append(p)
                except OSError:
                    continue
            candidates.sort(key=lambda p: p.stat().st_mtime)
            if candidates:
                if process_one(candidates[0]):
                    tasks_done += 1
                    _CUR["tasks_done"] = tasks_done
                    heartbeat(tasks_done, None)
                    last_heartbeat = time.time()
        except Exception as e:
            log(f"ERROR en el loop (se sigue): {type(e).__name__}: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
