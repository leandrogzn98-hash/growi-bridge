"""Prueba de las automatizaciones (ESTADO-AUTOMATIONS.md).

La app REAL (main() de una COPIA en %TEMP%, puerto de prueba 8797, share y
cola.db propios) con su programador corriendo. Desde su bucle de Tk:
espera el chequeo de salud del arranque, abre la ventana, escribe un
recordatorio con el teclado de verdad, espera a que se ejecute a su hora,
apaga el vigía, prueba la cuota contra logs y el límite de 1 aviso al día.
Se cuentan las llamadas a cualquier motor (_run_cli_engine/_run_http_engine):
tienen que ser 0.

  python pruebas/prueba_automations.py
"""

import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "automations"
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
        time.sleep(0.02)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-auto-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-auto", encoding="utf-8")
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaAuto",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a", GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_auto", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp)}
    motores = {"llamadas": 0}
    for nombre in ("_run_cli_engine", "_run_http_engine"):
        orig = getattr(gb, nombre)

        def envuelta(*a, _o=orig, **k):
            motores["llamadas"] += 1
            return _o(*a, **k)
        setattr(gb, nombre, envuelta)
    toasts = []
    orig_toast = gb.toast
    gb.toast = lambda text, ctx=None: (toasts.append([time.strftime("%H:%M:%S"), text]), orig_toast(text, ctx))
    W = gb._widgets

    def bombear(s):
        fin = time.time() + s
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.05)

    def captura(nombre, w):
        from PIL import ImageGrab
        x, y = w.winfo_rootx(), w.winfo_rooty()
        ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def pasos():
        bombear(28)  # el programador hace el chequeo de salud a los 20 s del arranque
        ev["b_salud_al_arrancar"] = gb.auto_historial("salud-arranque")
        ev["iniciales"] = [{k: a[k] for k in ("id", "nombre", "motor", "activo", "proactivo")} |
                           {"horario": gb.auto_describir(json.loads(a["horario"]))} for a in gb.auto_lista()]
        top = gb.automations_ui()
        top.attributes("-topmost", True)
        bombear(2)
        ent = W["auto_ent"]
        raton(ent.winfo_rootx() + 40, ent.winfo_rooty() + ent.winfo_height() // 2)
        bombear(0.3)
        teclas("recuérdame en 1 minuto probar el gate de calidad")
        bombear(0.3)
        u32.keybd_event(0x0D, 0, 0, 0)
        u32.keybd_event(0x0D, 0, 2, 0)
        bombear(1.5)
        ev["a_mensaje_ventana"] = W["auto_msg"].cget("text")
        recs = [a for a in gb.auto_lista() if a["tipo"] == "recordatorio"]
        ev["a_guardado_estructurado"] = [{k: a[k] for k in ("id", "nombre", "tipo", "horario", "encargo", "motor",
                                                            "entrega", "texto_original")} for a in recs]
        W["auto_pintar"]()
        bombear(1)
        captura("1-ventana-con-recordatorio", top)
        # (d) apagar el vigía y forzar que «le toque»: no tiene que correr
        gb.auto_activar("vigia-cola", False)
        gb._cola("UPDATE automatizaciones SET proxima = ? WHERE id = 'vigia-cola'", (time.time() - 5,))
        n_antes = len(gb.auto_historial("vigia-cola"))
        gb.auto_tick()
        ev["d_vigia_apagado_runs_antes_despues"] = [n_antes, len(gb.auto_historial("vigia-cola"))]
        # (c) cuota contra logs: sin límite -> sin dato; con límite y un result de $8 -> aviso
        ev["c_cuota_sin_limite"] = gb._auto_cuota()
        (gb.RESULTS).mkdir(parents=True, exist_ok=True)
        (gb.RESULTS / "prueba-gasto.result.json").write_text(json.dumps({"cost_usd": 8.0}), encoding="utf-8")
        s = gb.load_settings()
        s["aviso_cuota_semanal_usd"] = 10
        gb.save_settings(s)
        cuota = [a for a in gb.auto_lista() if a["id"] == "cuota-max-75"][0]
        ev["c_cuota_con_limite_10"] = gb.auto_ejecutar(cuota)
        # límite anti-molestia: un segundo aviso proactivo el mismo día no sale
        ev["e_cuota_segunda_vez_mismo_dia"] = gb.auto_ejecutar(cuota)
        # (a) esperar a que el recordatorio corra a su hora (lo dispara el bucle real)
        t0 = time.time()
        while time.time() - t0 < 100 and any(a["tipo"] == "recordatorio" for a in gb.auto_lista()):
            bombear(2)
        ev["a_recordatorio_ejecutado_y_borrado"] = {
            "sigue_en_la_lista": any(a["tipo"] == "recordatorio" for a in gb.auto_lista()),
            "segundos_esperados": round(time.time() - t0, 1),
            "historial": [h for h in gb.auto_historial() if h["auto_id"].startswith("rec-")]}
        W["auto_pintar"]()
        bombear(1)
        captura("2-historial", top)
        ev["e_historial"] = gb.auto_historial(n=20)
        ev["toasts"] = toasts
        ev["llamadas_a_motores"] = motores["llamadas"]
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "automatizaciones:" in x][-15:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
        top.destroy()
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
