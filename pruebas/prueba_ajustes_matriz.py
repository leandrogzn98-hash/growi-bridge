"""Prueba de la matriz motor × permiso y los avisos de la cola en Ajustes (ESTADO-AJUSTES-MATRIZ.md). Oculta.

Siembra politicas.json con dos reglas reales («No permitir nunca: escribir fuera» y «Preguntar siempre: leer») y
pone el guardrail en «delicado»; la matriz debe decir lo mismo que politica_decidir y _desde (lo del runner).

  python pruebas/prueba_ajustes_matriz.py 100 | 150
  python pruebas/prueba_ajustes_matriz.py 100 clasica | sinctk | flag
  python pruebas/prueba_ajustes_matriz.py 100 arranque [fuente.py]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
REGLAS = [{"accion": "escribir_fuera", "decision": "deny", "carpeta": ""},
          {"accion": "leer", "decision": "ask", "carpeta": ""}]


def preparar(app, tmp):
    (app / "politicas.json").write_text(json.dumps({"reglas": REGLAS}), encoding="utf-8")


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("ajustes")
    h.bombear(1.5)
    if VAR == "arranque":
        return
    M = gb._MTZ
    m = M.get("datos") or {}
    ev["tarjeta"] = type(M["card"]).__name__ if M.get("card") is not None else None
    ev["columnas"] = m.get("columnas")
    ev["guardrail"] = m.get("guardrail")
    # (a) cada motor y lo que puede, en pantalla
    pantalla = {}
    for f in m.get("filas", []):
        if (f["motor"], "_aviso") in M["celdas"]:
            pantalla[f["motor"]] = {"aviso": str(M["celdas"][(f["motor"], "_aviso")].cget("text"))}
        else:
            pantalla[f["motor"]] = {t: getattr(M["celdas"][(f["motor"], t)], "_valor", "")
                                    for t, _c, _n in m["columnas"]}
            ev.setdefault("a_simbolos", {})[f["motor"]] = {t: str(M["celdas"][(f["motor"], t)].cget("text"))
                                                           for t, _c, _n in m["columnas"]}
    ev["a_matriz"] = pantalla
    ev["a_estados"] = {f["motor"]: f["estado"] for f in m.get("filas", [])}
    # comprobar 2 motores con herramientas contra politicas.json + guardrail, con las funciones del runner
    tabla, _e = gb.cargar_riesgos()
    esperado = {}
    for t, _c, nivel in m["columnas"]:
        acc = {"tipo": t, "nivel": nivel, "nombre": t, "rutas": []}
        if nivel == "R3":
            esperado[t] = "Pregunta"
            continue
        dec, _r = gb.politica_decidir(acc, {"cwd": ""})
        if dec:
            esperado[t] = {"allow": "Sí", "ask": "Pregunta", "deny": "No"}[dec] + " *"
        else:
            esperado[t] = "Pregunta" if gb._rango(nivel) >= gb._rango(gb._desde(tabla, gb.guardrail_level())) else "Sí"
    con_herr = [mo for mo, e in ev["a_estados"].items() if e == "ok"][:2]
    ev["a_esperado"] = esperado
    ev["a_cuadra"] = {mo: pantalla[mo] == esperado for mo in con_herr}
    # (b) de lectura: las celdas no tienen manejadores y no cambian nada
    antes = (json.dumps(gb.politicas_leer()[0], sort_keys=True), gb.load_settings().get("guardrail"))
    sin_bind = all(not c.bind() for c in M["celdas"].values())
    for c in list(M["celdas"].values())[:8]:
        for seq in ("<Button-1>", "<Return>", "<space>"):
            if c.bind(seq):
                h.disparar(c, seq)
    h.bombear(0.2)
    despues = (json.dumps(gb.politicas_leer()[0], sort_keys=True), gb.load_settings().get("guardrail"))
    ev["b_lectura"] = {"celdas_sin_manejadores": sin_bind, "nada_cambio": antes == despues,
                       "celdas_enfocables": sum(1 for c in M["celdas"].values() if str(c.cget("takefocus")) == "1")}
    # (c) avisos de la cola: no existe ningún ajuste de notificación -> «sin notificaciones configuradas», sin toggles
    ev["c_avisos"] = {k: str(v.cget("text")) for k, v in M["avisos"].items()}
    toggles = [w for w in h.todos(M["avisos"]["espera"].master.master)
               if type(w).__name__ in ("_Switch", "CTkSwitch", "Checkbutton", "CTkCheckBox") or hasattr(w, "_on")]
    ev["c_toggles"] = len(toggles)
    # (d) motor sin clave: aviso en línea
    ev["d_sin_clave"] = {mo: v.get("aviso") for mo, v in pantalla.items() if ev["a_estados"][mo] == "sin_clave"}
    # DPI: la rejilla cabe en el contenido a ventana mínima
    mw = int(gb._root.minsize()[0])
    contenido = mw - int(W["sidebar"].cget("width")) - gb.S(40 + 32 + 24 + 14)
    rej = next(iter(M["celdas"].values())).master
    ev["e_dpi"] = {"minsize_ancho": mw, "contenido": contenido, "rejilla_pedida": rej.winfo_reqwidth(),
                   "cabe": rej.winfo_reqwidth() <= contenido}


correr("ajustes-matriz", pasos, dpi=DPI, variante=VAR, preparar=preparar, antes_de_main=antes_de_main,
       settings={"guardrail": "delicado", **({"piloto_ctk": False} if VAR == "flag" else {})}, puerto=8777,
       fuente=FUENTE)
