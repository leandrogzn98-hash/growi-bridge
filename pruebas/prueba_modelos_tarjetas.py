"""Prueba de las 4 tarjetas de Modelos en CustomTkinter (ESTADO-MODELOS-TARJETAS.md). Oculta: no abre ventanas.

  python pruebas/prueba_modelos_tarjetas.py 100 | 150
  python pruebas/prueba_modelos_tarjetas.py 100 clasica | sinctk | flag
  python pruebas/prueba_modelos_tarjetas.py 100 arranque [fuente.py]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
TARJETAS = ("Tu PC", "Quién responde", "Qué puede hacer", "Reglas")


def preparar(app, tmp):
    (app / "rules.json").write_text(json.dumps([{"text": "Responde en español", "on": True},
                                                {"text": "No borres nada sin preguntar", "on": False}]),
                                    encoding="utf-8")


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("modelos")
    h.bombear(2.0)
    if VAR == "arranque":
        ev["ms_tarjetas"] = gb._MDL4["ms"] if hasattr(gb, "_MDL4") else None
        return
    M = gb._MDL4
    ev["a_ctk_por_tarjeta"] = M["ctk"]
    ev["a_ms_por_tarjeta"] = M["ms"]
    ev["a_tipos"] = {k: type(W[k]).__name__ for k in ("mdl_specs", "mdl_specs_detail", "mdl_check_btn",
                                                         "mdl_engine_desc", "mdl_abilities_box", "mdl_rules_box",
                                                         "mdl_rule_entry")}
    # mismo contenido: Tu PC, habilidades y reglas
    ev["a_tu_pc"] = {"resumen": str(W["mdl_specs"].cget("text")), "detalle": str(W["mdl_specs_detail"].cget("text"))[:120],
                     "esperado": gb.pc_specs_summary(gb._mdl["specs"])}
    hab = gb.list_abilities()
    ab = W["mdl_abilities_box"]
    switches = [w for w in h.todos(ab) if type(w).__name__ in ("_SwitchBarra", "Canvas")
                and (type(w).__name__ == "_SwitchBarra" or hasattr(w, "_on"))]
    ev["a_habilidades"] = {"lista": len(hab) + len(gb.mcp_herramientas_conocidas()), "interruptores": len(switches),
                           "tipo": sorted({type(x).__name__ for x in switches})}
    rb = W["mdl_rules_box"]
    rsw = [w for w in h.todos(rb) if hasattr(w, "_on")]
    ev["a_reglas"] = {"archivo": gb.load_rules(), "interruptores": [bool(w._on) for w in rsw],
                      "tipo": sorted({type(x).__name__ for x in rsw})}
    # mismos manejadores: añadir regla, apagar la 1.ª con su interruptor
    W["mdl_rule_entry"].insert(0, "Regla de la prueba")
    gb._add_rule()
    h.bombear(0.3)
    rsw = [w for w in h.todos(W["mdl_rules_box"]) if hasattr(w, "_on")]
    sw0 = rsw[0]
    if hasattr(sw0, "toggle"):
        sw0.toggle()
    else:
        h.disparar(sw0, "<Button-1>")
    h.bombear(0.3)
    ev["a_reglas_tras"] = {"archivo": gb.load_rules(), "filas": len(rsw)}
    # (b) Automático primero con ✓, y (c) coste por motor
    cb = W["mdl_engine"]
    ev["b_combobox_visible"] = bool(cb.winfo_manager())
    if M.get("motores_box") is not None:
        gb._mdl4_elegir(gb.AUTO_LABEL)
        h.bombear(0.5)
        rows = M["motores_rows"]
        orden = list(rows)
        ev["b_auto"] = {"primero": orden[0], "texto_esperado": gb.AUTO_LABEL,
                        "check": str(rows[orden[0]]["check"].cget("text")),
                        "elegido": rows[orden[0]]["elegido"], "settings_motor": gb.load_settings().get("motor"),
                        "otros_con_check": [k for k in orden[1:] if str(rows[k]["check"].cget("text")).strip()]}
        ev["c_coste"] = {k: {"coste": str(r["coste"].cget("text")), "hay_dato": r["hay_coste"],
                             "estado": str(r["estado"].cget("text")), "card": type(r["card"]).__name__,
                             "boton": type(r["boton"]).__name__} for k, r in rows.items()}
        # elegir otro motor desde su tarjeta mueve el ✓ y lo guarda
        otro = "Claude Sonnet" if "Claude Sonnet" in rows else orden[1]
        rows[otro]["boton"].invoke()
        h.bombear(0.5)
        rows = M["motores_rows"]
        ev["b_elegir_otro"] = {"elegido": [k for k, r in rows.items() if r["elegido"]],
                               "settings": {k: gb.load_settings().get(k) for k in ("motor", "default_engine")}}
        ev["foco"] = {k: {"takefocus": str(r["boton"]._canvas.cget("takefocus")),
                          "espacio": bool(r["boton"]._canvas.bind("<space>"))} for k, r in list(rows.items())[:3]}
        # DPI: la línea 1 de la tarjeta (✓ + nombre + botón) y el estado caben a ventana mínima
        mw = int(gb._root.minsize()[0])
        contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 32 + 24 + 14)
        peor = max(r["boton"].master.winfo_reqwidth() for r in rows.values())
        wl = max(round(int(str(r["estado"].cget("wraplength"))) * gb.SCALE) + gb.S(30) for r in rows.values())
        ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "linea1_max": peor, "estado_max": wl,
                       "cabe": peor <= contenido and wl <= contenido}
    else:
        ev["clasica_motor"] = {"valores": len(cb.cget("values")), "elegido": cb.get(),
                               "primero_no_cabecera": next((v for v in cb.cget("values") if not v.startswith(gb._SECCION_PREFIJO)), None)}


correr("modelos-tarjetas", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8791, fuente=FUENTE)
