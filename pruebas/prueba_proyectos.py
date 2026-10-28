"""Prueba de los proyectos (ESTADO-PROYECTOS.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Las
tareas pasan por el runner real (_process_one_impl); el motor es falso y apunta
el prompt que recibe. La búsqueda de las carpetas de los proyectos iniciales es
REAL (en este PC). La MEMORY.md de la copia lleva unas líneas de prueba
(marcadas como tal) para ver de dónde salen las instrucciones iniciales.

  python pruebas/prueba_proyectos.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "proyectos"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-proyectos-"))
    app, aq, sm = tmp / "app", tmp / "clientes" / "Aqualine", tmp / "clientes" / "Summit Maker"
    for d in (app, aq, sm, tmp / "memoria"):
        d.mkdir(parents=True)
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "delicado", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp / "clientes")]}), encoding="utf-8")
    (tmp / "memoria" / "MEMORY.md").write_text(
        "# Memoria (LÍNEAS DE PRUEBA, no son las de Leandro)\n"
        "- HAYAI: implementación de IA y automatización.\n"
        "- Summit Maker con Angelis: talleres hands-on.\n", encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_proy", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    PROMPTS = {}

    def falso(task):
        PROMPTS[task["id"]] = gb.prompt_de_tarea(task)
        r = gb._base_result(task, task["motor"])
        r.update(status="ok", result="hecho [simulado]", cost_usd=0.02, finished_at=gb._now_iso(), duration_s=0.1)
        return r
    gb._run_task_motor = falso
    ev = {"copia": str(tmp)}
    # (4) los iniciales: carpeta REAL buscada en este PC, instrucciones de MEMORY.md
    ev["iniciales"] = [{k: p.get(k) for k in ("nombre", "carpeta", "carpeta_falta", "instrucciones",
                                              "instrucciones_nota")} for p in gb.proyectos_iniciales()]
    # (a) crear Aqualine con el formulario (los mismos datos que pide la ventana)
    pa, _f = gb.proyecto_guardar("Aqualine", "Aqualine", str(aq), "Escribe en tono comercial y breve.",
                                 guardrail="siempre", modelo="haiku")
    ps, _f = gb.proyecto_guardar("Summit Maker", "Summit Maker (con Angelis)", str(sm),
                                 "Talleres hands-on: todo con ejemplos prácticos.", guardrail="nunca", modelo="sonnet")
    (gb.proyecto_memoria_dir(pa) / "MEMORY.md").write_text(
        "# Memoria del proyecto Aqualine\n- El precio del filtro X es 120 (dato de prueba).\n", encoding="utf-8")
    # (b) cambiar de proyecto en un gesto: guardrail, modelo, carpeta (y asistente)
    antes = {"guardrail": gb.guardrail_level(), "modelo_chat": gb.superficie_modelo("chat", avisar=False),
             "carpeta_tareas_nuevas": gb.asis_cwd_envio()}
    ok_a, cambios_a = gb.proyecto_activar("aqualine")
    en_aq = {"guardrail": gb.guardrail_level(), "modelo_chat": gb.superficie_modelo("chat", avisar=False),
             "carpeta_tareas_nuevas": gb.asis_cwd_envio(), "bandeja": gb._tray_title()}
    ok_s, cambios_s = gb.proyecto_activar("summit-maker")
    en_sm = {"guardrail": gb.guardrail_level(), "modelo_chat": gb.superficie_modelo("chat", avisar=False),
             "carpeta_tareas_nuevas": gb.asis_cwd_envio(), "bandeja": gb._tray_title()}
    ev["b_cambio"] = {"antes": antes, "aqualine": [cambios_a, en_aq], "summit": [cambios_s, en_sm]}

    def correr(tid, proyecto, cwd):
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps({"id": tid, "cwd": str(cwd), "motor": "claude", "revisar": False,
                                 "prompt": "Prepara un resumen.", "proyecto": proyecto}, ensure_ascii=False),
                     encoding="utf-8")
        gb._process_one_impl(f)
    correr("t-aq-1", "Aqualine", aq)
    correr("t-aq-2", "Aqualine", aq)
    correr("t-sm-1", "Summit Maker", sm)
    # cambiar de proyecto a mitad no mueve la tarea: se queda con el suyo
    ev["a_tareas"] = {"Aqualine": gb.proyecto_tareas("Aqualine"), "Summit Maker": gb.proyecto_tareas("Summit Maker")}
    ev["a_prompt_aqualine"] = PROMPTS["t-aq-1"][PROMPTS["t-aq-1"].find("PROYECTO"):][:400]
    # (c) la memoria no se mezcla
    ev["c_prompt_summit_sin_aqualine"] = "filtro X" not in PROMPTS["t-sm-1"]
    ev["c_prompt_aqualine_con_su_memoria"] = "filtro X" in PROMPTS["t-aq-1"]
    hits, _m = gb.mem_buscar_ordenado("filtro")
    ev["c_buscar_en_summit"] = [(h["texto"], h["origen"]) for h in hits]
    gb.proyecto_activar("aqualine")
    hits, _m = gb.mem_buscar_ordenado("filtro")
    ev["c_buscar_en_aqualine"] = [(h["texto"], h["origen"]) for h in hits]
    # (d) gasto por proyecto
    ev["d_gasto_por_proyecto"] = {k: {kk: (sorted(vv) if isinstance(vv, set) else vv) for kk, vv in v.items()}
                                  for k, v in gb.gasto_por_proyecto_7d().items()}
    ev["palette"] = [t for t, _i in gb._palette_sections("")][:2]
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "proyectos:" in x][-10:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
