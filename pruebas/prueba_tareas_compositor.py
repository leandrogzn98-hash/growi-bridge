"""Prueba del compositor «Pedirle algo a Growi…» de Tareas (ESTADO-TAREAS-COMPOSITOR.md). Oculta: no abre ventanas.

El runner de la copia se sustituye por uno inerte: las tareas se ENCOLAN de verdad (el .task.json en la cola, por
_send_ask, el camino de la paleta Ctrl+K) pero nadie las ejecuta (no se gasta nada).

  python pruebas/prueba_tareas_compositor.py 100 | 150
  python pruebas/prueba_tareas_compositor.py 100 clasica | sinctk | flag
  python pruebas/prueba_tareas_compositor.py 100 arranque [fuente.py]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None

    def runner_inerte(stop):  # la cola se llena, nadie la vacía
        stop.wait()
    gb.runner_loop = runner_inerte


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("tareas")
    h.bombear(2.0)
    if VAR == "arranque":
        ev["log_comp"] = [x[26:] for x in h.log().splitlines() if "tareas: compositor" in x]
        return
    C = gb._COMP
    box, sel = W["ask_text"], W["ask_engine"]
    ev["tipos"] = {"campo": type(box).__name__, "selector": type(sel).__name__, "enviar": type(C["enviar"]).__name__,
                   "estado": type(W["ask_status"]).__name__}
    ev["placeholder"] = str(C["ph"].cget("text")) if C.get("ph") is not None else None
    ev["selector_por_defecto"] = sel.get()
    ev["acento_enviar"] = (str(C["enviar"].cget("fg_color")) if hasattr(C["enviar"], "_canvas")
                           else str(C["enviar"].cget("style")))
    tareas = lambda: sorted(p.name for p in gb.TASKS.glob("*.task.json"))  # noqa: E731
    # (c) vacío no envía
    antes = tareas()
    box.delete("1.0", "end")
    C["enviar"].invoke()
    h.bombear(0.3)
    box.insert("1.0", "   \n  ")
    gb._comp_enviar()
    h.bombear(0.3)
    ev["c_vacio"] = {"antes": antes, "despues": tareas(), "no_creo_nada": tareas() == antes,
                     "errores_en_log": h.log().count("Traceback")}
    # (b) Automático (recomendado) -> la tarea queda con el router automático
    sel.set(gb.AUTO_LABEL)
    box.insert("1.0", "Resume en 3 puntos qué hace la carpeta pruebas")
    C["enviar"].invoke()
    h.bombear(0.5)
    nuevas = [t for t in tareas() if t not in antes]
    d1 = json.loads((gb.TASKS / nuevas[0]).read_text(encoding="utf-8")) if nuevas else {}
    ev["b_auto"] = {"archivo": nuevas, "motor": d1.get("motor"), "model": d1.get("model"),
                    "prompt": d1.get("prompt"), "esperado_motor": gb.AUTO}
    # (d) campo limpio y la tarea en la lista
    gb._tasks_fp[0] = None
    gb._refresh_tasks_ui()
    h.bombear(0.4)
    ids = list(W["tasks_tree"].get_children())
    ev["d_despues"] = {"campo": box.get("1.0", "end").strip(), "en_la_lista": d1.get("id") in ids,
                       "estado_fila": W["tasks_tree"].set(d1["id"], "estado") if d1.get("id") in ids else None,
                       "aviso": str(W["ask_status"].cget("text"))[:60],
                       "placeholder_visible": (bool(C["ph"].winfo_manager()) if C.get("ph") is not None else None)}
    # (a) con un motor elegido a mano (Claude Haiku) y con Intro en el campo
    antes2 = tareas()
    if "Claude Haiku" in gb._ASK_ENGINES:
        sel.set("Claude Haiku")
    box.insert("1.0", "Dime la hora en Caracas")
    h.disparar(getattr(box, "_textbox", box), "<Return>")
    h.bombear(0.5)
    nuevas2 = [t for t in tareas() if t not in antes2]
    d2 = json.loads((gb.TASKS / nuevas2[0]).read_text(encoding="utf-8")) if nuevas2 else {}
    ev["a_motor_elegido"] = {"selector": sel.get(), "archivo": nuevas2, "model": d2.get("model"),
                             "motor": d2.get("motor"), "esperado": gb._ASK_ENGINES.get(sel.get()),
                             "campo_limpio": not box.get("1.0", "end").strip()}
    # el selector: sus valores son los de siempre (engine_choices, con cabeceras) y elegir dispara lo mismo
    ev["selector_valores"] = list(sel.cget("values"))[:6]
    if hasattr(sel, "elegir"):
        sel.elegir("Claude Opus") if "Claude Opus" in gb._ASK_ENGINES else None
        ev["selector_elegir"] = sel.get()
    # foco: Tab llega al campo, al selector y a Enviar
    campo_tf = getattr(box, "_textbox", box)
    ev["foco"] = {"campo": str(campo_tf.cget("takefocus")) or "nativo (Text)",
                  "selector": (str(sel.btn._canvas.cget("takefocus")) if hasattr(sel, "btn") else
                               str(sel.cget("takefocus")) or "nativo (Combobox)"),
                  "enviar": (str(C["enviar"]._canvas.cget("takefocus")) if hasattr(C["enviar"], "_canvas") else
                             "ttk.Button"), "intro_enlazado": bool(campo_tf.bind("<Return>"))}
    # DPI: la fila selector + Enviar cabe en el contenido a ventana mínima
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 32 + 14)
    fila = C["enviar"].master
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "fila_pedida": fila.winfo_reqwidth(),
                   "cabe": fila.winfo_reqwidth() <= contenido}


correr("tareas-compositor", pasos, dpi=DPI, variante=VAR, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8783, fuente=FUENTE)
