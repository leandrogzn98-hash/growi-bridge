"""Prueba de t-workflows-052 (workflows reutilizables) en una instancia AISLADA.

C:\\Users\\forte\\growi-bridge\\_prueba-workflows-052\\app\\ = el growi-bridge.py y
el engines.json del REPO + la config de la app instalada (solo se lee), con su
propia share, cola.db, log, settings.json y workflows\\. La ventana NUNCA se
muestra: la tarjeta se construye en un Tk retirado (withdraw) y los botones se
pulsan con invoke(). Los motores se lanzan ocultos.

  a) validacion: ciclo, dependencia que no existe, {x} sin declarar,
     {resultado:} de un paso que no es anterior, motor que no existe,
     parametro que falta -> cada uno con su motivo y nada encolado
  b) estimado: sin historial (grueso), con 3 ejecuciones sembradas (total y
     rango esperados, «basado en 3 ejecuciones previas»), otra version de los
     pasos, un workflow nuevo (tus tareas parecidas) y un paso de codex ($0 extra);
     «Guardar como workflow» desde un plan hecho a mano y desde el detalle
  c) /gateway/workflows con token = workflows_vista(); sin token, 401
  f) la tarjeta (CustomTkinter y Tk clasico): estimado, «Pasos», formulario de
     parametros, umbral por plan -> «Ejecutar igual» -> encolado
  d) de verdad, 3 ejecuciones de un workflow de 3 pasos con Haiku: orden
     (cada paso empieza despues de que termina el anterior), {resultado:}
     rellenado, archivos, y estimado contra real en cada ejecucion
  e) fallo a mitad con el guardrail «siempre»: el paso 1 (codex) espera tu si y
     el 2 no arranca; aprobado, corre; el 2 (motor desactivado) falla ->
     el plan necesita tu decision y el 3 nunca se encola

Uso: python prueba_workflows_052.py [--sin-motores]   (sin-motores: a, b, c, f)
Evidencia: pruebas\\evidencia\\workflows-052\\resultado.json
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
from datetime import datetime
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
p052.BASE = p052.REAL / "_prueba-workflows-052"
p052.APP = p052.BASE / "app"
APP = p052.APP
EVID = REPO / "pruebas" / "evidencia" / "workflows-052"
SIN_MOTORES = "--sin-motores" in sys.argv
OUT: dict = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "casos": {}}
SECRETO = "secreto-de-prueba-workflows"


def caso(k, ok, **datos):
    OUT["casos"][k] = dict(ok=bool(ok), **datos)
    print(f"[{'OK' if ok else 'FALLA'}] {k}: {json.dumps(datos, ensure_ascii=False, default=str)[:600]}", flush=True)


def escribir_wf(gb, d):
    gb.WF_DIR.mkdir(parents=True, exist_ok=True)
    (gb.WF_DIR / f"{d['id']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def tareas_en_cola(gb):
    return sorted(p.name for p in gb.TASKS.glob("*.task.json"))


def ajustes(gb, **kw):
    s = gb.load_settings()
    s.update(kw)
    gb.save_settings(s)


# ------------------------------------------------------------------ a
def caso_a(gb):
    base = {"id": "malo", "nombre": "Malo", "pasos": [{"id": "uno", "prompt": "hola"}]}
    malos = {
        "ciclo": dict(base, pasos=[{"id": "a", "prompt": "x", "depende_de": ["b"]},
                                   {"id": "b", "prompt": "y", "depende_de": ["a"]}]),
        "dependencia_inexistente": dict(base, pasos=[{"id": "a", "prompt": "x", "depende_de": ["fantasma"]}]),
        "param_sin_declarar": dict(base, pasos=[{"id": "a", "prompt": "Traduce {texto}"}]),
        "resultado_no_anterior": dict(base, pasos=[{"id": "a", "prompt": "x {resultado:b}"},
                                                   {"id": "b", "prompt": "y", "depende_de": []}]),
        "motor_inexistente": dict(base, pasos=[{"id": "a", "prompt": "x", "motor": "motor:noexiste"}]),
        "id_raro": dict(base, id="Con Espacios"),
        "sin_pasos": dict(base, pasos=[]),
    }
    motivos = {k: gb.wf_validar(d)[1] for k, d in malos.items()}
    claves = {"ciclo": "ciclo", "dependencia_inexistente": "fantasma", "param_sin_declarar": "{texto}",
              "resultado_no_anterior": "{resultado:b}", "motor_inexistente": "noexiste", "id_raro": "id",
              "sin_pasos": "pasos"}
    ok_motivos = all(motivos[k] and claves[k] in motivos[k] for k in malos)
    # bueno: sin depende_de -> depende del anterior; con depende_de [] -> empieza solo
    wf, err = gb.wf_validar({"id": "bueno", "nombre": "Bueno", "parametros": [{"nombre": "x"}],
                             "pasos": [{"id": "a", "prompt": "uno {x}"}, {"id": "b", "prompt": "dos"},
                                       {"id": "c", "prompt": "tres {resultado:a}", "depende_de": ["b"]}]})
    deps = [p["depende_de"] for p in wf["pasos"]] if wf else None
    # parametro que falta al ejecutar: no se encola nada
    escribir_wf(gb, {"id": "con-param", "nombre": "Con parámetro",
                     "parametros": [{"nombre": "archivo", "pregunta": "¿Qué archivo?"}],
                     "pasos": [{"id": "a", "prompt": "Lee {archivo}"}]})
    antes = tareas_en_cola(gb)
    r = gb.encolar_workflow("con-param", {})
    # un archivo roto sale en la lista con su motivo, sin poder ejecutarse
    (gb.WF_DIR / "roto.json").write_text("{ esto no es json", encoding="utf-8")
    roto = next(x for x in gb.workflows_cargar() if x["id"] == "roto")
    caso("a_validacion", ok_motivos and err is None and deps == [[], ["a"], ["b"]] and not r["ok"]
         and r.get("faltan") == ["¿Qué archivo?"] and tareas_en_cola(gb) == antes and roto["error"] and not roto["wf"],
         motivos=motivos, bueno_depende_de=deps, falta_param=r.get("error"), roto=roto["error"])
    (gb.WF_DIR / "roto.json").unlink()
    (gb.WF_DIR / "con-param.json").unlink()


# ------------------------------------------------------------------ b
WF_SEMBRADO = {"id": "sembrado", "nombre": "Sembrado (3 pasos)", "descripcion": "historial sembrado",
               "motor": "haiku", "pasos": [{"id": "uno", "prompt": "Paso uno"}, {"id": "dos", "prompt": "Paso dos"},
                                           {"id": "tres", "prompt": "Paso tres"}]}
COSTOS = {"uno": [0.010, 0.012, 0.014], "dos": [0.020, 0.022, 0.030], "tres": [0.005, 0.006, 0.007]}


def sembrar_historial(gb, wf):
    now = gb._now_iso()
    for i in range(3):
        pid = f"wf-sembrado-2026010{i + 1}-120000"
        gb._cola("INSERT OR REPLACE INTO dag_planes (plan_id, estado, orden, creado_en, actualizado_en) "
                 "VALUES (?,?,?,?,?)", (pid, "terminado", json.dumps(["uno", "dos", "tres"]), now, now))
        gb._cola("INSERT OR REPLACE INTO workflow_runs (plan_id, workflow_id, nombre, huella, parametros, estimado, "
                 "creado_en) VALUES (?,?,?,?,?,?,?)", (pid, "sembrado", wf["nombre"], wf["huella"], "{}",
                                                        json.dumps({"medio": {"equiv": 0.04, "real": 0}}),
                                                        f"2026-01-0{i + 1}T12:00:00-04:00"))
        for n, fid in enumerate(("uno", "dos", "tres"), 1):
            tid = f"{pid}-{fid}"
            gb._cola("INSERT OR REPLACE INTO dag_fases (plan_id, fase_id, n, prompt, depende_de, al_fallar, criterios, "
                     "estado, task_id, actualizado_en, extra) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (pid, fid, n, "x", "[]", "pedir_decision", "[]", "terminada", tid, now,
                      json.dumps({"dinero": "equiv"})))
            c = COSTOS[fid][i]
            (gb.RESULTS / f"{tid}.result.json").write_text(json.dumps(
                {"id": tid, "motor": "claude", "status": "ok", "cost_usd": c, "result": "ok"}), encoding="utf-8")
            gb._family_update(tid, sumar_costo=c, tarea=tid, estado="sin_revision")


def limpiar_historial(gb):
    for t in ("dag_planes", "dag_fases", "workflow_runs"):
        gb._cola(f"DELETE FROM {t} WHERE plan_id LIKE 'wf-sembrado-%' OR plan_id LIKE 'plan-manual%'")
    for p in list(gb.RESULTS.glob("wf-sembrado-*")) + list(gb.RESULTS.glob("plan-manual*")):
        p.unlink()
    gb._WF_MEMO.clear()


def caso_b(gb):
    escribir_wf(gb, WF_SEMBRADO)
    wf = gb.wf_get("sembrado")["wf"]
    e0 = gb.wf_estimar(wf)
    grueso = (e0["ejecuciones"] == 0 and {p["fuente"] for p in e0["pasos"]} == {"grueso"}
              and "estimado grueso" in e0["texto"])
    sembrar_historial(gb, wf)
    e1 = gb.wf_estimar(wf)
    medio, rango = e1["medio"]["equiv"], e1["rango"]["equiv"]
    esperado_medio = 0.012 + 0.022 + 0.006
    esperado_rango = [0.010 + 0.020 + 0.005, 0.014 + 0.030 + 0.007]
    ok_hist = (abs(medio - esperado_medio) < 1e-9 and all(abs(a - b) < 1e-9 for a, b in zip(rango, esperado_rango))
               and e1["ejecuciones"] == 3 and "basado en 3 ejecuciones previas" in e1["texto"]
               and all(p["fuente"] == "historial" and p["n"] == 3 for p in e1["pasos"]))
    # otra version de los pasos: sigue usando el historial, pero lo dice
    escribir_wf(gb, dict(WF_SEMBRADO, pasos=[{"id": "uno", "prompt": "Paso uno, cambiado"},
                                             {"id": "dos", "prompt": "Paso dos"}, {"id": "tres", "prompt": "Paso tres"}]))
    e2 = gb.wf_estimar(gb.wf_get("sembrado")["wf"])
    ok_version = "(0 con esta versión de los pasos)" in e2["texto"] and e2["ejecuciones"] == 3
    escribir_wf(gb, WF_SEMBRADO)
    # un workflow nuevo: sin ejecuciones previas, tus tareas parecidas (9 results de claude sembrados)
    escribir_wf(gb, {"id": "nuevo", "nombre": "Nuevo", "motor": "haiku",
                     "pasos": [{"id": "a", "prompt": "Escribe un saludo"},
                               {"id": "b", "prompt": "Resúmelo", "motor": "motor:codex"}]})
    e3 = gb.wf_estimar(gb.wf_get("nuevo")["wf"])
    fu = {p["id"]: p for p in e3["pasos"]}
    ok_nuevo = (fu["a"]["fuente"] == "parecidas" and fu["b"]["fuente"] == "sin_costo"
                and fu["b"]["texto"] == "$0 extra (va con la suscripción)" and "tus tareas parecidas" in e3["texto"]
                and "más 1 paso a $0 extra" in e3["texto"])
    caso("b_estimado", grueso and ok_hist and ok_version and ok_nuevo,
         sin_historial=e0["texto"], con_historial=e1["texto"], medio=medio, rango=rango,
         esperado={"medio": esperado_medio, "rango": esperado_rango}, otra_version=e2["texto"], nuevo=e3["texto"])
    (gb.WF_DIR / "nuevo.json").unlink()
    # «Guardar como workflow» desde un plan hecho a mano (sin workflow) y desde el detalle de una fase suya
    now = gb._now_iso()
    gb._cola("INSERT OR REPLACE INTO dag_planes (plan_id, estado, orden, motor, creado_en, actualizado_en) "
             "VALUES (?,?,?,?,?,?)", ("plan-manual", "terminado", json.dumps(["a", "b"]), "codex", now, now))
    for n, (fid, deps) in enumerate((("a", []), ("b", ["a"])), 1):
        gb._cola("INSERT OR REPLACE INTO dag_fases (plan_id, fase_id, n, prompt, depende_de, al_fallar, criterios, "
                 "estado, task_id, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
                 ("plan-manual", fid, n, f"Fase {fid}", json.dumps(deps), "saltar_con_aviso",
                  json.dumps(["algo existe"]), "terminada", f"plan-manual-{fid}", now))
    ok1, ruta1 = gb.wf_desde_plan("plan-manual")
    g1 = json.loads(Path(ruta1).read_text(encoding="utf-8")) if ok1 else {}
    gb._tdet_fila = lambda: {"id": "plan-manual-b"}  # el detalle con una FASE del plan elegida
    msg = gb._tdet_guardar_wf()
    gb._tdet_fila = lambda: {"id": "t-suelta"}
    msg_no = gb._tdet_guardar_wf()
    copia = gb.WF_DIR / "plan-manual-2.json"
    ok_guardar = (ok1 and g1["pasos"][1]["depende_de"] == ["a"] and g1["pasos"][0]["motor"] == "motor:codex"
                  and g1["pasos"][0]["al_fallar"] == "saltar_con_aviso" and g1["pasos"][0]["criterios"] == ["algo existe"]
                  and gb.wf_validar(g1)[1] is None and "Guardado en" in msg and copia.exists()
                  and "Solo un plan" in msg_no and gb.wf_plan_de("plan-manual-a") == "plan-manual")
    caso("b_guardar_como_workflow", ok_guardar, guardado=g1, detalle=msg, copia=copia.name, fila_suelta=msg_no)
    for f in (Path(ruta1) if ok1 else None, copia):
        if f and f.exists():
            f.unlink()


# ------------------------------------------------------------------ c
def caso_c(gb):
    class H(gb.BridgeHandler):
        SECRET = SECRETO

        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/gateway/workflows"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {SECRETO}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d, code = json.loads(r.read().decode("utf-8")), r.status
        try:
            urllib.request.urlopen(url, timeout=10)
            sin = None
        except urllib.error.HTTPError as e:
            sin = e.code
    finally:
        srv.shutdown()
    local = gb.workflows_vista()

    def resumen(x):
        return [(w["id"], (w.get("estimado") or {}).get("texto")) for w in x["workflows"]]
    caso("c_gateway_workflows", code == 200 and sin == 401 and resumen(d) == resumen(local),
         codigo=code, sin_token=sin, workflows=resumen(d))


# ------------------------------------------------------------------ f
def _textos(w):
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
            continue
        if "Button" in cls:
            btn.setdefault(str(t), []).append(x)
        else:
            txt.append(str(t))
    return txt, btn


def pintar_ya(gb, root, espera=30):
    gb._WFUI["leyendo"] = False
    gb._wf_pedir()
    fin = time.time() + espera
    while gb._WFUI["leyendo"] and time.time() < fin:
        time.sleep(0.05)
    gb._drain_ui_queue()
    root.update()


def esperar_lanzado(gb, root, espera=30):
    fin = time.time() + espera
    while time.time() < fin:
        gb._drain_ui_queue()
        root.update()
        if not gb._WFUI["lanzando"]:
            break
        time.sleep(0.05)
    for _ in range(40):  # el _wf_pedir del final
        gb._drain_ui_queue()
        root.update()
        time.sleep(0.05)


def caso_f(gb, root, kit):
    import tkinter as tk
    if kit == "tk":
        os.environ["GROWI_BRIDGE_CTK"] = "0"
    else:
        os.environ.pop("GROWI_BRIDGE_CTK", None)
    escribir_wf(gb, {"id": "con-idioma", "nombre": "Con idioma", "motor": "haiku",
                     "parametros": [{"nombre": "tema", "pregunta": "¿Sobre qué?"},
                                    {"nombre": "idioma", "pregunta": "¿Idioma?", "por_defecto": "es"}],
                     "pasos": [{"id": "a", "prompt": "Escribe sobre {tema} en {idioma}"}]})
    page = tk.Frame(root, bg=gb.THEME["bg"])
    page.pack(fill="both", expand=True)
    gb._WFUI.update(abiertos=set(), form=None, confirmar=None, lanzando=False)
    gb._workflows_build(page)
    pintar_ya(gb, root)
    tipo = type(gb._WFUI["kit"]).__name__
    txt, btn = _textos(gb._WFUI["box"])
    ok_lista = ("Sembrado (3 pasos)" in txt and any("basado en 3 ejecuciones previas" in t for t in txt)
                and any(t.startswith("Última (terminada") for t in txt) and len(btn.get("Ejecutar", [])) == 2)
    gb._WFUI["botones"]["sembrado"]["pasos"].invoke()
    txt2, _b = _textos(gb._WFUI["box"])
    ok_pasos = any(t.startswith("1. uno — claude haiku · empieza") and "2. dos — claude haiku · después de uno" in t
                   for t in txt2)
    # con parametros: «Ejecutar» abre el formulario; el umbral por plan, minimo -> «Ejecutar igual»
    ajustes(gb, umbral_plan_usd=0.000001)
    gb._WFUI["botones"]["con-idioma"]["ejecutar"].invoke()
    txt3, btn3 = _textos(gb._WFUI["box"])
    entradas = dict(gb._WFUI["entradas"])
    ok_form = ("¿Sobre qué?" in txt3 and "¿Idioma? (opcional)" in txt3 and "Lanzar" in btn3
               and entradas["idioma"].get() == "es")
    entradas["tema"].insert(0, "los gatos")
    antes = tareas_en_cola(gb)
    gb._WFUI["botones"]["con-idioma"]["lanzar"].invoke()
    esperar_lanzado(gb, root)
    txt4, btn4 = _textos(gb._WFUI["box"])
    pide = (any("pasa tu umbral por plan" in t for t in txt4) and "Ejecutar igual" in btn4
            and tareas_en_cola(gb) == antes)
    gb._WFUI["botones"]["con-idioma"]["igual"].invoke()
    esperar_lanzado(gb, root)
    r = gb._WFUI.get("ultimo_lanzado") or {}
    nuevas = sorted(set(tareas_en_cola(gb)) - set(antes))
    plan = json.loads((gb.TASKS / nuevas[0]).read_text(encoding="utf-8")) if nuevas else {}
    msg = gb._WFUI["msg"].cget("text")
    ok_lanza = (r.get("ok") and len(nuevas) == 1 and plan["fases"][0]["prompt"] == "Escribe sobre los gatos en es"
                and plan["fases"][0]["model"] == "haiku" and plan["workflow"]["parametros"] == {"tema": "los gatos",
                                                                                              "idioma": "es"}
                and Path(plan["cwd"]).is_dir() and msg.startswith("Lanzado como wf-con-idioma-"))
    for n in nuevas:
        (gb.TASKS / n).unlink()  # no se corre: el runner no está encendido en este caso
    if plan.get("cwd"):
        shutil.rmtree(plan["cwd"], ignore_errors=True)
    ajustes(gb, umbral_plan_usd=5.0)
    page.destroy()
    gb._WFUI.update(kit=None, box=None, msg=None)
    (gb.WF_DIR / "con-idioma.json").unlink()
    caso(f"f_tarjeta_{kit}", ok_lista and ok_pasos and ok_form and pide and ok_lanza, kit=tipo,
         lista=ok_lista, pasos=ok_pasos, formulario=ok_form, umbral_pide_confirmacion=pide, lanzado=ok_lanza,
         textos=txt2, aviso=msg, plan_fase=plan.get("fases", [{}])[0])


# ------------------------------------------------------------------ d / e: de verdad
def esperar(cond, seg, cada=1.0):
    fin = time.time() + seg
    while time.time() < fin:
        r = cond()
        if r:
            return r
        time.sleep(cada)
    return None


def _ts(iso):
    return datetime.fromisoformat(iso).timestamp() if iso else None


WF_REAL = {"id": "tres-pasos", "nombre": "Tres pasos (prueba)", "descripcion": "rojo → verde → azul",
           "motor": "haiku", "al_fallar": "pedir_decision",
           "pasos": [
               {"id": "rojo", "revisar": False,
                "prompt": "Crea en esta carpeta el archivo uno.txt con una sola línea: rojo. No hagas nada más. "
                          "Responde solo: ROJO."},
               {"id": "verde", "revisar": False,
                "prompt": "Lee uno.txt de esta carpeta y crea dos.txt con esa línea y debajo otra: verde. "
                          "No hagas nada más. Responde solo: VERDE-{n}."},
               {"id": "azul", "revisar": False,
                "prompt": "El paso anterior respondió: «{resultado:verde}». Crea tres.txt con el contenido de "
                          "dos.txt y debajo una línea más con lo que respondió el paso anterior. No hagas nada "
                          "más. Responde solo: AZUL."}],
           "parametros": [{"nombre": "n", "pregunta": "número de la ejecución", "por_defecto": "0"}]}


def arrancar_runner(gb):
    gb.messagebox.showinfo = lambda *a, **k: None  # nunca un diálogo de verdad
    gb._espera_refrescar = lambda: None
    gb.POLL_SECONDS = 1
    gb.state["runner"] = "corriendo"
    stop = threading.Event()
    threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()
    return stop


def caso_d(gb):
    escribir_wf(gb, WF_REAL)
    corridas = []
    for n in (1, 2, 3):
        wf = gb.wf_get("tres-pasos")["wf"]
        est = gb.wf_estimar(wf)
        r = gb.encolar_workflow("tres-pasos", {"n": str(n)})
        if not r["ok"]:
            corridas.append({"n": n, "error": r["error"]})
            break
        pid = r["id"]
        fin = esperar(lambda p=pid: (gb._dag_plan(p) or {}).get("estado") in ("terminado", "necesita_decision",
                                                                           "abortado", "detenido"), 900)
        plan = gb._dag_plan(pid) or {}
        fases = gb._dag_fases(pid)
        pasos = []
        for f in fases:
            res = json.loads((gb.RESULTS / f"{f['task_id']}.result.json").read_text(encoding="utf-8"))
            pasos.append({"id": f["fase_id"], "estado": f["estado"], "inicio": res.get("started_at"),
                          "fin": res.get("finished_at"), "costo": gb.wf_costo_tarea(f["task_id"]),
                          "respuesta": str(res.get("result") or "")[:80], "motor": res.get("motor"),
                          "modelo": res.get("model") or res.get("modelo")})
        orden_ok = all(_ts(pasos[i + 1]["inicio"]) >= _ts(pasos[i]["fin"]) for i in range(len(pasos) - 1)
                       if pasos[i]["fin"] and pasos[i + 1]["inicio"])
        t3 = json.loads((gb.DONE / f"{pid}-azul.task.json").read_text(encoding="utf-8"))
        cwd = Path(r["cwd"])
        tres = (cwd / "tres.txt").read_text(encoding="utf-8").strip() if (cwd / "tres.txt").exists() else None
        ult = gb.wf_ultima("tres-pasos")
        real = round(sum(p["costo"] or 0 for p in pasos), 6)
        e_tot = est["medio"]["equiv"] + est["medio"]["real"]
        corridas.append({"n": n, "plan": pid, "estado_plan": plan.get("estado"), "fin_en_tiempo": bool(fin),
                         "estimado_texto": est["texto"], "estimado": round(e_tot, 6),
                         "rango": est["rango"]["equiv"], "fuentes": est["fuentes"], "real": real,
                         "error_pct": round((real - e_tot) / e_tot * 100) if e_tot else None,
                         "real_en_rango": est["rango"]["equiv"][0] <= real <= est["rango"]["equiv"][1],
                         "pasos": pasos, "orden_ok": orden_ok,
                         "resultado_rellenado": f"VERDE-{n}" in t3["prompt"] and "{resultado:" not in t3["prompt"],
                         "tres_txt": tres, "ultima": ult and ult["texto"]})
    ok = (len(corridas) == 3 and all(c.get("estado_plan") == "terminado" and c["orden_ok"] and c["resultado_rellenado"]
                                     and c["tres_txt"] and f"VERDE-{c['n']}" in c["tres_txt"]
                                     and all(p["costo"] for p in c["pasos"]) for c in corridas)
          and corridas[0]["fuentes"] != ["historial"] and corridas[2]["fuentes"] == ["historial"]
          and "basado en 2 ejecuciones previas" in corridas[2]["estimado_texto"])
    caso("d_tres_ejecuciones_haiku", ok, corridas=corridas)


def caso_e(gb):
    ajustes(gb, guardrail="siempre", motores_off=["gemini"])
    trabajo = gb.WF_RUNS
    escribir_wf(gb, {"id": "fallo-a-mitad", "nombre": "Fallo a mitad", "al_fallar": "pedir_decision",
                     "pasos": [{"id": "codex", "motor": "motor:codex", "revisar": False,
                                "acciones": [{"tipo": "crear_en_proyecto", "ruta": str(trabajo)}],
                                "prompt": "Crea en esta carpeta el archivo hecho.txt con una sola línea: hecho. "
                                          "No hagas nada más y responde HECHO."},
                               {"id": "gemini", "motor": "motor:gemini", "prompt": "Esto no debe correr: gemini está "
                                                                                   "desactivado"},
                               {"id": "final", "prompt": "Esto nunca se encola", "motor": "haiku"}]})
    r = gb.encolar_workflow("fallo-a-mitad")
    pid = r["id"]
    tid1 = f"{pid}-codex"
    retenida = esperar(lambda: (gb.cola_get(tid1) or {}).get("estado") == "esperando_aprobacion", 120)
    fases_retenida = {f["fase_id"]: f["estado"] for f in gb._dag_fases(pid)}
    no_arranco_2 = not (gb.TASKS / f"{pid}-gemini.task.json").exists() and fases_retenida["gemini"] == "pendiente"
    apr = gb.apr_de_raiz(tid1) or {}
    ok_apr = gb.approve_waiting(tid1, apr.get("approval_id"))
    fin = esperar(lambda: (gb._dag_plan(pid) or {}).get("estado") != "en_curso", 600)
    plan = gb._dag_plan(pid) or {}
    fases = {f["fase_id"]: (f["estado"], f.get("motivo")) for f in gb._dag_fases(pid)}
    hecho = Path(r["cwd"]) / "hecho.txt"
    txt = gb.dag_txt(pid)
    ok = (bool(retenida) and no_arranco_2 and bool(fin) and plan.get("estado") == "necesita_decision"
          and fases["codex"][0] == "terminada" and fases["gemini"][0] == "necesita_decision"
          and fases["final"][0] == "pendiente" and not (gb.DONE / f"{pid}-final.task.json").exists()
          and hecho.exists())
    caso("e_fallo_a_mitad", ok, retenida_esperando_aprobacion=bool(retenida), fases_mientras_retenida=fases_retenida,
         aprobada=ok_apr, plan=plan.get("estado"), fases=fases, archivo_paso1=hecho.exists(), plan_txt=txt)
    ajustes(gb, guardrail="nunca", motores_off=[])


def main():
    p052.preparar()
    gb = p052.cargar()
    for d in (gb.RESULTS, gb.TASKS, gb.DONE, gb.WAITING):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    ajustes(gb, guardrail="nunca", umbral_plan_usd=5.0)
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # nunca se muestra ni toma el foco
    gb._root = root
    stop = None
    try:
        caso_a(gb)
        caso_b(gb)
        caso_c(gb)
        caso_f(gb, root, "ctk")
        caso_f(gb, root, "tk")
        limpiar_historial(gb)
        (gb.WF_DIR / "sembrado.json").unlink()
        if not SIN_MOTORES:
            stop = arrancar_runner(gb)
            caso_d(gb)
            caso_e(gb)
    finally:
        if stop:
            stop.set()
            time.sleep(2)
        root.destroy()
    OUT["fin"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT["todo_ok"] = all(c["ok"] for c in OUT["casos"].values())
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=2, default=str),
                                         encoding="utf-8")
    log = APP / "growi-bridge.log"
    if log.exists():
        shutil.copy2(log, EVID / "growi-bridge-aislada.log")
    if gb.COLA_DB.exists():
        con = sqlite3.connect(str(gb.COLA_DB))
        filas = [dict(zip(("plan_id", "workflow_id", "huella", "estimado"), r)) for r in con.execute(
            "SELECT plan_id, workflow_id, huella, estimado FROM workflow_runs")]
        con.close()
        OUT["workflow_runs"] = filas
        (EVID / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    print("TODO OK" if OUT["todo_ok"] else "HAY FALLOS", flush=True)


if __name__ == "__main__":
    main()
