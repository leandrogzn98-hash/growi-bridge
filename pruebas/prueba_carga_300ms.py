"""Prueba de la regla de los 300 ms (ESTADO-CARGA-300MS.md).

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
OUT = REPO / "pruebas" / "evidencia" / "carga-300ms"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-carga-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaCarga",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_carga", app / "growi-bridge.py")
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
        bombear(3)  # la ventana ya pintada: el primer update() tarda casi 1 s y falsearia la medida
        # (a) medir: 100 ms -> nada; 600 ms -> carga; 1500 ms -> carga+detalle
        gb._CARGA_REG.clear()
        vistos = []
        for ms in (100, 600, 1500):
            gb.con_carga(f"prueba {ms} ms", lambda ms=ms: time.sleep(ms / 1000), lambda _r: None,
                         mostrar=lambda ms=ms: vistos.append((ms, "mostrar")),
                         detalle=lambda t, ms=ms: vistos.append((ms, "detalle")), texto="x")
        bombear(2.2)
        ev["a_registro"] = list(gb._CARGA_REG)
        ev["a_que_se_mostro"] = vistos
        # (b) esqueleto en Modelos: la lista tarda 2 s
        orig_rma = gb.run_model_action
        gb.run_model_action = lambda *a, **k: (time.sleep(2), orig_rma(*a, **k))[1]
        gb._mdl["installed"] = None
        gb._mdl["list_req"] = None
        gb.state["runner"] = "parado"  # asi la lista va por run_model_action (la lenta de la prueba)
        W["show_page"]("modelos")
        gb.request_models_list(force=True)
        gb._render_models()
        bombear(0.15)
        box = W["mdl_installed_box"]
        ev["b_a_150ms_esqueleto"] = any(getattr(c, "_esqueleto", False) for c in box.winfo_children())
        bombear(0.5)
        ev["b_a_650ms_esqueleto"] = any(getattr(c, "_esqueleto", False) for c in box.winfo_children())
        ev["b_debug"] = {"hijos": [type(c).__name__ + ("*" if getattr(c, "_esqueleto", False) else "")
                                   for c in box.winfo_children()], "lib": len(gb.lib_installed()),
                         "installed": gb._mdl["installed"], "carga": [gb._mdl["carga"].patron,
                                                                      gb._mdl["carga"].hecha]}
        try:
            cv = box.winfo_toplevel()
            canvas = W["mdl_installed_box"]
            par = canvas
            while par is not None and par.winfo_class() != "Canvas":
                par = par.master
            if par is not None:
                inner = par.winfo_children()[0] if par.winfo_children() else None
                y = box.winfo_rooty() - par.winfo_rooty() + par.canvasy(0) - 120
                par.yview_moveto(max(0, y) / max(1, float(par.bbox("all")[3])))
                bombear(0.2)
        except Exception as e:
            ev["b_scroll_err"] = str(e)
        captura("1-modelos-esqueleto")
        bombear(0.7)
        ev["b_a_1350ms_texto"] = [c.cget("text") for c in box.winfo_children() if getattr(c, "_esq_txt", False)]
        captura("2-modelos-esqueleto-con-texto")
        bombear(3)
        ev["b_al_llegar_la_lista_sin_esqueleto"] = not any(getattr(c, "_esqueleto", False)
                                                          for c in box.winfo_children())
        gb.run_model_action = orig_rma
        # (b2) esqueleto en Skills: el indice sigue «leyendo» 1,5 s
        W["show_page"]("skills")
        bombear(1)
        gb._SKX["estado"], gb._SKX["at"] = "carga", None
        gb._skb_render()
        lista = W["skb_lista"]

        def hay():
            return any(getattr(c, "_esqueleto", False) for c in lista.winfo_children())
        bombear(0.15)
        ev["b2_skills_150ms_esqueleto"] = hay()
        bombear(0.5)
        ev["b2_skills_650ms_esqueleto"] = hay()
        gb._skb_render()  # el repintado no lo borra
        ev["b2_skills_tras_repintar_esqueleto"] = hay()
        par = lista
        while par is not None and par.winfo_class() != "Canvas":
            par = par.master
        if par is not None:
            par.yview_moveto(0)
        bombear(0.6)
        ev["b2_skills_1250ms_estado"] = W["skb_estado"].cget("text")
        captura("1b-skills-esqueleto")
        gb.skills_indexar("prueba")  # el indice de verdad
        gb._skb_render()
        bombear(0.3)
        ev["b2_skills_al_llegar_sin_esqueleto"] = not hay()
        ev["b2_registro_skills"] = [x for x in gb._CARGA_REG if x[0] == "lista de skills"]
        # (c) boton con spinner y sin doble clic (raton de verdad)
        llamadas = {"n": 0}
        gb.check_update_available = lambda: (llamadas.__setitem__("n", llamadas["n"] + 1), time.sleep(2), None)[2]
        W["show_page"]("ajustes")
        W["aj_ir_a"]("buscar actualizaciones")
        bombear(0.5)
        b = W["aj_buscar_act"]
        x, y = centro(b)
        raton(x, y)
        bombear(0.05)
        raton(x, y)  # segundo clic: no debe lanzar otra busqueda
        bombear(0.5)
        ev["c_boton_a_550ms"] = {"texto": b.cget("text"), "estado": str(b.cget("state"))}
        captura("3-boton-spinner")
        bombear(2.5)
        ev["c_boton_al_final"] = {"texto": b.cget("text"), "estado": str(b.cget("state"))}
        ev["c_busquedas_lanzadas_con_2_clics"] = llamadas["n"]
        # (d) descarga: el texto real de progreso
        ev["d_progreso"] = gb.lib_progress_text({"bytes": 126 * 1048576, "total": 609 * 1048576,
                                                 "estado": "descargando", "speed": 10.8 * 1048576, "eta": 45})
        ev["d_progreso_sin_velocidad_aun"] = gb.lib_progress_text({"bytes": 1048576, "total": 609 * 1048576,
                                                                  "estado": "descargando", "speed": None})
        # (e) fila «Trabajando…» en Tareas para una tarea en curso sin resultado
        gb._live_active = lambda: {"task_id": "t-prueba-trabajando", "raiz": "t-prueba-trabajando",
                                   "estado": "corriendo"}
        gb._live_values = lambda lv, corto=False: {"estado": "corriendo", "motor": "claude (sonnet)",
                                                   "tiempo": "42 s", "tokens": "1.2k / 300", "costo": "~$0.01",
                                                   "revision": "—"}
        W["show_page"]("tareas")
        gb._apply_live_to_tree()
        bombear(0.5)
        t = W["tasks_tree"]
        ev["e_fila"] = list(t.item("t-prueba-trabajando", "values")) if t.exists("t-prueba-trabajando") else None
        captura("4-tareas-trabajando")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "carga:" in x][-8:]
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
