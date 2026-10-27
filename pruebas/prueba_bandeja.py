"""Prueba de «minimizar a la bandeja» (ESTADO-MINIMIZAR-BANDEJA.md).

Arranca una copia AISLADA de growi-bridge.py de este repo (carril A) en
%TEMP%\\growi-prueba-bandeja: share, cola, token, mutex y puerto propios
(GROWI_BRIDGE_SHARE / _COLA / _TOKEN_DIR / _MUTEX / _PORT), asi que no toca
la app instalada ni su puerto 8787. Despues la maneja con el raton de verdad
(SendInput) y lee el estado de las ventanas con la API de Windows.

  python pruebas/prueba_bandeja.py lanzar [puerto] [a|b]  arranca la copia (sin on_close: instalacion nueva)
  python pruebas/prueba_bandeja.py estado            ventanas, barra de tareas, icono, puente, tasklist
  python pruebas/prueba_bandeja.py x                 clic real en la X de la ventana
  python pruebas/prueba_bandeja.py min               clic real en el boton minimizar
  python pruebas/prueba_bandeja.py dobleclic         doble clic real en el icono de la bandeja
  python pruebas/prueba_bandeja.py menu <texto>      clic derecho en el icono y clic en la opcion
  python pruebas/prueba_bandeja.py clic <x> <y>      clic real en un punto de la pantalla
  python pruebas/prueba_bandeja.py captura <nombre>  captura de pantalla en <prueba>\\capturas
  python pruebas/prueba_bandeja.py ajuste            on_close guardado en settings.json
  python pruebas/prueba_bandeja.py fin_sesion        WM_QUERYENDSESSION + WM_ENDSESSION a sus ventanas
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("TEMP", ".")) / "growi-prueba-bandeja"
ESTADO = BASE / "prueba.json"
SECRETO = "prueba-bandeja-secreto"

u32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # coordenadas fisicas, como las del raton
except Exception:
    u32.SetProcessDPIAware()

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
u32.SendMessageW.restype = ctypes.c_ssize_t
u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                    wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u32.GetWindow.restype = wintypes.HWND


def _st():
    return json.loads(ESTADO.read_text(encoding="utf-8"))


def _ventanas(pid):
    out = []

    def cb(h, _l):
        p = wintypes.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            cls = ctypes.create_unicode_buffer(256)
            tit = ctypes.create_unicode_buffer(256)
            u32.GetClassNameW(h, cls, 256)
            u32.GetWindowTextW(h, tit, 256)
            ex = u32.GetWindowLongPtrW(h, -20)  # GWL_EXSTYLE
            owner = u32.GetWindow(h, 4)  # GW_OWNER
            vis = bool(u32.IsWindowVisible(h))
            tool, app = bool(ex & 0x80), bool(ex & 0x40000)
            out.append({"hwnd": h, "clase": cls.value, "titulo": tit.value, "visible": vis,
                        "minimizada": bool(u32.IsIconic(h)),
                        # Regla de Windows para la barra de tareas y Alt+Tab.
                        "en_barra_de_tareas": vis and not tool and (not owner or app)})
        return True
    u32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT),
                ("rcNormalPosition", wintypes.RECT)]


def _area(h):
    """Area de la posicion normal (una ventana minimizada mide casi 0 en
    GetWindowRect: -32000,-32000)."""
    wp = WINDOWPLACEMENT(ctypes.sizeof(WINDOWPLACEMENT))
    u32.GetWindowPlacement(h, ctypes.byref(wp))
    r = wp.rcNormalPosition
    return (r.right - r.left) * (r.bottom - r.top)


def _principal(pid):
    """La ventana principal: la TkTopLevel «Growi Bridge» mas grande (la
    mascota es otra TkTopLevel pequena con el mismo titulo)."""
    cands = [w for w in _ventanas(pid) if w["clase"] == "TkTopLevel" and w["titulo"].startswith("Growi Bridge")]
    return max(cands, key=lambda w: _area(w["hwnd"])) if cands else None


class NOTIFYICONIDENTIFIER(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("guidItem", ctypes.c_byte * 16)]


def _icono(pid):
    """(hwnd de la ventana de pystray, rect del icono en la bandeja o None)."""
    for w in _ventanas(pid):
        m = re.match(r"GrowiBridgeB?(\d+)SystemTrayIcon$", w["clase"])
        if m:
            nid = NOTIFYICONIDENTIFIER(ctypes.sizeof(NOTIFYICONIDENTIFIER), w["hwnd"],
                                       int(m.group(1)) & 0xFFFFFFFF)
            r = wintypes.RECT()
            hr = ctypes.windll.shell32.Shell_NotifyIconGetRect(ctypes.byref(nid), ctypes.byref(r))
            return w["hwnd"], ((r.left, r.top, r.right, r.bottom) if hr == 0 else None)
    return None, None


def _raton(x, y, boton="izq", veces=1):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    down, up = (0x0002, 0x0004) if boton == "izq" else (0x0008, 0x0010)
    for _ in range(veces):
        u32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.05)
        u32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.08)


def _boton_titulo(hwnd, hit):
    """Centro del boton de la barra de titulo (HTCLOSE=20, HTMINBUTTON=8).
    Windows 11 dibuja los botones (DWM) mas anchos que el diseno clasico que
    contesta WM_NCHITTEST: el «minimizar» de WM_NCHITTEST cae en el borde del
    «maximizar» visible. Por eso se usan los limites que da DWM
    (DWMWA_CAPTION_BUTTON_BOUNDS: minimizar | maximizar | cerrar)."""
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    b = wintypes.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 5, ctypes.byref(b), ctypes.sizeof(b)) == 0 \
            and b.right > b.left:
        ancho = (b.right - b.left) / 3
        i = {8: 0, 9: 1, 20: 2}[hit]
        return int(r.left + b.left + ancho * (i + 0.5)), int(r.top + (b.top + b.bottom) / 2)
    filas = {}
    for dy in range(0, 60, 2):
        y = r.top + dy
        xs = [x for x in range(r.right - 2, r.left, -2)
              if u32.SendMessageW(hwnd, 0x0084, 0, ((y & 0xFFFF) << 16) | (x & 0xFFFF)) == hit]
        if xs:
            filas[y] = xs
    if not filas:
        return None
    ys = sorted(filas)
    y = ys[len(ys) // 2]  # la fila del medio del boton, no el borde
    return (min(filas[y]) + max(filas[y])) // 2, y


def _salud(puerto):
    out = {}
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 127.0.0.1 sin proxy
    for ruta in ("/gateway/salud", "/health"):
        req = urllib.request.Request(f"http://127.0.0.1:{puerto}{ruta}", headers={"X-Shared-Secret": SECRETO})
        try:
            with op.open(req, timeout=5) as r:
                out[ruta] = f"HTTP {r.status} {r.read().decode()[:120]}"
        except urllib.error.HTTPError as e:
            out[ruta] = f"HTTP {e.code} {e.read().decode()[:120]}"
        except Exception as e:
            out[ruta] = f"sin respuesta ({type(e).__name__}: {e})"
    return out


def _tasklist(pid):
    r = subprocess.run(["tasklist", "/v", "/fi", f"PID eq {pid}", "/fo", "list"],
                       capture_output=True, text=True, encoding="cp850", errors="replace")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def _pythonw_growi():
    """Procesos python/pythonw cuyo comando es la copia de prueba."""
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        if "python" in (p.info["name"] or "").lower() and str(BASE) in cl:
            out.append({"pid": p.pid, "name": p.info["name"], "cmdline": cl})
    return out


def lanzar(puerto=8795, carril="a"):
    if BASE.exists():  # todo menos las capturas de corridas anteriores
        for p in BASE.iterdir():
            if p.name != "capturas":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    app = BASE / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__"))
    if os.environ.get("PRUEBA_GB_ORIGEN"):  # otra version de growi-bridge.py (p. ej. la de antes del cambio)
        shutil.copy2(os.environ["PRUEBA_GB_ORIGEN"], app / "growi-bridge.py")
    (app / "secret.txt").write_text(SECRETO, encoding="utf-8")
    # Instalacion nueva: SIN on_close. Mascota encendida para ver que sigue y que se cierra.
    (app / "settings.json").write_text(json.dumps({
        "lane": carril, "onboarding_done": True, "guardrail": "nunca", "mascot": True,
        "auto_update": False, "copia_claude": False, "motor_local_parar_al_salir": False,
        "bridge_port": puerto}, indent=2), encoding="utf-8")
    (BASE / "claude-projects-vacia").mkdir()
    env = dict(os.environ, GROWI_BRIDGE_SHARE=str(BASE / "share"), GROWI_BRIDGE_COLA=str(BASE / "cola.db"),
               GROWI_BRIDGE_TOKEN_DIR=str(BASE / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaBandeja",
               GROWI_BRIDGE_PORT=str(puerto), GROWI_BRIDGE_CLAUDE_PROJECTS=str(BASE / "claude-projects-vacia"),
               GROWI_BRIDGE_LANE=carril)
    pyw = Path(sys.executable).with_name("pythonw.exe")
    p = subprocess.Popen([str(pyw), str(app / "growi-bridge.py")], cwd=str(app), env=env)
    ESTADO.write_text(json.dumps({"pid": p.pid, "puerto": puerto, "app": str(app)}), encoding="utf-8")
    for _ in range(60):
        time.sleep(1)
        if _principal(p.pid) and _icono(p.pid)[0]:
            break
    time.sleep(3)
    return {"pid": p.pid, "puerto": puerto, "app": str(app),
            "settings_al_arrancar": json.loads((app / "settings.json").read_text(encoding="utf-8"))}


def estado():
    st = _st()
    pid = st["pid"]
    hw, rect = _icono(pid)
    vivo = bool(_pythonw_growi())
    return {"pid": pid, "proceso_vivo": vivo,
            "ventana_principal": _principal(pid) if vivo else None,
            "ventanas_visibles": [w for w in _ventanas(pid) if w["visible"]],
            "en_barra_de_tareas": [w["titulo"] for w in _ventanas(pid) if w["en_barra_de_tareas"]],
            "icono_bandeja": {"ventana_pystray": hw, "rect": rect} if hw else None,
            "puente": _salud(st["puerto"]), "tasklist_v": _tasklist(pid),
            "pythonw_de_la_prueba": _pythonw_growi()}


def boton(hit):
    pid = _st()["pid"]
    w = _principal(pid)
    pt = _boton_titulo(w["hwnd"], hit)
    if not pt:
        return {"error": "no encontre el boton (WM_NCHITTEST)"}
    _raton(*pt)
    time.sleep(1.5)
    return {"clic_en": pt, "hit": hit}


def _desborde():
    """Iconos del desborde «^» de Windows 11 (lo abre si hace falta)."""
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(Path(__file__).with_name("bandeja_uia.ps1")), "json_ocultos"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(r.stdout.strip() or "[]")
    except ValueError:
        return []


def _menu_abierto():
    """(hwnd, pid) del menu contextual abierto (#32768) o (0, 0)."""
    h = u32.FindWindowW("#32768", None)
    if not h or not u32.IsWindowVisible(h):
        return 0, 0
    p = wintypes.DWORD()
    u32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return h, p.value


def _escape():
    u32.keybd_event(0x1B, 0, 0, 0)
    u32.keybd_event(0x1B, 0, 2, 0)
    time.sleep(0.5)


def _donde_esta_mi_icono(pid):
    """Centro del icono de ESTA copia. Shell_NotifyIconGetRect no sirve para
    iconos del desborde de Windows 11, asi que: si esta a la vista se usa
    ese rect; si no, se prueba clic derecho en cada icono «Growi» del
    desborde y vale el que abre un menu de NUESTRO pid (los demas: Escape,
    sin tocar nada de la app instalada ni del carril B)."""
    _hw, rect = _icono(pid)
    if rect:
        return ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2), "barra de tareas (Shell_NotifyIconGetRect)"
    for it in _desborde():
        if not re.search(r"Growi|Permisos|Gasto", it["name"]):
            continue
        c = (it["x"] + it["w"] // 2, it["y"] + it["h"] // 2)
        _raton(*c, boton="der")
        time.sleep(0.9)
        _h, mpid = _menu_abierto()
        _escape()
        if mpid == pid:
            return c, "desborde ^ (clic derecho verificado: el menú es del pid de la prueba)"
        _desborde()  # se cerro al pulsar Escape: se vuelve a abrir para el siguiente
    return None, "no encontre el icono"


def dobleclic():
    pid = _st()["pid"]
    c, como = _donde_esta_mi_icono(pid)
    if not c:
        return {"error": como}
    if "desborde" in como:
        _desborde()
    _raton(*c, veces=2)
    time.sleep(1.5)
    return {"doble_clic_en": c, "icono": como}


def menu(texto):
    pid = _st()["pid"]
    c, como = _donde_esta_mi_icono(pid)
    if not c:
        return {"error": como}
    if "desborde" in como:
        _desborde()
    _raton(*c, boton="der")
    time.sleep(1.0)
    hmenu_win, mpid = _menu_abierto()
    if not hmenu_win:
        return {"error": "no aparecio el menu contextual"}
    if mpid != pid:
        _escape()
        return {"error": f"el menu abierto es del pid {mpid}, no de la prueba ({pid}): no se pulsa nada"}
    hmenu = u32.SendMessageW(hmenu_win, 0x01E1, 0, 0)  # MN_GETHMENU
    items = []
    for i in range(u32.GetMenuItemCount(hmenu)):
        b = ctypes.create_unicode_buffer(256)
        u32.GetMenuStringW(hmenu, i, b, 256, 0x400)  # MF_BYPOSITION
        items.append(b.value)
    idx = next((i for i, t in enumerate(items) if t.startswith(texto)), None)
    if idx is None:
        u32.keybd_event(0x1B, 0, 0, 0)
        u32.keybd_event(0x1B, 0, 2, 0)
        return {"error": f"no hay «{texto}» en el menu", "menu": items}
    r = wintypes.RECT()
    u32.GetMenuItemRect(None, hmenu, idx, ctypes.byref(r))
    _raton((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(2)
    return {"menu": items, "clic_en": texto, "icono": como, "menu_del_pid": mpid}


def captura(nombre):
    from PIL import ImageGrab
    d = BASE / "capturas"
    d.mkdir(exist_ok=True)
    f = d / f"{nombre}.png"
    ImageGrab.grab(all_screens=True).save(f)
    return {"captura": str(f)}


def fin_sesion():
    """Lo que hace Windows al cerrar sesion: WM_QUERYENDSESSION a cada ventana
    de nivel superior del proceso y, si todas dicen que si, WM_ENDSESSION."""
    pid = _st()["pid"]
    ws = _ventanas(pid)
    res = {"ventanas": [(w["clase"], w["titulo"]) for w in ws], "query": [], "end": []}
    logoff = 0x80000000  # ENDSESSION_LOGOFF
    for w in ws:
        r = ctypes.c_size_t()
        ok = u32.SendMessageTimeoutW(w["hwnd"], 0x0011, 0, logoff, 0x2, 5000, ctypes.byref(r))
        res["query"].append({"clase": w["clase"], "respuesta": r.value if ok else "sin respuesta"})
    t0 = time.time()
    for w in ws:
        r = ctypes.c_size_t()
        ok = u32.SendMessageTimeoutW(w["hwnd"], 0x0016, 1, logoff, 0x2, 20000, ctypes.byref(r))
        res["end"].append({"clase": w["clase"], "volvio": bool(ok), "s": round(time.time() - t0, 1)})
    for _ in range(20):
        if not _pythonw_growi():
            break
        time.sleep(0.5)
    res["s_hasta_salir"] = round(time.time() - t0, 1)
    res["pythonw_de_la_prueba_despues"] = _pythonw_growi()
    return res


def ajuste():
    s = json.loads((Path(_st()["app"]) / "settings.json").read_text(encoding="utf-8"))
    return {"on_close": s.get("on_close", "(sin clave)"), "close_toast_shown": s.get("close_toast_shown")}


def log_tail(n=12):
    f = Path(_st()["app"]) / "growi-bridge.log"
    return f.read_text(encoding="utf-8").splitlines()[-n:]


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    r = {"lanzar": lambda: lanzar(int(args[0]) if args else 8795, args[1] if len(args) > 1 else "a"), "estado": estado,
         "x": lambda: boton(20), "min": lambda: boton(8), "dobleclic": dobleclic,
         "menu": lambda: menu(args[0]), "clic": lambda: (_raton(int(args[0]), int(args[1])), {"clic": args})[1],
         "captura": lambda: captura(args[0]), "fin_sesion": fin_sesion, "ajuste": ajuste,
         "log": lambda: log_tail(int(args[0]) if args else 12)}[cmd]()
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str))
