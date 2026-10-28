"""Prueba de que la mascota no tapa el ✕ del detalle de Tareas (ESTADO-MASCOTA-SOLAPE.md). Oculta: no abre ventanas.

Sin ventana visible no hay coordenadas de pantalla reales, así que la prueba mide la LÓGICA con la geometría real:
la mascota donde la pone la app (_mascot_pos, esquina inferior derecha de esta pantalla) y el ✕ del detalle con la
ventana maximizada en 4 alturas de scroll: arriba, medio, abajo y la del hallazgo (justo debajo de la mascota). La
ventana de la mascota es un registrador de withdraw/deiconify (la de verdad no se puede mostrar en esta prueba).

  python pruebas/prueba_mascota_solape.py 100 | 150
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
HOY = time.strftime("%Y-%m-%dT09:00:00-04:00")


def preparar(app, tmp):
    res = tmp / "share" / "outbox" / "runner-results"
    (res / "t-solape.orquestacion.json").write_text(json.dumps({
        "raiz": "t-solape", "estado": "aprobada", "motor": "claude", "ronda": 1, "actualizado": HOY,
        "tareas": ["t-solape"], "encargo": "tarea para el solape"}), encoding="utf-8")


class VentanaMascota:
    """Lo que el vigilante usa de la ventana de la mascota, registrando cada llamada."""

    def __init__(self, x, y, lado):
        self.r, self.visible, self.llamadas = (x, y, x + lado, y + lado), True, []

    def winfo_rootx(self):
        return self.r[0]

    def winfo_rooty(self):
        return self.r[1]

    def winfo_width(self):
        return self.r[2] - self.r[0]

    def winfo_height(self):
        return self.r[3] - self.r[1]

    def withdraw(self):
        self.visible = False
        self.llamadas.append("withdraw")

    def deiconify(self):
        self.visible = True
        self.llamadas.append("deiconify")

    def attributes(self, *a):
        self.llamadas.append(f"attributes{a}")


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("tareas")
    h.bombear(1.5)
    gb._tasks_fp[0] = None
    gb._refresh_tasks_ui()
    h.bombear(0.4)
    sw, sh = gb._root.winfo_screenwidth(), gb._root.winfo_screenheight()
    mx, my = gb._mascot_pos()
    masc = VentanaMascota(mx, my, gb.MASCOT_SIZE)
    gb._mascot["win"] = masc
    ev["pantalla"] = (sw, sh)
    ev["mascota_rect"] = masc.r
    cer = gb._TDET["cerrar"]
    lado = gb.S(32)
    # el ✕ va en la cabecera del detalle, a la derecha del contenido (ventana maximizada): x fija; y según el scroll
    x_cerrar = sw - gb.S(20 + 16 + 14) - lado
    alturas = {"arriba": gb.S(160), "medio": sh // 2, "abajo": sh - gb.S(140),
               "hallazgo": my + gb.MASCOT_SIZE // 2 - lado // 2}
    real_rect, real_abierto = gb._rect_pantalla, gb._detalle_abierto
    estado_det = {"abierto": True}
    pos = {"y": 0}
    gb._rect_pantalla = lambda w: (x_cerrar, pos["y"], x_cerrar + lado, pos["y"] + lado) if w is cer else real_rect(w)
    gb._detalle_abierto = lambda: estado_det["abierto"]
    W["tasks_tree"].selection_set("t-solape")
    gb._show_task_detail()
    h.bombear(0.3)
    ajustes = {k: gb.load_settings().get("mascot") for k in ("antes",)}
    res = {}
    for nombre, y in alturas.items():
        pos["y"] = y
        masc.llamadas.clear()
        apartada = gb.mascota_solape_paso()
        # «se puede pulsar»: el ✕ no queda debajo de una mascota visible
        tapado = masc.visible and gb.rects_se_tocan((x_cerrar, y, x_cerrar + lado, y + lado), masc.r)
        res[nombre] = {"y_cerrar": y, "toca_la_mascota": gb.rects_se_tocan((x_cerrar, y, x_cerrar + lado, y + lado),
                                                                             masc.r, margen=gb.S(6)),
                       "mascota_apartada": apartada, "llamadas": list(masc.llamadas), "cerrar_tapado": tapado}
    ev["b_posiciones"] = res
    ev["b_pulsable_en_todas"] = not any(r["cerrar_tapado"] for r in res.values())
    # (d) en la posición del hallazgo: cerrar el detalle -> la mascota vuelve; reabrir -> se aparta otra vez
    pos["y"] = alturas["hallazgo"]
    gb.mascota_solape_paso()
    masc.llamadas.clear()
    estado_det["abierto"] = False
    cer.invoke()  # el ✕ de verdad: quita la selección y cierra el detalle
    h.bombear(0.2)
    gb.mascota_solape_paso()
    ev["d_cerrar"] = {"seleccion": list(W["tasks_tree"].selection()), "mascota_visible": masc.visible,
                      "llamadas": list(masc.llamadas)}
    masc.llamadas.clear()
    estado_det["abierto"] = True
    W["tasks_tree"].selection_set("t-solape")
    gb._show_task_detail()
    gb.mascota_solape_paso()
    ev["d_reabrir"] = {"mascota_visible": masc.visible, "llamadas": list(masc.llamadas)}
    estado_det["abierto"] = False
    gb.mascota_solape_paso()
    # (c) la mascota, igual fuera del detalle: ni el ajuste ni el interruptor cambian; apagarla sigue funcionando
    ev["c_mascota"] = {"ajuste_mascot_antes": ajustes["antes"], "ajuste_mascot_despues": gb.load_settings().get("mascot"),
                       "visible_fuera_del_detalle": masc.visible, "veces_apartada": gb._SOLAPE["veces"]}
    gb._mascot["win"] = None  # como si la apagaras con su interruptor
    ev["c_apagada"] = {"paso_sin_ventana": gb.mascota_solape_paso(), "estado": dict(gb._SOLAPE)}
    gb._rect_pantalla, gb._detalle_abierto = real_rect, real_abierto
    ev["log"] = [x[26:] for x in h.log().splitlines() if "mascota:" in x][-6:]


correr("mascota-solape", pasos, dpi=DPI, preparar=preparar, puerto=8775)
