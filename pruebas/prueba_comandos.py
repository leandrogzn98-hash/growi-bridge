"""Prueba de los comandos de script (ESTADO-COMANDOS-SCRIPT.md).

La app REAL (copia en %TEMP%, puerto 8797) con comandos\\ = las 2 plantillas
del repo + scripts de prueba. Desde su bucle de Tk: paleta, ejecucion por
modo, interruptor (clic de verdad), aviso de lo delicado, marca de
«descargado de internet» y .ps1 bloqueado (PSExecutionPolicyPreference=
Restricted solo para este proceso: no toca la politica del sistema).

  python pruebas/prueba_comandos.py
"""

import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "comandos"
u32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

PRUEBAS = {
    "prueba-silencioso.bat": "@echo off\r\n:: @growi.titulo Prueba silenciosa\r\n:: @growi.descripcion Deja una marca\r\n"
                             ":: @growi.modo silencioso\r\n:: @growi.autor prueba\r\necho hecho> marca-silencioso.txt\r\n",
    "prueba-ventana.py": "# @growi.titulo Prueba ventana\n# @growi.descripcion Escribe un saludo\n# @growi.modo ventana\n"
                         "print('hola desde la ventana')\n",
    "prueba-lista.py": "# @growi.titulo Prueba lista\n# @growi.modo lista\nimport json\n"
                       "print(json.dumps({'items': [{'titulo': 'uno', 'accion': {'tipo': 'copiar', 'valor': 'valor-uno'}},"
                       " {'titulo': 'dos', 'accion': {'tipo': 'copiar', 'valor': 'valor-dos'}}]}))\n",
    "prueba-delicada.py": "# @growi.titulo Prueba delicada\n# @growi.modo silencioso\n# @growi.autor prueba\nimport os\n"
                          "open('borrame.txt', 'w').close()\nos.remove('borrame.txt')\n",
    "prueba-ps.ps1": "# @growi.titulo Prueba PowerShell\n# @growi.modo ventana\nWrite-Output 'hola desde ps1'\n",
    "prueba-descargada.bat": "@echo off\r\n:: @growi.titulo Prueba descargada\r\n:: @growi.modo silencioso\r\necho x\r\n",
    "sin-cabecera.bat": "@echo off\r\necho nada\r\n",
}


def raton(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-cmds-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    for n, t in PRUEBAS.items():
        (app / "comandos" / n).write_bytes(t.encode("utf-8"))
    with open(app / "comandos" / "prueba-descargada.bat:Zone.Identifier", "w") as fh:  # marca de internet
        fh.write("[ZoneTransfer]\nZoneId=3\n")
    (app / "secret.txt").write_text("prueba-cmds", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit"}),
        encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            if isinstance(m.get("autenticacion"), dict):
                m["autenticacion"].pop("sesion_cli", None)
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaCmds",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a", GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      PSExecutionPolicyPreference="Restricted")
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_cmds", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp)}
    W = gb._widgets
    toasts = []
    gb.toast = lambda text, ctx=None: toasts.append(text)

    def bombear(seg):
        fin = time.time() + seg
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def captura(nombre, w):
        from PIL import ImageGrab
        w.update()
        x, y = w.winfo_rootx(), w.winfo_rooty()
        ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def cmd(archivo):
        return next(c for c in gb._CMDS["lista"] if c["archivo"] == archivo)

    def pasos():
        r = gb._root
        bombear(2)
        lista = gb.comandos_descubrir()
        ev["descubiertos"] = [{k: c[k] for k in ("archivo", "titulo", "modo", "descripcion", "autor", "pide",
                                                 "activo", "problemas", "de_internet")} for c in lista]
        # (a) en la paleta
        gb.comandos_paleta_sync()
        secs = dict((t, [c["label"] for c in it]) for t, it in gb._palette_sections(""))
        ev["a_paleta_seccion_mis_comandos"] = secs.get("Mis comandos")
        ev["a_descargado_fuera_de_la_paleta"] = "Prueba descargada" not in (secs.get("Mis comandos") or [])
        ev["a_paleta_buscar_prueba"] = [c["label"] for _t, it in gb._palette_sections("prueba") for c in it]
        # (b) cada modo
        out = gb.comando_ejecutar(cmd("prueba-silencioso.bat"), args=[], espera=True)
        ev["b_silencioso"] = {"rc": out["rc"], "marca_creada": (app / "comandos" / "marca-silencioso.txt").exists(),
                              "toast": toasts[-1:]}
        out = gb.comando_ejecutar(cmd("prueba-ventana.py"), args=[], espera=True)
        ev["b_ventana"] = {"rc": out["rc"], "stdout": out["stdout"].strip(),
                           "ventana": W["cmd_ventana"].title()}
        captura("1-modo-ventana", W["cmd_ventana"])
        W["cmd_ventana"].destroy()
        out = gb.comando_ejecutar(cmd("prueba-lista.py"), args=[], espera=True)
        top, lb, items = W["cmd_lista"]
        ev["b_lista"] = {"items": [lb.get(i) for i in range(lb.size())]}
        top.attributes("-topmost", True)
        top.focus_force()
        lb.focus_force()
        lb.selection_clear(0, "end")
        lb.selection_set(1)
        bombear(0.4)
        top._elegir()  # el manejador de Intro / doble clic sobre la fila elegida
        bombear(0.5)
        ev["b_lista_enter_copia"] = r.clipboard_get()
        # (e) las 2 plantillas
        out = gb.comando_ejecutar(cmd("archivos-recientes.py"), args=[], espera=True)
        top, lb, items = W["cmd_lista"]
        ev["e_plantilla_archivos_recientes"] = {"rc": out["rc"], "items": len(items),
                                                "primero": lb.get(0) if lb.size() else None}
        captura("2-plantilla-lista", top)
        top.destroy()
        out = gb.comando_ejecutar(cmd("abrir-resultados.bat"), args=[], espera=True)
        ev["e_plantilla_abrir_resultados"] = {"rc": out["rc"], "carpeta_existe": (tmp / "share" / "outbox").exists()}
        # (d) delicado: la primera vez pregunta con el texto completo
        vista = {}

        def responder():
            t = W.get("cmd_permiso_top")
            if t is not None and t.winfo_exists():
                vista["titulo"] = t.title()
                textos = [w for w in t.winfo_children() if w.winfo_class() == "Text"]
                vista["texto_completo_mostrado"] = textos[0].get("1.0", "end").strip() if textos else None
                captura("3-permiso-delicado", t)
                boton = [b for f in t.winfo_children() if f.winfo_class() == "Frame" for b in f.winfo_children()][0]
                bx, by = boton.winfo_rootx() + 20, boton.winfo_rooty() + boton.winfo_height() // 2
                raton(bx, by)  # clic de verdad en «Permitir este comando»
        r.after(1500, responder)
        out1 = gb.comando_ejecutar(cmd("prueba-delicada.py"), args=[], espera=True)
        vista["rc_primera"] = out1 and out1["rc"]
        W["cmd_permiso_top"] = None
        out2 = gb.comando_ejecutar(cmd("prueba-delicada.py"), args=[], espera=True)
        vista["segunda_vez_pregunto"] = W.get("cmd_permiso_top") is not None
        vista["rc_segunda"] = out2 and out2["rc"]
        vista["decision_guardada"] = (gb.load_settings().get("comandos_permisos") or {}).get("prueba-delicada.py")
        ev["d_delicado"] = vista
        # (5) descargado de internet: no se ejecuta
        gb.messagebox.showwarning = lambda t, m: ev.__setitem__("descargado_aviso", m)
        ev["descargado_resultado"] = gb.comando_ejecutar(cmd("prueba-descargada.bat"), args=[], espera=True)
        # (f) .ps1 bloqueado por ExecutionPolicy -> aviso + Bypass explicito
        out = gb.comando_ejecutar(cmd("prueba-ps.ps1"), args=[], espera=True)
        top = W["cmd_ventana"]
        ev["f_ps1_bloqueado"] = {"bloqueado": out["bloqueado_ps"], "salida": (out["stderr"] or out["stdout"])[:300],
                                 "aviso": [w.cget("text") for w in top.winfo_children() if w.winfo_class() == "Label"]}
        captura("4-ps1-bloqueado", top)
        boton = [w for w in top.winfo_children() if w.winfo_class() == "TButton"][0]
        ev["f_boton"] = boton.cget("text")
        top.destroy()
        out = gb.comando_ejecutar(cmd("prueba-ps.ps1"), args=[], bypass=True, espera=True)
        ev["f_con_bypass"] = {"rc": out["rc"], "stdout": out["stdout"].strip(), "argv": out["argv"]}
        W["cmd_ventana"].destroy()
        # (c) interruptor con clic de verdad en «Mis comandos»
        top = gb.comandos_ui()
        top.attributes("-topmost", True)
        bombear(1)
        b = W["cmds_botones"]["prueba-ventana.py"]
        par = b
        while par is not None and par.winfo_class() != "Canvas":
            par = par.master
        if par is not None:  # que la fila se vea antes de hacer clic
            y = b.winfo_rooty() - par.winfo_rooty() + par.canvasy(0) - 80
            par.yview_moveto(max(0, y) / max(1, float(par.bbox("all")[3])))
            bombear(0.5)
        raton(b.winfo_rootx() + 20, b.winfo_rooty() + b.winfo_height() // 2)
        bombear(0.5)
        ev["c_texto_boton_tras_clic"] = b.cget("text")
        captura("5-mis-comandos", top)
        gb.comandos_paleta_sync()
        ev["c_tras_desactivar"] = {
            "en_paleta": any(c["label"] == "Prueba ventana" for c in gb._PALETTE_CMDS),
            "archivo_sigue": (app / "comandos" / "prueba-ventana.py").exists(),
            "settings_comandos_off": gb.load_settings().get("comandos_off")}
        top.destroy()
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "comandos:" in x][-14:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
        gb.quit_app()

    def _seguro():
        try:
            pasos()
        except Exception:
            import traceback
            ev["error_prueba"] = traceback.format_exc()
            (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                                encoding="utf-8")
            gb.quit_app()
    orig = gb.build_gui

    def build():
        root = orig()
        root.after(2000, _seguro)
        return root
    gb.build_gui = build
    gb.maybe_onboarding = lambda: None
    gb.main()
    os._exit(0)


if __name__ == "__main__":
    main()
