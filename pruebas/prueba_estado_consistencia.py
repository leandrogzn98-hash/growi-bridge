"""Prueba del estado único de Estado (ESTADO-ESTADO-CONSISTENCIA-045.md). Oculta: no abre ventanas.

Recorre los cuatro casos en la instancia de prueba y lee TODOS los indicadores (pastilla de la barra lateral, banner,
botón de encendido y su texto, puntos de Servicios, tarjetas de salud):
  arriba   : puente, runner y proxy respondiendo (el proxy real del PC)
  abajo    : el puente se detiene de verdad (stop_bridge)
  parcial  : el puente vuelve; la prueba del proxy da «falla» (no se puede apagar el proxy real del VPS desde aquí)
  opus     : el runner con una tarea de Claude Opus en curso y la sonda de la nube fallando 3 veces

  python pruebas/prueba_estado_consistencia.py 100 | 150
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("estado")
    h.bombear(4.0)

    def leer(nombre):
        gb.refresh_ui()
        gb._refresh_conn_widgets()
        gb._est_pintar(forzar=True) if gb._EST.get("kit") is not None else None
        h.bombear(0.5)
        eu = gb.estado_unico()
        ind = {"estado_unico": {k: eu[k] for k in ("nivel", "puente", "runner", "proxy", "nube_caida", "caidos",
                                                    "texto")},
               "barra_lateral": str(W["conn_chip"].cget("text")),
               "banner_visible": bool(W["cloud_banner"].winfo_manager()),
               "banner_texto": str(W["cloud_banner_txt"].cget("text")) if W["cloud_banner"].winfo_manager() else "",
               "boton_texto": str(W["power_label"].cget("text")),
               "boton_color": str(W["power_label"].cget("fg")),
               "puntos": {k: str(W[f"{k}_dot"].cget("fg")) for k in ("bridge", "runner", "proxy")},
               "bandeja": gb._tray_kind().split("|")[0],
               "tarjetas": {k: (v["color"], v["texto"]) for k, v in gb._EST.get("salud", {}).items()
                            if k in ("puente", "runner", "proxy")}}
        todos = " | ".join([ind["barra_lateral"], ind["banner_texto"], ind["boton_texto"]]
                           + [t for _c, t in ind["tarjetas"].values()])
        verde = gb.THEME["green"]
        ind["regla"] = {"dice_sin_conexion": "Sin conexión" in todos,
                        "dice_todo_encendido": "Todo encendido" in todos,
                        "puntos_verdes": [k for k, c in ind["puntos"].items() if c.upper() == verde.upper()]}
        ev[nombre] = ind

    # arriba
    leer("a_arriba")
    # abajo: el puente se detiene de verdad
    gb.stop_bridge()
    h.bombear(2.0)
    leer("b_abajo")
    # parcial: el puente vuelve (y el gateway responde) y la prueba del proxy da «falla»
    gb.start_bridge()
    for _ in range(30):
        h.bombear(1.0)
        gb._gw_refrescar_ahora()
        h.bombear(0.3)
        if gb.estado_unico()["puente"] == "arriba":
            break
    prev_proxy = dict(gb._AV["rows"].get("proxy") or {})
    gb.state["proxy_on"] = True
    gb._AV["rows"]["proxy"] = {"estado": "falla", "frase": "el proxy no responde (prueba)"}
    leer("c_parcial")
    gb._AV["rows"]["proxy"] = prev_proxy or {"estado": "ok", "frase": "Conectado"}
    # opus: tarea de Claude Opus en curso + la sonda de la nube fallando
    (gb.OUTBOX / gb._STATUS_NOMBRE["principal"]).write_text(json.dumps({
        "last_poll": datetime.now().astimezone().isoformat(timespec="seconds"),
        "current": {"id": "t-opus-en-curso", "motor": "claude", "modelo": "opus", "modelo_real": "claude-opus-5-5"},
        "ultima_ejecucion": {"tarea": "t-anterior", "motor": "claude", "modelo": "claude-opus-5-5", "status": "ok"}}),
        encoding="utf-8")
    gb._AV["rows"]["claude"] = {"estado": "falla", "ruta": "proxy", "frase": "no responde (prueba)"}
    gb._AV["rows"]["ollama"] = {"estado": "falla", "frase": "no responde (prueba)"}
    gb._AV["nube_fallos"] = 3
    leer("d_opus")
    # la sonda pasa de «conectado» a «sin» con Opus trabajando: ningún toast de alarma
    avisos, orig = [], gb.toast
    gb.toast = lambda msg, *a, **k: avisos.append(msg)
    try:
        gb._AV["last_conn"] = "conectado"
        gb._after_availability()
    finally:
        gb.toast = orig
    ev["d_opus"]["toasts_de_conexion"] = avisos
    ev["d_opus"]["sonda"] = {"conn_state": gb.conn_state(), "nube_fallos": gb._AV["nube_fallos"],
                             "probe": gb.estado_unico()["banner"]["probe"]}
    ev["log"] = [x[26:] for x in h.log().splitlines() if "puente:" in x][-4:]


correr("estado-consistencia", pasos, dpi=DPI, puerto=8773, espera_ms=6000)
