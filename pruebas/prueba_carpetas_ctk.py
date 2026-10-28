"""Prueba de la página Carpetas en CustomTkinter (ESTADO-CARPETAS-CTK.md). Oculta: no abre ventanas.

  python pruebas/prueba_carpetas_ctk.py 100            CTk
  python pruebas/prueba_carpetas_ctk.py 150            CTk a 150 % simulado
  python pruebas/prueba_carpetas_ctk.py 100 clasica    GROWI_BRIDGE_CTK=0
  python pruebas/prueba_carpetas_ctk.py 100 sinctk     import de customtkinter roto
  python pruebas/prueba_carpetas_ctk.py 100 rota       CTk se importa pero falla al dibujar
  python pruebas/prueba_carpetas_ctk.py 100 flag       piloto_ctk: false
  python pruebas/prueba_carpetas_ctk.py 100 arranque [fuente.py]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
RUTAS: list = []


def preparar(app, tmp):
    for n in ("proyecto-uno", "proyecto dos con espacios y un nombre largo para partir la línea a 150 %"):
        (tmp / n).mkdir()
        RUTAS.append(str(tmp / n))
    RUTAS.append(str(tmp / "no-existe-en-este-pc"))
    (app / "folders.json").write_text(json.dumps({"allowed_roots": RUTAS}), encoding="utf-8")


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None  # import customtkinter -> ImportError
    elif VAR == "rota":
        import customtkinter as ctk

        class Rota(ctk.CTkFrame):
            def __init__(self, *a, **k):
                raise RuntimeError("CTk roto a propósito (prueba)")
        ctk.CTkFrame = Rota


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    if VAR == "arranque":
        ev["log_carpetas"] = [x for x in h.log().splitlines() if "carpetas: página" in x]
        return
    W["show_page"]("carpetas")
    h.bombear(1.0)
    page = gb._root
    ev["ctk"] = gb._CARP["ctk"]
    ev["log_carpetas"] = [x for x in h.log().splitlines() if "carpetas: " in x and ("página" in x or "Custom" in x)]
    if gb._CARP["ctk"]:
        filas = gb._CARP["filas"]
        # (a) todas las filas y botones en CTk
        ev["a_filas"] = [{"ruta": f["ruta"], "existe": f["existe"], "abrir": type(f["abrir"]).__name__,
                          "quitar": type(f["quitar"]).__name__, "abrir_estado": str(f["abrir"].cget("state")),
                          "esquinas_boton": f["abrir"].cget("corner_radius")} for f in filas]
        ev["a_card"] = {"tipo": type(gb._CARP["lista"]).__name__,
                        "esquinas": gb._CARP["lista"].cget("corner_radius"),
                        "botones_pie": [type(gb._CARP["btn_anadir"]).__name__, type(gb._CARP["btn_reset"]).__name__]}
        ev["a_rutas_iguales_a_folders_json"] = [f["ruta"] for f in filas] == gb.load_folders() == RUTAS
        # (b) cada «Abrir» abre su carpeta real (os.startfile registrado, sin abrir el Explorador)
        for f in filas:
            if f["existe"]:
                h.disparar(f["abrir"]._canvas, "<space>")  # Espacio con el foco: el mismo invoke del clic
                h.bombear(0.2)
        ev["b_abiertos"] = h.abiertos
        ev["b_cuadra"] = h.abiertos == [f["ruta"] for f in filas if f["existe"]]
        # (d) foco: cada botón activo es parada de Tab (takefocus 1) con Espacio/Intro enlazados; el anillo azul
        # lo pinta el foco global (t-teclado-foco). Oculta, Tk no recorre el orden de Tab (nada es «visible»).
        botones = [f[k] for f in filas for k in ("abrir", "quitar")] + [gb._CARP["btn_anadir"], gb._CARP["btn_reset"]]
        ev["d_foco"] = [{"texto": str(b.cget("text")), "estado": str(b.cget("state")),
                         "takefocus": str(b._canvas.cget("takefocus")), "espacio": bool(b._canvas.bind("<space>")),
                         "intro": bool(b._canvas.bind("<Return>"))} for b in botones]
        ev["d_anillo"] = {"color": gb.foco_color(), "foco_global_enlazado": bool(page.bind_all("<FocusIn>"))}
        # Quitar (Espacio) quita de folders.json la fila y repinta
        h.disparar(filas[-1]["quitar"]._canvas, "<space>")
        h.bombear(0.4)
        ev["quitar"] = {"folders_json": gb.load_folders(), "filas": len(gb._CARP["filas"])}
        # DPI: la ventana (oculta) a su tamaño mínimo; la ruta larga se parte y los botones caben en la fila
        mw, mh = (int(x) for x in page.minsize())
        page.geometry(f"{mw}x{mh}")
        h.bombear(1.0)
        f1 = gb._CARP["filas"][1]
        fila, txt, ab, qu = f1["abrir"].master, f1["texto"].master, f1["abrir"], f1["quitar"]
        ev["e_dpi"] = {"minsize": (mw, mh), "ventana": (page.winfo_width(), page.winfo_height()),
                       "fila_ancho": fila.winfo_width(), "texto_ancho": txt.winfo_width(),
                       "wraplength_ruta": f1["texto"].cget("wraplength"),
                       "ruta_alto": f1["texto"].winfo_reqheight(),
                       "abrir_x": ab.winfo_x(), "quitar_derecha": qu.winfo_x() + qu.winfo_width(),
                       "ruta_no_pisa_botones": txt.winfo_x() + txt.winfo_width() <= ab.winfo_x(),
                       "botones_dentro": qu.winfo_x() + qu.winfo_width() <= fila.winfo_width(),
                       "ruta_dentro_de_su_caja": f1["texto"].cget("wraplength") * gb.SCALE <= txt.winfo_width()}
        # Al ancho mínimo de la ventana: contenido = mínimo - barra - márgenes de página (20+20), de la tarjeta
        # (16+16) y la barra de scroll; el pack da a la ruta lo que dejan los botones, y su <Configure> la parte.
        contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 32 + 14)
        botones = ab.winfo_reqwidth() + qu.winfo_reqwidth() + gb.S(8)
        h.disparar(getattr(txt, "_canvas", txt), "<Configure>", w=contenido - botones, h=40)  # CTkFrame enlaza en su canvas
        wl = int(f1["texto"].cget("wraplength"))
        ev["e_dpi_ancho_minimo"] = {"contenido": contenido, "botones": botones, "caja_ruta": contenido - botones,
                                    "wraplength_ruta_px": round(wl * gb.SCALE),
                                    "cabe": round(wl * gb.SCALE) + botones <= contenido}
    else:
        lb = W["folders_list"]
        ev["clasica"] = {"lista": type(lb).__name__, "items": list(lb.get(0, "end")),
                         "iguales": list(lb.get(0, "end")) == gb.load_folders()}
        lb.selection_set(len(RUTAS) - 1)
        gb.remove_folder_ui()
        h.bombear(0.3)
        ev["clasica"]["tras_quitar"] = gb.load_folders()


correr("carpetas-ctk", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8794, fuente=FUENTE)
