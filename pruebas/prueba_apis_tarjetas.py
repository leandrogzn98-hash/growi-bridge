"""Prueba de las tarjetas de conexión de APIs (ESTADO-APIS-TARJETAS.md). Oculta: no abre ventanas.

Claves FALSAS contra un servidor local (127.0.0.1:8793) que contesta 200 a la clave buena y 401 al resto: nada sale a
internet ni se gasta. El almacén es un archivo DPAPI de la copia (GROWI_BRIDGE_CRED_BACKEND=dpapi).

  python pruebas/prueba_apis_tarjetas.py 100 | 150
  python pruebas/prueba_apis_tarjetas.py 100 clasica | sinctk | flag
  python pruebas/prueba_apis_tarjetas.py 100 arranque [fuente.py]
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
PUERTO_FALSO = 8793
PEDIDOS: list = []
BUENA = "sk-bueno-prueba-0123456789abcdef"
MALA = "sk-malo-prueba-0123456789abcdef"


class Falso(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        PEDIDOS.append(self.path)
        ok = self.headers.get("Authorization") == f"Bearer {BUENA}"
        cuerpo = json.dumps({"data": [{"id": "modelo-falso"}]} if ok else
                            {"error": {"message": "clave falsa de la prueba"}}).encode()
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO_FALSO), Falso)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    if VAR == "arranque":  # build_gui (lo mide el arnés) y el dibujo de APIs al abrirla (la superficie es perezosa)
        W["show_page"]("apis")
        h.bombear(1.5)
        ev["log_apis"] = [x for x in h.log().splitlines() if "claves: apis:" in x]
        return
    base = f"http://127.0.0.1:{PUERTO_FALSO}"
    ev["guardar"] = [gb.cred_guardar("openai", "prueba", base + "/v1", BUENA),
                     gb.cred_guardar("groq", "prueba", base + "/openai/v1", MALA),
                     gb.cred_guardar("xai", "vieja", base + "/v1", MALA)]
    s = gb.load_settings()  # la de xAI queda guardada pero inactiva
    for c in s["credenciales"]:
        if c["proveedor"] == "xai":
            c["activa"] = False
    gb.save_settings(s)
    W["show_page"]("apis")
    h.bombear(1.5)
    inst = gb._CLV["inst"]["apis"]
    k = inst["kit"]
    ev["kit"] = type(k).__name__
    rows = inst["conex_rows"]

    def estados():
        rr = inst["conex_rows"]
        return {p: {"estado": r["estado"], "texto": str(r["texto"].cget("text")), "accion": r["accion"],
                    "boton": type(r["boton"]).__name__, "card": type(r["card"]).__name__} for p, r in rr.items()}
    ev["a_tarjetas"] = estados()
    ev["a_todas"] = sorted(rows) == sorted(gb.CRED_ORDER)
    if hasattr(rows["openai"]["card"], "cget") and type(rows["openai"]["card"]).__name__ == "CTkFrame":
        ev["a_esquinas"] = rows["openai"]["card"].cget("corner_radius")
    # (b) probar con clave (bueno -> Conectada) y con clave mala (-> Error) desde la tarjeta
    for prov in ("openai", "groq"):
        inst["conex_rows"][prov]["boton"].invoke()
        h.bombear(0.3)
        ev.setdefault("b_durante", {})[prov] = inst["conex_rows"][prov]["estado"]
    for _ in range(60):
        h.bombear(0.5)
        if not gb._CLV["busy"]:
            break
    h.bombear(0.5)
    pr = gb.load_settings().get("credenciales_pruebas") or {}
    ev["b_tras_probar"] = {p: v for p, v in estados().items() if p in ("openai", "groq", "xai", "anthropic")}
    ev["b_pruebas_guardadas"] = {c: {"ok": v["ok"], "texto": v["texto"]} for c, v in pr.items()}
    ev["b_cuadra"] = (inst["conex_rows"]["openai"]["estado"] == "conectada"
                      and inst["conex_rows"]["groq"]["estado"] == "error"
                      and inst["conex_rows"]["xai"]["estado"] == "sin_activa"
                      and inst["conex_rows"]["anthropic"]["estado"] == "sin_clave"
                      and pr[gb.cred_cuenta("openai", "prueba")]["ok"] is True
                      and pr[gb.cred_cuenta("groq", "prueba")]["ok"] is False)
    ev["b_pedidos_al_servidor_local"] = PEDIDOS
    # (c) los botones de acción: «Poner clave» prepara el formulario; el «Probar clave» de la fila sigue igual
    inst["conex_rows"]["anthropic"]["boton"].invoke()
    h.bombear(0.4)
    ev["c_poner_clave"] = {"proveedor_form": inst["f_prov"].get(), "url_form": inst["f_url"].get(),
                           "esperado": gb.CRED_PROVIDERS["anthropic"]["base"]}
    cu = gb.cred_cuenta("openai", "prueba")
    inst["rows"][cu]["probar"].invoke()
    for _ in range(60):
        h.bombear(0.5)
        if not gb._CLV["busy"]:
            break
    ev["c_probar_de_la_fila"] = {"texto_fila": str(inst["rows"][cu]["estado"].cget("text")),
                                 "tarjeta": inst["conex_rows"]["openai"]["estado"]}
    # foco: cada botón de tarjeta es parada de Tab con Espacio/Intro (CTk) o un ttk.Button (clásica)
    ev["d_foco"] = {}
    for p, r in inst["conex_rows"].items():
        b = r["boton"]
        cv = getattr(b, "_canvas", None)
        ev["d_foco"][p] = ({"takefocus": str(cv.cget("takefocus")), "espacio": bool(cv.bind("<space>"))}
                           if cv is not None else {"ttk": type(b).__name__, "takefocus": str(b.cget("takefocus"))})
    # DPI: el texto de estado (wrap 440) + márgenes cabe en el contenido a ventana mínima
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 32 + 24 + 14)
    lab = inst["conex_rows"]["groq"]["texto"]
    wl = int(str(lab.cget("wraplength")) or 0)
    wl_px = round(wl * gb.SCALE) if ev["kit"] == "_KitCtk" else wl
    l1 = inst["conex_rows"]["groq"]["boton"].master
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "wrap_estado_px": wl_px,
                   "linea1_pedida": l1.winfo_reqwidth(), "cabe": wl_px <= contenido and l1.winfo_reqwidth() <= contenido}


correr("apis-tarjetas", pasos, dpi=DPI, variante=VAR, antes_de_main=antes_de_main,
       settings={"piloto_ctk": False} if VAR == "flag" else None, puerto=8792, fuente=FUENTE)
