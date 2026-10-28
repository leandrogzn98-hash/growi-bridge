"""Arnés de las pruebas GUI ocultas (desde la 0.4.5, a pedido de Leandro: el PC está en uso).

Arranca la app REAL (main() de una COPIA del repo, con share/cola/token/mutex propios y un puerto de prueba,
nunca 8787/8789). Ninguna ventana se muestra ni roba el foco: Tk y Toplevel nacen en withdraw(), y deiconify,
lift y focus_force no hacen nada. show_window, la mascota y el icono de bandeja se neutralizan. os.startfile se registra en vez de
abrir el Explorador. Se mide con cget/winfo_req*. Los clics corren el manejador enlazado (`disparar`), porque
event_generate no llega a ventanas sin mapear. Capturas solo con PRUEBA_VER=1 (a pedido).

Uso:
    from arnes_oculto import correr
    def pasos(h): ...          # h: Arnes (gb, W, ev, bombear, disparar, todos, guardar, ...)
    correr("carpetas", pasos, dpi="100", settings={...}, env={...})
"""

import ctypes
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VER = os.environ.get("PRUEBA_VER") == "1"
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:  # noqa: BLE001
    pass


def _ocultar_ventanas():
    import tkinter as tk

    def _oculta(base):
        class Oculta(base):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                base.withdraw(self)

            def deiconify(self):
                return None

            def lift(self, *a):
                return None

            def focus_force(self):
                return None
        Oculta.__name__ = base.__name__
        return Oculta
    tk.Tk = _oculta(tk.Tk)
    tk.Toplevel = _oculta(tk.Toplevel)


class _BandejaMuda:
    """Icono de bandeja que no se muestra: cualquier llamada (update_menu, notify, stop...) no hace nada."""
    visible = False
    title = ""

    def __getattr__(self, _nombre):
        return lambda *a, **k: None


class Arnes:
    def __init__(self, gb, app, tmp, out, pref, ev):
        self.gb, self.app, self.tmp, self.out, self.pref, self.ev = gb, app, tmp, out, pref, ev
        self.W = gb._widgets
        self.abiertos = []  # lo que la app pidió abrir con os.startfile

    def bombear(self, seg):
        fin = time.time() + seg
        while time.time() < fin:
            self.gb._root.update()
            time.sleep(0.03)

    def todos(self, w):
        out = [w]
        for ch in w.winfo_children():
            out += self.todos(ch)
        return out

    def disparar(self, widget, secuencia, **campos):
        """Corre el manejador enlazado a la secuencia del widget (como un clic o una tecla real).
        campos: valores de los campos del evento por su letra de Tk (w=ancho, h=alto, x, y...)."""
        guion = widget.bind(secuencia)
        if not guion:
            raise RuntimeError(f"{widget} no tiene {secuencia}")
        widget.tk.eval(re.sub(r"%(\S)", lambda m: str(widget) if m.group(1) == "W" else str(campos.get(m.group(1), 0)),
                         guion))

    def foto(self, nombre):
        if not VER:
            return
        from PIL import ImageGrab
        r = self.gb._root
        tk = self.gb.tk
        tk.Wm.deiconify(r)
        self.bombear(0.6)
        x, y = r.winfo_rootx(), r.winfo_rooty()
        ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True).save(
            self.out / f"{self.pref}-{nombre}.png")

    def log(self):
        return (self.app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")

    def guardar(self):
        log = self.log()
        self.ev["tracebacks_en_log"] = log.count("Traceback")
        (self.out / f"evidencia-{self.pref}.json").write_text(
            json.dumps(self.ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def correr(nombre, pasos, dpi="100", variante="ctk", settings=None, env=None, preparar=None, puerto=8795,
           fuente=None, espera_ms=6000, antes_de_main=None):
    """Arranca la app oculta y corre pasos(h) a los espera_ms de build_gui. Devuelve el dict de evidencia.

    preparar(app, tmp): siembra archivos antes de importar. antes_de_main(gb): parches tras importar."""
    out = REPO / "pruebas" / "evidencia" / nombre
    out.mkdir(parents=True, exist_ok=True)
    pref = f"{dpi}-{variante}"
    tmp = Path(tempfile.mkdtemp(prefix=f"growi-prueba-{nombre}-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json", "*.patch"))
    if fuente:
        shutil.copy(fuente, app / "growi-bridge.py")
    (app / "secret.txt").write_text(f"prueba-{nombre}", encoding="utf-8")
    st = {"lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": False, "auto_update": False,
          "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": puerto, "on_close": "quit",
          "keep_awake": True, "apariencia": "oscuro"}
    st.update(settings or {})
    (app / "settings.json").write_text(json.dumps(st), encoding="utf-8")
    (tmp / "share" / "outbox" / "runner-results").mkdir(parents=True)
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            if isinstance(m.get("autenticacion"), dict):
                m["autenticacion"].pop("sesion_cli", None)
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    if preparar:
        preparar(app, tmp)
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX=f"Local\\GrowiPrueba{nombre}",
                      GROWI_BRIDGE_PORT=str(puerto), GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      GROWI_BRIDGE_DPI="144" if dpi == "150" else "96")
    if variante == "clasica":
        os.environ["GROWI_BRIDGE_CTK"] = "0"
    os.environ.update(env or {})
    if not VER:
        _ocultar_ventanas()
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location(f"gb_{nombre}", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    ev = {"copia": str(tmp), "variante": variante, "dpi": dpi}
    h = Arnes(gb, app, tmp, out, pref, ev)
    gb.os.startfile = lambda p, *a, **k: h.abiertos.append(str(p))  # nunca abre el Explorador
    if not VER:
        gb.show_window = lambda *a, **k: None
        gb.show_mascot = lambda *a, **k: gb._mascot.update(win="prueba")
        gb.hide_mascot = lambda *a, **k: gb._mascot.update(win=None)
        gb.build_tray = lambda *a, **k: _BandejaMuda()  # sin icono en la bandeja del sistema
    if antes_de_main:
        antes_de_main(gb)
    orig = gb.build_gui

    def _seguro():
        try:
            pasos(h)
        except Exception:  # noqa: BLE001
            ev["error_prueba"] = traceback.format_exc()
        try:
            h.guardar()
        finally:
            gb.quit_app()

    def build():
        t0 = time.perf_counter()
        root = orig()
        ev["build_gui_s"] = round(time.perf_counter() - t0, 2)
        root.after(espera_ms, _seguro)
        return root
    gb.build_gui = build
    gb.main()
    print(json.dumps(ev, ensure_ascii=True, indent=1, default=str), flush=True)
    os._exit(0)
