"""Prueba de la cadena de respaldo en el runner (ESTADO-ROUTER-FALLBACKS.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Las
tareas pasan por el runner real (_process_one_impl -> router_antes -> motor
-> reintento / respaldo -> _after_run). Los motores del ejecutor son FALSOS
dentro del proceso (_run_task_motor): cada uno contesta lo que diga MODOS
(429, 401 u ok), sin red y sin gastar. La revisión de (e) es REAL: la cadena
del revisor de engines.json con llama-server parado y el Ollama local ($0).

  python pruebas/prueba_router_runner.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "router-fallbacks"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-router-"))
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
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_router", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    gb.MAX_RETRIES = 1  # un reintento (en la app son 3, con 30 s / 2 min / 8 min)
    gb.RETRY_BACKOFF_S = (0.01,)
    MODOS, LLAMADAS = {}, []
    AL_CORRER = {}

    def falso(task):
        mid = task["motor"]
        LLAMADAS.append(f"{task['id']}:{mid}")
        if AL_CORRER.get(task["id"]):
            AL_CORRER.pop(task["id"])()
        r = gb._base_result(task, mid)
        modo = MODOS.get(mid, "ok")
        r.update(finished_at=gb._now_iso(), duration_s=0.1, exit_code=0 if modo == "ok" else 1)
        if modo == "429":
            r.update(status="error", error=f"{mid}: HTTP 429 Too Many Requests (rate limit) [simulado]")
        elif modo == "401":
            r.update(status="error", error=f"{mid}: HTTP 401 Unauthorized: invalid api key [simulado]")
        else:
            if "notas.txt" in task["prompt"]:
                (work / "notas.txt").write_text("Soleado por la mañana.\nNublado a mediodía.\nLluvia débil de "
                                                "noche.\n", encoding="utf-8")
            r.update(status="ok", result=f"hecho por {mid} [simulado]: escribí notas.txt con tres líneas",
                     cost_usd=0.0)
        return r
    gb._run_task_motor = falso
    ORIG_ES = gb.engine_status
    gb.engine_status = lambda mid, *a, **k: (True, "") if mid in ("claude", "gemini", "llama", "ollama") else (False, "no")
    ev = {"copia": str(tmp)}

    def correr(tid, prompt="Escribe un resumen corto del archivo notas.", max_n=12, **extra):
        LLAMADAS.clear()
        t = {"id": tid, "cwd": str(work), "motor": "claude", "revisar": False, "prompt": prompt}
        t.update(extra)
        f = gb.TASKS / f"{tid}.task.json"
        f.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
        for _ in range(max_n):
            if not f.exists():
                break
            fila = gb.cola_get(tid) or {}
            if fila.get("estado") == "en_cola" and fila.get("proximo_intento") and fila["proximo_intento"] > time.time() + 5:
                break  # pospuesta: espera al breaker
            gb._process_one_impl(f)
        fam = gb.load_family(tid) or {}
        res = gb.RESULTS / f"{tid}.result.json"
        r = json.loads(res.read_text(encoding="utf-8")) if res.exists() else {}
        return {"llamadas": list(LLAMADAS), "estado": fam.get("estado"), "motor_final": r.get("motor"),
                "ruta_motor": r.get("ruta_motor"), "motor_elegido": r.get("motor_elegido"),
                "escalon_previo": r.get("escalon_previo"), "motivo_escalado": r.get("motivo_escalado"),
                "reporte": str(fam.get("reporte") or "")[:300], "cola": (gb.cola_get(tid) or {}).get("estado"),
                "cola_motivo": str((gb.cola_get(tid) or {}).get("motivo") or "")[:200]}

    # (a) la cadena, desde engines.json (allowlist)
    ev["a_cadena_ejecutor"] = gb.cadena_ejecutor()
    ev["a_cadena_revisor"] = [(x.get("motor"), x.get("modelo")) for x in gb._rev_cfg().get("orden") or []]
    ev["a_fallback_cfg"] = {k: v for k, v in gb.fallback_cfg().items() if not str(k).startswith("_")}
    # (b) 429 en claude y en gemini -> llama; con la degradación declarada
    MODOS.update(claude="429", gemini="429", llama="ok")
    ev["b_429_cae_por_la_cadena"] = correr("t-r-429", degradacion=True)
    # (b) 401 en claude -> nunca respaldo ni reintento
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="401")
    ev["b_401_no_cambia"] = correr("t-r-401", degradacion=True)
    # (g) sin regla de degradación -> necesita_decision con lo hecho guardado
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="429")
    ev["g_sin_regla"] = correr("t-r-sinregla")
    # (g) con regla pero la cadena entera cae -> necesita_decision
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="429", gemini="429", llama="429")
    ev["g_cadena_agotada"] = correr("t-r-agotada", degradacion=True)
    # (c) circuit breaker: 3 fallos seguidos de claude -> 5 min al respaldo
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="429", gemini="ok", llama="ok")
    ev["c_fallo_1_2"] = correr("t-r-brk1")
    ev["c_fallo_3"] = correr("t-r-brk2")
    ev["c_breaker"] = {k: dict(v) for k, v in gb._MOTOR_BRK.items()}
    ev["c_con_breaker_y_regla"] = correr("t-r-brk3", degradacion=True)
    ev["c_con_breaker_sin_regla"] = correr("t-r-brk4")
    # (5) aviso de cuota: Claude al 95 % -> la tarea (con regla) empieza ya en el respaldo, antes del corte
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="ok", gemini="ok", llama="ok")
    orig_q = gb._quota_pct
    gb._quota_pct = lambda: 95.0  # simulado: la cuota real no se toca
    ev["cuota_antes_del_corte"] = correr("t-r-cuota", degradacion=True)
    ev["cuota_sin_regla"] = correr("t-r-cuota2")
    gb._quota_pct = orig_q
    # (d) reordenar la cadena MIENTRAS corre una tarea: esa termina con su motor; la siguiente ve el orden nuevo
    gb._MOTOR_BRK.clear()
    MODOS.update(claude="ok", gemini="ok", llama="ok")
    AL_CORRER["t-r-encurso"] = lambda: ev.update(d_guardar=gb.fallback_guardar(ejecutor=["llama", "claude", "gemini"]))
    ev["d_en_curso"] = correr("t-r-encurso")
    ev["d_cadena_despues"] = gb.cadena_ejecutor()
    gb.fallback_guardar(ejecutor=["claude", "gemini", "llama"])
    # (e) revisión real por la cadena del revisor (llama-server parado -> Ollama local)
    gb.engine_status = ORIG_ES  # la revisión usa el estado real de los motores
    ev["e_revision"] = correr("t-r-revision", prompt="Escribe en notas.txt tres líneas sobre el clima de hoy.",
                              revisar=True, criterios=["notas.txt existe"])
    rev = gb.RESULTS / "t-r-revision.revision.json"
    rv = json.loads(rev.read_text(encoding="utf-8")) if rev.exists() else {}
    ev["e_revision_json"] = {k: rv.get(k) for k in ("motor_revision", "motor_elegido", "motivo_eleccion",
                                                    "escalon_previo", "motivo_escalado", "cadena_revisor",
                                                    "aprobado", "cost_usd")}
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "respaldo" in x or "motores: cambio" in x
                 or "necesita tu decisión" in x or "revisión por la cadena" in x][-24:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runner.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
