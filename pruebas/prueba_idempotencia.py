"""Prueba de run_id, idempotencia, cuarentena y compensación (ESTADO-IDEMPOTENCIA-CUARENTENA.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Las
tareas pasan por el runner real (_process_one_impl). El EJECUTOR es falso
(dentro del proceso) y el JUEZ «claude» es falso (este archivo con --juez):
rechaza la primera vez y aprueba la segunda, para que haya una ronda de
corrección. La «muerte entre hacer y apuntar» se simula cortando la función
después del efecto. No gasta nada ni llama a nadie de fuera.

  python pruebas/prueba_idempotencia.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "idempotencia"


def juez():
    cont = Path(os.environ["IDEM_JUEZ"])
    n = int(cont.read_text() or 0) + 1 if cont.exists() else 1
    cont.write_text(str(n))
    if n == 1:
        v = {"puntuacion": {"completitud": 2, "correccion": 3, "no_regresion": 5, "evidencia": 2}, "aprobado": "no",
             "que_falta": [{"falta": "falta la línea de cierre", "arreglo": "añade «fin» al final de notas.txt"}],
             "evidencia": ["notas.txt"]}
    else:
        v = {"puntuacion": {"completitud": 5, "correccion": 5, "no_regresion": 5, "evidencia": 5}, "aprobado": "si",
             "que_falta": [], "evidencia": ["notas.txt"]}
    for e in ({"type": "system", "subtype": "init", "session_id": "j", "model": "juez-simulado"},
              {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(v), "num_turns": 1,
               "session_id": "j"}):
        print(json.dumps(e), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-idem-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), IDEM_JUEZ=str(tmp / "juez.txt"))
    spec = importlib.util.spec_from_file_location("gb_idem", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    gb.efectos_init()
    MODO = {"x": "ok"}

    def ejecutor(task):
        r = gb._base_result(task, task["motor"])
        r.update(finished_at=gb._now_iso(), duration_s=0.1, cost_usd=0.012)
        if MODO["x"] == "ambiguo":
            r.update(status="error", error="el motor devolvió algo que no se entiende: «0xBEEF: estado 7»")
        elif MODO["x"] == "401":
            r.update(status="error", error="HTTP 401 Unauthorized: invalid api key")
        else:
            (work / "notas.txt").write_text("uno\ndos\ntres\n" + ("fin\n" if task.get("ronda") else ""),
                                            encoding="utf-8")
            r.update(status="ok", result="escribí notas.txt [simulado]")
        return r
    gb._run_task_motor = ejecutor
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [
        sys.executable, str(Path(__file__).resolve()), "--juez", prompt]
    gb._swap_args = lambda c, old, new: list(c)
    orig_rev = gb._rev_cfg
    gb._rev_cfg = lambda: dict(orig_rev(), orden=[{"motor": "claude", "modelo": "juez-simulado"}])
    ev = {"copia": str(tmp)}

    def correr(tid, prompt, **extra):
        t = {"id": tid, "cwd": str(work), "motor": "claude", "prompt": prompt}
        t.update(extra)
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
        for _ in range(6):
            pend = sorted(gb.TASKS.glob(f"{tid}*.task.json"))
            if not pend:
                break
            gb._process_one_impl(pend[0])
        return gb.load_family(tid) or {}

    # (a) un encargo con una ronda de corrección: el run_id en todos los archivos
    fam = correr("t-idem-run", "Escribe notas.txt con tres líneas y una línea de cierre.",
                 criterios=["notas.txt tiene la línea de cierre"])
    run_id = "t-idem-run"
    archivos = {}
    for p in sorted(list(gb.RESULTS.glob("t-idem-run*.json")) + list(gb.DONE.glob("t-idem-run*.task.json"))):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            archivos[p.name] = d.get("run_id")
        except (OSError, ValueError):
            archivos[p.name] = "ilegible"
    ev["a_run_id"] = {"estado": fam.get("estado"), "rondas": fam.get("ronda"), "familia_run_id": fam.get("run_id"),
                      "archivos": archivos,
                      "todos_llevan_el_run_id": all(v == run_id for v in archivos.values())}
    # una aprobación también lo lleva
    s = gb.load_settings()
    s["guardrail"] = "delicado"
    gb.save_settings(s)
    correr("t-idem-apr", f"Borra el archivo {work}\\viejo.txt.")
    reg = [json.loads(x) for x in gb.APR_LOG.read_text(encoding="utf-8").splitlines()]
    ev["a_aprobacion_run_id"] = [{k: x.get(k) for k in ("evento", "approval_id", "run_id")} for x in reg][-1:]
    s["guardrail"] = "nunca"
    gb.save_settings(s)
    # (b) efecto externo con muerte entre hacer y apuntar: no se repite
    enviados = []
    destino = tmp / "buzon"
    destino.mkdir()

    class Muerte(Exception):
        pass

    def enviar_y_morir():
        (destino / "pedido-1.json").write_text("{}", encoding="utf-8")
        enviados.append(1)
        raise Muerte("el runner murió entre «enviar» y «apuntar enviado» (simulado)")
    try:
        gb.efecto_ejecutar("run-b", "enviar", "pedido_vm", {"x": 1}, enviar_y_morir,
                           comprobar=lambda: (destino / "pedido-1.json").exists() and "está en el buzón")
    except Muerte as e:
        ev["b_muerte"] = str(e)
    ev["b_fila_tras_morir"] = gb.efecto_get("run-b:enviar")["estado"]

    def enviar():
        (destino / "pedido-1.json").write_text("{}", encoding="utf-8")
        enviados.append(1)
        return "enviado"
    ev["b_reintento"] = gb.efecto_ejecutar("run-b", "enviar", "pedido_vm", {"x": 1}, enviar,
                                           comprobar=lambda: (destino / "pedido-1.json").exists() and "está en el buzón")
    ev["b_tercera_vez"] = gb.efecto_ejecutar("run-b", "enviar", "pedido_vm", {"x": 1}, enviar)
    ev["b_veces_que_se_envio"] = len(enviados)
    # sin forma de comprobarlo -> cuarentena, no se repite
    try:
        gb.efecto_ejecutar("run-c", "correo", "enviar_correo", {"a": "ana"}, enviar_y_morir)
    except Muerte:
        pass
    ev["b_sin_comprobar"] = gb.efecto_ejecutar("run-c", "correo", "enviar_correo", {"a": "ana"}, enviar)
    # dinero: otra cantidad = otro efecto (fingerprint)
    ev["b_dinero_claves"] = [gb.efecto_clave("run-d", "pago", {"usd": 5}, "mover_dinero"),
                             gb.efecto_clave("run-d", "pago", {"usd": 7}, "mover_dinero")]
    # el envío de la cosecha usa la misma puerta
    gb.COSECHA_IN.mkdir(parents=True, exist_ok=True)
    (gb.COSECHA_IN / "estado-vm.json").write_text(json.dumps({"tiktok_ms_token": True}), encoding="utf-8")
    p, _m = gb.cosecha_crear("tiktok", "#prueba", 100, "C1")
    ev["b_cosecha"] = {"aprobar": gb.cosecha_aprobar(p["id"]), "efecto": gb.efecto_get(f"{p['id']}:enviar_a_la_vm")}
    # (c) un fallo ambiguo -> en_cuarentena con error y entrada a la vista
    MODO["x"] = "ambiguo"
    fam = correr("t-idem-ambiguo", "Haz algo con notas.txt.", revisar=False)
    snap = gb.RESULTS / "t-idem-ambiguo.cuarentena.json"
    ev["c_cuarentena"] = {"estado": fam.get("estado"), "cola": (gb.cola_get("t-idem-ambiguo") or {}).get("estado"),
                          "reporte": fam.get("reporte"),
                          "snapshot": json.loads(snap.read_text(encoding="utf-8")) if snap.exists() else None}
    ev["c_abandonar"] = gb.cuarentena_abandonar("t-idem-ambiguo")
    # (d) un fallo definitivo con el reporte completo
    MODO["x"] = "401"
    fam = correr("t-idem-401", "Resume notas.txt.", revisar=False)
    ev["d_reporte_fallo"] = {"estado": fam.get("estado"), "reporte": fam.get("reporte")}
    # (e) compensación: retirar el pedido de la VM; un correo no tiene
    ev["e_compensar_pedido"] = gb.efecto_compensar(f"{p['id']}:enviar_a_la_vm")
    ev["e_compensar_correo"] = gb.efecto_compensar("run-c:correo")
    ev["e_tabla"] = gb.EFECTOS_COMPENSACION
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "efectos:" in x or "CUARENTENA" in x or "cuarentena:" in x][-12:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--juez":
        juez()
    else:
        main()
