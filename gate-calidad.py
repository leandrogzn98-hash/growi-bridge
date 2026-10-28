"""Gate de calidad local de Growi Bridge (ver ESTADO-GATE-CALIDAD.md).

Filtro previo y gratis ($0: solo comandos locales, ningun modelo) antes de la
revision por criterios. Corre, en orden y SOLO sobre lo que cambio:

  a) py_compile de cada .py tocado;
  b) ruff check de los .py tocados;
  c) mypy de los .py tocados;
  d) pytest -q de los tests que tocan lo cambiado (si no hay, la suite
     completa con tope de 120 s; si no hay suite, lo dice y sigue);
  e) smoke de Tkinter: arranca una COPIA de growi-bridge.py (en %TEMP%, con
     share, cola, token, mutex propios y un puerto de prueba desde 8797; nunca
     8787/8788/8789), espera 200 en /gateway/salud (tope 60 s), mira que el log
     no tenga tracebacks y la cierra por su salida limpia (la X con
     on_close=quit -> quit_app). Solo si cambio growi-bridge.py o un archivo
     que la app lee al arrancar.

QUE BLOQUEA (salida 2):
  - py_compile falla en un .py cambiado;
  - ruff, reglas de error (E9 sintaxis, F63 comparaciones invalidas, F7
    errores de sentencia, F82 nombres sin definir) en LINEAS cambiadas;
  - mypy «error:» en lineas cambiadas (salvo los codigos de AVISO_MYPY);
  - un test en rojo;
  - smoke: traceback en el log, sin 200 en /gateway/salud en 60 s, o la app
    no sale sola con su salida limpia (en ese caso se mata igual).

QUE NO BLOQUEA (sale como AVISO):
  - el resto de reglas por defecto de ruff (estilo: el proyecto no tiene
    configuracion de ruff ni usa ruff format);
  - mypy: notes y los codigos de AVISO_MYPY (el proyecto no tiene anotaciones);
  - cualquier hallazgo en lineas NO cambiadas o archivos no tocados
    (preexistente);
  - ruff, mypy o pytest no instalados; no hay suite; la suite pasa de 120 s.

ARCHIVOS CAMBIADOS (en este orden):
  1) stdin JSON con "archivos" o "files" (lista), o --archivos en la linea
     de ordenes;
  2) si no: hook de Claude Code. El Stop hook recibe por stdin session_id y
     transcript_path; del transcript salen los archivos de Edit/Write/
     MultiEdit/NotebookEdit, mas git diff --name-only contra la base de la
     sesion (HEAD al empezar, guardado por --registrar-base en
     UserPromptSubmit) y los no rastreados nuevos;
  3) sin hook: git diff --name-only HEAD + no rastreados;
  4) sin git ni transcript: todos los .py.
  «Lineas cambiadas» = hunks de git diff -U0 contra la base; un archivo nuevo
  o fuera de git cuenta entero.

HOOK: salida 2 + resumen por stderr bloquea el stop y devuelve el fallo al
agente. Para no entrar en bucle, tras MAX_BLOQUEOS bloqueos seguidos en la
misma sesion deja terminar (salida 0) y el log dice FALLA SIN CORREGIR: la
revision lo ve como fallo. En una sesion de revision (GROWI_TAREA_ROL=
revision) no corre.

LOG: <raiz>/gate-calidad/gate-calidad-<id>.log y, si hay share/outbox/
(GROWI_BRIDGE_SHARE, <raiz>/share, o la raiz es share/inbox), una copia ahi
(id = GROWI_TAREA_ID si lo pone el runner, si no el session_id del hook, si
no «manual»). La primera
linea es «GATE: PASA|FALLA|FALLA SIN CORREGIR». El gateway lo adjunta al
prompt de revision (_gate_para_revision en growi-bridge.py).

Uso a mano:
  python gate-calidad.py                         lo cambiado segun git
  python gate-calidad.py --archivos a.py b.py    estos archivos
  python gate-calidad.py --smoke | --sin-smoke   forzar / saltar el smoke
"""

import json
import os
import py_compile
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MAX_BLOQUEOS = 3
TOPE_PYTEST_S = 120
TOPE_SMOKE_S = 60  # 30 s se quedaba corto: con el PC en uso la app (HEAD igual) abre el puente en 25-31 s (28-oct-2026)
PUERTOS_PRUEBA = range(8797, 8820)
PUERTOS_PROHIBIDOS = {8787, 8788, 8789}
RUFF_ERRORES = "E9,F63,F7,F82"
AVISO_MYPY = {"var-annotated", "import-untyped", "import-not-found", "annotation-unchecked", "no-redef"}
# Lo que lee la app al arrancar: si cambia, toca smoke aunque no cambie el .py.
APP = "growi-bridge.py"
APP_DATOS = ("engines.json", "models-catalog.json", "riesgos.json", "availability.json", "models-preset.ini")
NO_MIRAR = {".git", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache", "gate-calidad", "share",
            ".venv", "venv", "node_modules"}
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(cmd, cwd, timeout=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, check=False, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, creationflags=OCULTO)


def _git(raiz, *args):
    try:
        r = _run(["git", *args], raiz, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _raiz(cwd):
    top = _git(cwd, "rev-parse", "--show-toplevel")
    return (Path(top.strip()) if top else Path(cwd)).resolve()


def _dir_gate(raiz):
    d = raiz / "gate-calidad"
    d.mkdir(exist_ok=True)
    return d


def _estado_sesion(raiz, sesion):
    f = _dir_gate(raiz) / f"sesion-{sesion}.json"
    try:
        return f, json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f, {}


def registrar_base(entrada):
    """UserPromptSubmit: guarda HEAD y la hora al empezar la sesion (una vez)."""
    raiz = _raiz(entrada.get("cwd") or os.getcwd())
    sesion = entrada.get("session_id")
    if not sesion:
        return 0
    f, st = _estado_sesion(raiz, sesion)
    if "base" not in st:
        head = _git(raiz, "rev-parse", "HEAD")
        st.update(base=head.strip() if head else None, desde=time.time(), bloqueos=0)
        f.write_text(json.dumps(st), encoding="utf-8")
    return 0


def _del_transcript(path):
    """Archivos que el agente escribio en la sesion (Edit/Write/...)."""
    out = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                try:
                    ev = json.loads(linea)
                except ValueError:
                    continue
                for c in ((ev.get("message") or {}).get("content") or []) if isinstance(ev, dict) else []:
                    if (isinstance(c, dict) and c.get("type") == "tool_use"
                            and c.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit")):
                        p = (c.get("input") or {}).get("file_path") or (c.get("input") or {}).get("notebook_path")
                        if p:
                            out.append(p)
    except OSError:
        pass
    return out


def _cambiados(raiz, entrada, base, desde):
    """(lista de Path absolutos existentes, de donde salio la lista)."""
    explicitos = entrada.get("archivos") or entrada.get("files")
    if explicitos:
        return [Path(raiz, p).resolve() for p in explicitos], "lista recibida"
    nombres, fuentes = set(), []
    if entrada.get("transcript_path"):
        t = _del_transcript(entrada["transcript_path"])
        nombres.update(Path(raiz, p).resolve() for p in t)
        fuentes.append(f"transcript ({len(set(t))})")
    if _git(raiz, "rev-parse", "HEAD") is not None:
        d = _git(raiz, "diff", "--name-only", base or "HEAD") or ""
        nuevos = _git(raiz, "ls-files", "--others", "--exclude-standard") or ""
        nombres.update((raiz / p).resolve() for p in d.split())
        for p in nuevos.splitlines():
            f = (raiz / p).resolve()
            if not desde or (f.exists() and f.stat().st_mtime >= desde):
                nombres.add(f)
        fuentes.append(f"git diff {(base or 'HEAD')[:10]} + no rastreados")
    elif not nombres:  # sin git ni transcript: todos los .py
        nombres.update(p.resolve() for p in raiz.rglob("*.py") if not NO_MIRAR & set(p.parts))
        fuentes.append("sin git: todos los .py")
    dentro = [p for p in nombres if p.exists() and raiz in p.parents and not NO_MIRAR & set(p.relative_to(raiz).parts)]
    return sorted(dentro), " + ".join(fuentes)


def _lineas_cambiadas(raiz, f, base):
    """set de lineas cambiadas, o None = el archivo entero cuenta como nuevo."""
    rel = f.relative_to(raiz).as_posix()
    if _git(raiz, "cat-file", "-e", f"{base or 'HEAD'}:{rel}") is None:
        return None
    d = _git(raiz, "diff", "-U0", base or "HEAD", "--", rel) or ""
    out = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", d, re.MULTILINE):
        ini, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        out.update(range(ini, ini + n))
    return out


def _tocada(lineas, n):
    return lineas is None or n in lineas


def _tiene(modulo):
    try:
        return _run([sys.executable, "-m", modulo, "--version"], ".", timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class Chequeo:
    def __init__(self, nombre):
        self.nombre, self.estado, self.detalle, self.avisos, self.s = nombre, "PASA", [], [], 0.0

    def falla(self, msg):
        self.estado = "FALLA"
        self.detalle.append(msg)

    def texto(self):
        out = [f"[{self.estado}] {self.nombre} ({self.s:.1f} s)"]
        out += [f"    {d}" for d in self.detalle[:25]]
        if len(self.detalle) > 25:
            out.append(f"    ... y {len(self.detalle) - 25} mas")
        out += [f"    aviso: {a}" for a in self.avisos[:10]]
        if len(self.avisos) > 10:
            out.append(f"    aviso: ... y {len(self.avisos) - 10} avisos mas (no bloquean)")
        return "\n".join(out)


def ch_compile(raiz, pys):
    c = Chequeo("py_compile")
    for f in pys:
        try:  # lo mismo que py_compile, sin escribir el .pyc
            py_compile.compile(str(f), cfile=str(_dir_gate(raiz) / "py_compile.pyc"), doraise=True)
        except py_compile.PyCompileError as e:
            c.falla(f"{f.relative_to(raiz)}: {e.msg.strip().splitlines()[-1]}")
    if c.estado == "PASA":
        c.detalle.append(f"{len(pys)} archivo(s) compilan")
    return c


def _ruff(raiz, pys, select=None):
    cmd = [sys.executable, "-m", "ruff", "check", "--output-format", "json", "--no-fix", "--quiet",
           "--cache-dir", str(_dir_gate(raiz) / ".ruff_cache")]
    if select:
        cmd += ["--select", select]
    r = _run(cmd + [str(p) for p in pys], raiz, timeout=120)
    try:
        return json.loads(r.stdout or "[]")
    except ValueError:
        return [{"code": None, "message": (r.stderr or r.stdout).strip()[:300], "filename": "", "location": {}}]


def ch_ruff(raiz, pys, lineas):
    c = Chequeo("ruff check")
    if not _tiene("ruff"):
        c.estado = "AVISO"
        c.detalle.append("FALTA: ruff no esta instalado (python -m pip install ruff); no bloquea")
        return c
    vistos = set()
    for h in _ruff(raiz, pys, RUFF_ERRORES):
        f = Path(h.get("filename") or "")
        n = (h.get("location") or {}).get("row") or 0
        vistos.add((str(f), n, h.get("code")))
        msg = f"{f.name}:{n}: {h.get('code') or 'sintaxis'} {h.get('message')}"
        if f.name and _tocada(lineas.get(f.resolve(), set()), n):
            c.falla(msg)
        else:
            c.avisos.append(f"preexistente (linea no cambiada): {msg}")
    estilo = [h for h in _ruff(raiz, pys) if (str(Path(h.get("filename") or "")),
                                              (h.get("location") or {}).get("row") or 0, h.get("code")) not in vistos]
    mias = [h for h in estilo
            if _tocada(lineas.get(Path(h.get("filename") or "").resolve(), set()), (h.get("location") or {}).get("row") or 0)]
    c.avisos += [f"estilo en linea cambiada: {Path(h['filename']).name}:{h['location']['row']}: {h.get('code')} "
                 f"{h.get('message')}" for h in mias]
    if len(estilo) > len(mias):
        c.avisos.append(f"{len(estilo) - len(mias)} hallazgos de estilo preexistentes en lineas no cambiadas")
    if c.estado == "PASA":
        c.detalle.append(f"sin errores ({RUFF_ERRORES}) en lineas cambiadas de {len(pys)} archivo(s)")
    return c


def ch_mypy(raiz, pys, lineas):
    c = Chequeo("mypy")
    if not _tiene("mypy"):
        c.estado = "AVISO"
        c.detalle.append("FALTA: mypy no esta instalado (python -m pip install mypy); no bloquea")
        return c
    pre = 0
    for f in pys:  # uno a uno: los nombres con guion no son modulos y dos «main» chocarian
        r = _run([sys.executable, "-m", "mypy", "--ignore-missing-imports", "--follow-imports=silent",
                  "--no-error-summary", "--show-error-codes", "--no-pretty", "--cache-dir",
                  str(_dir_gate(raiz) / ".mypy_cache"), str(f)], raiz, timeout=300)
        for linea in r.stdout.splitlines():
            m = re.match(r"^(.*?):(\d+):(?:\d+:)? (error|note): (.*?)(?:\s+\[([a-z-]+)\])?$", linea)
            if not m:
                if "error" in linea.lower() and r.returncode == 2:
                    c.falla(f"{f.name}: mypy no pudo analizar: {linea.strip()[:200]}")
                continue
            ruta, n, tipo, msg, code = m.groups()
            g = Path(raiz, ruta).resolve()
            if tipo == "note":
                continue
            texto = f"{g.name}:{n}: {msg} [{code}]"
            if g != f.resolve() or not _tocada(lineas.get(f.resolve(), set()), int(n)):
                pre += 1
            elif code in AVISO_MYPY:
                c.avisos.append(f"no bloquea ({code}): {texto}")
            else:
                c.falla(texto)
    if pre:
        c.avisos.append(f"{pre} errores de mypy preexistentes en lineas no cambiadas")
    if c.estado == "PASA":
        c.detalle.append(f"sin errores en lineas cambiadas de {len(pys)} archivo(s)")
    return c


def _tests(raiz):
    return sorted(p for p in raiz.rglob("*.py")
                  if (p.name.startswith("test_") or p.name.endswith("_test.py"))
                  and not NO_MIRAR & set(p.relative_to(raiz).parts))


def ch_pytest(raiz, cambiados):
    c = Chequeo("pytest")
    todos = _tests(raiz)
    if not todos:
        c.estado = "OMITIDO"
        c.detalle.append("no hay suite de tests (test_*.py); no bloquea")
        return c
    if not _tiene("pytest"):
        c.estado = "AVISO"
        c.detalle.append("FALTA: pytest no esta instalado; no bloquea")
        return c
    claves = {f.stem for f in cambiados} | {f.stem.replace("-", "_") for f in cambiados}
    afectados = []
    for t in todos:
        try:
            src = t.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if t in cambiados or any(k and k in src for k in claves):
            afectados.append(t)
    if afectados:
        sel, que = afectados, f"{len(afectados)} test(s) afectados"
    else:
        sel, que = todos, "ningun test afectado: suite completa"
    try:
        r = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *map(str, sel)], raiz,
                 timeout=TOPE_PYTEST_S)
    except subprocess.TimeoutExpired:
        c.estado = "AVISO"
        c.detalle.append(f"{que}: no termino en {TOPE_PYTEST_S} s; no bloquea")
        return c
    resumen = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode in (0, 5):
        c.detalle.append(f"{que}: {resumen}")
    else:
        c.falla(f"{que}: {resumen}")
        c.detalle += [x for x in r.stdout.splitlines() if x.startswith(("FAILED", "ERROR", "E "))][:20]
    return c


def _puerto_libre():
    for p in PUERTOS_PRUEBA:
        if p in PUERTOS_PROHIBIDOS:
            continue
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return None


def _ventanas_tk(pid):
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    out = []

    def cb(h, _l):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            cls = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(h, cls, 64)
            if cls.value == "TkTopLevel":
                out.append(h)
        return True
    u32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return out


LANZADOR_OCULTO = """import runpy, sys, tkinter as tk


def _oculta(base):
    class Oculta(base):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            base.withdraw(self)

        def deiconify(self):
            return None

        def lift(self, *a):
            return None

        def focus_force(self):
            return None
    Oculta.__name__ = base.__name__
    return Oculta


tk.Tk = _oculta(tk.Tk)
tk.Toplevel = _oculta(tk.Toplevel)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def ch_smoke(raiz):
    """Copia aislada de la app; nunca toca la instalada ni sus puertos."""
    c = Chequeo("smoke Tkinter (/gateway/salud)")
    puerto = _puerto_libre()
    if puerto is None:
        c.falla(f"no hay puerto de prueba libre en {PUERTOS_PRUEBA.start}-{PUERTOS_PRUEBA.stop - 1}")
        return c
    base = Path(os.environ.get("TEMP", raiz)) / f"gate-calidad-smoke-{os.getpid()}"
    app = base / "app"
    shutil.copytree(raiz, app, ignore=shutil.ignore_patterns(
        *NO_MIRAR, "pruebas", "*.log", "settings.json", "secret.txt", "gateway.lock", "*.db"))
    # En la COPIA (nunca en el engines.json del repo): sin servidor de motor
    # local (no adopta ni cierra el de la app instalada) y sin comprobar la
    # sesion de los CLI (`agy models` tarda ~40 s y build_gui la espera: el
    # smoke mide si la app arranca, no la red de un CLI ajeno).
    try:
        e = json.loads((app / "engines.json").read_text(encoding="utf-8"))
        for m in (e.get("motores") or {}).values():
            if isinstance(m, dict):
                m.pop("servidor", None)
                if isinstance(m.get("autenticacion"), dict):
                    m["autenticacion"].pop("sesion_cli", None)
        (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    except (OSError, ValueError):
        pass
    secreto = f"gate-{os.getpid()}-{time.time_ns()}"
    (app / "secret.txt").write_text(secreto, encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "nunca", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": puerto,
        "on_close": "quit"}), encoding="utf-8")
    (base / "claude-projects").mkdir()
    env = dict(os.environ, GROWI_BRIDGE_SHARE=str(base / "share"), GROWI_BRIDGE_COLA=str(base / "cola.db"),
               GROWI_BRIDGE_TOKEN_DIR=str(base / "token"), GROWI_BRIDGE_MUTEX=f"Local\\GrowiBridgeGate{os.getpid()}",
               GROWI_BRIDGE_PORT=str(puerto), GROWI_BRIDGE_CLAUDE_PROJECTS=str(base / "claude-projects"),
               GROWI_BRIDGE_LANE="a")
    for k in ("GROWI_TAREA_ID", "GROWI_TAREA_ROL"):
        env.pop(k, None)
    si = subprocess.STARTUPINFO()
    si.dwFlags, si.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 7  # SW_SHOWMINNOACTIVE: no roba el foco
    # Y la app arranca con todas sus ventanas ocultas (withdraw): el PC puede estar en uso.
    lanzador = base / "lanzar-oculto.py"
    lanzador.write_text(LANZADOR_OCULTO, encoding="utf-8")
    pyw = Path(sys.executable).with_name("pythonw.exe")
    p = subprocess.Popen([str(pyw if pyw.exists() else sys.executable), str(lanzador), str(app / APP)],
                         cwd=str(app), env=env, startupinfo=si)
    c.detalle.append(f"copia en {base}, puerto {puerto}, pid {p.pid}")
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0, salud = time.time(), None
    try:
        while time.time() - t0 < TOPE_SMOKE_S and p.poll() is None:
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{puerto}/gateway/salud",
                                             headers={"X-Shared-Secret": secreto})
                with op.open(req, timeout=2) as r:
                    if r.status == 200:
                        salud = round(time.time() - t0, 1)
                        break
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.5)
        if salud is None:
            c.falla("/gateway/salud no respondio 200 en "
                    f"{TOPE_SMOKE_S} s" + (f" (la app salio con {p.returncode})" if p.poll() is not None else ""))
        else:
            c.detalle.append(f"/gateway/salud 200 a los {salud} s")
            time.sleep(2)  # que terminen de arrancar ventana, bandeja e hilos
        if p.poll() is None:
            for h in _ventanas_tk(p.pid):
                import ctypes
                ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE = la X (on_close=quit)
            try:
                p.wait(25)
                c.detalle.append(f"salida limpia (quit_app) con codigo {p.returncode}")
            except subprocess.TimeoutExpired:
                c.falla("la app no salio sola en 25 s tras la X con on_close=quit; se mata")
    finally:
        if p.poll() is None:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False,
                           creationflags=OCULTO)
            p.wait(10)
        logf = app / "growi-bridge.log"
        txt = logf.read_text(encoding="utf-8", errors="replace") if logf.exists() else ""
        malos = [x for x in txt.splitlines() if "Traceback" in x or "error no controlado" in x]
        if malos:
            c.falla(f"{len(malos)} traceback(s) en el log de la copia")
            i = txt.find("Traceback")
            c.detalle += txt[i:i + 1500].splitlines()[:20]
        elif salud is not None and not malos:
            c.detalle.append("log sin tracebacks")
        vivo = p.poll() is None
        if vivo:
            c.falla(f"el pid {p.pid} sigue vivo")
        if c.estado == "PASA":
            shutil.rmtree(base, ignore_errors=True)
        else:
            c.detalle.append(f"copia conservada para mirar: {base}")
    return c


def correr(entrada, forzar_smoke=None):
    t0 = time.time()
    raiz = _raiz(entrada.get("cwd") or os.getcwd())
    sesion = entrada.get("session_id")
    tid = os.environ.get("GROWI_TAREA_ID") or sesion or "manual"
    tid = re.sub(r"[^A-Za-z0-9._-]", "_", tid)
    est_f, est = _estado_sesion(raiz, sesion) if sesion else (None, {})
    base = est.get("base") if sesion else None
    cambiados, fuente = _cambiados(raiz, entrada, base, est.get("desde"))
    pys = [f for f in cambiados if f.suffix == ".py"]
    lineas = {f: _lineas_cambiadas(raiz, f, base) for f in pys}
    cab = [f"raiz: {raiz}", f"id: {tid}", f"archivos cambiados ({fuente}): "
           + (", ".join(str(f.relative_to(raiz)) for f in cambiados) or "(ninguno)")]
    chequeos = []
    if pys:
        chequeos.append(ch_compile(raiz, pys))
        for fn in (ch_ruff, ch_mypy):
            t = time.time()
            ck = fn(raiz, pys, lineas)
            ck.s = time.time() - t
            chequeos.append(ck)
        t = time.time()
        ck = ch_pytest(raiz, cambiados)
        ck.s = time.time() - t
        chequeos.append(ck)
    else:
        sin = Chequeo("py_compile / ruff / mypy / pytest")
        sin.estado = "OMITIDO"
        sin.detalle.append("no cambio ningun .py")
        chequeos.append(sin)
    app_toca = any(f.relative_to(raiz).as_posix() in (APP, *APP_DATOS) or f.relative_to(raiz).parts[0] == "temas"
                   for f in cambiados)
    if (raiz / APP).exists() and (forzar_smoke or (forzar_smoke is None and app_toca)):
        t = time.time()
        ck = ch_smoke(raiz)
        ck.s = time.time() - t
        chequeos.append(ck)
    elif (raiz / APP).exists():
        sm = Chequeo("smoke Tkinter (/gateway/salud)")
        sm.estado = "OMITIDO"
        sm.detalle.append("saltado con --sin-smoke" if forzar_smoke is False
                          else f"no cambio {APP} ni lo que lee al arrancar")
        chequeos.append(sm)
    falla = any(c.estado == "FALLA" for c in chequeos)
    total = round(time.time() - t0, 1)
    resultado = "FALLA" if falla else "PASA"
    bloquear = falla
    if est_f is not None:
        est["bloqueos"] = (est.get("bloqueos") or 0) + 1 if falla else 0
        if falla and est["bloqueos"] > MAX_BLOQUEOS:
            resultado, bloquear = "FALLA SIN CORREGIR", False
        est["historial"] = [*(est.get("historial") or []), f"{time.strftime('%H:%M:%S')} {resultado}"][-20:]
        est_f.write_text(json.dumps(est), encoding="utf-8")
        cab.append("historial de esta sesion: " + " -> ".join(est["historial"]))
    txt = "\n".join([f"GATE: {resultado} ({total} s, $0: sin modelo)", *cab, ""] + [c.texto() for c in chequeos])
    if resultado == "FALLA SIN CORREGIR":
        txt += f"\n\nEl agente no lo corrigio tras {MAX_BLOQUEOS} bloqueos: se deja terminar; la revision lo ve como fallo."
    log = _dir_gate(raiz) / f"gate-calidad-{tid}.log"
    log.write_text(txt + "\n", encoding="utf-8")
    (_dir_gate(raiz) / "ultimo.txt").write_text(str(log) + "\n", encoding="utf-8")
    # Copia en share/outbox/ (donde la busca la revision del gateway instalado):
    # GROWI_BRIDGE_SHARE si esta puesto, una share/ en la raiz, o la raiz es share/inbox.
    for sh in (os.environ.get("GROWI_BRIDGE_SHARE"), raiz / "share", raiz.parent if raiz.name == "inbox" else None):
        out = Path(sh) / "outbox" if sh else None
        if out is not None and out.is_dir():
            try:
                (out / log.name).write_text(txt + "\n", encoding="utf-8")
            except OSError:
                pass
            break
    print(txt + f"\n\nlog: {log}")
    return txt, bloquear, log


def main():
    args = sys.argv[1:]
    entrada = {}
    if sys.stdin is not None and not sys.stdin.isatty() and "--sin-stdin" not in args:
        # Un hook manda el JSON y cierra stdin; a mano puede quedar abierto sin
        # nada: se lee en un hilo con tope de 3 s para no colgarse.
        import threading
        caja = []
        hilo = threading.Thread(target=lambda: caja.append(sys.stdin.read()), daemon=True)
        hilo.start()
        hilo.join(3)
        try:
            entrada = json.loads(caja[0]) if caja and caja[0].strip() else {}
        except ValueError:
            entrada = {}
    if "--registrar-base" in args:
        return registrar_base(entrada)
    if os.environ.get("GROWI_TAREA_ROL") == "revision":
        return 0  # la sesion del juez no cambia nada: el gate ya corrio en la tarea
    if "--archivos" in args:
        entrada["archivos"] = [a for a in args[args.index("--archivos") + 1:] if not a.startswith("--")]
    forzar = True if "--smoke" in args else False if "--sin-smoke" in args else None
    txt, bloquear, log = correr(entrada, forzar)
    if bloquear and not entrada.get("hook_event_name"):
        return 2  # a mano: el resumen ya salio por stdout
    if bloquear:  # hook: salida 2 + stderr = Claude Code no deja parar y se lo da al agente
        sys.stderr.write(txt + f"\n\nGate de calidad: FALLA. Corrige lo de arriba (solo lo que bloquea) y "
                               f"vuelve a terminar; el gate corre otra vez solo. Log: {log}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
