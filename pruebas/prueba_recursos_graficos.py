"""Prueba de los gráficos, el selector de rango y las tarjetas de Recursos (ESTADO-RECURSOS-GRAFICOS.md).
Oculta: no abre ventanas. Las muestras son lecturas REALES de este PC: el contador de la barra lateral (cada 2 s,
CPU y RAM) y lecturas completas (_res_sample, la misma de la página) que la prueba pide a mano, porque con la
ventana oculta la lectura automática se pausa (así está hecha).

  python pruebas/prueba_recursos_graficos.py 100 | 150
  python pruebas/prueba_recursos_graficos.py 100 clasica | sinctk | flag
  python pruebas/prueba_recursos_graficos.py 100 arranque [fuente.py]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("recursos")
    h.bombear(1.0)
    if VAR == "arranque":
        ev["log_res"] = [x[26:] for x in h.log().splitlines() if "recursos: tarjetas" in x]
        return
    G = gb._RESG
    ev["kit"] = type(G["kit"]).__name__
    ev["selector"] = type(G["selector"]).__name__
    ev["tarjeta"] = type(W["res_cpu_val"].master).__name__
    # ~75 s de muestras reales (el contador de la barra lateral, cada 2 s) + 4 lecturas completas
    lecturas = []
    t_fin = time.time() + 75
    n = 0
    while time.time() < t_fin:
        h.bombear(2.0)
        if n % 9 == 0:
            d = gb._res_sample()
            gb._res_apply(d)
            lecturas.append(d)
        n += 1
    d = gb._res_sample()
    gb._res_apply(d)
    h.bombear(0.5)
    hist = list(gb._RESH)
    ev["historial"] = {"muestras": len(hist), "segundos": round(hist[-1]["ts"] - hist[0]["ts"], 1),
                       "cpu": [round(m["cpu"], 1) for m in hist if m.get("cpu") is not None][-12:],
                       "ram": [round(m["ram"], 1) for m in hist if m.get("ram") is not None][-6:],
                       "con_gpu": sum(1 for m in hist if m.get("gpu") is not None),
                       "con_disco": sum(1 for m in hist if m.get("disco") is not None)}
    # (a) los gráficos se dibujan con esas muestras
    for k in G["graf"]:
        gb._resg_grafico(k, gb.S(500))
    ev["a_graficos"] = {k: {"puntos": g.get("muestras"), "items": len(g["cv"].find_all())} for k, g in G["graf"].items()}
    # (b) el rango cambia la ventana de datos
    rangos = {}
    for clave, _lab, _s in gb.RES_RANGOS:
        gb._resg_rango(clave)
        h.bombear(0.2)
        rangos[clave] = {"muestras_cpu": G["graf"]["cpu"].get("muestras"), "nota": str(G["nota"].cget("text"))}
    ev["b_rangos"] = rangos
    gb._resg_rango("5m")
    # (c) las tarjetas cuadran con su fuente (la última lectura completa)
    gbb = 1024 ** 3
    ev["c_tarjetas"] = {"pantalla": {k: (str(W[f"res_{k}_val"].cget("text")), str(W[f"res_{k}_sub"].cget("text")))
                                     for k in ("cpu", "ram", "gpu", "disk")},
                        "fuente": {"cpu": None if d.get("cpu") is None else f"{d['cpu']:.0f} %",
                                   "ram": f"{gb._gb(d['ram_used'] / gbb)} GB",
                                   "gpu": f"{d['gpu']['util']:.0f} %" if d.get("gpu") else None,
                                   "disk": f"{gb._gb(d['disk'][1] / gbb)} GB" if d.get("disk") else None},
                        "sparkline_muestras": dict(G.get("spark_n") or {})}
    ev["c_cuadra"] = all(ev["c_tarjetas"]["pantalla"][k][0] == v for k, v in ev["c_tarjetas"]["fuente"].items()
                         if v is not None)
    # (d) la lista de procesos sigue igual: mismas columnas, mismos enlaces y el mismo botón
    tree = W["res_tree"]
    ev["d_procesos"] = {"columnas": list(tree.cget("columns")), "esperadas": [c for c, _l in gb._RES_COLS],
                        "filas": len(tree.get_children()),
                        "enlaces": {s_: bool(tree.bind(s_)) for s_ in ("<<TreeviewSelect>>", "<Delete>", "<F5>")},
                        "boton_cerrar": str(W["res_kill_btn"].cget("text")), "buscador": type(W["res_search"]).__name__}
    # foco: el selector (CTk: cada botón del segmentado; clásica: radios)
    sel = G["selector"]
    if hasattr(sel, "_buttons_dict"):
        ev["foco_selector"] = {lab: str(b._canvas.cget("takefocus")) for lab, b in sel._buttons_dict.items()}
    else:
        ev["foco_selector"] = [type(w).__name__ for w in sel.winfo_children()]
    # DPI: a ventana mínima cada tarjeta mide 1/4 del contenido (el grid las encoge); su texto se parte a ese ancho
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 14)
    col = (contenido - gb.S(24)) // 4
    peor = 0
    for k in ("cpu", "ram", "gpu", "disk"):
        card = W[f"res_{k}_val"].master
        h.disparar(getattr(card, "_canvas", card), "<Configure>", w=col, h=90)
        peor = max(peor, max(ch.winfo_reqwidth() for ch in card.winfo_children()
                             if ch.winfo_class() == "Label") + gb.S(24))
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "cuarto_de_contenido": col,
                   "texto_mas_ancho_con_margen": peor, "selector_pedido": sel.winfo_reqwidth(),
                   "cabe": peor <= col and sel.winfo_reqwidth() <= contenido}


correr("recursos-graficos", pasos, dpi=DPI, variante=VAR, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8780, fuente=FUENTE,
       espera_ms=3000)
