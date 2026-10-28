"""Prueba del modelo por superficie y niveles Auto (ESTADO-MODELO-POR-SUPERFICIE.md).

(Basada en prueba_ajustes_reorg.py: app real en 8797.)

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
OUT = REPO / "pruebas" / "evidencia" / "modelo-superficie"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-sup-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaSup",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_sup", app / "growi-bridge.py")
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
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        W["show_page"]("ajustes")
        W["aj_ir_a"]("Modelo para")
        bombear(1)
        captura("1-selectores")
        cbs = W["aj_superficie"]
        ev["a_selectores"] = {k: v.get() for k, v in cbs.items()}
        # elegir Codex para el chat (como el usuario: valor + evento)
        lab_codex = gb._label_de_modelo("motor:codex")
        cbs["chat"].set(lab_codex)
        cbs["chat"].event_generate("<<ComboboxSelected>>")
        bombear(0.5)
        ev["a_tras_elegir_chat"] = gb.load_settings().get("modelo_superficie")
        lab_haiku = gb._label_de_modelo("haiku")
        cbs["revision"].set(lab_haiku)
        cbs["revision"].event_generate("<<ComboboxSelected>>")
        bombear(0.3)
        ev["a_tras_elegir_revision"] = gb.load_settings().get("modelo_superficie")
        ev["a_chat_usa_su_modelo"] = gb._default_engine_label(gb.engine_choices())
        # (b) el nivel cambia la decision real del router
        enc = "Escribe una función en Python que ordene una lista y explica cómo funciona"
        ev["b_router"] = {}
        for nv in ("rapido", "equilibrado", "potente"):
            gb.auto_nivel_poner(nv)
            dec, err = gb.route_task(enc)
            ev["b_router"][nv] = {"elegido": (dec or {}).get("elegido"), "motivo": (dec or {}).get("motivo"),
                                  "error": err}
        gb.auto_nivel_poner("equilibrado")
        ev["b_visible_en_paleta"] = [c["label"] for c in gb._PALETTE_CMDS if c["id"].startswith("auto_")]
        ev["b_segmentado_ajustes"] = W["aj_auto_nivel"].get()
        # (c) perfil con modelo propio
        ev["c_perfil_codex"] = gb.asis_motor_tarea({"nombre": "Prueba", "modelo": "codex"})
        gb.motor_activar("codex", False)
        bombear(0.3)
        ev["c_perfil_codex_apagado"] = gb.asis_motor_tarea({"nombre": "Prueba", "modelo": "codex"})
        # (d) el chat tenia Codex: al apagar codex vuelve a Automatico con aviso
        ev["d_tras_apagar_codex"] = gb.load_settings().get("modelo_superficie")
        gb.motor_activar("codex", True)
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "superficies:" in x or "router: modo" in x][-8:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        gb.quit_app()

    toasts = []
    gb.toast = lambda t, c=None: toasts.append(t)

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
