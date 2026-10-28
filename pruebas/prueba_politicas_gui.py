"""Prueba del editor de reglas permanentes (ESTADO-POLITICAS-PERSISTENTES.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada):
Ajustes -> Permisos y seguridad -> «Editar reglas»: crea, edita y revoca
(con confirmación) reglas, y mira el registro de decisiones. El paso por el
runner real está en prueba_politicas_runner.py.

  python pruebas/prueba_politicas_gui.py
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
OUT = REPO / "pruebas" / "evidencia" / "politicas"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-polgui-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaPol",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_pol_gui", app / "growi-bridge.py")
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

    def boton_txt(texto, base=None, n=0):
        hall = []
        for w in _todos(base or gb._root):
            try:
                if ({c.__name__ for c in type(w).__mro__} & {"CTkButton", "Button"}) and str(w.cget("text")) == texto:
                    hall.append(w)
            except Exception:
                pass
        if len(hall) <= n:
            raise LookupError(texto)
        return hall[n]

    def captura_top(nombre):
        from PIL import ImageGrab
        t = gb._POLUI["top"]
        t.update()
        x, y = t.winfo_rootx(), t.winfo_rooty()
        ImageGrab.grab((x, y, x + t.winfo_width(), y + t.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def reglas_txt():
        return [gb.politica_frase(r) for r in gb.politicas_leer()[0]]

    def pasos():
        r = gb._root
        r.deiconify()
        RESP = [True]
        preguntas = []
        gb.messagebox.askyesno = lambda t, m, **k: (preguntas.append(m), RESP[0])[1]
        carpeta = str(tmp / "compartida")
        os.makedirs(carpeta, exist_ok=True)
        # (b) desde Ajustes -> Permisos y seguridad -> «Editar reglas»
        W["show_page"]("ajustes")
        bombear(1.5)
        boton_txt("Editar reglas").invoke()
        bombear(1.5)
        top = gb._POLUI["top"]
        top.attributes("-topmost", True)
        ev["b_editor_abierto"] = top.winfo_exists() and top.title()
        # crear: «Permitir siempre: escribir fuera … en compartida»
        ids = [t for t, _l in gb._POLUI["tipos"]]
        gb._POLUI["accion"].current(ids.index("escribir_fuera"))
        gb._POLUI["carpeta"].insert(0, carpeta)
        boton_txt("Añadir regla", top).invoke()
        bombear(0.6)
        ev["b_creada"] = {"mensaje": gb._POLUI["msg"].cget("text"), "reglas": reglas_txt()}
        # intentar «Permitir siempre» algo R2 (borrar): no se deja
        gb._POLUI["accion"].current(ids.index("borrar"))
        boton_txt("Añadir regla", top).invoke()
        bombear(0.4)
        ev["b_allow_R2_rechazado"] = gb._POLUI["msg"].cget("text")
        gb._pol_limpiar()
        # otra: «No permitir nunca: borrar en cualquier carpeta»
        gb._POLUI["accion"].current(ids.index("borrar_recursivo"))
        seg = gb._POLUI["decision"]
        if hasattr(seg, "_keys"):
            seg.set("No permitir nunca")
        else:
            seg.var.set("deny")
        boton_txt("Añadir regla", top).invoke()
        bombear(0.6)
        ev["b_dos_reglas"] = reglas_txt()
        captura_top("1-editor-dos-reglas")
        # editar la primera: pasa a «Preguntar siempre»
        boton_txt("Editar", top, 0).invoke()
        bombear(0.4)
        ev["b_editando"] = gb._POLUI["msg"].cget("text")
        if hasattr(seg, "_keys"):
            seg.set("Preguntar siempre")
        else:
            seg.var.set("ask")
        boton_txt("Guardar cambios", top).invoke()
        bombear(0.6)
        ev["b_editada"] = reglas_txt()
        # revocar: primero «no» (se queda), luego «sí» (se va)
        RESP[0] = False
        boton_txt("Revocar", top, 0).invoke()
        bombear(0.4)
        ev["b_revocar_dijo_no"] = {"pregunta": preguntas[-1], "reglas": reglas_txt()}
        RESP[0] = True
        boton_txt("Revocar", top, 0).invoke()
        bombear(0.6)
        ev["b_revocada"] = reglas_txt()
        ev["b_politicas_json"] = json.loads(gb.POL_FILE.read_text(encoding="utf-8"))
        # (f) el registro, en la misma ventana
        ev["f_registro"] = [t for _e, t in gb.politicas_auditoria(10)]
        captura_top("2-editor-registro")
        top.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "políticas" in x][-8:]
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
