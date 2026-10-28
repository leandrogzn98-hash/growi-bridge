"""Prueba de las herramientas MCP en «Qué puede hacer» (ESTADO-MCP-STREAMABLE-HTTP.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada):
abre Modelos, ve las herramientas MCP (última lista real de DeepWiki) con su
interruptor, apaga una con el ratón y abre la ventana MCP.

  python pruebas/prueba_mcp_gui.py
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
OUT = REPO / "pruebas" / "evidencia" / "mcp"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-mcpgui-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True, "mcp_servidor": True,
        "mcp_cache": {"deepwiki": [[n, "herramienta de DeepWiki"] for n, _a in json.loads(
            (OUT / "evidencia.json").read_text(encoding="utf-8"))["c_deepwiki_herramientas"]["tools"]]}}),
        encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaMcp",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_mcp_gui", app / "growi-bridge.py")
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

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        W["show_page"]("modelos")
        bombear(2.0)
        box = W["mdl_abilities_box"]
        gb._scroll_a(box)
        bombear(0.6)
        filas = [f for f in box.winfo_children() if f.winfo_children()]
        mcp = []
        for f in filas:
            t = [str(w.cget("text")) for w in _todos(f) if isinstance(w, gb.tk.Label)]
            if t and t[0].startswith("MCP"):
                mcp.append((t[0], f))
        ev["c_filas_mcp_en_que_puede_hacer"] = [t for t, _f in mcp]
        captura("1-que-puede-hacer-con-mcp")
        # apagar con el ratón el interruptor de la primera herramienta MCP
        t0, f0 = mcp[0]
        sw = next(w for w in _todos(f0) if isinstance(w, gb.tk.Canvas))
        raton(*centro(sw))
        bombear(0.8)
        st = json.loads((app / "settings.json").read_text(encoding="utf-8"))
        ev["c_tras_clic"] = {"fila": t0, "apagadas_en_settings": st.get("mcp_herramientas_apagadas"),
                             "lo_que_ve_el_runner": gb.mcp_usar("deepwiki", t0.split(": ", 1)[1], {})}
        captura("2-mcp-apagada")
        r.attributes("-topmost", False)
        top = gb.mcp_ui()
        top.attributes("-topmost", True)
        top.lift()
        bombear(8.0)
        x, y = top.winfo_rootx(), top.winfo_rooty()
        from PIL import ImageGrab
        ImageGrab.grab((x, y, x + top.winfo_width(), y + top.winfo_height()), all_screens=True).save(OUT / "3-ventana-mcp.png")
        ev["servidor_mcp"] = {"escucha": gb._MCP["server"].server_address if gb._MCP["server"] else None}
        top.destroy()
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "mcp:" in x][-8:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia-gui.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
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
            (OUT / "evidencia-gui.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
            gb.quit_app()
    gb.build_gui = build
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
