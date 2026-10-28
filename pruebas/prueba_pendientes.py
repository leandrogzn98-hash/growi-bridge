"""Prueba de «qué falta por responder» por persona (ESTADO-PENDIENTES-POR-PERSONA.md).

Copia aislada de growi-bridge.py. Los encargos son de PRUEBA (los nombres son
los del spec): familias del runner y encargos en la cola. Se corre el mismo
resumen de las 21:00 (la automatización «resumen-2100», _auto_resumen).

  python pruebas/prueba_pendientes.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "pendientes"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-pend-"))
    app = tmp / "app"
    app.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "onboarding_done": True}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_pend", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.RESULTS, gb.TASKS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    ev = {"copia": str(tmp)}

    def resumen():
        r = gb._auto_resumen()
        texto = sorted(gb.OUTBOX.glob("resumen-*.md"))[-1].read_text(encoding="utf-8")
        return r, texto[texto.find("## Qué falta por responder"):]

    # (d) sin ningún encargo con persona: «nada pendiente»
    gb._family_update("t-ordenar", encargo="Ordena mis descargas por tipo.", estado="aprobada")
    ev["d_cero"] = resumen()[1]
    # encargos que pasaron por el Bridge (familias y uno en cola), con fechas distintas
    gb._family_update("t-william", encargo="Responde a William sobre el precio del filtro X.", estado="aprobada",
                      creada="2026-10-27T10:00:00-04:00")
    gb._family_update("t-vero", encargo="Prepara el presupuesto del taller y envíaselo a Vero mañana.",
                      estado="necesita_decision", creada="2026-10-26T09:00:00-04:00")
    for i in range(7):
        gb._family_update(f"t-luis-{i}", encargo=f"Escríbele a Luis Galban sobre la función {i + 1} de Barquicinema.",
                          estado="aprobada", creada=f"2026-10-{10 + i:02d}T12:00:00-04:00")
    (gb.TASKS / "t-angelis.task.json").write_text(json.dumps(
        {"id": "t-angelis", "prompt": "Confírmale a Angelis la sala del taller del sábado."}, ensure_ascii=False),
        encoding="utf-8")
    r, sec = resumen()
    ev["a_resumen"] = {"automatizacion": r, "seccion": sec}
    pp = gb.pendientes_por_persona()
    ev["a_por_persona"] = {k: [(i["que"], i["origen"]) for i in v] for k, v in pp.items()}
    # (b) lo que no pasó por el Bridge no aparece: no hay ninguna fuente de chats; un texto suelto sin tarea no cuenta
    ev["b_solo_bridge"] = {"personas": sorted(pp), "fuentes": "familias del runner + encargos en la cola",
                           "un_chat_que_no_pasó_por_bridge": "Diana" not in pp}
    # (c) marcar uno como hecho: no vuelve en el resumen siguiente
    gb.pendiente_marcar_hecho(pp["William"][0]["id"])
    _r, sec2 = resumen()
    ev["c_tras_marcar"] = {"william_en_el_siguiente": "William" in sec2, "seccion": sec2}
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "pendientes:" in x][-6:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (OUT / "resumen-seccion.md").write_text(sec, encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
