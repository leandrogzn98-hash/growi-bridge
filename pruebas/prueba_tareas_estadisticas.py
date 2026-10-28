"""Prueba de la fila de estadisticas, las pildoras y la tarea fijada en Tareas
(ESTADO-TAREAS-ESTADISTICAS.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8797) en tema oscuro, con 54 tareas sembradas en varios
estados, 3 resultados de hoy con costo y una tarea corriendo (runner-live.json).

  python pruebas/prueba_tareas_estadisticas.py 100
  python pruebas/prueba_tareas_estadisticas.py 150
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
MODO = "oscuro"
DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
ESTADOS = ["aprobada", "aprobada", "fallida", "necesita_decision", "sin_revision", "pendiente", "aprobada",
           "esperando_aprobacion", "fallida", "aprobada"]
SEMILLA: list = [(f"t-semilla-{i:02d}", ESTADOS[i % len(ESTADOS)], 0.05 * (i % 3), i % 2 == 0) for i in range(51)]
SEMILLA += [("t-revisando-02", "revisando", None, True), ("t-corriendo-02", "en_curso", None, True)]
NOMBRE = f"{MODO}-{DPI}"
OUT = REPO / "pruebas" / "evidencia" / "tareas-estadisticas"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-tstats-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True, "apariencia": MODO}), encoding="utf-8")
    res = tmp / "share" / "outbox" / "runner-results"
    res.mkdir(parents=True)
    hoy = time.strftime("%Y-%m-%dT%H:%M:%S-04:00")
    ayer = time.strftime("%Y-%m-%dT%H:%M:%S-04:00", time.localtime(time.time() - 86400))
    for tid, est, costo, es_hoy in SEMILLA + [("t-corriendo-01", "en_curso", None, True)]:
        (res / f"{tid}.orquestacion.json").write_text(json.dumps({
            "raiz": tid, "estado": est, "motor": "claude", "ronda": 1, "costo_usd": costo,
            "actualizado": hoy if es_hoy else ayer, "tareas": [tid], "encargo": "tarea de prueba"}),
            encoding="utf-8")
    for tid, costo in (("t-semilla-00", 0.31), ("t-semilla-06", 0.07), ("t-semilla-09", 0.02)):
        (res / f"{tid}.result.json").write_text(json.dumps({
            "id": tid, "raiz": tid, "status": "ok", "motor": "claude", "modelo": "claude-opus-5-5",
            "cost_usd": costo, "finished_at": hoy, "duration_s": 40,
            "uso": {"tokens_in": 1000, "tokens_out": 300, "modelo_real": "claude-opus-5-5"}}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaTStats",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      GROWI_BRIDGE_DPI="144" if DPI == "150" else "96")
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_tstats", app / "growi-bridge.py")
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

    def foto(nombre):
        r = gb._root
        r.attributes("-topmost", False)
        r.attributes("-topmost", True)
        r.lift()
        bombear(0.4)
        captura(f"{DPI}-{nombre}")

    def filas_tabla():
        t = W["tasks_tree"]
        return list(t.get_children())

    def fam(tid, **kw):
        f = res / f"{tid}.orquestacion.json"
        d = json.loads(f.read_text(encoding="utf-8"))
        d.update(kw)
        f.write_text(json.dumps(d), encoding="utf-8")

    def vivo(**kw):
        (gb.OUTBOX / "runner-live.json").write_text(json.dumps(kw), encoding="utf-8")

    def pasos():
        r = gb._root
        r.deiconify()
        vivo(task_id="t-corriendo-01", raiz="t-corriendo-01", estado="trabajando", motor="claude",
             modelo="claude-opus-5-5", elapsed_s=75, cost_usd_estimado=0.12, dinero="equiv",
             actualizado=gb._now_iso())
        W["show_page"]("tareas")
        bombear(6.0)
        # (c) las 3 estadisticas contra los datos sembrados / del dia
        st = {k: (n.cget("text"), s_.cget("text")) for k, (n, s_) in gb._T45["stats"].items()}
        dm = gb.day_by_model()
        ev["c_estadisticas"] = {"pantalla": st, "esperado": {
            "en_curso": len({t for t, e, _c, _h in SEMILLA if e in ("en_curso", "revisando")} | {"t-corriendo-01"}),
            "aprobadas_hoy": sum(1 for _t, e, _c, h in SEMILLA if e == "aprobada" and h),
            "gasto_real_day_by_model": round(sum(b["cost"] for k, b in dm.items() if k[0] == "real"), 2),
            "gasto_equiv_day_by_model": round(sum(b["cost"] for k, b in dm.items() if k[0] == "equiv"), 2)}}
        # (a) la fijada, y sigue a la vista al bajar hasta la ultima de las 54 filas
        t = W["tasks_tree"]
        gb._scroll_a(gb._T45["fijada_card"], margen=12)  # la página, a la zona de la lista
        bombear(0.6)
        t.yview_moveto(1.0)  # y la tabla, hasta la última de las 54 filas
        bombear(0.6)
        f1, f2 = gb._T45["fijada"]
        card = gb._T45["fijada_card"]
        cv = next(c for c in gb._scroll_canvases if c.winfo_ismapped())
        ev["a_fijada"] = {"titulo": f1.cget("text"), "detalle": f2.cget("text"),
                          "filas_en_tabla": len(t.get_children()),
                          "ultima_fila_visible": t.bbox(t.get_children()[-1]) != "",
                          "fijada_visible": cv.winfo_rooty() <= card.winfo_rooty() < cv.winfo_rooty() + cv.winfo_height()}
        foto("a-fijada-y-54-filas")
        # (d) cada pildora filtra y su contador cuadra con las filas de la tabla
        pills = {}
        for key, lab, _e, _col in gb.TFILTROS:
            gb._T45["pills"][key].invoke()
            bombear(0.5)
            pills[key] = {"contador": gb._T45["cuentas"][key], "filas": len(filas_tabla()),
                          "texto": gb._T45["pills"][key].cget("text"),
                          "estados_vistos": sorted({t.set(x, "estado") for x in filas_tabla()})}
        ev["d_pildoras"] = pills
        gb._T45["pills"]["necesita_decision"].invoke()
        bombear(0.5)
        foto("d-filtro-necesita-decision")
        gb._T45["pills"]["todos"].invoke()
        bombear(0.4)
        ev["e_explicacion"] = gb._T45["expl"].cget("text")
        t.selection_set(filas_tabla()[0])
        bombear(0.3)
        ev["fila_seleccionada_fondo"] = gb.ttk.Style().map("Tareas.Treeview", "background")
        # (b) termina la que corria: se fija la siguiente en curso, y luego ninguna (en vivo)
        vivo(task_id="t-corriendo-01", raiz="t-corriendo-01", estado="terminado", motor="claude",
             actualizado="2026-01-01T00:00:00-04:00")
        fam("t-corriendo-01", estado="aprobada")
        bombear(7.0)
        ev["b_tras_terminar"] = {"titulo": f1.cget("text"), "detalle": f2.cget("text"),
                                 "en_curso": gb._T45["stats"]["en_curso"][0].cget("text")}
        foto("b-se-fija-la-siguiente")
        for tid, e, _c, _h in SEMILLA:
            if e in ("en_curso", "revisando"):
                fam(tid, estado="aprobada")
        bombear(7.0)
        ev["b_sin_ninguna"] = {"titulo": f1.cget("text"), "detalle": f2.cget("text"),
                               "en_curso": gb._T45["stats"]["en_curso"][0].cget("text")}
        foto("b-ninguna-corriendo")
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "tareas:" in x][-5:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / f"evidencia-{DPI}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                                   encoding="utf-8")
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
