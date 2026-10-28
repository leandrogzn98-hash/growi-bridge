"""Prueba del onboarding con fallos (ESTADO-ONBOARDING-FALLOS.md).

(Basada en prueba_ajustes_reorg.py: app real en 8797.)

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada) y,
desde su propio bucle de Tk, abre Ajustes y la usa con el raton y el teclado
de verdad (SetCursorPos + mouse_event, SendInput): lee los grupos en orden,
escribe «proxy» en el buscador, pulsa un interruptor y mira settings.json,
y abre la zona peligrosa. Captura cada paso y sale con quit_app.

  python pruebas/prueba_ajustes_reorg.py
"""

import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "onboarding-fallos"
u32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def raton(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def teclas(texto):
    class KI(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INP(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("ki", KI), ("pad", ctypes.c_byte * 8)]
    for ch in texto:
        for fl in (0x4, 0x6):
            i = INP(1, KI(0, ord(ch), fl, 0, 0))
            u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INP))
        time.sleep(0.03)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-ob-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": False, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaOb",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_ob", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp)}
    W = gb._widgets

    def captura(nombre):
        from PIL import ImageGrab
        r = gb._root
        x, y = r.winfo_rootx(), r.winfo_rooty()
        ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def centro(w):
        return w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2

    ORIG_MO = []

    def bombear(seg):
        fin = time.time() + seg
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        preguntas = []
        gb.messagebox.askyesno = lambda t, m, **k: (preguntas.append(m), RESP[0])[1]
        RESP = [False]
        # deteccion con plan B: sin internet (simulado: google no responde) y sin Claude
        orig_probe = gb._probe
        gb._probe = lambda url, *a, **k: (None, "", 4000, "timed out") if "google" in url else orig_probe(url, *a, **k)
        det = gb.onboarding_detect()
        det["cli"]["claude"] = None  # sin Claude instalado (simulado)
        gb._OB["det"] = det
        ev["det"] = {k: det.get(k) for k in ("plan", "internet", "internet_detalle", "vram_gb", "sin_comprobar")}
        gb.open_onboarding()
        bombear(1)
        gb._OB["choice"].set("claude")
        gb._ob_render()
        bombear(0.5)
        captura("0-paso1-claude-por-instalar")
        gb._ob_next()  # paso 0 -> plan B salta «conectar» -> paso 2
        bombear(0.8)
        s = gb.load_settings()
        ev["a_plan_b"] = {"paso": gb._OB["step"], "nota": gb._OB.get("nota"),
                          "default_engine": s.get("default_engine"), "pendientes": s.get("onboarding_pendientes")}
        captura("1-plan-b-paso3")
        # guardrail: Siguiente sin cambiar el nivel conserva «delicado»
        g0 = gb.guardrail_level()
        gb._ob_save_step(2)
        ev["g_siguiente_sin_cambiar"] = {"antes": g0, "despues": gb.guardrail_level(), "preguntas": len(preguntas)}
        gb._OB["level"].set("mirar")
        RESP[0] = False
        gb._ob_save_step(2)
        ev["g_cambiar_y_decir_no"] = {"guardrail": gb.guardrail_level(), "pregunta": preguntas[-1:] }
        gb._OB["level"].set(gb._OB["level_ini"])
        # progreso: cerrar a la mitad y reabrir
        gb._OB["frame"].destroy()
        gb._OB["frame"] = None
        gb.open_onboarding()
        bombear(0.5)
        ev["c_reabrir_sigue_en_paso"] = gb._OB["step"]
        gb._ob_next(skip=True)  # saltar «carpetas» -> pendiente
        bombear(1.5)
        ev["c_saltar_queda_pendiente"] = gb.load_settings().get("onboarding_pendientes")
        # paso 4: proxy caido
        gb.proxy_url = lambda: "http://127.0.0.1:9"
        gb._ob_run_checks()
        bombear(12)
        ic, msg = gb._OB["checks"]["proxy"]
        ev["b_proxy_caido_paso4"] = {"texto": msg.cget("text"), "botones_visibles": bool(gb._OB["proxy_botones"].winfo_manager())}
        captura("2-paso4-proxy-caido")
        btn = [b for b in gb._OB["proxy_botones"].winfo_children() if b.cget("text") == "Seguir sin proxy"][0]
        btn.invoke()
        bombear(0.3)
        ev["b_seguir_sin_proxy"] = {"texto": msg.cget("text"), "pendientes": gb.load_settings().get("onboarding_pendientes")}
        ev["f_ejemplo"] = gb._ob_example()
        gb._ob_finish(start=True)
        bombear(0.5)
        ev["f_chat_trae_el_ejemplo"] = W["ask_text"].get("1.0", "end").strip()
        ev["f_paleta_primera_vez"] = [(t, [i["label"] for i in it]) for t, it in gb._palette_sections("")][:1]
        ev["f_paleta_segunda_vez"] = [t for t, _it in gb._palette_sections("")][:2]
        # «Otro» con dos datos
        gb._OB["frame"] = None
        gb.open_onboarding()
        gb._OB["step"] = 0
        gb._OB["choice"].set("otro")
        gb._OB["otro_nombre"].set("MiIA")
        gb._OB["otro_cmd"].set('miia -p "{prompt}"')
        gb._ob_save_step(0)
        ev["b_otro"] = {"asistente_otro": gb.load_settings().get("asistente_otro"),
                        "pendientes": gb.load_settings().get("onboarding_pendientes")}
        gb._OB["frame"].destroy()
        gb._OB["frame"] = None
        # (d) checklist en Estado, tachada sola por deteccion
        gb.save_folders([str(tmp)])
        gb._ob_checklist_refresh()
        W["show_page"]("estado")
        bombear(1)
        ev["d_checklist"] = gb._widgets.get("ob_check_estado")
        captura("3-estado-checklist")
        # (e) reinstalacion: ya hay configuracion
        s = gb.load_settings()
        s["onboarding_done"] = False
        s["assistant"] = "claude"
        gb.save_settings(s)
        RESP[0] = True
        ORIG_MO[0]()
        ev["e_reinstalacion"] = {"pregunta": preguntas[-1], "onboarding_done": gb.load_settings().get("onboarding_done"),
                                 "overlay_abierto": gb._OB.get("frame") is not None}
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "configuración inicial" in x][-10:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        gb.quit_app()

    def _textos(w):
        out = []
        for ch in w.winfo_children():
            try:
                out.append(str(ch.cget("text")))
            except Exception:
                pass
            out += _textos(ch)
        return out

    orig = gb.build_gui

    def build():
        root = orig()
        root.after(6000, lambda: _seguro(pasos))
        return root

    def _seguro(fn):
        try:
            fn()
        except Exception:
            import traceback
            ev["error_prueba"] = traceback.format_exc()
            (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
            gb.quit_app()
    gb.build_gui = build
    ORIG_MO.append(gb.maybe_onboarding)
    gb.maybe_onboarding = lambda: None  # la prueba abre el onboarding a mano
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


if __name__ == "__main__":
    main()
