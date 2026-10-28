"""Prueba de las tarjetas de salud y de métrica de Estado (ESTADO-ESTADO-TARJETAS.md). Oculta: no abre ventanas.

Siembra motores-salud.json con claude sano (y nada de meshy: «sin datos») y resultados de 3 días (hoy 3 con 30,
60 y 90 s; ayer 2; hace 5 días 1), con costo.

  python pruebas/prueba_estado_tarjetas.py 100 | 150
  python pruebas/prueba_estado_tarjetas.py 100 clasica | sinctk | flag
  python pruebas/prueba_estado_tarjetas.py 100 arranque [fuente.py]
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
HOY = datetime.now().astimezone()


def preparar(app, tmp):
    (app / "motores-salud.json").write_text(json.dumps({
        "claude": {"hora": HOY.strftime("%Y-%m-%dT%H:%M:%S-04:00"), "disponible": True, "motivo": "binario: claude",
                   "version": "2.1.312"}}), encoding="utf-8")
    res = tmp / "share" / "outbox" / "runner-results"
    for i, (dias, dur, costo) in enumerate(((0, 30, 0.10), (0, 60, 0.20), (0, 90, 0.05), (1, 40, 0.30),
                                            (1, 50, 0.0), (5, 20, 0.15))):
        t = (HOY - timedelta(days=dias)).strftime("%Y-%m-%dT10:00:00-04:00")
        (res / f"t-met-{i}.result.json").write_text(json.dumps({
            "id": f"t-met-{i}", "raiz": f"t-met-{i}", "status": "ok", "motor": "claude", "modelo": "claude-opus-5-5",
            "cost_usd": costo, "finished_at": t, "duration_s": dur}), encoding="utf-8")


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("estado")
    h.bombear(2.0)
    gb._est_pintar(forzar=True)
    h.bombear(0.5)
    if VAR == "arranque":
        ev["log_est"] = [x[26:] for x in h.log().splitlines() if "estado: tarjetas" in x]
        return
    E = gb._EST
    ev["kit"] = type(E["kit"]).__name__
    # el healthcheck del arranque reescribe motores-salud.json: aquí se deja claude sano y meshy sin registro
    sal = gb._salud()
    sal.pop("meshy", None)
    sal["claude"] = {"hora": HOY.strftime("%Y-%m-%dT%H:%M:%S-04:00"), "disponible": True,
                     "motivo": "binario: claude", "version": "2.1.312"}
    gb.MOTORES_SALUD_FILE.write_text(json.dumps(sal), encoding="utf-8")
    gb._est_pintar(forzar=True)
    h.bombear(0.3)
    # (a) salud: servicios y motores
    ev["a_salud"] = {k: {"nombre": v["nombre"], "color": v["color"], "texto": v["texto"],
                         "punto": str(v["punto"].cget("text"))} for k, v in E["salud"].items()}
    ev["a_puente_cuadra"] = (E["salud"]["puente"]["color"] == "green") == (gb.state.get("bridge") == "corriendo")
    ev["a_tarjeta_tipo"] = type(next(iter(E["salud"].values()))["label"].master).__name__
    # (b) métricas: lo que se ve frente a la fuente
    met = gb.estado_metricas()
    dm = gb.day_by_model()
    ev["b_metricas_pantalla"] = {k: (str(m["num"].cget("text")), str(m["sub"].cget("text")))
                                 for k, m in E["metricas"].items()}
    ev["b_fuente"] = {"dias": met["dias"], "tareas": met["tareas"], "mediana_s": met["mediana_s"],
                      "real": met["real"], "equiv": met["equiv"],
                      "day_by_model_hoy": {"real": round(sum(b["cost"] for k, b in dm.items() if k[0] == "real"), 4),
                                           "equiv": round(sum(b["cost"] for k, b in dm.items() if k[0] == "equiv"), 4)}}
    ev["b_esperado_sembrado"] = {"tareas_hoy": 3, "mediana_hoy_s": 60, "tareas_7_dias": 6}
    # (c) sparkline: un punto por día con datos, en el Canvas, con el de hoy marcado
    for key, m in E["metricas"].items():
        gb._est_spark(key, gb.S(220))
    ev["c_spark"] = {k: {"serie": m["serie"], "puntos": len(m.get("puntos") or []),
                         "items_canvas": len(m["cv"].find_all()),
                         "y_hoy": round(m["puntos"][-1][1], 1) if m.get("puntos") else None}
                     for k, m in E["metricas"].items()}
    # (d) el mapa conserva el resaltado
    gb.ver_mapa()
    h.bombear(0.3)
    card = W.get("mapa_card")
    ev["d_mapa"] = {"existe": card is not None, "borde": str(card.cget("highlightthickness")) if card else None,
                    "color": str(card.cget("highlightbackground")) if card else None,
                    "resaltados": len(gb._MAPA_RES.get("orig") or [])}
    # (e) el banner sigue su lógica: lo que decide cloud_banner_decidir es lo que se ve
    gb._refresh_cloud_banner()
    h.bombear(0.2)
    b = W["cloud_banner"]
    ev["e_banner"] = {"decision": {k: v for k, v in (gb._AV.get("banner") or {}).items() if k != "probe"},
                      "probe": (gb._AV.get("banner") or {}).get("probe"), "visible": bool(b.winfo_manager()),
                      "cuadra": bool(b.winfo_manager()) == bool((gb._AV.get("banner") or {}).get("mostrar"))}
    # DPI: a ventana mínima cada tarjeta mide media columna; su texto se parte a ese ancho y cabe
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 24 + 14)
    col = (contenido - gb.S(16)) // 2
    peor = 0
    for v in E["salud"].values():
        card = v["label"].master
        h.disparar(getattr(card, "_canvas", card), "<Configure>", w=col, h=80)
        peor = max(peor, v["label"].winfo_reqwidth() + gb.S(24))
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "media_columna": col,
                   "texto_mas_ancho_con_margen": peor, "dos_columnas_caben": peor <= col}


correr("estado-tarjetas", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8781, fuente=FUENTE)
