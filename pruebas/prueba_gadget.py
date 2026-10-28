"""Prueba de la puerta USB/serie del gadget (ESTADO-GADGET-ESP32.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8797). Sin hardware: el gadget es pruebas/emulador_gadget.py
en tcp://127.0.0.1:8830. Lista los puertos serie REALES del PC, elige y abre el
emulador desde la ventana, conversa (las órdenes se teclean), y dos PEDIR del
emulador (R2 y R3) pasan por el runner real de la copia.

  python pruebas/prueba_gadget.py
"""

import ctypes
import subprocess
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
EMU = 8830
OUT = REPO / "pruebas" / "evidencia" / "gadget"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-gadget-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaGadget",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    (tmp / "trabajo").mkdir()
    (tmp / "trabajo" / "viejo.txt").write_text("x", encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp / "trabajo")]}), encoding="utf-8")
    emu = subprocess.Popen([sys.executable, str(REPO / "pruebas" / "emulador_gadget.py"), str(EMU),
                            "--pedir", f"Borra el archivo {tmp / 'trabajo' / 'viejo.txt'}.",
                            "--pedir", f"Borra en masa todo con rm -rf {tmp / 'trabajo'}."])
    time.sleep(1.0)
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_gadget", app / "growi-bridge.py")
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
        ev["a_puertos_reales"] = gb.gadget_puertos()
        ev["seguridad_sin_elegir"] = gb.gadget_abrir("COM3")  # nunca abre uno que no se eligió
        top = gb.gadget_ui()
        top.attributes("-topmost", True)
        top.lift()
        bombear(1.5)
        cap(top, "1-gadget-puertos-reales")
        ui = gb._GADGET["ui"]
        ui["cb"].set(f"tcp://127.0.0.1:{EMU}")
        ui["abrir"]()
        bombear(1.5)
        ev["c_abierto"] = ui["est"].cget("text")
        for orden in ("PING", "LED ON", "MOSTRAR Hola Leandro", "ESTADO", "BAILA"):
            ui["ent"].delete(0, "end")
            ui["ent"].insert(0, orden)
            bombear(0.3)
            ui["enviar"]()
            bombear(0.4)
            ev.setdefault("b_conversacion", []).append([ui["ent"].get(), ui["est"].cget("text")])
        cap(top, "2-gadget-conversacion")
        # lo que el gadget pidió (PEDIR) pasa por el runner real de la copia
        fin = time.time() + 40
        fams = {}
        while time.time() < fin:
            bombear(1.0)
            fams = {}
            for f in (gb.RESULTS).glob("t-serie-*.orquestacion.json"):
                d = json.loads(f.read_text(encoding="utf-8"))
                fams[f.name.split(".")[0]] = {"estado": d.get("estado"),
                                              "aprobacion": (d.get("aprobacion") or {}).get("estado"),
                                              "motivo": str(d.get("motivo_decision") or "")[:160]}
            if len(fams) >= 2 and all(v["estado"] in ("esperando_aprobacion", "necesita_decision") for v in fams.values()):
                break
        ev["d_pedidos_por_serie"] = fams
        st = json.loads((app / "settings.json").read_text(encoding="utf-8"))
        ev["c_puerto_registrado_en_settings"] = st.get("gadget_puerto")
        gb.gadget_cerrar()
        bombear(0.5)
        ev["c_gadget_log"] = (app / "gadget.log").read_text(encoding="utf-8").splitlines()
        top.destroy()
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "gadget:" in x][-10:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        gb.quit_app()

    def cap(w, nombre):
        from PIL import ImageGrab
        w.attributes("-topmost", False)
        w.attributes("-topmost", True)
        w.lift()
        w.focus_force()
        bombear(0.6)
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
    try:
        gb.main()
    finally:
        emu.kill()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
