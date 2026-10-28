"""Prueba de la página «Sobre mí» (ESTADO-PERFIL-SOBRE-MI.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada):
abre «Sobre mí» desde Ajustes, escribe con el teclado de verdad (se guarda
solo), mira lo que recibiría la siguiente tarea, la abre desde la paleta,
exporta y borra (con aviso). El paso por el runner real está en
prueba_perfil_runner.py.

  python pruebas/prueba_perfil_gui.py
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
OUT = REPO / "pruebas" / "evidencia" / "perfil-sobre-mi"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-perfilgui-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaPerfil",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_perfil_gui", app / "growi-bridge.py")
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
        preguntas = []
        gb.messagebox.askyesno = lambda t, m, **k: (preguntas.append(m), True)[1]
        # (a) desde Ajustes -> General -> «Editar mi perfil»
        W["show_page"]("ajustes")
        bombear(1.5)
        btn = None
        for w in _todos(gb._root):
            try:
                if "Button" in type(w).__name__ and str(w.cget("text")) == "Editar mi perfil":
                    btn = w
            except Exception:
                pass
        ev["a_boton_en_ajustes"] = btn is not None
        btn.invoke()
        bombear(1.0)
        ev["a_pagina"] = W.get("pagina_actual")
        ev["a_estado_sin_perfil"] = gb._PRF["estado"].cget("text")
        captura("1-sobre-mi-vacio")
        # escribir con el teclado de verdad en «Quién soy» y «Qué vendo / qué hago»
        for key, texto in (("quien", "Leandro, de Barquisimeto."),
                           ("hago", "HAYAI: implementacion de IA y automatizacion. Summit Maker con Angelis.")):
            tb = gb._PRF["campos"][key]
            tb.focus_set()
            bombear(0.3)
            raton(*centro(tb))
            bombear(0.3)
            teclas(texto)
            bombear(0.3)
        bombear(1.5)  # guardado solo (700 ms despues de la ultima tecla)
        ev["a_estado_tras_escribir"] = gb._PRF["estado"].cget("text")
        ev["a_archivo"] = gb.perfil_archivo().read_text(encoding="utf-8") if gb.perfil_archivo().exists() else None
        ev["a_leido"] = gb.perfil_leer()
        captura("2-sobre-mi-guardado")
        # (b) lo que la siguiente tarea recibiría (el runner lo prueba aparte, con tareas reales)
        ev["b_bloque_prompt"] = gb.perfil_bloque_prompt({"id": "t-gui-1", "prompt": "Saluda a un cliente."})
        # desde la paleta
        W["show_page"]("estado")
        bombear(0.5)
        cmd = next(c for c in gb._PALETTE_CMDS if c["id"] == "perfil")
        ev["paleta"] = cmd["label"]
        cmd["fn"]()
        bombear(0.8)
        ev["paleta_lleva_a"] = W.get("pagina_actual")
        # (d) exportar y borrar
        dest = tmp / "perfil-exportado.md"
        gb.filedialog.asksaveasfilename = lambda **k: str(dest)
        boton_txt("Exportar").invoke()
        bombear(0.5)
        ev["d_exportado"] = {"existe": dest.exists(), "estado": gb._PRF["estado"].cget("text"),
                             "contenido": dest.read_text(encoding="utf-8") if dest.exists() else None}
        boton_txt("Borrar mi perfil").invoke()
        bombear(0.8)
        ev["d_borrado"] = {"pregunta": preguntas[-1] if preguntas else None,
                           "archivo_existe": gb.perfil_archivo().exists(),
                           "aviso": gb._PRF["estado"].cget("text"),
                           "siguiente_tarea": gb.perfil_bloque_prompt({"id": "t-gui-2", "prompt": "Saluda."})}
        captura("3-borrado")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "perfil" in x][-10:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        gb.quit_app()

    def boton_txt(texto):
        for w in _todos(gb._root):
            try:
                if type(w).__name__ in ("CTkButton", "Button") and str(w.cget("text")) == texto:
                    return w
            except Exception:
                pass
        raise LookupError(texto)

    def _todos(w):
        out = [w]
        for ch in w.winfo_children():
            out += _todos(ch)
        return out

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
