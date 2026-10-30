"""(c) lado APP: abre la ventana real de la copia aislada, escribe en «Pedirle
algo» (pagina Tareas) y pulsa el boton «Enviar» de verdad (invoke). Guarda una
captura y el id. Uso: python encolar_desde_app.py <prompt> <criterio> <motor-label>"""
import ctypes
import importlib.machinery
import importlib.util
import json
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

APP = Path(r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app")
EVI = APP.parent / "evidencia"
EVI.mkdir(exist_ok=True)
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
prompt, criterio, label = sys.argv[1], sys.argv[2], sys.argv[3]
src = APP / "growi-bridge.py"
ld = importlib.machinery.SourceFileLoader("growi_bridge", str(src))
spec = importlib.util.spec_from_file_location("growi_bridge", src, loader=ld)
gb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gb)
gb._dpi_awareness()
root = gb.build_gui()
root.geometry("1100x1400+40+10")
root.update()
gb._widgets["show_page"]("tareas")
root.update()
w = gb._widgets
w["ask_text"].insert("1.0", prompt)
w["ask_criterios"].insert("1.0", criterio)
labels = list(w["ask_engine"].cget("values"))
assert label in labels, (label, labels)
w["ask_engine"].set(label)
root.update()


def boton(wd, texto):
    for ch in wd.winfo_children():
        try:
            if ch.cget("text") == texto:
                return ch
        except Exception:
            pass
        b = boton(ch, texto)
        if b is not None:
            return b
    return None


antes = set(p.name for p in gb.TASKS.glob("*.task.json"))
gb._scroll_a(w["ask_text"])
root.update()
b = boton(w["ask_text"].master, "Enviar")
assert b is not None, "no encuentro el boton Enviar"
b.invoke()
for _ in range(10):
    root.update()
    time.sleep(0.1)
nuevos = sorted(set(p.name for p in gb.TASKS.glob("*.task.json")) - antes)
estado_txt = w["ask_status"].cget("text")


def captura(nombre):
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    ww, hh = r.right - r.left, r.bottom - r.top
    dc = u.GetWindowDC(hwnd)
    mdc = g.CreateCompatibleDC(dc)
    bmp = g.CreateCompatibleBitmap(dc, ww, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16),
                    ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32),
                    ("x", ctypes.c_int32), ("y", ctypes.c_int32), ("c", ctypes.c_uint32), ("i", ctypes.c_uint32)]
    bi = BIH(ctypes.sizeof(BIH), ww, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(ww * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    from PIL import Image
    Image.frombuffer("RGBA", (ww, hh), buf, "raw", "BGRA", 0, 1).convert("RGB").save(EVI / nombre)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(hwnd, dc)
    return str(EVI / nombre)


try:
    cap = captura("app-pedirle-algo-enviado.png")
except Exception as e:
    cap = f"captura no disponible: {e}"
print(json.dumps({"pid": os.getpid(), "nuevos": nuevos, "ask_status": estado_txt, "captura": cap,
                  "boton": type(b).__name__}, ensure_ascii=False))
root.destroy()
