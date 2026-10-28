"""Prueba del interruptor por motor (ESTADO-INTERRUPTOR-MOTOR.md).

(Basada en prueba_ajustes_reorg.py: app real en 8797, raton de verdad.)

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
OUT = REPO / "pruebas" / "evidencia" / "interruptor-motor"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-onoff-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True, "default_engine": "sonnet"}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaOnOff",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_onoff", app / "growi-bridge.py")
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

    def pasos():
        import hashlib
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        eng_antes = hashlib.sha256((app / "engines.json").read_bytes()).hexdigest()
        ev["antes"] = {"selector": [c[1] for c in gb.engine_choices()], "codex": gb.engine_status("codex")}
        W["show_page"]("modelos")
        bombear(1.5)
        cb = W["mot_sel"]
        lab = next(l for l, m in gb._MOT["ids"].items() if m == "codex")
        cb.set(lab)
        gb._mot_render()
        bombear(0.5)
        b = W["mot_onoff_btn"]
        par = b
        while par is not None and par.winfo_class() != "Canvas":
            par = par.master
        if par is not None:
            y = b.winfo_rooty() - par.winfo_rooty() + par.canvasy(0) - 200
            par.yview_moveto(max(0, y) / max(1, float(par.bbox("all")[3])))
            bombear(0.5)
        raton(*centro(b))  # clic de verdad en «Desactivar este motor»
        bombear(1)
        captura("1-codex-desactivado")
        ev["a_tras_clic"] = {"boton": b.cget("text"), "estado": W["mot_onoff"].cget("text"),
                             "selector": [c[1] for c in gb.engine_choices()],
                             "engine_status": gb.engine_status("codex"),
                             "router_disponible": gb._router_available("codex"),
                             "tarea_con_codex": gb.validate_task({"id": "t1", "prompt": "x", "motor": "codex"})[1],
                             "motores_off": gb.load_settings().get("motores_off")}
        ev["b_engines_json_intacto"] = hashlib.sha256((app / "engines.json").read_bytes()).hexdigest() == eng_antes
        ev["b_descriptor_codex_sigue"] = "codex" in gb.engine_ids() and bool(gb.engine_raw("codex"))
        raton(*centro(b))  # reactivar: un clic
        bombear(1)
        ev["c_reactivar"] = {"boton": b.cget("text"), "estado": W["mot_onoff"].cget("text"),
                             "en_selector": "motor:codex" in [c[1] for c in gb.engine_choices()]}
        orig = gb._resolve_binary
        gb._resolve_binary = lambda eng: None if (eng or {}).get("id") == "codex" else orig(eng)
        gb.motor_activar("codex", False)
        ev["c_reactivar_sin_binario"] = gb.motor_activar("codex", True)
        gb._resolve_binary = orig
        ev["d_principal_sin_sustituto"] = gb.motor_activar("claude", False)
        ev["d_principal_con_sustituto"] = gb.motor_activar("claude", False, sustituto="codex")
        ev["d_tras_sustituir"] = {"principal": gb.default_motor(), "default_engine": gb.load_settings().get(
            "default_engine"), "claude_en_selector": any(c[1] in ("sonnet", "opus", "haiku") for c in gb.engine_choices())}
        gb.motor_activar("claude", True)
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "motores: «" in x][-6:]
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
