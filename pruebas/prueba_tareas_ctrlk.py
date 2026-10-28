"""Prueba del campo «Buscar o pedirle algo (Ctrl K)» del encabezado de Tareas (ESTADO-TAREAS-CTRLK.md).
Oculta: no abre ventanas. El runner es inerte (las tareas se encolan, nadie las ejecuta).

  python pruebas/prueba_tareas_ctrlk.py 100 | 150
  python pruebas/prueba_tareas_ctrlk.py 100 arranque [fuente.py]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
HOY = time.strftime("%Y-%m-%dT09:00:00-04:00")
SEMILLA = [("t-factura-01", "aprobada", "Ordenar las facturas de octubre"),
           ("t-factura-02", "fallida", "Sumar las facturas pendientes"),
           ("t-blender-07", "pendiente", "Render de la mascota en Blender"),
           ("t-notas-11", "aprobada", "Pasar las notas de la reunión a Obsidian")]


def preparar(app, tmp):
    res = tmp / "share" / "outbox" / "runner-results"
    for tid, est, enc in SEMILLA:
        (res / f"{tid}.orquestacion.json").write_text(json.dumps({
            "raiz": tid, "estado": est, "motor": "claude", "ronda": 1, "actualizado": HOY, "tareas": [tid],
            "encargo": enc}), encoding="utf-8")


def antes_de_main(gb):
    def runner_inerte(stop):
        stop.wait()
    gb.runner_loop = runner_inerte


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("tareas")
    h.bombear(2.0)
    gb._tasks_fp[0] = None
    gb._refresh_tasks_ui()
    h.bombear(0.5)
    if VAR == "arranque":
        return
    tree, ent, var = W["tasks_tree"], W["tareas_busca"], gb._T45["busca_var"]
    filas = lambda: list(tree.get_children())  # noqa: E731
    ev["campo"] = {"tipo": type(ent).__name__, "placeholder": str(gb._T45["busca_ph"].cget("text")),
                   "en_encabezado": str(ent.master.master) == str(W["tasks_tree"].master.winfo_children()[0])}
    ev["inicio"] = filas()
    # (a) filtra en vivo por id y por título
    for q in ("factura-0", "BLENDER", "obsidian", "reunión"):
        var.set(q)
        h.bombear(0.3)
        ev.setdefault("a_filtra", {})[q] = filas()
    # (b) borrar quita el filtro
    var.set("")
    h.bombear(0.3)
    ev["b_sin_filtro"] = {"filas": filas(), "igual_que_al_inicio": filas() == ev["inicio"]}
    # Intro con coincidencias: elige la primera
    var.set("notas")
    h.bombear(0.3)
    gb._busca_intro()
    h.bombear(0.3)
    ev["intro_coincide"] = {"seleccion": list(tree.selection()), "detalle": str(gb._TDET["campos"]["tarea"].cget("text"))}
    # (c) sin coincidencias + Intro -> encargo nuevo con el router automático
    antes = sorted(p.name for p in gb.TASKS.glob("*.task.json"))
    var.set("Hazme una lista de la compra para la semana")
    h.bombear(0.3)
    ev["c_sin_coincidencias_filas"] = filas()
    W["ask_engine"].set("Claude Haiku") if "Claude Haiku" in gb._ASK_ENGINES else None
    prev_motor = W["ask_engine"].get()
    gb._busca_intro()
    h.bombear(0.5)
    nuevas = [p for p in sorted(x.name for x in gb.TASKS.glob("*.task.json")) if p not in antes]
    d = json.loads((gb.TASKS / nuevas[0]).read_text(encoding="utf-8")) if nuevas else {}
    gb._tasks_fp[0] = None
    gb._refresh_tasks_ui()
    h.bombear(0.4)
    ev["c_encargo"] = {"archivo": nuevas, "motor": d.get("motor"), "model": d.get("model"), "prompt": d.get("prompt"),
                       "en_la_lista": d.get("id") in filas(), "campo_limpio": var.get() == "",
                       "selector_del_compositor_igual": W["ask_engine"].get() == prev_motor}
    # (d) Ctrl+K desde la lista -> foco al campo (oculta: se registra focus_set)
    focos = []
    of_e, of_t = ent.focus_set, tree.focus_set
    ent.focus_set = lambda: (focos.append("campo"), of_e())
    tree.focus_set = lambda: (focos.append("lista"), of_t())
    pal_antes = gb._palette.get("win")
    gb._atajo_ejecutar("abrir_paleta", "paleta")
    h.bombear(0.3)
    ev["d_ctrl_k"] = {"foco": list(focos), "paleta_abierta": gb._palette.get("win") is not pal_antes}
    # (e) Esc limpia y devuelve el foco a la lista
    focos.clear()
    var.set("algo")
    h.bombear(0.2)
    h.disparar(ent, "<Escape>")
    h.bombear(0.3)
    ev["e_esc"] = {"campo": var.get(), "foco": list(focos), "filas_sin_filtro": filas() == ev["c_encargo"].get("lista", filas())}
    # (f) fuera de Tareas, Ctrl+K abre la paleta de siempre, con sus resultados
    W["show_page"]("estado")
    h.bombear(0.4)
    gb._atajo_ejecutar("abrir_paleta", "paleta")
    h.bombear(0.8)
    pal = gb._palette.get("win")
    secs = gb._palette_sections("ajustes")
    ev["f_paleta"] = {"abierta": pal is not None and bool(pal.winfo_exists()), "tipo": type(pal).__name__,
                      "secciones": [s for s, _c in secs][:3], "resultados": len(secs[0][1]) if secs else 0}
    # DPI: el campo + el título caben en el ancho del contenido a ventana mínima
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 14)
    cab = ent.master.master
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "encabezado_pedido": cab.winfo_reqwidth(),
                   "cabe": cab.winfo_reqwidth() <= contenido}


correr("tareas-ctrlk", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       puerto=8782, fuente=FUENTE)
