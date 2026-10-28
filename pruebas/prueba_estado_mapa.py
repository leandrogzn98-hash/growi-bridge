"""Prueba de «Ver el mapa» (ESTADO-ESTADO-MAPA.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8797). Pulsa el botón «Ver el mapa» del banner (invoke)
desde Estado y desde Tareas y mide si la tarjeta del mapa queda visible y
resaltada, y si el resalte se va solo (o con un clic). 150 = DPI 144 y
ventana al tamaño mínimo.

  python pruebas/prueba_estado_mapa.py 100
  python pruebas/prueba_estado_mapa.py 150
"""

import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
MINIMA = DPI == "150"
OUT = REPO / "pruebas" / "evidencia" / "estado-mapa"
u32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def raton(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def teclas(texto):
    class KI(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INP(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KI), ("pad", ctypes.c_byte * 8)]
    for ch in texto:
        for fl in (0x4, 0x6):
            i = INP(1, KI(0, ord(ch), fl, 0, 0))
            u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
        time.sleep(0.03)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-mapa-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaMapa",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      GROWI_BRIDGE_DPI="144" if DPI == "150" else "96")
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_mapa", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp)}
    W = gb._widgets

    def captura(nombre):
        from PIL import ImageGrab
        r = gb._root
        x, y = r.winfo_rootx(), r.winfo_rooty()
        ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def centro(w):
        return w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2

    def bombear(seg):
        fin = time.time() + seg
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def _todos(w):
        out = [w]
        for ch in w.winfo_children():
            out += _todos(ch)
        return out

    def foto(nombre):
        r = gb._root
        r.attributes("-topmost", False)
        r.attributes("-topmost", True)
        r.lift()
        bombear(0.3)
        captura(f"{DPI}-{nombre}")

    def textos_mapa():
        out = []
        for w in _todos(W["mapa_card"]):
            try:
                t = str(w.cget("text"))
            except Exception:
                continue
            if t and "Comprobado" not in t and "hace" not in t:
                out.append(t)
        return out

    def medir(nombre):
        card = W["mapa_card"]
        cv = next(c for c in gb._scroll_canvases if c.winfo_ismapped())
        top_v, bot_v = cv.winfo_rooty(), cv.winfo_rooty() + cv.winfo_height()
        top, alto = card.winfo_rooty(), card.winfo_height()
        hijos = [w for w in _todos(card) if type(w) in (gb.tk.Frame, gb.tk.Label)]
        ev[nombre] = {"pagina": W.get("pagina_actual"), "tarjeta_arriba_px": top - top_v,
                      "alto_tarjeta": alto, "alto_visible": bot_v - top_v,
                      "arriba_visible": top_v <= top < bot_v,
                      "entera_visible": top >= top_v and top + alto <= bot_v,
                      "borde": [card.cget("highlightthickness"), card.cget("highlightbackground")],
                      "fondo_hijos": sorted({str(w.cget("bg")) for w in hijos})}

    def boton_ver_mapa():
        b = W["cloud_banner"]
        return next(w for w in _todos(b) if "Button" in type(w).__name__ and w.cget("text") == "Ver el mapa")

    def pasos():
        r = gb._root
        r.deiconify()
        if MINIMA:
            mw, mh = r.minsize()
            r.geometry(f"{mw}x{mh}")
        ev["ventana"] = {"escala": gb.SCALE, "minima": MINIMA}
        W["show_page"]("estado")
        bombear(2.0)
        gb._ULTIMA["d"] = {"tarea": "t-x", "motor": "llama", "modelo": "hermes-3-8b-q4_k_m", "status": "ok",
                           "error": "", "at": gb._now_iso()}  # el banner con «Ver el mapa» a la vista
        gb.runner_heartbeat()
        bombear(6.0)
        ev["e_filas_antes"] = textos_mapa()
        medir("a_antes")
        foto("a-antes")
        boton_ver_mapa().invoke()
        bombear(0.6)
        medir("a_despues_desde_estado")
        foto("a-despues-resaltado")
        bombear(3.2)  # (c) se quita solo a los ~3 s
        medir("c_tras_3s")
        foto("c-tras-3s")
        # (b) desde Tareas
        W["show_page"]("tareas")
        bombear(1.0)
        boton_ver_mapa().invoke()
        bombear(0.6)
        medir("b_desde_tareas")
        foto("b-desde-tareas")
        # la siguiente interacción también lo quita
        W["av_when"].event_generate("<Button-1>")
        bombear(0.3)
        medir("c_tras_un_clic")
        ev["e_filas_despues"] = textos_mapa()
        ev["e_filas_iguales"] = ev["e_filas_antes"] == ev["e_filas_despues"]
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "Ver el mapa" in x][-3:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / f"evidencia-{DPI}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                                   encoding="utf-8")
        gb.quit_app()

    def _textos(w):
        out = []
        for ch in w.winfo_children():
            try:
                out.append(str(ch.cget("text")))
            except Exception:
                pass
            out += _textos(ch)
        return out

    orig = gb.build_gui

    def build():
        root = orig()
        root.after(6000, lambda: _seguro(pasos))
        return root

    def _seguro(fn):
        try:
            fn()
        except Exception:
            import traceback
            ev["error_prueba"] = traceback.format_exc()
            (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
            gb.quit_app()
    gb.build_gui = build
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
