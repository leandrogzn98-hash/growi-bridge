"""Prueba del detalle debajo de la tabla de Tareas y de las columnas que caben (ESTADO-TAREAS-DETALLE.md).
Oculta: no abre ventanas; «Abrir resultados» se registra en vez de abrir nada.

Siembra t-detalle-a (revisada: 2 checks de código, uno pasa y otro falla, + un juez que aprueba, con su hora y su
.result.json) y t-detalle-b (sin revisión ni resultados).

  python pruebas/prueba_tareas_detalle.py 100 | 150
  python pruebas/prueba_tareas_detalle.py 100 clasica | sinctk | flag
  python pruebas/prueba_tareas_detalle.py 100 arranque [fuente.py]
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
HORA = time.strftime("%Y-%m-%dT10:42:07-04:00")


def preparar(app, tmp):
    res = tmp / "share" / "outbox" / "runner-results"
    (res / "t-detalle-a.orquestacion.json").write_text(json.dumps({
        "raiz": "t-detalle-a", "estado": "necesita_decision", "motor": "claude", "ronda": 2, "costo_usd": 0.42,
        "actualizado": HORA, "tareas": ["t-detalle-a", "t-detalle-a-r2"], "ultimo_resultado": "t-detalle-a-r2",
        "encargo": "ordenar Descargas por tipo",
        "ultima_revision": {"id": "t-detalle-a-r2", "aprobado": False, "decision": "necesita_decision",
                            "motor": "reglas + claude", "que_falta": ["falta el archivo plan.md"],
                            "checks": [{"criterio": "existe plan.md", "resultado": "falla"}]}}), encoding="utf-8")
    (res / "t-detalle-a-r2.revision.json").write_text(json.dumps({
        "id": "t-detalle-a-r2", "revisado_at": HORA,
        "checks_deterministas": [{"criterio": "el comando pytest sale con 0", "resultado": "pasa",
                                  "detalle": ["pytest: salió con exit 0 en 3 s"]},
                                 {"criterio": "existe plan.md", "resultado": "falla",
                                  "detalle": ["plan.md no existe"]}],
        "veredictos": [{"rol": "juez", "motor": "claude", "aprobado": True, "puntuacion": 4}]}), encoding="utf-8")
    (res / "t-detalle-a-r2.result.json").write_text(json.dumps({
        "id": "t-detalle-a-r2", "raiz": "t-detalle-a", "status": "ok", "motor": "claude", "cost_usd": 0.42,
        "finished_at": HORA, "duration_s": 95, "result": "hecho",
        "uso": {"tokens_in": 12000, "tokens_out": 3400}}), encoding="utf-8")
    (res / "t-detalle-b.orquestacion.json").write_text(json.dumps({
        "raiz": "t-detalle-b", "estado": "pendiente", "motor": "ollama", "ronda": 0, "actualizado": HORA,
        "tareas": ["t-detalle-b"], "encargo": "resumen corto"}), encoding="utf-8")


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("tareas")
    h.bombear(2.0)
    gb._tasks_fp[0] = None
    gb._refresh_tasks_ui()
    h.bombear(0.8)
    if VAR == "arranque":
        ev["log_det"] = [x[26:] for x in h.log().splitlines() if "tareas: detalle" in x]
        return
    T = gb._TDET
    tree = W["tasks_tree"]
    ev["kit"] = type(T["kit"]).__name__
    ev["card"] = type(T["card"]).__name__
    ev["vacio_al_inicio"] = {"texto": str(T["vacio"].cget("text")), "cuerpo_oculto": not T["cuerpo"].winfo_manager()}

    def ver(tid):
        tree.selection_set(tid)
        h.bombear(0.4)
        gb._show_task_detail()
        h.bombear(0.3)
        lin = [[str(w.cget("text")) for w in r.winfo_children()] for r in T["linea"].winfo_children()]
        return {"campos": {k: str(v.cget("text")) for k, v in T["campos"].items()},
                "resumen": str(T["resumen"].cget("text")), "linea": lin, "aviso": str(T["aviso"].cget("text")),
                "tarea_mono": str(T["campos"]["tarea"].cget("font"))}
    ev["a_tarea_a"] = ver("t-detalle-a")
    ev["a_tarea_b"] = ver("t-detalle-b")
    # (c) Abrir resultados: la real de A; B lo dice y no abre nada
    tree.selection_set("t-detalle-b")
    gb._show_task_detail()
    T["abrir"].invoke()
    h.bombear(0.2)
    ev["c_b"] = {"abiertos": list(h.abiertos), "aviso": str(T["aviso"].cget("text"))}
    tree.selection_set("t-detalle-a")
    gb._show_task_detail()
    T["abrir"].invoke()
    h.bombear(0.2)
    ev["c_a"] = {"abiertos": list(h.abiertos), "esperado": str(gb.RESULTS / "t-detalle-a-r2.result.json")}
    ev["c_acento"] = (str(T["abrir"].cget("fg_color")) if ev["kit"] == "_KitCtk" else str(T["abrir"].cget("style")))
    # (d) Volver a la cola: el foco a la lista, en la fila elegida. Oculta, Tk no da el foco a nadie (la ventana
    # no está activa): se registra la llamada a focus_set de la lista.
    focos = []
    orig_focus = tree.focus_set
    tree.focus_set = lambda: (focos.append(str(tree)), orig_focus())
    T["volver"].invoke()
    h.bombear(0.3)
    ev["d_volver"] = {"focus_set_en_lista": len(focos), "fila_con_foco": tree.focus()}
    # (e) cerrar: siempre en la cabecera (hueco propio a la derecha) y cierra
    cer = T["cerrar"]
    ev["e_cerrar"] = {"texto": str(cer.cget("text")), "en_cabecera": str(cer.master.master) == str(T["card"].winfo_children()[0]),
                      "lado": cer.master.pack_info().get("side")}
    focos.clear()
    cer.invoke()
    h.bombear(0.3)
    ev["e_cerrar"].update(seleccion=list(tree.selection()), cuerpo_oculto=not T["cuerpo"].winfo_manager(),
                          focus_set_en_lista=len(focos))
    # foco de los botones
    ev["foco"] = {str(b.cget("text")): (str(b._canvas.cget("takefocus")) if hasattr(b, "_canvas") else type(b).__name__)
                  for b in (T["abrir"], T["volver"], T["reencolar"], T["cerrar"])}
    # columnas: a ventana mínima, lo que se ve cabe; «● necesita decisión» cabe en Estado
    import tkinter.font as tkfont
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 14)
    h.disparar(tree, "<Configure>", w=contenido, h=200)
    vis = list(tree.cget("displaycolumns"))
    suma = sum(int(tree.column(c, "width")) for c in vis)
    necesita = tkfont.Font(font=(gb.MONO, 10)).measure("● necesita decisión") + gb.S(12)  # texto + margen de celda
    ev["tabla"] = {"minsize_ancho": mw, "contenido": contenido, "columnas_visibles": vis, "suma_anchos": suma,
                   "cabe": suma <= contenido, "estado_ancho": int(tree.column("estado", "width")),
                   "estado_necesita": necesita, "estado_cabe": int(tree.column("estado", "width")) >= necesita,
                   "ancho_completo_100": gb.tareas_columnas_para(gb.S(960))}
    h.disparar(tree, "<Configure>", w=gb.S(1200), h=200)
    ev["tabla"]["ancha"] = list(tree.cget("displaycolumns"))


correr("tareas-detalle", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8784, fuente=FUENTE)
