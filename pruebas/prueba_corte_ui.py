"""Prueba de la prueba de corte: protocolo, checklist y registro (ESTADO-PRUEBA-CORTE.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada):
abre «Prueba de corte» desde la paleta, mira el checklist y registra en el
resiliencia.log DE LA COPIA una línea «sin prueba» y otra marcada «simulado».
NO corta la luz (eso lo hace Leandro, nunca un programa).

  python pruebas/prueba_corte_ui.py
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
OUT = REPO / "pruebas" / "evidencia" / "prueba-corte"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-corte-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaCorte",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_corte", app / "growi-bridge.py")
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

    def captura_top(nombre):
        from PIL import ImageGrab
        t = gb._CORTE["top"]
        t.update()
        x, y = t.winfo_rootx(), t.winfo_rooty()
        ImageGrab.grab((x, y, x + t.winfo_width(), y + t.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def pasos():
        r = gb._root
        r.deiconify()
        # (a) desde la paleta
        cmd = next(c for c in gb._PALETTE_CMDS if c["id"] == "prueba_corte")
        ev["a_paleta"] = cmd["label"]
        cmd["fn"]()
        bombear(1.5)
        top = gb._CORTE["top"]
        top.attributes("-topmost", True)
        ev["a_ventana"] = top.title()
        ev["a_protocolo_en_la_app"] = gb.PROTOCOLO_CORTE.exists()
        # (c) el checklist con lo que la app ve ahora (sin tarea larga en curso)
        ev["c_checklist"] = gb.corte_checklist()
        captura_top("1-protocolo-y-checklist")
        # (b) registrar: «real» sin decir qué se cortó no se guarda
        k = gb._CORTE["kit"]
        seg = gb._CORTE["tipo"]
        seg.set("Real (breaker o desenchufar)") if hasattr(seg, "_keys") else seg.var.set("real")
        gb._corte_guardar()
        bombear(0.3)
        ev["b_real_sin_datos"] = gb._CORTE["msg"].cget("text")
        # «sin prueba este mes» (con un clic)
        gb._corte_sin_prueba()
        bombear(0.3)
        # una prueba SIMULADA (marcada como tal) para ver el formato completo
        seg.set("Simulado") if hasattr(seg, "_keys") else seg.var.set("simulado")
        for key, val in (("cortado", "SIMULADO en la prueba automática: no se cortó la luz"),
                         ("perdido", "nada (no hubo corte)"), ("solo", "—"), ("a_mano", "—"),
                         ("notas", "línea de ejemplo de la prueba del formulario; no es una prueba de corte")):
            gb._CORTE["campos"][key].insert(0, val)
        gb._corte_guardar()
        bombear(0.5)
        ev["b_mensaje"] = gb._CORTE["msg"].cget("text")
        ev["b_resiliencia_log"] = gb.RESIL_LOG.read_text(encoding="utf-8").splitlines()
        top.winfo_children()[0].yview_moveto(1.0)  # el canvas con scroll de la ventana
        bombear(0.4)
        captura_top("2-registro")
        top.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "prueba de corte" in x][-6:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
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
