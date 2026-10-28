"""Prueba de la barra lateral 0.4.5 (ESTADO-BARRA-LATERAL.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8796) en tema oscuro, sin tareas ni gasto (contadores en 0),
y luego siembra tareas, gasto de hoy, fallos del mapa y modelos (contadores en N).

  python pruebas/prueba_barra_lateral.py 100
  python pruebas/prueba_barra_lateral.py 150
  python pruebas/prueba_barra_lateral.py 100 clasica    (GROWI_BRIDGE_CTK=0)
  python pruebas/prueba_barra_lateral.py 100 arranque [fuente.py]   (solo mide build_gui)

La ventana NUNCA se muestra ni roba el foco (el PC está en uso): la raíz queda en withdraw(), show_window y la
mascota se neutralizan, y se mide con winfo_req*. Capturas solo con PRUEBA_VER=1 (a pedido).
"""

import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODO = "oscuro"
DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VARIANTE = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = Path(sys.argv[3]) if len(sys.argv) > 3 else None
OUT = REPO / "pruebas" / "evidencia" / "barra-lateral"
VER = os.environ.get("PRUEBA_VER") == "1"
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def _ocultar_ventanas():
    """Toda ventana Tk de la prueba nace oculta y no se puede mostrar ni ponerse delante (el PC está en uso)."""
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


def _area_trabajo_alto():
    """Alto del área de trabajo de Windows (pantalla menos la barra de tareas)."""
    from ctypes import wintypes
    rc = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0)  # SPI_GETWORKAREA
    return rc.bottom - rc.top


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-barra-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json", "*.patch"))
    if FUENTE:
        shutil.copy(FUENTE, app / "growi-bridge.py")
    (app / "secret.txt").write_text("prueba-barra", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8796, "on_close": "quit",
        "keep_awake": True, "apariencia": MODO}), encoding="utf-8")
    res = tmp / "share" / "outbox" / "runner-results"
    res.mkdir(parents=True)
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaBarra",
                      GROWI_BRIDGE_PORT="8796", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      GROWI_BRIDGE_DPI="144" if DPI == "150" else "96")
    if VARIANTE == "clasica":
        os.environ["GROWI_BRIDGE_CTK"] = "0"
    if not VER:
        _ocultar_ventanas()
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_barra", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp), "variante": VARIANTE, "dpi": DPI}
    W = gb._widgets
    pref = f"{DPI}-{VARIANTE}"

    def bombear(seg):
        fin = time.time() + seg
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def foto(nombre):
        if not VER:  # oculta: sin capturas
            return
        from PIL import ImageGrab
        r = gb._root
        if r.state() != "normal":  # si algo la mandó a la bandeja, se vuelve a mostrar para la captura
            r.deiconify()
        r.attributes("-topmost", False)
        r.attributes("-topmost", True)
        r.lift()
        bombear(0.5)
        x, y = r.winfo_rootx(), r.winfo_rooty()
        im = ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True)
        im.save(OUT / f"{pref}-{nombre}.png")
        ev.setdefault("fotos", {})[nombre] = {"caja": (x, y, r.winfo_width(), r.winfo_height()),
                                              "estado": r.state(), "negra": im.convert("L").getextrema() == (0, 0)}

    def todos(w):
        out = [w]
        for ch in w.winfo_children():
            out += todos(ch)
        return out

    def txt(k):
        return W[k].cget("text") if W.get(k) is not None else None

    def contadores():
        return {n: txt(f"nav_count_{n}") for n in ("estado", "modelos", "tareas")}

    def pintar():
        gb.refresh_ui()
        bombear(0.3)

    def fam(tid, est):
        (res / f"{tid}.orquestacion.json").write_text(json.dumps({
            "raiz": tid, "estado": est, "motor": "claude", "ronda": 1, "actualizado": gb._now_iso(),
            "tareas": [tid], "encargo": "tarea de prueba"}), encoding="utf-8")

    def cabe(alto):
        """Lo que hay empaquetado en la barra (alto pedido) cabe en el alto mínimo de la ventana."""
        sb = W["sidebar"]
        partes = [w for w in sb.winfo_children() if w.winfo_manager()]
        pedido = sum(w.winfo_reqheight() for w in partes)
        return {"alto_pedido_barra": pedido, "alto_minimo": alto, "todo_dentro": pedido <= alto,
                "partes": len(partes), "buscar_acciones_visible": bool(W["kc_chip"].master.winfo_manager()),
                "detalle_consumo_visible": bool(W["sb_consumo_det"].winfo_manager())}

    def disparar(w, secuencia):
        """Corre el manejador enlazado a la secuencia (oculta, event_generate no llega a ventanas sin mapear)."""
        import re
        guion = re.sub(r"%(\S)", lambda m: str(w) if m.group(1) == "W" else "0", w.bind(secuencia))
        w.tk.eval(guion)

    def pulsar(sw):
        """Clic en el interruptor (CTk: su canvas; clásico: el Canvas), sin tocar el foco del sistema."""
        if hasattr(sw, "toggle"):
            sw.toggle()  # lo mismo que hace su <Button-1> / <space>
        else:
            disparar(sw, "<Button-1>")

    def pasos():
        r = gb._root
        if VER:
            r.deiconify()
        W["show_page"]("estado")
        gb._AV["rows"] = {}
        gb._mdl["installed"] = []
        gb._tasks_fp[0] = None
        bombear(3.0)
        pintar()
        sb = W["sidebar"]
        marca = [w.cget("text") for w in todos(sb.winfo_children()[0]) if isinstance(w, gb.tk.Label)][:4]
        ev["a_barra"] = {"ancho_px": int(sb.cget("width")), "pack_propagate": sb.pack_propagate(),
                         "esperado_px": gb.S(gb.BARRA_PX),
                         "marca_textos": marca, "avatar": any(str(w.cget("image")) for w in todos(sb)
                                                              if isinstance(w, gb.tk.Label)),
                         "iconos": gb.fuente_iconos(),
                         "glifos": {n: hex(ord(b._icono.cget("text"))) for n, b in W["nav_btns"].items()
                                    if getattr(b, "_icono", None) is not None}}
        # (b) contadores en 0 (el mapa y Ollama reales se re-leen solos: se ponen a 0 y se lee al momento)
        gb._AV["rows"] = {}
        gb._mdl["installed"] = []
        W["nav_count_modelos"].config(text=str(len(gb._mdl["installed"])))  # lo mismo que hace el tick
        gb._barra_pintar()
        ev["b_cero"] = contadores()
        # (c) consumo con 0
        ev["c_cero"] = {"pantalla": (txt("sb_consumo"), txt("sb_consumo_det"))}
        # (d) guardrail inicial
        ev["d_inicial"] = {"nivel": txt("sb_gr_nivel"), "cola": txt("sb_gr_cola"),
                           "punto": W["sb_gr_punto"].cget("fg")}
        foto("1-ceros")
        # ---- N: 7 tareas, 2 fallos del mapa, 3 modelos, gasto de hoy
        for i in range(7):
            fam(f"t-barra-{i}", ["aprobada", "en_curso", "fallida"][i % 3])
        for tid, costo, modelo in (("t-barra-0", 0.31, "claude-opus-5-5"), ("t-barra-3", 0.07, "claude-opus-5-5")):
            (res / f"{tid}.result.json").write_text(json.dumps({
                "id": tid, "raiz": tid, "status": "ok", "motor": "claude", "modelo": modelo,
                "cost_usd": costo, "finished_at": gb._now_iso(), "duration_s": 40,
                "uso": {"tokens_in": 1000, "tokens_out": 300, "modelo_real": modelo}}), encoding="utf-8")
        gb._AV["rows"] = {"a": {"estado": "falla"}, "b": {"estado": "falla"}, "c": {"estado": "ok"}}
        gb._mdl["installed"] = [{"name": "m1"}, {"name": "m2"}, {"name": "m3"}]
        W["show_page"]("tareas")
        bombear(2.0)
        gb._tasks_fp[0] = None
        gb._refresh_tasks_ui()
        bombear(11.0)  # el tick de 10 s pinta modelos
        pintar()
        ev["b_n"] = {"pantalla": contadores(), "esperado": {
            "estado": sum(1 for v in gb._AV["rows"].values() if v.get("estado") == "falla"),
            "modelos": len(gb._mdl["installed"]), "tareas": len(gb._task_rows()[0])}}
        dm = gb.day_by_model()
        ev["c_n"] = {"pantalla": (txt("sb_consumo"), txt("sb_consumo_det")), "day_by_model": {
            "real": round(sum(b["cost"] for k, b in dm.items() if k[0] == "real"), 2),
            "equiv": round(sum(b["cost"] for k, b in dm.items() if k[0] == "equiv"), 2),
            "n": sum(b["n"] for k, b in dm.items() if not k[2])},
            "tareas_estadistica_gasto": gb._T45["stats"]["gasto"][0].cget("text") if gb._T45.get("stats") else None}
        foto("2-con-n")
        # (d) cambiar el nivel en Ajustes (el radio real) y clic en la tarjeta
        W["show_page"]("ajustes")
        bombear(1.0)
        radios = [w for w in todos(r) if type(w).__name__ in ("CTkRadioButton", "Radiobutton")
                  and "solo lo delicado" in str(w.cget("text"))]
        if radios:
            radios[0].invoke()
        bombear(1.0)
        pintar()
        ev["d_tras_cambiar"] = {"radio_encontrado": bool(radios), "settings": gb.load_settings().get("guardrail"),
                                "nivel": txt("sb_gr_nivel"), "cola": txt("sb_gr_cola"),
                                "punto": W["sb_gr_punto"].cget("fg")}
        s = gb.load_settings()
        s["guardrail"] = "nunca"
        gb.save_settings(s)
        pintar()
        ev["d_nunca"] = {"nivel": txt("sb_gr_nivel"), "punto": W["sb_gr_punto"].cget("fg"), "verde": gb.THEME["green"]}
        foto("3-guardrail-nunca")
        W["show_page"]("estado")
        bombear(0.5)
        card = W["sb_gr_card"]
        disparar(card, "<Button-1>")
        bombear(1.5)
        ev["d_clic"] = {"pagina": W.get("pagina_actual")}
        W["show_page"]("estado")
        bombear(0.5)
        ev["d_foco"] = {"borde_foco": str(card.cget("highlightcolor")), "takefocus": str(card.cget("takefocus")),
                        "grosor": str(card.cget("highlightthickness"))}
        disparar(card, "<Return>")
        bombear(1.0)
        ev["d_intro"] = {"pagina": W.get("pagina_actual")}
        foto("4-clic-abre-permisos")
        # (e) interruptor de la mascota: cambia y persiste
        sw = W["mascot_sw"]
        ev["e_tipo"] = type(sw).__name__
        antes = gb.load_settings().get("mascot")
        pulsar(sw)
        bombear(1.5)
        tras = gb.load_settings().get("mascot")
        ev["e_interruptor"] = {"antes": antes, "tras_clic": tras, "dibujo": bool(sw._on),
                               "mascota_visible": gb._mascot["win"] is not None}
        pulsar(sw)
        bombear(1.5)
        ev["e_vuelta"] = {"settings": gb.load_settings().get("mascot"), "dibujo": bool(sw._on),
                          "mascota_visible": gb._mascot["win"] is not None}
        gb.set_switch(sw, True)  # como refresh_ui: el dibujo sigue al estado sin llamar al comando
        bombear(0.3)
        ev["e_set_switch"] = {"dibujo": bool(sw._on), "settings_sin_cambiar": gb.load_settings().get("mascot")}
        gb.set_switch(sw, False)
        # Altura minima: la ventana al minimo y todo cabe
        mw, mh = (int(x) for x in r.minsize())
        ev["altura_minima"] = {"minsize": (mw, mh), "area_de_trabajo_alto": _area_trabajo_alto(), **cabe(mh)}
        foto("5-altura-minima")
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log_barra"] = [x for x in log.splitlines() if "barra lateral" in x][-4:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / f"evidencia-{pref}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                                    encoding="utf-8")
        gb.quit_app()

    def solo_arranque():
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log_barra"] = [x for x in log.splitlines() if "barra lateral" in x][-2:]
        gb.quit_app()

    orig = gb.build_gui

    if not VER:  # nada sale a la pantalla ni roba el foco
        gb.show_window = lambda *a, **k: None
        gb.show_mascot = lambda *a, **k: gb._mascot.update(win="prueba")
        gb.hide_mascot = lambda *a, **k: gb._mascot.update(win=None)

    def build():
        t0 = time.perf_counter()
        root = orig()
        if not VER:
            root.withdraw()
        ev["build_gui_s"] = round(time.perf_counter() - t0, 2)
        root.after(6000, lambda: _seguro(solo_arranque if VARIANTE == "arranque" else pasos))
        return root

    def _seguro(fn):
        try:
            fn()
        except Exception:
            import traceback
            ev["error_prueba"] = traceback.format_exc()
            (OUT / f"evidencia-{pref}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                                        encoding="utf-8")
            gb.quit_app()
    gb.build_gui = build
    gb.main()
    print(json.dumps(ev, ensure_ascii=True, indent=1, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
