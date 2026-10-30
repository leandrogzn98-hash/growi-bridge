"""Prueba de t-vista-agentes-052 (Vista de Agentes) en una instancia AISLADA.

C:\\Users\\forte\\growi-bridge\\_prueba-vista-agentes-052\\app\\ = el
growi-bridge.py y el engines.json del REPO + la config de la app instalada
(solo se lee), con su propia share, cola.db, log y settings.json (guardrail
«siempre»: todo encargo espera tu sí). La ventana NUNCA se muestra: el
tablero se construye en un Tk retirado (withdraw) y los botones se pulsan con
invoke(). Los motores se lanzan ocultos (CREATE_NO_WINDOW).

  a) estados sembrados en cola.db + familias + result.json -> cada uno cae en
     su columna (y los que no tocan, en ninguna)
  b) el tablero (CustomTkinter y Tk clásico) pinta esas tarjetas, con Aprobar /
     Rechazar solo donde se puede aprobar; «Ver» selecciona la tarea en la lista
  c) /gateway/agentes devuelve lo mismo que vista_agentes(); sin token, 401
  d) de verdad: dos tareas de codex retenidas por el guardrail -> «Rechazar» en
     una (sale del tablero) y «Aprobar» en la otra -> Te necesitan ->
     Trabajando -> Terminadas, con Codex de verdad
  e) refrescar no congela: lo que tarda pintar en el hilo de la ventana

Uso: python prueba_vista_agentes_052.py [--sin-motores]   (sin-motores: a, b, c, e)
Evidencia: pruebas\\evidencia\\vista-agentes-052\\resultado.json
"""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
_src = REPO / "pruebas" / "prueba_motor_generico_052.py"
_ld = importlib.machinery.SourceFileLoader("p052", str(_src))
_spec = importlib.util.spec_from_loader("p052", _ld)
assert _spec is not None
p052: Any = importlib.util.module_from_spec(_spec)
_ld.exec_module(p052)  # reutiliza preparar() y cargar() de la prueba del multimotor
p052.BASE = p052.REAL / "_prueba-vista-agentes-052"
p052.APP = p052.BASE / "app"
APP = p052.APP
EVID = REPO / "pruebas" / "evidencia" / "vista-agentes-052"
SIN_MOTORES = "--sin-motores" in sys.argv
OUT = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "casos": {}}
SECRETO = "secreto-de-prueba-vista-agentes"


def caso(k, ok, **datos):
    OUT["casos"][k] = dict(ok=bool(ok), **datos)
    print(f"[{'OK' if ok else 'FALLA'}] {k}: {json.dumps(datos, ensure_ascii=False, default=str)[:500]}", flush=True)


def iso(ts):
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def sembrar(gb):
    """Una fila por estado (y las que NO deben salir), con su familia y su result."""
    gb.cola_init()
    ahora = time.time()
    trabajo = APP / "share" / "inbox" / "trabajo"
    filas = []  # (id, raiz, estado, motor, ronda, hace_s, motivo, familia, result)

    def f(tid, estado, hace_s, motor="claude", raiz=None, ronda=0, motivo=None, fam=None, res=None):
        filas.append((tid, raiz or tid, estado, motor, ronda, hace_s, motivo, fam, res))

    f("t-va-curso", "en_curso", 75, motor="codex", fam={"estado": "en_curso", "encargo": "Escribe el resumen del lote"})
    f("t-va-revisando", "en_curso", 40, fam={"estado": "revisando", "encargo": "Arregla el carrusel de Summit"})
    f("t-va-decision", "necesita_decision", 600,
      fam={"estado": "necesita_decision", "encargo": "Sube la web a staging",
           "reporte": "Los jueces no coinciden: decide tú."})
    f("t-va-fallida", "fallida", 1200, motivo="claude no esta en el PATH de este usuario",
      fam={"estado": "fallida", "encargo": "Ordena las facturas"})
    f("t-va-cuarentena", "fallida", 1500, motor="gemini",
      fam={"estado": "en_cuarentena", "encargo": "Revisa el contrato", "reporte": "Fallo que no encaja: en cuarentena."})
    f("t-va-rechazada", "fallida", 300, motivo="rechazada por el usuario (definitivo, sin reintentos)",
      fam={"estado": "rechazada", "encargo": "No debe salir"})
    f("t-va-vieja", "fallida", 8 * 86400, fam={"estado": "fallida", "encargo": "Fallida de hace 8 días"})
    f("t-va-aprobada", "terminada", 900,
      fam={"estado": "aprobada", "encargo": "Traduce el brief", "costo_usd": 0.12, "tareas": ["t-va-aprobada"],
           "ultima_revision": {"aprobado": True}},
      res={"status": "ok", "motor": "claude", "duration_s": 42.0, "cost_usd": 0.12, "result": "Traducido y guardado."})
    f("t-va-sinrev", "terminada", 1000, motor="codex",
      fam={"estado": "sin_revision", "encargo": "Crea el archivo", "tareas": ["t-va-sinrev"]},
      res={"status": "ok", "motor": "codex", "duration_s": 29.0, "result": "LISTO"})
    f("t-va-ayer", "terminada", 30 * 3600, fam={"estado": "aprobada", "encargo": "Terminada hace 30 h"})
    f("t-va-r", "terminada", 700, fam=None)
    f("t-va-r-r2", "necesita_decision", 650, raiz="t-va-r", ronda=1,
      fam={"estado": "necesita_decision", "encargo": "Encargo con dos rondas", "tareas": ["t-va-r", "t-va-r-r2"]})
    f("t-va-cola", "en_cola", 20, motivo="espera hueco: el 1 lo ocupa t-va-curso (Codex)")
    f("t-va-arch", "archivada", 500, fam={"estado": "aprobada", "encargo": "Archivada"})
    f("t-va-espera-sin-archivo", "esperando_aprobacion", 100, fam={"estado": "esperando_aprobacion",
                                                                   "encargo": "Su encargo ya no está"})
    for n in range(12):
        f(f"t-va-lote-{n:02d}", "terminada", 2000 + n * 60, motor="codex",
          fam={"estado": "sin_revision", "encargo": f"Lote {n}"}, res={"status": "ok", "duration_s": 10 + n})
    con = sqlite3.connect(str(gb.COLA_DB))
    for tid, raiz, estado, motor, ronda, hace_s, motivo, fam, res in filas:
        ts = ahora - hace_s
        con.execute("INSERT OR REPLACE INTO tareas (id, archivo, estado, motor, ronda, raiz, creado_en, "
                    "actualizado_en, actualizado_ts, motivo) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (tid, str(gb.DONE / f"{tid}.task.json"), estado, motor, ronda, raiz, iso(ts), iso(ts), ts, motivo))
        if fam is not None:
            (gb.RESULTS / f"{raiz}.orquestacion.json").write_text(
                json.dumps(dict({"raiz": raiz, "tareas": [tid]}, **fam), ensure_ascii=False), encoding="utf-8")
        if res is not None:
            (gb.RESULTS / f"{tid}.result.json").write_text(json.dumps(dict({"id": tid}, **res)), encoding="utf-8")
    con.commit()
    con.close()
    del trabajo
    return {"terminadas_24h_sembradas": 14}


ESPERADO = {
    "trabajando": {"t-va-curso", "t-va-revisando"},
    "necesitan": {"t-va-decision", "t-va-fallida", "t-va-cuarentena", "t-va-r"},
    "fuera": {"t-va-rechazada", "t-va-vieja", "t-va-ayer", "t-va-arch", "t-va-espera-sin-archivo", "t-va-cola"},
}


def caso_a(gb):
    gb.state["current"], gb.state["current_motor"] = "t-va-curso", "codex"
    gb.state["paso"] = "Codex escribiendo el resumen"
    gb._ACT["started_at"] = (datetime.now().astimezone() - timedelta(seconds=75)).isoformat()
    gb._LIVE["d"] = {"cost_usd_estimado": 0.0123, "tokens_in": 1000, "tokens_out": 200}
    t0 = time.time()
    v = gb.vista_agentes()
    ms = round((time.time() - t0) * 1000, 1)
    ids = {c: [it["id"] for it in v[c]] for c in ("trabajando", "necesitan", "terminadas")}
    todos = set().union(*ids.values())
    cur = next((it for it in v["trabajando"] if it["id"] == "t-va-curso"), {})
    rev = next((it for it in v["trabajando"] if it["id"] == "t-va-revisando"), {})
    ap = next((it for it in v["terminadas"] if it["id"] == "t-va-aprobada"), {})
    r2 = next((it for it in v["necesitan"] if it["id"] == "t-va-r"), {})
    fal = next((it for it in v["necesitan"] if it["id"] == "t-va-fallida"), {})
    ok = (set(ids["trabajando"]) == ESPERADO["trabajando"] and set(ids["necesitan"]) == ESPERADO["necesitan"]
          and not (todos & ESPERADO["fuera"]) and len(v["terminadas"]) == 10 and v["mas"]["terminadas"] == 4
          and v["terminadas"][0]["id"] == "t-va-aprobada"
          and cur.get("hueco") == 1 and cur.get("cubo") == "chatgpt-plus" and 70 <= cur.get("segundos", 0) <= 120
          and cur.get("paso") == "Codex escribiendo el resumen" and cur.get("tokens") == 1200
          and cur.get("costo_vivo") == 0.0123
          and rev.get("estado") == "revisando" and rev.get("hueco") is None
          and ap.get("revision") == "aprobó" and ap.get("duracion_s") == 42.0 and ap.get("costo") == 0.12
          and ap.get("cubo") == "claude-max"
          and r2.get("tarea") == "t-va-r-r2" and r2.get("ronda") == 1
          and "PATH" in (fal.get("motivo") or "") and not fal.get("puede_aprobar")
          and v["en_cola"] == 1 and v["error"] is None)
    caso("a_estados_en_su_columna", ok, ids=ids, mas=v["mas"], en_cola=v["en_cola"], ms_lectura=ms,
         trabajando=v["trabajando"], ejemplo_terminada=ap, ejemplo_ronda=r2, ejemplo_fallida=fal,
         cubo_cuarentena=next((it["cubo"] for it in v["necesitan"] if it["id"] == "t-va-cuarentena"), None))
    return v


def _textos(w):
    """Todo el texto visible bajo un widget (CTk o Tk) y sus botones {texto: widget}."""
    txt, btn = [], {}
    pila = [w]
    while pila:
        x = pila.pop()
        try:
            pila.extend(reversed(x.winfo_children()))
        except Exception:
            continue
        cls = type(x).__name__
        try:
            t = x.cget("text")
        except Exception:
            continue
        if not t or cls in ("Label",) and type(x.master).__name__ in ("CTkLabel", "CTkButton"):
            continue  # el Label interno de un CTkLabel/CTkButton ya se cuenta en su dueño
        if "Button" in cls:
            btn.setdefault(str(t), []).append(x)
        else:
            txt.append(str(t))
    return txt, btn


def _tarjetas(gb, col):
    _head, box = gb._VA["cols"][col]
    out = {}
    for card in box.winfo_children():
        txt, btn = _textos(card)
        tid = next((t.split(" · ")[0] for t in txt if " · " in t and t.split(" · ")[0].startswith("t-")), None)
        if tid:
            out[tid] = {"textos": txt, "botones": sorted(btn), "_b": btn}
    return out


def pintar_ya(gb, root, espera=10):
    gb._VA["leyendo"] = False
    gb._va_pedir()
    fin = time.time() + espera
    while gb._VA["leyendo"] and time.time() < fin:
        time.sleep(0.05)
    t0 = time.time()
    gb._drain_ui_queue()
    root.update()
    return round((time.time() - t0) * 1000, 1)


def caso_b(gb, root, kit):
    import tkinter as tk
    from tkinter import ttk
    if kit == "tk":
        os.environ["GROWI_BRIDGE_CTK"] = "0"
    else:
        os.environ.pop("GROWI_BRIDGE_CTK", None)
    page = tk.Frame(root, bg=gb.THEME["bg"])
    page.pack(fill="both", expand=True)
    gb._vista_agentes_build(page)
    ms_pinta = pintar_ya(gb, root)
    cols = {c: _tarjetas(gb, c) for c in ("trabajando", "necesitan", "terminadas")}
    heads = {c: gb._VA["cols"][c][0].cget("text") for c in cols}
    pie = gb._VA["pie"].cget("text")
    # «Ver»: selecciona la tarea en la lista (un Treeview de verdad, oculto como todo)
    vistos = {}
    tree = ttk.Treeview(page, columns=("tarea",), show="headings")
    tree.insert("", "end", iid="t-va-aprobada", values=("t-va-aprobada",))
    gb._widgets["tasks_tree"] = tree
    gb._widgets["show_page"] = lambda p: vistos.setdefault("pagina", p)
    gb._refresh_tasks_ui = lambda: None
    gb._show_task_detail = lambda _e=None: vistos.setdefault("detalle", tree.selection())
    cols["terminadas"]["t-va-aprobada"]["_b"]["Ver"][0].invoke()
    sin_botones = all(c["botones"] == ["Ver"] for k in ("trabajando", "terminadas") for c in cols[k].values())
    sin_aprobar_en_fallidas = all("Aprobar" not in c["botones"] for c in cols["necesitan"].values())
    cur = cols["trabajando"].get("t-va-curso", {}).get("textos", [])
    ok = (set(cols["trabajando"]) == ESPERADO["trabajando"] and set(cols["necesitan"]) == ESPERADO["necesitan"]
          and len(cols["terminadas"]) == 10 and sin_botones and sin_aprobar_en_fallidas
          and heads["terminadas"] == "Terminadas (14)" and heads["trabajando"] == "Trabajando (2)"
          and any("hueco 1" in t and "cubo chatgpt-plus" in t for t in cur)
          and any("Codex escribiendo el resumen" in t and "1.2 k tokens" in t for t in cur)
          and "En cola: 1 tarea" in pie and vistos.get("pagina") == "tareas"
          and tuple(vistos.get("detalle") or ()) == ("t-va-aprobada",)
          and any("y 4 más" in t for t in _textos(gb._VA["cols"]["terminadas"][1])[0]))
    # el tiempo se repinta solo, sin rehacer las tarjetas
    antes = [str(w) for w in gb._VA["vars"]]
    time.sleep(1.2)
    pintar_ya(gb, root)
    mismas = antes == [str(w) for w in gb._VA["vars"]]
    caso(f"b_tablero_{kit}", ok and mismas, kit=gb._VA["kit"].nombre, cabeceras=heads, pie=pie,
         trabajando={k: v["textos"] for k, v in cols["trabajando"].items()},
         necesitan={k: {"textos": v["textos"], "botones": v["botones"]} for k, v in cols["necesitan"].items()},
         terminadas=sorted(cols["terminadas"]), ver=vistos, tarjetas_reutilizadas=mismas, ms_pintar=ms_pinta)
    page.destroy()


def caso_c(gb):
    class H(gb.BridgeHandler):
        SECRET = SECRETO

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/gateway/agentes"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {SECRETO}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d, code = json.loads(r.read().decode("utf-8")), r.status
        try:
            urllib.request.urlopen(url, timeout=10)
            sin = None
        except urllib.error.HTTPError as e:
            sin = e.code
    finally:
        srv.shutdown()
    local = gb.vista_agentes()

    def ids(x):
        return {c: [it["id"] for it in x[c]] for c in ("trabajando", "necesitan", "terminadas")}
    caso("c_gateway_agentes", code == 200 and sin == 401 and ids(d) == ids(local) and d["en_cola"] == local["en_cola"],
         codigo=code, sin_token=sin, ids=ids(d), claves=sorted(d))


def limpiar_sembrado(gb):
    con = sqlite3.connect(str(gb.COLA_DB))
    con.execute("DELETE FROM tareas WHERE id LIKE 't-va-%'")
    con.commit()
    con.close()
    for p in gb.RESULTS.glob("t-va-*"):
        p.unlink()
    gb.state["current"] = None
    gb.state["paso"] = None
    gb._LIVE["d"] = None


def esperar(cond, seg, cada=0.5):
    fin = time.time() + seg
    while time.time() < fin:
        r = cond()
        if r:
            return r
        time.sleep(cada)
    return cond()


def caso_d(gb, root):
    import tkinter as tk
    os.environ.pop("GROWI_BRIDGE_CTK", None)
    page = tk.Frame(root, bg=gb.THEME["bg"])
    page.pack(fill="both", expand=True)
    gb._vista_agentes_build(page)
    avisos = []
    gb.messagebox.showinfo = lambda *a, **k: avisos.append(a)  # nunca un diálogo de verdad
    gb._espera_refrescar = lambda: None
    trabajo = APP / "share" / "inbox" / "trabajo"
    gb.POLL_SECONDS = 1
    gb.state["runner"] = "corriendo"
    stop = threading.Event()
    threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
    linea = []  # (segundos, columna de t-va-codex, estado)
    t0 = time.time()

    def donde(tid):
        v = gb.vista_agentes()
        for c in ("necesitan", "trabajando", "terminadas"):
            for it in v[c]:
                if it["id"] == tid:
                    return c, it
        return None, None
    try:
        for tid in ("t-va-codex", "t-va-no"):
            task = {"id": tid, "motor": "codex", "cwd": str(trabajo), "timeout_min": 10,
                    "permission_mode": "acceptEdits", "revisar": False, "memoria": False,
                    # R1 declarada: con el guardrail «siempre» queda retenida hasta tu sí
                    "acciones": [{"tipo": "crear_en_proyecto", "ruta": str(trabajo / f"{tid}.txt")}],
                    "prompt": f"Crea en esta carpeta el archivo {tid}.txt con una sola línea: listo. "
                              "No hagas nada más y responde LISTO."}
            tmp = gb.TASKS / f"{tid}.tmp"
            tmp.write_text(json.dumps(task, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, gb.TASKS / f"{tid}.task.json")
        retenidas = esperar(lambda: all(donde(t)[0] == "necesitan" for t in ("t-va-codex", "t-va-no")), 90)
        pintar_ya(gb, root)
        nec = _tarjetas(gb, "necesitan")
        botones = {t: nec.get(t, {}).get("botones") for t in ("t-va-codex", "t-va-no")}
        _c, it_no = donde("t-va-no")
        nec["t-va-no"]["_b"]["Rechazar"][0].invoke()
        pintar_ya(gb, root)
        rechazo_fuera = donde("t-va-no")[0] is None and "t-va-no" not in _tarjetas(gb, "necesitan")
        fam_no = gb.load_family("t-va-no") or {}
        nec["t-va-codex"]["_b"]["Aprobar"][0].invoke()
        linea.append((round(time.time() - t0, 1), "necesitan", "aprobada desde el tablero"))
        ultimo = None
        tablero_trabajando = False
        fin = time.time() + 600
        while time.time() < fin:
            c, it = donde("t-va-codex")
            if (c, it and it["estado"]) != ultimo:
                ultimo = (c, it and it["estado"])
                linea.append((round(time.time() - t0, 1), c, it and it["estado"],
                              it and (it.get("paso") or it.get("revision"))))
            if c == "trabajando" and not tablero_trabajando:
                pintar_ya(gb, root)
                tablero_trabajando = "t-va-codex" in _tarjetas(gb, "trabajando")
            if c == "terminadas":
                break
            time.sleep(1)
        pintar_ya(gb, root)
        term = _tarjetas(gb, "terminadas").get("t-va-codex", {})
        _c, it = donde("t-va-codex")
        f = trabajo / "t-va-codex.txt"
        cols = [x[1] for x in linea]
        ok = (bool(retenidas) and botones["t-va-codex"] == ["Aprobar", "Rechazar", "Ver"]
              and rechazo_fuera and fam_no.get("estado") == "rechazada"
              and "trabajando" in cols and cols[-1] == "terminadas"
              and cols.index("trabajando") < cols.index("terminadas") and tablero_trabajando
              and bool(term) and f.exists() and it and it["motor"] == "codex" and it["cubo"] == "chatgpt-plus"
              and it["costo"] is None and it["costo_txt"] == "costo sin dato"  # codex no da costo: nunca un $0 falso
              and not avisos)
        caso("d_codex_te_necesitan_trabajando_terminadas", ok, linea=linea, botones_retenidas=botones,
             aprobacion_no=it_no and {k: it_no.get(k) for k in ("approval_id", "nivel", "vence_txt", "motivo")},
             rechazada={"fuera_del_tablero": rechazo_fuera, "familia": fam_no.get("estado")},
             tarjeta_en_trabajando=tablero_trabajando, tarjeta_terminada=term.get("textos"),
             terminada=it, archivo=f.read_text(encoding="utf-8").strip() if f.exists() else None, avisos=avisos)
    finally:
        stop.set()
        time.sleep(2)
        page.destroy()


def main():
    p052.preparar()
    sp = APP / "settings.json"
    s = json.loads(sp.read_text(encoding="utf-8"))
    s["guardrail"] = "siempre"
    s.pop("limites_cubo", None)
    sp.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    gb = p052.cargar()
    for d in (gb.RESULTS, gb.TASKS, gb.DONE, gb.WAITING):
        d.mkdir(parents=True, exist_ok=True)
    OUT["siembra"] = sembrar(gb)
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # nunca se muestra ni toma el foco
    gb._root = root
    try:
        caso_a(gb)
        caso_b(gb, root, "ctk")
        caso_b(gb, root, "tk")
        caso_c(gb)
        # e) lo que tarda pintar en el hilo de la ventana con todo sembrado (leer va en otro hilo)
        page = tk.Frame(root)
        gb._vista_agentes_build(page)
        tiempos = []
        for _ in range(5):
            gb._VA["fp"] = None
            tiempos.append(pintar_ya(gb, root))
        t0 = time.time()
        gb.vista_agentes()
        lectura = round((time.time() - t0) * 1000, 1)
        page.destroy()
        caso("e_refresco_sin_congelar", max(tiempos) < 500, ms_pintar_en_ventana=tiempos,
             ms_leer_en_hilo=lectura, cada_ms=gb.VA_CADA_MS)
        limpiar_sembrado(gb)
        if not SIN_MOTORES:
            caso_d(gb, root)
    finally:
        root.destroy()
    OUT["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT["todo_ok"] = all(c["ok"] for c in OUT["casos"].values())
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=2, default=str),
                                         encoding="utf-8")
    log = APP / "growi-bridge.log"
    if log.exists():
        shutil.copy2(log, EVID / "growi-bridge-aislada.log")
    print("TODO OK" if OUT["todo_ok"] else "HAY FALLOS", flush=True)


if __name__ == "__main__":
    main()
