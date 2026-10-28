"""Prueba de movimiento y alto contraste (ESTADO-MOVIMIENTO-CONTRASTE.md).

Dos arranques de la app real: «movimiento» (Windows sin animaciones, simulado
en el proceso) y «contraste» (Windows en alto contraste, simulado). No se
toca ningún ajuste de Windows.

  python pruebas/prueba_movimiento_contraste.py movimiento|contraste

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
OUT = REPO / "pruebas" / "evidencia" / "movimiento-contraste"
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


MODO = sys.argv[1] if len(sys.argv) > 1 else "movimiento"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-acc-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": True, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaAcc",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]  # (el modo ya se leyo)
    spec = importlib.util.spec_from_file_location("gb_acc", app / "growi-bridge.py")
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
        if MODO == "movimiento":
            anim = []
            for _ in range(60):  # 3 s mirando si la mascota se anima o el boton tiene animacion en curso
                anim.append((gb._mascot.get("animating"), bool(gb._power_anim.get("job"))))
                bombear(0.05)
            ev["a_sin_animaciones_windows"] = {"preferencia": gb.load_settings().get("reducir_movimiento") or "sistema",
                                               "windows_anima": gb.animaciones_sistema(),
                                               "mascota_animada_alguna_vez": any(a for a, _b in anim),
                                               "boton_animado_alguna_vez": any(b for _a, b in anim)}
            gb.set_power(not gb.state["power"])
            ev["a_boton_al_cambiar_sin_job"] = gb._power_anim.get("job") is None
            ev["b_tres_valores"] = {}
            for pref in ("sistema", "animar", "nunca"):
                gb.movimiento_poner(pref)
                ev["b_tres_valores"][pref] = gb.movimiento_permitido()
            gb.movimiento_poner("animar")
            gb._mascot_play("wave")
            ev["b_con_animar_la_mascota_se_mueve"] = gb._mascot.get("animating")
            W["show_page"]("ajustes")
            W["aj_ir_a"]("Reducir movimiento")
            bombear(1)
            captura("1-ajuste-reducir-movimiento")
        else:
            T = gb.THEME
            ev["d_alto_contraste"] = {"detectado": gb._TEMA.get("alto_contraste"),
                                      "sistema": {k: gb._sys_color(i) for k, i in (("fondo", 5), ("texto", 8),
                                                                                  ("boton", 15), ("seleccion", 13))},
                                      "tema_app": {k: T[k] for k in ("bg", "text", "sidebar", "blue", "line")}}
            ev["d_tokens_son_del_sistema"] = (T["bg"].lower() == gb._sys_color(5) and
                                              T["text"].lower() == gb._sys_color(8))
            for pag in ("estado", "tareas", "ajustes"):
                W["show_page"](pag)
                bombear(1.2)
                captura(f"2-contraste-{pag}")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "temas:" in x or "apariencia:" in x][-5:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / f"evidencia-{MODO}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
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
    if MODO == "movimiento":
        gb.animaciones_sistema = lambda: False  # Windows con los efectos de animacion apagados
    else:
        gb.alto_contraste_sistema = lambda: True  # Windows con un tema de contraste
    gb.maybe_onboarding = lambda: None
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
