"""Prueba del perfil «Sobre mí» en el runner (ESTADO-PERFIL-SOBRE-MI.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Las
tareas pasan por el runner real (_process_one_impl -> prompt_de_tarea ->
motor). El motor «claude» es falso: guarda el prompt que recibe (para ver el
fragmento inyectado). Al final, UNA tarea real con el modelo local de Ollama
(Hermes 3, $0) con campos vacíos, para ver que no los inventa.

  python pruebas/prueba_perfil_runner.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "perfil-sobre-mi"
HERMES = "hf.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF:Q4_K_M"


def falso():
    prompt = sys.stdin.read() if not sys.stdin.isatty() else ""
    prompt = prompt or " ".join(sys.argv[2:])
    with open(os.environ["PERFIL_PROMPTS"], "a", encoding="utf-8") as fh:
        fh.write("=== PROMPT ===\n" + prompt + "\n")
    for ev in ({"type": "system", "subtype": "init", "session_id": "f", "model": "falso"},
               {"type": "result", "subtype": "success", "is_error": False, "result": "hecho",
                "total_cost_usd": 0, "num_turns": 1, "session_id": "f"}):
        print(json.dumps(ev), flush=True)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-perfil-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True,
                                                   "user_name": "Leandro"}), encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), PERFIL_PROMPTS=str(tmp / "prompts.txt"))
    spec = importlib.util.spec_from_file_location("gb_perfil", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [
        sys.executable, str(Path(__file__).resolve()), "--falso", prompt]
    gb._swap_args = lambda c, old, new: list(c)
    gb._approval_needed = lambda task: None
    gb.cola_init()
    ev = {"copia": str(tmp)}

    def correr(tid, prompt, **extra):
        (tmp / "prompts.txt").write_text("", encoding="utf-8")
        t = {"id": tid, "cwd": str(work), "motor": "claude", "revisar": False, "prompt": prompt}
        t.update(extra)
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
        gb._process_one_impl(f)
        p = (tmp / "prompts.txt").read_text(encoding="utf-8")
        i = p.find("PERFIL DEL USUARIO")
        return p[i:p.find("--- Fin del perfil ---", i) + 22] if i >= 0 else None

    # Datos del perfil: los del spec (de MEMORY.md), nada inventado. «Cómo escribo» y «A quién le hablo» vacíos.
    gb.perfil_guardar({"quien": "Leandro, de Barquisimeto.",
                       "hago": "HAYAI: implementación de IA y automatización. Summit Maker con Angelis "
                               "(talleres hands-on). Anuncios para clientes.",
                       "tono": "", "publico": "", "no_hago": ""})
    ev["b_tarea1"] = correr("t-perfil-1", "Escribe un saludo corto para un cliente.")
    gb.perfil_guardar(dict(gb.perfil_leer(), tono="Directo y cercano, tuteo, sin emojis."))
    ev["b_tarea2_tras_cambiar_tono"] = correr("t-perfil-2", "Escribe un saludo corto para un cliente.")
    ev["b_cambio_visto"] = ("Directo y cercano" in (ev["b_tarea2_tras_cambiar_tono"] or "")
                            and "Directo y cercano" not in (ev["b_tarea1"] or ""))
    ev["grupo_sin_perfil"] = correr("t-perfil-grupo", "Saluda al grupo.", canal="whatsapp-grupo")
    # (c) tarea REAL con el modelo local: tono y público vacíos -> no los inventa
    gb.perfil_guardar(dict(gb.perfil_leer(), tono=""))
    tid = "t-perfil-real"
    t = {"id": tid, "cwd": str(work), "motor": "ollama", "model": HERMES, "revisar": False,
         "prompt": "Dime en una sola línea cómo es mi tono al escribir y a quién le hablo, según lo que sabes de mí."}
    f = gb.TASKS / f"{tid}.task.json"
    f.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    gb._process_one_impl(f)
    res = gb.RESULTS / f"{tid}.result.json"
    res = res if res.exists() else None
    r = json.loads(res.read_text(encoding="utf-8")) if res else {}
    ev["c_real"] = {"motor": r.get("motor"), "modelo": r.get("modelo") or r.get("model"), "status": r.get("status"),
                    "respuesta": str(r.get("result") or r.get("error") or "")[:600],
                    "prompt_perfil": gb.perfil_bloque_prompt({"id": tid + "-ver"})}
    # (d) borrar -> la siguiente tarea va sin perfil y el log lo dice
    exp = gb.perfil_exportar(tmp / "perfil-exportado.md")
    ev["d_exportado"] = {"archivo": str(exp), "contenido": exp.read_text(encoding="utf-8")}
    ev["d_borrado"] = gb.perfil_borrar()
    ev["d_tarea_sin_perfil"] = correr("t-perfil-3", "Escribe un saludo corto para un cliente.")
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "perfil" in x][-12:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runner.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    else:
        main()
