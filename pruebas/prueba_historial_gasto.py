"""Prueba del historial de gasto por día (ESTADO-HISTORIAL-GASTO-045.md). Oculta: no abre ventanas.

  python pruebas/prueba_historial_gasto.py 100            siembra 3 días, añade un resultado hoy (el día crece)
  python pruebas/prueba_historial_gasto.py 100 reinicio   arranca otra instancia con el historial de la anterior y
                                                          SIN los registros viejos: los días siguen (no se borran)
  python pruebas/prueba_historial_gasto.py 100 real       verifica las cifras de referencia (26 y 27 oct) contra una
                                                          COPIA (solo lectura) de los registros de la app instalada
"""

import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import REPO, correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
HOY = datetime.now().astimezone()
PUENTE = REPO / "pruebas" / "evidencia" / "historial-gasto" / "_historial-de-la-primera.json"
INSTALADA = Path.home() / "growi-bridge" / "share" / "outbox" / "runner-results"


def _res(res, tid, dias, costo, motor="claude"):
    t = (HOY - timedelta(days=dias)).strftime("%Y-%m-%dT10:00:00-04:00")
    (res / f"{tid}.result.json").write_text(json.dumps({
        "id": tid, "raiz": tid, "status": "ok", "motor": motor, "modelo": "claude-opus-5-5" if motor == "claude"
        else "hermes3", "cost_usd": costo, "finished_at": t, "duration_s": 30}), encoding="utf-8")


def preparar(app, tmp):
    res = tmp / "share" / "outbox" / "runner-results"
    if VAR == "ctk":
        for i, (d, c, m) in enumerate(((2, 0.40, "claude"), (2, 0.25, "claude"), (1, 1.10, "claude"),
                                       (1, None, "ollama"), (0, 0.05, "claude"))):
            _res(res, f"t-gh-{i}", d, c, m)
    elif VAR == "reinicio":
        shutil.copy(PUENTE, tmp / "share" / "gasto-historial.json")
        _res(res, "t-gh-hoy-2", 0, 0.02)  # solo un registro de hoy: los de días anteriores ya no están
    elif VAR == "real":
        n = 0
        for f in INSTALADA.glob("*.json"):  # copia de solo lectura: la instalada no se toca
            if f.name.endswith((".result.json", ".revision.json")):
                shutil.copy(f, res / f.name)
                n += 1
        (tmp / "copiados.txt").write_text(str(n), encoding="utf-8")


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("tareas")
    h.bombear(3.0)
    gb.start_spend(force=True)
    h.bombear(3.0)
    gb._render_spend()
    if VAR == "real":
        calc = gb.gasto_por_dia()
        ev["registros_copiados"] = (h.tmp / "copiados.txt").read_text(encoding="utf-8")
        ev["dias"] = {d: calc[d] for d in sorted(calc)[-6:]}
        ev["referencia"] = {"2026-10-26": {"equiv_esperado": 424.63, "calculado": (calc.get("2026-10-26") or {}).get("equiv")},
                            "2026-10-27": {"equiv_esperado_parcial_07_09": 118.88,
                                           "calculado_dia_entero": (calc.get("2026-10-27") or {}).get("equiv")}}
        return
    hist, err = gb.gasto_historial_leer()
    ev["json"] = {"archivo": str(gb.GASTO_HIST_FILE), "error": err, "dias": hist}
    calc = gb.gasto_por_dia()
    ev["d_verificado"] = {d: {k: (hist.get(d) or {}).get(k) == calc[d][k] for k in ("real", "equiv", "local", "n")}
                          for d in calc}
    tot = gb.gasto_acumulado(hist)
    suma = {k: round(sum((f.get(k) or 0) for f in hist.values()), 4) for k in ("real", "equiv", "local", "n")}
    ev["b_total"] = {"pantalla": str(W["gh_total"].cget("text")), "acumulado": tot, "suma_filas": suma,
                     "cuadra": tot is not None and all(round(tot[k], 4) == suma[k] for k in suma)}
    ev["c_tabla"] = [W["gh_tree"].item(i, "values") for i in W["gh_tree"].get_children()]
    hoy_d = HOY.date().isoformat()
    sp = gb.spend_summary()["hoy"]
    ev["e_hoy"] = {"pantalla": {k: str(W[k].cget("text")) for k in ("sp_real", "sp_equiv", "sp_local", "sp_local_sub")},
                   "spend_summary_hoy": sp, "fila_de_hoy": hist.get(hoy_d),
                   "cuadra": (str(W["sp_equiv"].cget("text")) == f"${sp['equiv']:.2f}"
                              and abs(((hist.get(hoy_d) or {}).get("equiv") or 0) - sp["equiv"]) < 1e-6)}
    if VAR == "ctk":
        # el día crece al terminar una tarea: un resultado nuevo de hoy
        antes = (hist.get(hoy_d) or {}).get("equiv")
        _res(gb.RESULTS, "t-gh-nueva", 0, 0.30)
        gb._refresh_tasks_ui()
        h.bombear(3.0)
        hist2, _e = gb.gasto_historial_leer()
        ev["dia_crece"] = {"antes": antes, "despues": (hist2.get(hoy_d) or {}).get("equiv"),
                           "tabla": [W["gh_tree"].item(i, "values") for i in W["gh_tree"].get_children()][:1]}
        PUENTE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(gb.GASTO_HIST_FILE, PUENTE)
    else:  # reinicio
        ev["a_sobrevive"] = {"dias_del_historial": sorted(hist),
                             "dias_con_registros_ahora": sorted(calc),
                             "anteriores_siguen": all(d in hist for d in json.loads(
                                 PUENTE.read_text(encoding="utf-8"))["dias"])}


correr("historial-gasto", pasos, dpi=DPI, variante=VAR, preparar=preparar, puerto=8774, espera_ms=3000)
