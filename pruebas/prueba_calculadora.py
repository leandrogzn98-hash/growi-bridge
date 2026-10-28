"""Prueba de la calculadora de la paleta (ESTADO-CALCULADORA-PALETA.md).

(Basada en prueba_ajustes_reorg.py: app real en 8797, teclado de verdad.)

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada) y,
desde su propio bucle de Tk, abre Ajustes y la usa con el raton y el teclado
de verdad (SetCursorPos + mouse_event, SendInput): lee los grupos en orden,
escribe «proxy» en el buscador, pulsa un interruptor y mira settings.json,
y abre la zona peligrosa. Captura cada paso y sale con quit_app.

  python pruebas/prueba_ajustes_reorg.py
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
OUT = REPO / "pruebas" / "evidencia" / "calculadora"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-calc-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaCalc",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_calc", app / "growi-bridge.py")
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

    def portapapeles():
        u32.OpenClipboard(None)
        try:
            u32.GetClipboardData.restype = ctypes.c_void_p
            h = u32.GetClipboardData(13)  # CF_UNICODETEXT
            k32 = ctypes.windll.kernel32
            k32.GlobalLock.restype = ctypes.c_void_p
            p = k32.GlobalLock(ctypes.c_void_p(h))
            t = ctypes.wstring_at(p) if p else None
            k32.GlobalUnlock(ctypes.c_void_p(h))
            return t
        finally:
            u32.CloseClipboard()

    def filas():
        st = gb._palette.get("st") or {}
        return [r[2].get("label") for r in st.get("rows") or []]

    def escribir(texto):
        pal = gb._palette["win"]
        e = gb._palette["entry"]
        pal.lift()
        pal.focus_force()
        e.focus_force()
        e.delete(0, "end")
        r = gb._root
        for _ in range(5):
            r.update()
            time.sleep(0.03)
        teclas(texto)
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        return filas()

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        gb._open_palette()
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        ev["a_120x0.4"] = escribir("120*0.4")
        captura_pal("1-calculo")
        u32.keybd_event(0x0D, 0, 0, 0)
        u32.keybd_event(0x0D, 0, 2, 0)
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        ev["b_portapapeles_tras_enter"] = portapapeles()
        gb._open_palette()
        r.update()
        ev["a2_coma_decimal_279,58/1070"] = escribir("279,58/1070")
        ev["a3_split_40_40_20"] = escribir("1500*0.4")
        ev["c_codigo_no_se_evalua"] = escribir("__import__('os').system('calc')")
        ev["c2_division_por_cero"] = escribir("120/0")
        ev["c3_numero_enorme"] = escribir("99999999999999999*99999999999")
        ev["d_divisas_no_inventa"] = escribir("100 USD a Bs")
        ev["e_busqueda_normal_ajustes"] = escribir("ajustes")[:4]
        ev["e2_numero_solo_no_es_cuenta"] = escribir("2026")[:3]
        captura_pal("2-busqueda-normal")
        gb._palette["win"].destroy()
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "calculadora" in x][-3:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        gb.quit_app()

    def captura_pal(nombre):
        from PIL import ImageGrab
        w = gb._palette["win"]
        x, y = w.winfo_rootx(), w.winfo_rooty()
        ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

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
    gb.maybe_onboarding = lambda: None
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
