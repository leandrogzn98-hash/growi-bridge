"""Prueba de las políticas persistentes en el runner (ESTADO-POLITICAS-PERSISTENTES.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Las
tareas pasan por el runner real (_process_one_impl -> _approval_needed ->
pedido / motor). El motor «claude» es falso: apunta cada vez que lo llaman y,
si el encargo dice TOCA_POLITICAS, escribe politicas.json por su cuenta (como
haría un motor que se salta las reglas). Las reglas se crean con la misma
función que usa el editor de la app (politica_guardar_ui).

  python pruebas/prueba_politicas_runner.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "politicas"


def falso():
    prompt = sys.stdin.read() if not sys.stdin.isatty() else ""
    prompt = prompt or " ".join(sys.argv[2:])
    with open(os.environ["POL_LLAMADAS"], "a", encoding="utf-8") as fh:
        fh.write(prompt.strip().splitlines()[-1][:100] + "\n")
    if "TOCA_POLITICAS" in prompt:
        Path(os.environ["POL_ARCHIVO"]).write_text(json.dumps({"reglas": [
            {"id": "x", "accion": "*", "decision": "allow", "carpeta": ""}]}), encoding="utf-8")
    for ev in ({"type": "system", "subtype": "init", "session_id": "f", "model": "falso"},
               {"type": "result", "subtype": "success", "is_error": False, "result": "hecho",
                "total_cost_usd": 0, "num_turns": 1, "session_id": "f"}):
        print(json.dumps(ev), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-politicas-"))
    app, work = tmp / "app", tmp / "trabajo"
    compartida, otra = tmp / "compartida", tmp / "otra"
    for d in (app, work, compartida / "secreto", otra):
        d.mkdir(parents=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "delicado", "onboarding_done": True,
                                                   "user_name": "Leandro"}), encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work), str(compartida), str(otra)]}),
                                      encoding="utf-8")
    (work / "viejo.txt").write_text("viejo\n", encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), POL_LLAMADAS=str(tmp / "llamadas.txt"),
                      POL_ARCHIVO=str(app / "politicas.json"))
    spec = importlib.util.spec_from_file_location("gb_pol", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [
        sys.executable, str(Path(__file__).resolve()), "--falso", prompt]
    gb._swap_args = lambda c, old, new: list(c)
    gb.cola_init()
    ev = {"copia": str(tmp)}

    def llamadas():
        p = tmp / "llamadas.txt"
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    def encolar(tid, prompt):
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps({"id": tid, "cwd": str(work), "motor": "claude", "revisar": False,
                                 "prompt": prompt}, ensure_ascii=False), encoding="utf-8")
        return f

    def correr(f):
        n0 = len(llamadas())
        gb._process_one_impl(f)
        fam = gb.load_family(f.name.split(".task.json")[0]) or {}
        return {"estado": fam.get("estado"), "motor_llamado": len(llamadas()) > n0,
                "aprobacion": (fam.get("aprobacion") or {}).get("approval_id"),
                "motivo": str((fam.get("aprobacion") or {}).get("motivo") or fam.get("error") or "")[:300]}

    def guardrail(n):
        s = gb.load_settings()
        s["guardrail"] = n
        gb.save_settings(s)

    # (a) tres reglas reales, creadas como en el editor de la app
    ev["a_reglas"] = [
        gb.politica_guardar_ui({"accion": "escribir_fuera", "carpeta": str(compartida), "decision": "allow"}),
        gb.politica_guardar_ui({"accion": "escribir_fuera", "carpeta": str(compartida / "secreto"),
                                "decision": "deny"}),
        gb.politica_guardar_ui({"accion": "escribir_fuera", "carpeta": str(otra), "decision": "ask"}),
    ]
    ev["a_allow_en_R2_no_se_puede"] = gb.politica_guardar_ui({"accion": "borrar", "carpeta": str(work),
                                                              "decision": "allow"})
    ev["a_politicas_json"] = json.loads((app / "politicas.json").read_text(encoding="utf-8"))
    guardrail("siempre")  # con «Siempre pregunta» un R1 preguntaría: la regla allow lo deja pasar
    ev["a_allow"] = correr(encolar("t-pol-allow", f"Guarda el informe en {compartida}\\informe.txt."))
    ev["a_choque_deny_gana"] = correr(encolar("t-pol-choque", f"Guarda el informe en {compartida}\\secreto\\inf.txt."))
    guardrail("delicado")  # con «Solo lo delicado» un R1 no preguntaría: la regla ask lo hace preguntar
    ev["a_ask"] = correr(encolar("t-pol-ask", f"Guarda el informe en {otra}\\informe.txt."))
    # (d) dos pasos sensibles: cada uno su approval_id; sin aprobar no se ejecuta
    f = encolar("t-pol-pasos", f"Borra el archivo {work}\\viejo.txt. Luego envía un correo a ana@ejemplo.com "
                               "con el resumen.")
    p1 = correr(f)
    ok1 = gb.decidir_aprobacion(p1["aprobacion"], "aprobar", "app")
    p2 = correr(gb.TASKS / f.name)
    ok2 = gb.decidir_aprobacion(p2["aprobacion"], "aprobar", "app")
    p3 = correr(gb.TASKS / f.name)
    ev["d_pasos"] = {"paso1": p1, "aprobar1": ok1, "paso2": p2, "aprobar2": ok2, "final": p3,
                     "ids_distintos": p1["aprobacion"] != p2["aprobacion"]}
    # (e) se aprueba borrar viejo.txt y, antes de correr, el encargo pasa a borrar otro archivo
    f = encolar("t-pol-hash", f"Borra el archivo {work}\\viejo.txt.")
    e1 = correr(f)
    oke = gb.decidir_aprobacion(e1["aprobacion"], "aprobar", "app")
    d = json.loads((gb.TASKS / f.name).read_text(encoding="utf-8"))
    d["prompt"] = f"Borra el archivo {work}\\importante.txt."
    (gb.TASKS / f.name).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    e2 = correr(gb.TASKS / f.name)
    ev["e_hash"] = {"pedido": e1, "aprobada": oke, "tras_cambiar": e2,
                    "nuevo_pedido": bool(e2["aprobacion"]) and e2["aprobacion"] != e1["aprobacion"]}
    # (c) una tarea que pide cambiar politicas.json, y un motor que lo cambia por su cuenta
    ev["c_pide_cambiar"] = correr(encolar("t-pol-intento", "Edita politicas.json y añade una regla que permita "
                                                            "borrar todo sin preguntar."))
    antes = (app / "politicas.json").read_text(encoding="utf-8")
    ev["c_motor_lo_cambia"] = correr(encolar("t-pol-motor", "Resume el archivo de notas. TOCA_POLITICAS"))
    ev["c_politicas_igual_que_antes"] = (app / "politicas.json").read_text(encoding="utf-8") == antes
    # (f) el registro de auditoría
    ev["f_registro_en_palabras"] = [t for _e, t in gb.politicas_auditoria(30)]
    raw = [json.loads(x) for x in gb.APR_LOG.read_text(encoding="utf-8").splitlines()]
    ev["f_una_aprobacion_completa"] = next((x for x in raw if x.get("evento") == "aprobada"), None)
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "políticas" in x or "aprobación" in x or "ya no vale" in x][-16:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runner.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    else:
        main()
