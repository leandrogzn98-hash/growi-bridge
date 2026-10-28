"""Prueba de la pagina Ajustes reorganizada (ESTADO-AJUSTES-REORG.md).

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
OUT = REPO / "pruebas" / "evidencia" / "ajustes-reorg"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-ajustes-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaAjustes",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_aj", app / "growi-bridge.py")
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

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        W["show_page"]("ajustes")
        r.update()
        time.sleep(1.5)
        r.update()
        tab = W["aj_buscar"].master.master
        grupos = []
        for w in tab.winfo_children():
            try:
                t = w.cget("text")
            except Exception:
                continue
            f = None
            try:
                f = w.cget("font")
                f = f.cget("size") if hasattr(f, "cget") else f
            except Exception:
                pass
            if t and f == 17:
                grupos.append(t)
        ev["a_grupos_en_orden"] = grupos
        ev["a_filas_por_grupo"] = {}
        for grupo, _fila in W["aj_filas"]:
            ev["a_filas_por_grupo"][grupo] = ev["a_filas_por_grupo"].get(grupo, 0) + 1
        captura("1-ajustes-arriba")
        # (b) buscar «proxy» con el teclado de verdad
        raton(*centro(W["aj_buscar"]))
        r.update()
        teclas("proxy")
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        ev["b_resultado_buscador"] = W["aj_buscar_res"].cget("text")
        captura("2-buscar-proxy")
        canvas = W["aj_buscar"].master.master.master
        ev["b_scroll_y"] = canvas.yview()
        # (c) pulsar de verdad «No suspender mientras trabaja» y leer settings.json
        W["aj_ir_a"]("suspender")
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        sw = W["keepawake_sw"]
        antes = json.loads((app / "settings.json").read_text(encoding="utf-8")).get("keep_awake")
        raton(*centro(sw))
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        despues = json.loads((app / "settings.json").read_text(encoding="utf-8")).get("keep_awake")
        ev["c_keep_awake_settings_json"] = {"antes": antes, "despues_del_clic": despues,
                                            "interruptor": bool(sw.get())}
        captura("3-interruptor-guardado")
        raton(*centro(sw))  # se deja como estaba
        r.update()
        # (d) zona peligrosa
        W["aj_ir_a"]("zona peligrosa")
        for _ in range(10):
            r.update()
            time.sleep(0.05)
        ev["d_buscador_zona"] = W["aj_buscar_res"].cget("text")
        ev["d_zona_peligrosa_textos"] = sorted({t for g, f in W["aj_filas"] if g == "Zona peligrosa"
                                                for t in _textos(f) if t.strip()})[:12]
        captura("4-zona-peligrosa")
        # (b2) otros terminos
        ev["b2_otros"] = {}
        for q in ("tema", "atajo", "carpetas", "exportar config", "motor"):
            W["aj_ir_a"](q)
            r.update()
            ev["b2_otros"][q] = W["aj_buscar_res"].cget("text")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log_ajustes"] = [x for x in log.splitlines() if "ajustes:" in x][-12:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
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
    gb.maybe_onboarding = lambda: None
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
