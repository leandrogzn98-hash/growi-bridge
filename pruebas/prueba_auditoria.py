"""Auditoría final de la 0.4.5 (ESTADO-AUDITORIA-045.md). Oculta: nada se ve ni roba el foco (captura_oculta.py).

Captura Tareas, Modelos, Ajustes, Estado, Recursos y la configuración inicial, y mide lo que se ve en cada una:
textos con «·», etiquetas en MAYÚSCULAS, tamaños de letra por debajo de 9 pt, botones con el acento, filas de las
tablas, ancho de la barra lateral, tiempo de abrir cada página, tokens del tema y contrastes. Más unas comprobaciones
estáticas del código (gradientes, móvil, usos de #FF6363).

  python pruebas/prueba_auditoria.py 100 | 150
"""

import re
import sys
import time
import tkinter.font as tkfont
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import captura_oculta as co  # noqa: E402
from arnes_oculto import REPO, correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
PAGINAS = ("tareas", "modelos", "ajustes", "estado", "recursos")
CAPS = REPO / "pruebas" / "evidencia" / "auditoria" / "capturas-045"
TOKENS_045 = {"bg": "#0F0F0F", "card": "#1A1A1C", "line": "#2C2C2E", "text": "#F5F5F7", "muted": "#9A9AA0",
              "green": "#34C759", "orange": "#FA5102", "red": "#E5484D", "blue": "#0A84FF", "accent": "#FF6363"}


def _texto(w):
    try:
        return str(w.cget("text"))
    except Exception:  # noqa: BLE001
        return ""


def _pt(w):
    try:
        return tkfont.Font(font=w.cget("font")).actual("size")
    except Exception:  # noqa: BLE001
        return None


def medir_visible(h, raiz):
    """Lo que se ve ahora en la ventana (solo widgets mapeados)."""
    gb = h.gb
    acento = (gb._TEMA["actual"].get("fijos") or {}).get("accent", "").lower()
    puntos, mayus, chicos, acentos, filas = [], [], [], [], {}
    for w in h.todos(raiz):
        try:
            if not w.winfo_viewable():
                continue
        except Exception:  # noqa: BLE001
            continue
        t = _texto(w).strip()
        if t:
            if "·" in t:
                puntos.append(t[:120])
            letras = [c for c in t if c.isalpha()]
            if len(letras) >= 4 and t.upper() == t and t not in ("PNG", "JSON", "API", "CPU", "RAM", "GPU", "URL"):
                mayus.append((t[:60], _pt(w)))
            pt = _pt(w)
            if pt is not None and 0 < abs(pt) < 9:
                chicos.append((t[:60], pt))
        for opc in ("fg_color",):
            try:
                c = w.cget(opc)
            except Exception:  # noqa: BLE001
                continue
            c = c[-1] if isinstance(c, (list, tuple)) else c
            if isinstance(c, str) and c.lower() == acento and acento:
                acentos.append(t[:60] or type(w).__name__)
        if w.winfo_class() == "Treeview":
            estilo = str(w.cget("style") or "Treeview")
            filas[estilo] = ttk.Style().lookup(estilo, "rowheight")
    return {"textos_con_punto_medio": sorted(set(puntos)), "mayusculas": sorted(set(mayus)),
            "letra_menor_9pt": sorted(set(chicos), key=str), "botones_con_acento": sorted(set(acentos)),
            "filas_treeview": filas}


def estatico():
    src = (REPO / "growi-bridge.py").read_text(encoding="utf-8")
    lineas = src.splitlines()

    def donde(rx):
        return [f"{i + 1}: {ln.strip()[:110]}" for i, ln in enumerate(lineas) if re.search(rx, ln)]
    return {"gradientes": donde(r"(?i)gradient|degradad"),
            "movil": donde(r"(?i)m[oó]vil|breakpoint|\b390 ?px"),
            "ff6363": donde(r"(?i)#ff6363")}


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    r = gb._root
    CAPS.mkdir(parents=True, exist_ok=True)
    co.preparar(r, gb.S(940), gb.S(680), h.bombear)
    familias = set(tkfont.families())
    ev["fuente"] = {"en_uso": gb.FONT, "inter_instalada": "Inter" in familias, "mono": gb.MONO}
    T = gb.THEME
    acento = (gb._TEMA["actual"].get("fijos") or {}).get("accent")
    ev["tema"] = gb._TEMA["actual"].get("id")
    ev["tokens"] = {k: {"esperado": v, "real": (acento if k == "accent" else T.get(k)),
                        "igual": str(acento if k == "accent" else T.get(k)).upper() == v}
                    for k, v in TOKENS_045.items()}
    ev["tokens"]["sidebar_mas_oscura"] = {"sidebar": T.get("sidebar"), "bg": T.get("bg"),
                                          "ok": gb._tema_lum(T["sidebar"]) <= gb._tema_lum(T["bg"])}
    pares = [("text", "bg"), ("text", "card"), ("muted", "bg"), ("muted", "card"), ("green_text", "card"),
             ("red", "card"), ("orange_text", "card"), ("blue", "card")]
    ev["contraste"] = {f"{a}/{b}": round(gb.tema_contraste(T[a], T[b]), 2) for a, b in pares if a in T and b in T}
    if acento:
        ev["contraste"]["blanco/accent"] = round(gb.tema_contraste("#FFFFFF", acento), 2)
    ev["paginas"] = {}
    for p in PAGINAS:
        t0 = time.perf_counter()
        W["show_page"](p)
        r.update_idletasks()
        ms1 = round((time.perf_counter() - t0) * 1000)
        h.bombear(2.5)
        cap = co.capturar(r, CAPS / f"{DPI}-{p}.png", h.bombear, durante=lambda: medir_visible(h, r))
        W["show_page"]("registro")
        r.update_idletasks()
        t0 = time.perf_counter()
        W["show_page"](p)
        r.update_idletasks()
        ms2 = round((time.perf_counter() - t0) * 1000)
        cap["abrir_ms"] = {"primera": ms1, "segunda": ms2}
        ev["paginas"][p] = cap
    # barra lateral: ancho real con la ventana mostrada
    ev["barra_lateral"] = co.capturar(r, CAPS / f"{DPI}-estado-otra.png", h.bombear,
                                      durante=lambda: {"ancho_px": W["sidebar"].winfo_width(),
                                                       "esperado_px": gb.S(gb.BARRA_PX)})
    # configuración inicial
    gb.open_onboarding(r)
    h.bombear(2.5)
    ev["configuracion_inicial"] = co.capturar(r, CAPS / f"{DPI}-configuracion-inicial.png", h.bombear,
                                              durante=lambda: medir_visible(h, r))
    try:
        gb._OB["frame"].destroy()
    except Exception:  # noqa: BLE001
        pass
    ev["estatico"] = estatico()
    ev["filas_px_esperadas"] = {"FILA_PX": gb.FILA_PX, "a_este_dpi": gb.S(gb.FILA_PX)}


correr("auditoria", pasos, dpi=DPI, puerto=8776, espera_ms=6000)
