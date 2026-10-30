"""(c)/(d) compara la tarea de la APP y la de FUERA (y la del plan B): sus
.task.json y sus filas en cola.db (leida en SOLO LECTURA), y lo que la cola
visible (cola_visible_datos / cola_pendientes) muestra.
Uso: python encolar_comparar.py <id_app> <id_fuera> <id_planb>"""
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

APP = Path(r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app")
ida, idf, idb = sys.argv[1:4]
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)


def buscar(tid):
    for d in ("runner-tasks", "runner-tasks/esperando", "runner-tasks/processing", "runner-tasks/done"):
        p = APP / "share/inbox" / d / f"{tid}.task.json"
        if p.is_file():
            return p
    return None


con = sqlite3.connect((APP / "cola.db").as_uri() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def fila(tid):
    r = con.execute("SELECT * FROM tareas WHERE id=?", (tid,)).fetchone()
    return dict(r) if r else None


def apr(tid):
    try:
        r = con.execute("SELECT approval_id, estado, nivel, canal FROM aprobaciones WHERE tarea=? OR raiz=?",
                        (tid, tid)).fetchone()
        return dict(r) if r else None
    except sqlite3.Error as e:
        return f"(sin tabla/columna: {e})"


VOLATIL = {"id", "creado_en", "actualizado_en", "actualizado_ts", "archivo", "raiz", "historial"}
out = {}
for nombre, tid in (("app", ida), ("fuera", idf), ("planb", idb)):
    p = buscar(tid)
    d = json.loads(p.read_text(encoding="utf-8")) if p else None
    out[nombre] = {"id": tid, "archivo": str(p) if p else None, "task": d, "cola": fila(tid), "aprobacion": apr(tid)}
    print(f"\n== {nombre} {tid}\n  archivo: {p}\n  task.json: {json.dumps(d, ensure_ascii=False)}")
    print(f"  cola.db: {json.dumps(out[nombre]['cola'], ensure_ascii=False)}")
    print(f"  aprobacion: {out[nombre]['aprobacion']}")
ta = {k: v for k, v in (out["app"]["task"] or {}).items() if k != "id"}
tf = {k: v for k, v in (out["fuera"]["task"] or {}).items() if k != "id"}
print("\n(c) task.json app == fuera (sin el id):", ta == tf, "| claves:", list(ta) == list(tf))
ca = {k: v for k, v in (out["app"]["cola"] or {}).items() if k not in VOLATIL}
cf = {k: v for k, v in (out["fuera"]["cola"] or {}).items() if k not in VOLATIL}
print("(c) fila cola.db app == fuera (sin id/horas/archivo/raiz):", ca == cf, ca)
print("(c) misma carpeta de destino:", Path(out["app"]["archivo"] or "").parent == Path(out["fuera"]["archivo"] or "x").parent)
con.close()

src = APP / "growi-bridge.py"
ld = importlib.machinery.SourceFileLoader("growi_bridge", str(src))
spec = importlib.util.spec_from_file_location("growi_bridge", src, loader=ld)
gb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gb)
gb.log = lambda m: None
pend = gb.cola_pendientes()
ids = [p.get("id") for p in (pend or [])] if isinstance(pend, list) else pend
print("\ncola visible (cola_pendientes):", json.dumps(ids, ensure_ascii=False)[:600])
for tid in (ida, idf, idb):
    print(f"  {tid} en la cola visible:", tid in json.dumps(pend, ensure_ascii=False, default=str))
