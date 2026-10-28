"""Prueba de la configuración inicial en CustomTkinter (ESTADO-ONBOARDING-PIEL.md). Oculta: no abre ventanas.

Arranca con onboarding_done: false y recorre los 4 pasos. En el paso 2 mete una clave inválida (corta) y comprueba
el mensaje de siempre. Compara con la clásica: python pruebas/prueba_onboarding_piel.py 100 clasica.

  python pruebas/prueba_onboarding_piel.py 100 | 150
  python pruebas/prueba_onboarding_piel.py 100 clasica | sinctk | flag | rota
  python pruebas/prueba_onboarding_piel.py 100 arranque [fuente.py]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None
    elif VAR == "rota":  # la chrome CTk se dibuja; el cuerpo falla al dibujar -> la clásica, en el mismo paso
        def roto(_step):
            raise RuntimeError("CTk roto a propósito (prueba)")
        gb._ob_body_ctk = roto


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    OB = gb._OB
    for _ in range(40):  # maybe_onboarding va a los 400 ms; la detección, en su hilo
        h.bombear(0.5)
        if OB.get("frame") is not None and OB.get("det") is not None:
            break
    h.bombear(1.0)
    if VAR == "arranque":
        ev["log_ob"] = [x for x in h.log().splitlines() if "configuración inicial: pantalla" in x]
        return
    ev["piel"] = OB.get("piel")
    ev["log_piel"] = [x[26:] for x in h.log().splitlines() if "configuración inicial:" in x and
                      ("pantalla" in x or "CustomTkinter" in x)]

    def chrome():
        return {"kicker": str(OB["kicker"].cget("text")), "titulo": str(OB["title"].cget("text")),
                "sub": str(OB["sub"].cget("text"))[:60], "siguiente": str(OB["next"].cget("text")),
                "saltar": str(OB["skip"].cget("text")), "atras": str(OB["back"].cget("state"))}

    def controles():
        tipos = {}
        for w in h.todos(OB["body"]):
            n = type(w).__name__
            if n in ("CTkRadioButton", "CTkCheckBox", "CTkButton", "CTkEntry", "Radiobutton", "Checkbutton",
                     "Button", "Entry", "TButton", "TEntry"):
                tf = getattr(w, "_canvas", None)
                foco = (str(tf.cget("takefocus")) if tf is not None else str(w.cget("takefocus")))
                esp = bool(tf.bind("<space>")) if tf is not None else None
                tipos.setdefault(n, []).append({"takefocus": foco, "espacio": esp})
        return tipos
    if OB.get("piel") == "ctk":
        cont = OB["cont"]
        pi = cont.place_info()
        ev["a_tarjeta"] = {"tipo": type(OB["col"]).__name__, "esquinas": OB["col"].cget("corner_radius"),
                           "centrada": (pi.get("relx"), pi.get("rely"), pi.get("anchor"))}
        h.disparar(OB["fondo"], "<Configure>", w=900, h=700)
        ev["a_textura_puntos"] = {"puntos": len(OB["fondo"].find_all()), "color": gb._ob_color_puntos(),
                                  "fondo": gb.THEME["bg"]}

        def puntos():
            c = OB["prog"]
            return [c.itemcget(i, "fill") for i in c.find_all()]
    else:
        def puntos():
            c = OB["prog"]
            return [c.itemcget(i, "fill") for i in c.find_all()]
    recorrido = []
    # paso 1
    recorrido.append({"paso": 1, **chrome(), "puntos": puntos(), "controles": controles()})
    OB["choice"].set("claude")
    gb._ob_render()
    h.bombear(0.3)
    gb._ob_next()
    h.bombear(0.6)
    # paso 2: clave inválida -> el mensaje de siempre (en el log), y el paso avanza igual
    recorrido.append({"paso": 2, **chrome(), "puntos": puntos(), "controles": controles(),
                      "hay_campo_clave": OB.get("key_entry") is not None})
    if OB.get("key_entry") is not None:
        OB["key_entry"].delete(0, "end")
        OB["key_entry"].insert(0, "corta")
    gb._ob_next()
    h.bombear(0.6)
    ev["b_clave_invalida"] = [x[26:] for x in h.log().splitlines() if "configuración inicial: clave de" in x]
    # paso 3
    recorrido.append({"paso": 3, **chrome(), "puntos": puntos(), "controles": controles(),
                      "carpetas": list(OB["folder_vars"])[:3]})
    gb._ob_next()
    h.bombear(1.0)
    # paso 4: comprobaciones reales (proxy, asistente, carpetas)
    for _ in range(30):
        h.bombear(0.5)
        if all(str(ic.cget("text")) != "⠋" for ic, _m in OB["checks"].values()):
            break
    recorrido.append({"paso": 4, **chrome(), "puntos": puntos(), "controles": controles(),
                      "comprobaciones": {k: (str(ic.cget("text")), str(m.cget("text"))[:90])
                                         for k, (ic, m) in OB["checks"].items()}})
    ev["b_recorrido"] = recorrido
    # DPI: a ventana mínima la tarjeta mide min(680, ancho-40); los textos parten a 600 como mucho (CTk escala)
    if OB.get("piel") == "ctk":
        mw = int(gb._root.minsize()[0])
        ancho_tarjeta = min(gb.S(680), max(gb.S(480), mw - gb.S(40)))
        texto = round(600 * gb.SCALE) + gb.S(24 + 16 + 16 + 6)
        ev["e_dpi"] = {"minsize_ancho": mw, "ancho_tarjeta_minima": ancho_tarjeta, "texto_max_px": texto,
                       "cabe": texto <= ancho_tarjeta}
    gb._ob_next()  # «Empezar a hablar»
    h.bombear(0.8)
    s = gb.load_settings()
    ev["b_fin"] = {"onboarding_done": s.get("onboarding_done"), "assistant": s.get("assistant"),
                   "pagina": W.get("pagina_actual"), "frame_cerrado": OB.get("frame") is None,
                   "ejemplo_en_el_chat": (W["ask_text"].get("1.0", "end").strip()[:40]
                                          if W.get("ask_text") is not None else None)}


correr("onboarding-piel", pasos, dpi=DPI, variante=VAR, antes_de_main=antes_de_main,
       settings={"onboarding_done": False, **({"piloto_ctk": False} if VAR == "flag" else {})}, puerto=8785,
       fuente=FUENTE, espera_ms=1500)
