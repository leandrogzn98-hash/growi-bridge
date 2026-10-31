"""Prueba de los arreglos de BUGS-046-VIDEO (B2, B3, B4, B6, B7, B8, B10). Oculta: no abre ventanas.

  python pruebas/prueba_bugs_046.py

B1 (freeze al arrancar) se mide aparte: la migración de claves corre en un hilo y aquí solo se
comprueba que main() no la llama en el hilo de la ventana. B8 se prueba con eventos de rueda
sintéticos (touchpad = deltas pequeños). B5 necesita la página de Tripo abierta: queda para la
prueba en instancia aislada con los datos reales.
"""

import json
import re
import sys
import tkinter as tk
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


class _Cola(dict):
    """Resumen de cola vacío: cualquier contador que pida _gw_rows vale 0."""

    def __missing__(self, _k):
        return 0

    def get(self, k, default=None):
        return dict.get(self, k, default)


def pasos(h):
    gb, ev = h.gb, h.ev

    def ok(nombre, cond, detalle=""):
        ev.setdefault("checks", {})[nombre] = {"ok": bool(cond), "detalle": str(detalle)[:300]}

    # B3: el acento del tema Raycast es azul, no #FF6363
    tema = json.loads((REPO / "temas" / "oscuro-raycast.json").read_text(encoding="utf-8"))
    ok("B3_acento_azul", tema["fijos"]["accent"].lower() == "#6aa9ff"
       and "ff6363" not in json.dumps(tema["tokens"]).lower(), tema["fijos"]["accent"])

    # B2: con la sonda de Tailscale en False, nunca «Conectado»
    real = gb.conn_state
    try:
        gb.conn_state = lambda: "conectado"
        gb._IPX["tailscale"] = False
        t_caido, c_caido = gb.conn_text(), gb._conn_color()
        gb._IPX["tailscale"] = True
        t_ok = gb.conn_text()
        gb._IPX["tailscale"] = None
        t_none = gb.conn_text()
    finally:
        gb.conn_state = real
        gb._IPX["tailscale"] = None
    ok("B2_tailscale_caido", t_caido == "● Tailscale caído" and c_caido == gb.THEME["red"], t_caido)
    ok("B2_tailscale_ok", t_ok.startswith("● Conectado"), t_ok)
    ok("B2_sin_tunel_no_cambia", t_none.startswith("● Conectado"), t_none)
    sonda = gb._tailscale_sonda()  # real: True si este PC tiene Tailscale y el puente de prueba escucha ahí
    ok("B2_sonda_responde", sonda in (None, True, False), sonda)

    # B6: «Quitar» solo con atajo; sin atajo, «Asignar»
    fr = tk.Frame(gb._root)
    holder = {"c": None}
    alternar = gb._atajo_botones(lambda p, t, cmd: tk.Button(p, text=t, command=cmd), fr, holder)
    alternar(False)
    sin = [w.cget("text") for w in fr.pack_slaves()]
    alternar(True)
    con = [w.cget("text") for w in fr.pack_slaves()]
    alternar(True)
    con2 = [w.cget("text") for w in fr.pack_slaves()]
    fr.destroy()
    ok("B6_sin_atajo_asignar", sin == ["Asignar"], sin)
    ok("B6_con_atajo_quitar", con == ["Quitar"] and con2 == ["Quitar"], (con, con2))
    filas = [c for c in gb._ATAJOS["campos"] if c.foco.winfo_exists()]
    ok("B6_filas_reales_con_alternar", filas and all(c.al_cambiar for c in filas
                                                     if c.foco.winfo_toplevel() is gb._root),
       f"{len(filas)} campos")

    # B7: apagado con el puerto libre = gris, no rojo; los errores reales siguen en rojo
    apagado = gb.llm_textos({"proc": {}, "modelos": {}, "puerto": 8080, "instalado": (True, ""),
                             "responde": False})
    no_inst = gb.llm_textos({"proc": {}, "modelos": {}, "puerto": 8080, "instalado": (False, "falta"),
                             "responde": False})
    ocupado = gb.llm_textos({"proc": {"oyente": 99, "nuestro": False}, "modelos": {}, "puerto": 8080,
                             "instalado": (True, ""), "responde": False})
    ok("B7_apagado_gris", apagado[1] == "muted" and apagado[0].startswith("Apagado"), apagado[:2])
    ok("B7_errores_rojo", no_inst[1] == "red" and ocupado[1] == "red", (no_inst[1], ocupado[1]))

    # B10: credencial sin guardar -> fila con botón «Configurar»; guardada -> sin botón
    d = {"gateway": {"inicio": "2026-10-31T01:00:00", "uptime_s": 60}, "cola": _Cola(),
         "motores": [
             {"id": "gemini", "nombre": "Gemini", "disponible": True, "motivo": "",
              "credencial": {"proveedor": "gemini", "activa": "principal", "referencia": "principal",
                             "guardada": False}},
             {"id": "deepseek", "nombre": "DeepSeek", "disponible": True, "motivo": "",
              "credencial": {"proveedor": "deepseek", "activa": "principal", "referencia": "principal",
                             "guardada": True, "ultimos4": "abcd"}}]}
    try:
        rows = {r[0]: r for r in gb._gw_rows(d, "contenido")}
        sin_c, con_c = rows.get("m_gemini_c"), rows.get("m_deepseek_c")
        ok("B10_boton_configurar", sin_c is not None and len(sin_c) > 5 and sin_c[5]
           and sin_c[5][0] == "Configurar" and callable(sin_c[5][1]), sin_c)
        ok("B10_guardada_sin_boton", con_c is not None and (len(con_c) < 6 or not con_c[5]), con_c)
    except Exception as e:  # noqa: BLE001
        ok("B10_boton_configurar", False, f"{type(e).__name__}: {e}")

    # B8: la rueda acumula; deltas de touchpad (30) no saltan una unidad por evento
    movs = []
    real_scroll = tk.Canvas.yview_scroll
    tk.Canvas.yview_scroll = lambda self, n, what: movs.append(n)
    fr = tk.Frame(gb._root)
    try:
        gb._scrollable(fr)
        cv = gb._scroll_canvases[-1]
        for c in gb._scroll_canvases:  # solo el canvas de la prueba cuenta como visible
            c.winfo_ismapped = (lambda: True) if c is cv else (lambda: False)
        guion = gb._root.bind_all("<MouseWheel>")
        # 4 deltas de touchpad (-30) = una muesca hacia abajo; luego una muesca arriba y otra abajo
        for delta in (-30, -30, -30, -30, 120, -120):
            try:
                campos = {"D": str(delta), "W": str(cv)}
                gb._root.tk.eval(re.sub(r"%(\S)", lambda m: campos.get(m.group(1), "0"), guion))
            except Exception as e:  # noqa: BLE001
                ev.setdefault("b8_err", []).append(f"{type(e).__name__}: {e}"[:200])
        ok("B8_rueda_acumula", movs == [1, -1, 1], movs)
    finally:
        tk.Canvas.yview_scroll = real_scroll
        gb._scroll_canvases.remove(cv)
        fr.destroy()

    # B1: main() deja la migración de claves en un hilo
    src = (REPO / "growi-bridge.py").read_text(encoding="utf-8")
    ok("B1_migracion_en_hilo", "threading.Thread(target=_migrar_claves, daemon=True).start()" in src)
    ok("B1_mapa_en_hilo_ui", "_ui_call(_render_avail)" in src)

    ev["ok"] = all(v["ok"] for v in ev["checks"].values())
    for k, v in ev["checks"].items():
        print(("OK   " if v["ok"] else "FALLA"), k, v["detalle"])
    print("RESULTADO:", "ok" if ev["ok"] else "FALLA")


if __name__ == "__main__":
    ev = correr("bugs-046", pasos)
    sys.exit(0 if ev.get("ok") else 1)
