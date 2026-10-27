"""Prueba de «instancia unica + traer al frente» (ESTADO-MUTEX-INSTANCIA-UNICA.md).

Arranca copias AISLADAS de growi-bridge.py de este repo en
%TEMP%\\growi-prueba-mutex\\<carril>: share, cola, token, puerto y mutex
propios, asi que no toca la app instalada (8787) ni el carril B instalado.
El mutex de prueba se llama «Local\\GrowiBridgeInstanciaUnicaPrueba» (+
«-carrilB» en el B), asi el evento derivado es «Local\\GrowiBridgeMostrarPrueba»
(+ «-carrilB»): se prueba la misma derivacion que con los nombres reales.

  python pruebas/prueba_mutex.py lanzar <a|b> <puerto>    primera instancia (limpia la carpeta)
  python pruebas/prueba_mutex.py arrancar <a|b>           arranca otra vez SIN limpiar (lock obsoleto incluido)
  python pruebas/prueba_mutex.py segunda <a|b>            segunda copia: codigo de salida, tiempo y estado
  python pruebas/prueba_mutex.py primera_tarea <a|b>      primera instancia por tarea programada /RL HIGHEST
  python pruebas/prueba_mutex.py segunda_basico <a|b>     segunda copia SIN elevar (tarea /RL LIMITED, integridad media)
  python pruebas/prueba_mutex.py error5 <a|b>             fuerza el error 5 de CreateMutexW (mutex solo-SYSTEM)
  python pruebas/prueba_mutex.py esconder <a|b>           WM_CLOSE = la X (carril A: withdraw a la bandeja; B: iconify)
  python pruebas/prueba_mutex.py estado <a|b>             ventanas, iconos, puente, pythonw, lock
  python pruebas/prueba_mutex.py matar <a|b>              taskkill /F (simula una caida)
  python pruebas/prueba_mutex.py watchdog <a|b>           watchdog-gateway.ps1 apuntado a la copia de prueba
  python pruebas/prueba_mutex.py salir <a|b>              taskkill /F y limpia
"""

import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prueba_bandeja as pb  # noqa: E402  (ventanas, iconos, raton, salud)

REPO = pb.REPO
RAIZ = Path(os.environ.get("TEMP", ".")) / "growi-prueba-mutex"
u32 = pb.u32
u32.GetForegroundWindow.restype = wintypes.HWND
pb.SECRETO = "prueba-mutex-secreto"
pb.BASE = RAIZ  # capturas en %TEMP%growi-prueba-mutexpturas


def _base(carril):
    return RAIZ / carril


def _st(carril):
    return json.loads((_base(carril) / "prueba.json").read_text(encoding="utf-8"))


def _env(carril):
    b = _base(carril)
    return dict(os.environ, GROWI_BRIDGE_SHARE=str(b / "share"), GROWI_BRIDGE_COLA=str(b / "cola.db"),
                GROWI_BRIDGE_TOKEN_DIR=str(b / "token"),
                GROWI_BRIDGE_MUTEX="Local\\GrowiBridgeInstanciaUnicaPrueba" + ("-carrilB" if carril == "b" else ""),
                GROWI_BRIDGE_PORT=str(_st(carril)["puerto"]),
                GROWI_BRIDGE_CLAUDE_PROJECTS=str(b / "claude-projects-vacia"), GROWI_BRIDGE_LANE=carril)


def _pythonw(carril):
    """Procesos python de ESTA copia de prueba (por la ruta de su app)."""
    import psutil
    app = str(_base(carril) / "app")
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
            cwd = p.info["cwd"] or ""
        except Exception:
            continue
        if "python" in (p.info["name"] or "").lower() and "growi-bridge.py" in cl and (app in cl or cwd == app):
            out.append({"pid": p.pid, "name": p.info["name"], "cmdline": cl})
    return out


def _escuchan(puerto):
    import psutil
    return sorted({c.pid for c in psutil.net_connections("tcp")
                   if c.laddr and c.laddr.port == puerto and c.status == "LISTEN"})


def _iconos(pids):
    return {pid: bool(pb._icono(pid)[0]) for pid in pids}


def _fg():
    h = u32.GetForegroundWindow()
    p = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    t = ctypes.create_unicode_buffer(256)
    u32.GetWindowTextW(h, t, 256)
    return {"hwnd": h, "pid": p.value, "titulo": t.value}


def _arriba_del_todo(hwnd):
    """True si no hay ninguna ventana visible de otro proceso por encima
    (orden Z), sin contar la barra de tareas ni ventanas sin tamano."""
    h = u32.GetTopWindow(None)
    mio = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(mio))
    encima = []
    while h and h != hwnd:
        if u32.IsWindowVisible(h):
            p = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(p))
            r = wintypes.RECT()
            u32.GetWindowRect(h, ctypes.byref(r))
            cls = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cls, 256)
            ex = u32.GetWindowLongPtrW(h, -20)
            if (p.value != mio.value and r.right - r.left > 50 and r.bottom - r.top > 50
                    and not ex & 0x8 and cls.value not in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd")):
                encima.append(cls.value)  # 0x8 = WS_EX_TOPMOST (barras siempre encima)
        h = u32.GetWindow(h, 2)  # GW_HWNDNEXT
    return not encima, encima


def _lanzar_proc(carril):
    app = _base(carril) / "app"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return subprocess.Popen([str(pyw), str(app / "growi-bridge.py")], cwd=str(app), env=_env(carril))


def _esperar_ventana(pid, s=60):
    for _ in range(s):
        time.sleep(1)
        if pb._principal(pid) and pb._icono(pid)[0]:
            break
    time.sleep(3)


def lanzar(carril, puerto):
    b = _base(carril)
    if b.exists():
        shutil.rmtree(b)
    app = b / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__"))
    (app / "secret.txt").write_text(pb.SECRETO, encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": carril, "onboarding_done": True, "guardrail": "nunca", "mascot": False,
        "auto_update": False, "copia_claude": False, "motor_local_parar_al_salir": False,
        "bridge_port": puerto}, indent=2), encoding="utf-8")
    (b / "claude-projects-vacia").mkdir()
    (b / "prueba.json").write_text(json.dumps({"puerto": puerto}), encoding="utf-8")
    p = _lanzar_proc(carril)
    (b / "prueba.json").write_text(json.dumps({"pid": p.pid, "puerto": puerto}), encoding="utf-8")
    _esperar_ventana(p.pid)
    return estado(carril)


def arrancar(carril):
    """Arranque nuevo sobre la carpeta tal cual (con el gateway.lock que dejo la caida)."""
    st = _st(carril)
    lock = _base(carril) / "app" / "gateway.lock"
    antes = json.loads(lock.read_text(encoding="utf-8")) if lock.exists() else None
    p = _lanzar_proc(carril)
    st["pid"] = p.pid
    (_base(carril) / "prueba.json").write_text(json.dumps(st), encoding="utf-8")
    _esperar_ventana(p.pid)
    r = estado(carril)
    r["lock_obsoleto_antes"] = antes
    r["proceso_sigue_vivo"] = p.poll() is None
    return r


def estado(carril):
    st = _st(carril)
    pid = st.get("pid")
    procs = _pythonw(carril)
    w = pb._principal(pid) if pid else None
    lock = _base(carril) / "app" / "gateway.lock"
    return {"carril": carril, "pid_primera": pid, "pythonw_de_la_copia": procs,
            "ventanas_principales": [x for p in procs for x in [pb._principal(p["pid"])] if x],
            "ventana_primera": w, "iconos_bandeja_por_pid": _iconos([p["pid"] for p in procs]),
            "escuchan_en_el_puerto": {st["puerto"]: _escuchan(st["puerto"])},
            "puente": pb._salud(st["puerto"]),
            "gateway_lock": json.loads(lock.read_text(encoding="utf-8")) if lock.exists() else None,
            "primer_plano": _fg()}


def _log_tail(carril, n=6):
    f = _base(carril) / "app" / "growi-bridge.log"
    return [l for l in f.read_text(encoding="utf-8").splitlines() if "instancia unica" in l
            or "ya esta corriendo" in l or "arrancado" in l][-n:]


def _despues(carril, antes, t0):
    st = _st(carril)
    w = pb._principal(st["pid"])
    arriba = _arriba_del_todo(w["hwnd"]) if w else (False, [])
    return {"antes": antes, "despues": estado(carril),
            "primera_visible": bool(w and w["visible"]), "primera_minimizada": bool(w and w["minimizada"]),
            "primera_en_primer_plano": _fg()["pid"] == st["pid"],
            "primera_arriba_en_orden_z": arriba[0], "ventanas_por_encima": arriba[1],
            "log": _log_tail(carril)}


def segunda(carril):
    st = _st(carril)
    w = pb._principal(st["pid"])
    antes = {"visible": w["visible"], "minimizada": w["minimizada"], "primer_plano": _fg()}
    t0 = time.time()
    p = _lanzar_proc(carril)
    try:
        rc = p.wait(30)
    except subprocess.TimeoutExpired:
        rc = "SIGUE VIVA a los 30 s"
    dur = round(time.time() - t0, 2)
    time.sleep(1.5)
    r = _despues(carril, antes, t0)
    r.update({"segunda_pid": p.pid, "segunda_codigo_salida": rc, "segunda_segundos": dur,
              "segunda_sigue_viva": p.poll() is None})
    return r


def segunda_basico(carril):
    """Segunda copia SIN elevar (integridad media) contra la primera elevada:
    una tarea programada con /RL LIMITED corre con el token filtrado del
    usuario (runas /trustlevel no sirve: su copia abria el mutex, error 183).
    Ahi CreateMutexW da error 5 y el evento tiene que dejarse marcar igual."""
    st = _st(carril)
    w = pb._principal(st["pid"])
    antes = {"visible": w["visible"], "minimizada": w["minimizada"], "primer_plano": _fg()}
    nivel = _base(carril) / "segunda-basico-whoami.txt"
    if nivel.exists():
        nivel.unlink()
    bat, rcf = _bat(carril, "segunda-basico", [f'whoami /groups > "{nivel}"'])
    tarea = "GrowiBridgePruebaMutexLimitada"
    t0 = time.time()
    _tarea(tarea, bat, "LIMITED")
    r = _esperar_rc(carril, antes, t0, rcf)
    subprocess.run(["schtasks", "/delete", "/tn", tarea, "/f"], capture_output=True)
    try:
        g = nivel.read_text(encoding="cp850", errors="replace")
        r["segunda_integridad"] = [l.split()[0] if l.split() else l for l in g.splitlines()
                                   if "S-1-16-" in l] or g[-300:]
        r["segunda_integridad_sid"] = [s for s in ("S-1-16-8192", "S-1-16-12288") if s in g]
    except OSError:
        r["segunda_integridad"] = "sin whoami"
    return r


def _tarea(nombre, bat, nivel):
    subprocess.run(["schtasks", "/create", "/tn", nombre, "/tr", f'cmd /c "{bat}"', "/sc", "once",
                    "/st", "23:59", "/rl", nivel, "/it", "/f"], capture_output=True)
    subprocess.run(["schtasks", "/run", "/tn", nombre], capture_output=True)


def primera_tarea(carril):
    """Para la copia actual y arranca la primera instancia como en la
    instalacion: tarea programada con /RL HIGHEST (GrowiBridgeApp usa
    HighestAvailable). El lockfile del pid anterior queda (obsoleto)."""
    salir(carril)
    bat, _rcf = _bat(carril, "primera-tarea")
    _tarea("GrowiBridgePruebaMutexPrimera", bat, "HIGHEST")
    procs = []
    for _ in range(30):
        time.sleep(1)
        procs = _pythonw(carril)
        if procs:
            break
    st = _st(carril)
    st["pid"] = procs[0]["pid"] if procs else None
    (_base(carril) / "prueba.json").write_text(json.dumps(st), encoding="utf-8")
    if st["pid"]:
        _esperar_ventana(st["pid"])
    subprocess.run(["schtasks", "/delete", "/tn", "GrowiBridgePruebaMutexPrimera", "/f"], capture_output=True)
    return estado(carril)


def error5(carril):
    """Fuerza la rama ERROR_ACCESS_DENIED de instancia_unica(): este proceso
    crea un mutex que solo SYSTEM puede abrir (D:(A;;GA;;;SY)), asi que la
    copia, aun elevada, recibe 5 de CreateMutexW; y crea el evento de mostrar
    derivado de ese nombre. La copia tiene que decir «ya hay otra», marcar el
    evento y salir con 0 sin abrir ventana ni puerto."""
    k32, adv = ctypes.windll.kernel32, ctypes.windll.advapi32
    k32.CreateMutexW.restype = ctypes.c_void_p
    k32.CreateEventW.restype = ctypes.c_void_p

    class SA(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)]
    sd = ctypes.c_void_p()
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW("D:(A;;GA;;;SY)", 1, ctypes.byref(sd), None)
    sa = SA(ctypes.sizeof(SA), sd, False)
    nombre = "Local\\GrowiBridgeInstanciaUnicaPruebaE5" + ("-carrilB" if carril == "b" else "")
    hm = k32.CreateMutexW(ctypes.byref(sa), False, nombre)
    he = k32.CreateEventW(None, False, False, nombre.replace("InstanciaUnica", "Mostrar"))
    # Comprobacion: abrir el mutex desde este mismo proceso elevado da 5.
    k32.OpenMutexW.restype = ctypes.c_void_p
    ho = k32.OpenMutexW(0x1F0001, False, nombre)
    err_propio = k32.GetLastError()
    env = dict(_env(carril), GROWI_BRIDGE_MUTEX=nombre)
    app = _base(carril) / "app"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    puerto = _st(carril)["puerto"]
    antes = _pythonw(carril)
    t0 = time.time()
    p = subprocess.Popen([str(pyw), str(app / "growi-bridge.py")], cwd=str(app), env=env)
    try:
        rc = p.wait(30)
    except subprocess.TimeoutExpired:
        rc = "SIGUE VIVA"
    dur = round(time.time() - t0, 2)
    marcado = k32.WaitForSingleObject(ctypes.c_void_p(he), 0) == 0
    for h in (hm, he, ho):
        if h:
            k32.CloseHandle(ctypes.c_void_p(h))
    return {"mutex": nombre, "openmutex_desde_aqui_error": err_propio, "copia_pid": p.pid,
            "copia_codigo_salida": rc, "copia_segundos": dur, "evento_marcado_por_la_copia": marcado,
            "pythonw_antes": [x["pid"] for x in antes], "pythonw_despues": [x["pid"] for x in _pythonw(carril)],
            "escuchan_en_el_puerto": {puerto: _escuchan(puerto)},
            "log": [l for l in (app / "growi-bridge.log").read_text(encoding="utf-8").splitlines()
                    if f"pid {p.pid})" in l or f"copia (pid {p.pid})" in l][-3:]}


def _bat(carril, nombre, antes=()):
    """Un .bat que arranca la segunda copia con el entorno de la prueba y deja
    su codigo de salida en <nombre>.rc (cmd espera a pythonw dentro de un .bat)."""
    env = _env(carril)
    app = _base(carril) / "app"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    bat, rcf = _base(carril) / f"{nombre}.bat", _base(carril) / f"{nombre}.rc"
    lineas = ["@echo off", *antes] + [f'set "{k}={env[k]}"' for k in env if k.startswith("GROWI_BRIDGE_")] + [
        f'cd /d "{app}"', f'"{pyw}" growi-bridge.py', f'echo %ERRORLEVEL% > "{rcf}"']
    bat.write_bytes(("\r\n".join(lineas) + "\r\n").encode("utf-8"))
    if rcf.exists():
        rcf.unlink()
    return bat, rcf


def _esperar_rc(carril, antes, t0, rcf):
    for _ in range(60):
        if rcf.exists():
            break
        time.sleep(0.5)
    dur = round(time.time() - t0, 2)
    time.sleep(1.5)
    r = _despues(carril, antes, t0)
    r.update({"segunda_codigo_salida": rcf.read_text().strip() if rcf.exists() else "sin codigo (no termino)",
              "segunda_segundos": dur})
    return r


def _teclas(texto):
    """Escribe texto con SendInput (KEYEVENTF_UNICODE), como el teclado."""
    class KI(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INP(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KI), ("pad", ctypes.c_byte * 8)]
    for ch in texto:
        for fl in (0x4, 0x4 | 0x2):
            i = INP(1, KI(0, ord(ch), fl, 0, 0))
            u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
        time.sleep(0.005)


def segunda_usuario(carril):
    """Segunda copia lanzada como la lanza una persona: Win+R, escribir la
    orden, Enter (teclado real con SendInput). Asi la copia nace con derecho
    a ceder el primer plano, que es el caso de un doble clic en el acceso."""
    st = _st(carril)
    w = pb._principal(st["pid"])
    antes = {"visible": w["visible"], "minimizada": w["minimizada"], "primer_plano": _fg()}
    bat, rcf = _bat(carril, "segunda-usuario")
    t0 = time.time()
    u32.keybd_event(0x5B, 0, 0, 0)  # Win
    u32.keybd_event(0x52, 0, 0, 0)  # R
    u32.keybd_event(0x52, 0, 2, 0)
    u32.keybd_event(0x5B, 0, 2, 0)
    time.sleep(1.2)
    _teclas(f'cmd /c "{bat}"')
    time.sleep(0.2)
    u32.keybd_event(0x0D, 0, 0, 0)
    u32.keybd_event(0x0D, 0, 2, 0)
    return _esperar_rc(carril, antes, t0, rcf)


def esconder(carril):
    st = _st(carril)
    w = pb._principal(st["pid"])
    # WM_CLOSE: el mismo camino que la X (protocolo WM_DELETE_WINDOW de Tk;
    # instalacion nueva del carril A = «minimizar a la bandeja»). Sin raton:
    # no toca las ventanas de quien este usando el PC.
    if carril == "a":
        u32.PostMessageW(w["hwnd"], 0x0010, 0, 0)
    else:  # el B pregunta en la X: se usa minimizar (WM_SYSCOMMAND SC_MINIMIZE)
        u32.PostMessageW(w["hwnd"], 0x0112, 0xF020, 0)
    time.sleep(1.5)
    w = pb._principal(st["pid"])
    return {"wm_close_a": w["hwnd"], "visible": w["visible"], "minimizada": w["minimizada"],
            "en_barra_de_tareas": w["en_barra_de_tareas"]}


def matar(carril):
    st = _st(carril)
    r = subprocess.run(["taskkill", "/F", "/PID", str(st["pid"])], capture_output=True, text=True,
                       encoding="cp850", errors="replace")
    time.sleep(2)
    lock = _base(carril) / "app" / "gateway.lock"
    return {"taskkill": (r.stdout + r.stderr).strip(), "pythonw_de_la_copia": _pythonw(carril),
            "gateway_lock_queda": json.loads(lock.read_text(encoding="utf-8")) if lock.exists() else None}


def watchdog(carril):
    """El watchdog real (watchdog-gateway.ps1) con las rutas y el puerto de la
    copia de prueba: mismas comprobaciones (puerto, gateway.lock + pid vivo,
    CommandLine) y mismo relanzado (iniciar-growi-bridge.bat)."""
    st = _st(carril)
    b = _base(carril)
    app = b / "app"
    (b / "watchdog").mkdir(exist_ok=True)
    src = (REPO / "watchdog-gateway.ps1").read_text(encoding="utf-8")
    ini = src.index("$lanes = @(")
    fin = src.index("function Log")
    lanes = ("$lanes = @(\n    @{ Name = '%s'; Port = %d; Dir = '%s'\n       State = '%s'\n"
             "       Match = { param($c) $c -like '*%s*' } }\n)\n\n") % (
        carril.upper(), st["puerto"], app, b / "watchdog" / "watchdog-state.json", app)
    ps = src[:ini] + lanes + src[fin:]
    ps = ps.replace("$wd  = 'C:\\Users\\forte\\growi-bridge\\watchdog'", f"$wd  = '{b / 'watchdog'}'")
    ps = ps.replace("Start-Sleep -Seconds 60", "Start-Sleep -Seconds 5")  # la espera de cortesia, mas corta
    f = b / "watchdog-prueba.ps1"
    f.write_text(ps, encoding="utf-8")
    t0 = time.time()
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(f)],
                       capture_output=True, text=True, env=_env(carril), encoding="utf-8", errors="replace")
    nuevos = []
    for _ in range(60):
        nuevos = _pythonw(carril)
        if nuevos and pb._principal(nuevos[0]["pid"]):
            break
        time.sleep(1)
    time.sleep(4)
    if nuevos:
        st["pid"] = nuevos[0]["pid"]
        (b / "prueba.json").write_text(json.dumps(st), encoding="utf-8")
    log = (b / "watchdog" / "watchdog.log")
    return {"rc_watchdog": r.returncode, "stderr": r.stderr[-400:], "segundos": round(time.time() - t0, 1),
            "watchdog_log": log.read_text(encoding="utf-8").splitlines()[-3:] if log.exists() else None,
            "despues": estado(carril), "log": _log_tail(carril)}


def salir(carril):
    for p in _pythonw(carril):
        subprocess.run(["taskkill", "/F", "/PID", str(p["pid"])], capture_output=True)
    time.sleep(1)
    return {"quedan": _pythonw(carril)}


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    c = args[0] if args else "a"
    r = {"lanzar": lambda: lanzar(c, int(args[1])), "arrancar": lambda: arrancar(c),
         "segunda": lambda: segunda(c), "segunda_basico": lambda: segunda_basico(c),
         "segunda_usuario": lambda: segunda_usuario(c), "primera_tarea": lambda: primera_tarea(c),
         "error5": lambda: error5(c),
         "esconder": lambda: esconder(c), "estado": lambda: estado(c), "matar": lambda: matar(c),
         "watchdog": lambda: watchdog(c), "salir": lambda: salir(c),
         "captura": lambda: pb.captura(args[1])}[cmd]()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
