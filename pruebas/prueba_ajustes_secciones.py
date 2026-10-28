"""Prueba de Ajustes en secciones (ESTADO-AJUSTES-SECCIONES.md). Oculta: no abre ventanas.

NADA real se ejecuta en el PC: set_autostart (schtasks), pc_power (shutdown /s|/r /t 60) y pc_abort (shutdown /a)
se sustituyen ANTES de construir la ventana por registradores; las confirmaciones (askyesno / askstring) se
contestan solas. Así se prueba que cada control llama a su manejador, con la confirmación y el Cancelar.

  python pruebas/prueba_ajustes_secciones.py 100 | 150
  python pruebas/prueba_ajustes_secciones.py 100 clasica | sinctk | flag
  python pruebas/prueba_ajustes_secciones.py 150 texto150     (150 % de texto + 150 % de DPI)
  python pruebas/prueba_ajustes_secciones.py 100 arranque [fuente.py]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arnes_oculto import correr  # noqa: E402

DPI = sys.argv[1] if len(sys.argv) > 1 else "100"
VAR = sys.argv[2] if len(sys.argv) > 2 else "ctk"
FUENTE = sys.argv[3] if len(sys.argv) > 3 else None
LLAMADAS: list = []


def antes_de_main(gb):
    if VAR == "sinctk":
        sys.modules["customtkinter"] = None
    def registrar(*llamada, devuelve=True):
        LLAMADAS.append(llamada)
        return devuelve

    gb.set_autostart = lambda on: registrar("set_autostart", on)
    gb.pc_power = lambda action: registrar("pc_power", action)
    gb.pc_abort = lambda: registrar("pc_abort")
    gb.messagebox.askyesno = lambda *a, **k: registrar("confirmar", str(a[0]) if a else "")
    gb.messagebox.showinfo = lambda *a, **k: None
    import tkinter.simpledialog as sd
    sd.askstring = lambda *a, **k: registrar("escribir", "sin preguntar", devuelve="sin preguntar")


def pasos(h):
    gb, W, ev = h.gb, h.W, h.ev
    W["show_page"]("ajustes")
    h.bombear(1.5)
    if VAR == "arranque":
        return
    root = gb._root
    todos = h.todos(root)
    textos = [str(w.cget("text")) for w in todos if type(w).__name__ in ("CTkLabel", "Label")
              and _hay(w, "text")]
    ev["ctk"] = bool(W.get("ajustes_ctk")) if "ajustes_ctk" in W else None
    ev["log_ajustes"] = [x[26:] for x in h.log().splitlines() if "ajustes:" in x and ("CustomTkinter" in x or
                                                                                      "clásica" in x)][-2:]
    ev["log_dpi"] = [x[26:] for x in h.log().splitlines() if "DPI de la ventana" in x][-1:]
    ev["scale"] = gb.SCALE
    # (a) secciones y filas
    ev["a_secciones"] = [t for t in ("General", "Apariencia", "Conexión", "Motores, modelos y suscripciones",
                                     "Permisos y seguridad", "Zona peligrosa") if t in textos]
    ev["a_filas"] = {t: t in textos for t in ("Tamaño del texto", "Mascota", "Reducir movimiento", "Tema",
                                              "Antes de actuar", "Pedir permiso si puede costar mucho")}
    ev["a_estado_motores"] = {k: v for k, v in (W.get("aj_motores_estado") or {}).items()}
    radios = [w for w in todos if type(w).__name__ in ("CTkRadioButton", "Radiobutton")
              and _hay(w, "text") and str(w.cget("text")) in [lab for _k, lab, _e in gb.GUARDRAIL_LEVELS]]
    ev["a_guardrail_radios"] = sorted({str(w.cget("text")) for w in radios})
    # (b) Guardrail: las 3 opciones se guardan («Hazlo sin preguntar» con su doble confirmación)
    guard = {}
    for k, lab, _e in [x for x in gb.GUARDRAIL_LEVELS] + [gb.GUARDRAIL_LEVELS[0]]:
        rb = next((w for w in radios if str(w.cget("text")) == lab), None)
        if rb is None:
            guard[k] = "sin radio"
            continue
        LLAMADAS.clear()
        rb.invoke()
        h.bombear(0.3)
        guard[k] = {"settings": gb.load_settings().get("guardrail"), "confirmaciones": list(LLAMADAS)}
    ev["b_guardrail"] = guard
    # Motores: el estado mostrado = el de estado_salud_filas
    reales = {f[0]: f[3] for f in gb.estado_salud_filas() if f[0].startswith("motor:")}
    ev["b_motores_cuadra"] = {k: (v[1] == reales.get(k)) for k, v in (W.get("aj_motores_estado") or {}).items()}
    # Apariencia: tema, tamaño del texto y mascota
    tema = {}
    for modo in ("claro", "oscuro", "sistema", "oscuro"):
        gb.tema_elegir(modo=modo)
        h.bombear(0.4)
        tema[modo] = gb.load_settings().get("apariencia")
    ev["b_tema"] = tema
    tt = W.get("aj_tamano_texto")
    tam = {}
    for v in ("125", "150", "100"):
        gb.texto_tamano_poner(v)
        tam[v] = gb.load_settings().get("tamano_texto")
    ev["b_tamano_texto"] = {"guardado": tam, "control": type(tt).__name__ if tt is not None else None,
                            "valores": [x for x, _l in gb.TEXTO_TAMANOS]}
    sw = W.get("aj_mascota_sw")
    if sw is not None:
        antes = gb.load_settings().get("mascot")
        (sw.toggle() if hasattr(sw, "toggle") else h.disparar(sw, "<Button-1>"))
        h.bombear(0.4)
        ev["b_mascota"] = {"antes": antes, "despues": gb.load_settings().get("mascot"),
                           "barra_lateral_sigue": bool(W["mascot_sw"]._on) == bool(gb.load_settings().get("mascot")),
                           "tipo": type(sw).__name__}
        (sw.toggle() if hasattr(sw, "toggle") else h.disparar(sw, "<Button-1>"))
        h.bombear(0.3)
    # (c) prueba funcional de los controles del piloto (sin efectos reales)
    fun = []

    def chk(nombre, ok, detalle=""):
        fun.append({"control": nombre, "ok": bool(ok), "detalle": detalle})
    for key, ajuste in (("autostart_sw", None), ("autoupd_sw", "auto_update"), ("keepawake_sw", "keep_awake")):
        s_ = W.get(key)
        if s_ is None:
            chk(key, False, "no está")
            continue
        for _vuelta in range(2):
            LLAMADAS.clear()
            antes = gb.load_settings().get(ajuste) if ajuste else None
            (s_.toggle() if hasattr(s_, "toggle") else h.disparar(s_, "<Button-1>"))
            h.bombear(0.3)
            if ajuste:
                chk(f"{key} (vuelta {_vuelta + 1})", gb.load_settings().get(ajuste) != antes,
                    f"{ajuste}: {antes} -> {gb.load_settings().get(ajuste)}")
            else:
                chk(f"{key} (vuelta {_vuelta + 1})", any(c[0] == "set_autostart" for c in LLAMADAS), str(LLAMADAS))
    for modo, _lab in gb.CLOSE_MODES:
        gb._set_close_mode(modo)
        chk(f"al cerrar: {modo}", gb.load_settings().get("on_close") == modo, gb.load_settings().get("on_close"))
    def por_texto(t):  # la clásica no guarda estos botones en _widgets
        return next((w for w in h.todos(root) if _hay(w, "text") and str(w.cget("text")) == t
                     and hasattr(w, "invoke")), None)
    if W.get("aj_pc_cancel") is None:
        W["aj_pc_cancel"] = por_texto("Cancelar apagado")
    for key, accion, txt in (("aj_pc_off", "shutdown", "Apagar PC"), ("aj_pc_restart", "restart", "Reiniciar PC")):
        b = W.get(key) or por_texto(txt)
        LLAMADAS.clear()
        if b is not None:
            b.invoke()
            h.bombear(0.2)
        chk(f"{key}: confirma", any(c[0] == "confirmar" for c in LLAMADAS), str(LLAMADAS))
        chk(f"{key}: 60 s ({accion})", ("pc_power", accion) in LLAMADAS, str(LLAMADAS))
        LLAMADAS.clear()
        if W.get("aj_pc_cancel") is not None:
            W["aj_pc_cancel"].invoke()
            h.bombear(0.2)
        chk(f"{key}: Cancelar", ("pc_abort",) in LLAMADAS, str(LLAMADAS))
    ev["c_funcional"] = {"pasan": sum(1 for f in fun if f["ok"]), "total": len(fun), "detalle": fun}
    # (d) DPI + texto: lo de la barra cabe en la ventana mínima y las filas de Ajustes no pasan del contenido
    mw, mh = (int(x) for x in root.minsize())
    sb = W["sidebar"]
    pedido = sum(w.winfo_reqheight() for w in sb.winfo_children() if w.winfo_manager())
    contenido = mw - int(sb.cget("width")) - gb.S(40 + 14)
    import ctypes
    filas_anchas = []
    for w in todos:
        if type(w).__name__ == "CTkFrame" and w.winfo_manager() == "pack" and w.winfo_reqwidth() > contenido:
            try:
                if str(w.master).count(".") >= 4:
                    filas_anchas.append(w.winfo_reqwidth())
            except Exception:
                pass
    ev["d_dpi_texto"] = {"scale": gb.SCALE, "pantalla": (ctypes.windll.user32.GetSystemMetrics(0),
                                                         ctypes.windll.user32.GetSystemMetrics(1)),
                         "minsize": (mw, mh), "barra_pide": pedido, "barra_cabe": pedido <= mh,
                         "contenido": contenido, "filas_mas_anchas_que_el_contenido": sorted(filas_anchas)[-5:]}


def _hay(w, opt):
    try:
        w.cget(opt)
        return True
    except Exception:
        return False


correr("ajustes-secciones", pasos, dpi=DPI, variante=VAR, antes_de_main=antes_de_main,
       settings={**({"piloto_ctk": False} if VAR == "flag" else {}),
                 **({"tamano_texto": "150"} if VAR == "texto150" else {})},
       puerto=8779, fuente=FUENTE)
