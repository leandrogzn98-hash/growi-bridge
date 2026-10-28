"""Prueba del lote de la mascota (ESTADO-LOTE-MASCOTA-040.md): 4 estados,
6 reglas anti-molestia y memoria minima.

La app REAL (copia en %TEMP%, puerto 8797) con la mascota visible. Desde su
bucle de Tk: proxy caido de verdad (el proxy apunta a un puerto cerrado y el
mapa lo mide), una tarea real retenida esperando aprobacion, una tarea real
que falla (motor falso), y «sin internet» simulado en el mapa (no se puede
cortar internet del PC). Captura la mascota en cada estado. El reinicio se
prueba cargando otra vez el modulo sobre la misma carpeta.

  python pruebas/prueba_mascota.py
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
OUT = REPO / "pruebas" / "evidencia" / "mascota"
u32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass


def falso():
    print("fallo a proposito", file=sys.stderr)
    sys.exit(3)


def raton(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    u32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(0x0004, 0, 0, 0, 0)


def cargar(app, nombre):
    spec = importlib.util.spec_from_file_location(nombre, app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    return gb


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-mascota-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-mascota", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "siempre", "mascot": True, "auto_update": False,
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaMascota",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a", GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    gb = cargar(app, "gb_masc")
    OUT.mkdir(parents=True, exist_ok=True)
    ev = {"copia": str(tmp)}
    toasts, cajitas = [], []
    orig_toast = gb.toast
    gb.toast = lambda t, c=None: (toasts.append(t), orig_toast(t, c))
    gb.open_prompt_box = lambda *a, **k: cajitas.append(time.time())
    gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [sys.executable, str(Path(__file__).resolve()),
                                                                       "--falso"]
    gb._swap_args = lambda c, old, new: list(c)

    def bombear(s):
        fin = time.time() + s
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def cap(nombre):
        from PIL import ImageGrab
        w = gb._mascot["win"]
        w.lift()
        bombear(0.4)
        x, y = w.winfo_rootx(), w.winfo_rooty()
        ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def pasos():
        bombear(3)
        for r_ in ("proxy", "internet"):  # reposo limpio para la primera captura
            if r_ in gb._AV["rows"]:
                gb._AV["rows"][r_]["estado"] = "ok"
        gb._IPX["proxy_caido"] = None
        bombear(0.5)
        ev["reposo"] = gb.mascota_estado()
        cap("0-reposo")
        # proxy caido DE VERDAD: el proxy apunta a un puerto cerrado y el mapa lo mide
        real_px = gb.proxy_url
        gb.proxy_url = lambda: "http://127.0.0.1:9"
        gb.run_availability(only=["proxy"])
        gb._ipx_proxy_caido("prueba: el proxy no contesta")
        gb._ipx_proxy_caido("prueba: el proxy no contesta")  # misma caida otra vez
        bombear(1)
        ev["a_proxy_caido"] = {"estado": gb.mascota_estado(), "fila_proxy": gb._AV["rows"]["proxy"]["frase"],
                               "toasts_de_proxy": [t for t in toasts if "proxy" in t.lower()]}
        cap("1-proxy-caido")
        # regla 5: Descansar apaga los estados
        gb.mascota_descansar()
        ev["b5_descansar"] = gb.mascota_estado()
        gb._masc_mem_set(descansar_hasta=0)
        gb.proxy_url = real_px
        gb._AV["rows"]["proxy"]["estado"] = "ok"
        gb._IPX["proxy_caido"] = None
        # sin internet (simulado en el mapa)
        gb._AV["rows"]["internet"] = dict(gb._AV["rows"].get("internet") or {}, estado="falla")
        bombear(1)
        ev["a_sin_internet"] = {"estado": gb.mascota_estado(), "toasts_nuevos": toasts[-1:]}
        cap("2-sin-internet")
        gb._AV["rows"]["internet"]["estado"] = "ok"
        # esperando aprobacion: una tarea REAL retenida (permisos «siempre» + borrar)
        tf = gb.TASKS / "t-borrar.task.json"
        tf.write_text(json.dumps({"id": "t-borrar", "prompt": "Borra los archivos viejos de la carpeta de pruebas",
                                  "motor": "claude"}), encoding="utf-8")
        gb._process_one_impl(tf)
        gb._ESP["dato"] = gb.tareas_en_espera()  # lo que refresca su hilo cada pocos segundos
        bombear(1)
        ev["a_esperando"] = {"en_espera": list(gb._ESP["dato"]["ids"]), "estado": gb.mascota_estado()}
        cap("3-esperando")
        for f in gb.WAITING.glob("*.task.json"):
            f.unlink()
        gb._cola("UPDATE tareas SET estado='rechazada' WHERE id='t-borrar'")
        gb._ESP["dato"] = gb.tareas_en_espera()
        # tarea fallida REAL (motor falso que sale con error)
        gb.save_settings(dict(gb.load_settings(), guardrail="nunca"))
        tf = gb.TASKS / "t-falla.task.json"
        tf.write_text(json.dumps({"id": "t-falla", "prompt": "Haz algo pequeño", "motor": "claude",
                                  "revisar": False}), encoding="utf-8")
        gb._process_one_impl(tf)
        bombear(0.5)
        ev["a_fallo"] = {"estado_justo_despues": gb.mascota_estado()}
        cap("4-fallo")
        bombear(3)
        ev["b4_fallo_vuelve_al_reposo"] = gb.mascota_estado()
        ev["b1_mismo_fallo_otra_vez"] = gb.mascota_evento("fallo", "t-falla")
        # regla 2: clic = saludo, nunca la cajita (clic de verdad)
        w = gb._mascot["win"]
        raton(w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2)
        bombear(0.5)
        raton(w.winfo_rootx() + w.winfo_width() // 2, w.winfo_rooty() + w.winfo_height() // 2)
        bombear(0.5)
        ev["b2_c_clic"] = {"cajitas_abiertas": len(cajitas), "saludo_at": gb._MASC["saludo_at"] > 0}
        # regla 3 / memoria (a): no repetir
        ev["b3_decir_dos_veces"] = [gb.mascota_decir("¡Listo!"), gb.mascota_decir("¡Listo!"),
                                    gb.mascota_decir("¡Listo!", "Hecho."), gb.mascota_decir("¡Listo!", "Hecho.")]
        # memoria (b): solo la primera del dia
        ev["mem_b_primera_y_segunda"] = [gb.mascota_tarea_aprobada(), gb.mascota_tarea_aprobada()]
        # regla 6: el menu de la mascota no lleva botones de acciones del sistema
        import tkinter as tk
        menus = []
        orig_menu = tk.Menu.tk_popup
        tk.Menu.tk_popup = lambda self, *a, **k: menus.append([self.entrycget(i, "label") for i in
                                                               range(self.index("end") + 1)
                                                               if self.type(i) == "command"])
        gb._mascot_menu(type("E", (), {"x_root": 10, "y_root": 10})())
        tk.Menu.tk_popup = orig_menu
        ev["b6_menu"] = menus[0] if menus else None
        # validacion preparada
        gb.messagebox.askyesnocancel = lambda *a, **k: False
        gb.mascota_validacion_ui()
        ev["c_validacion_registro"] = (app / "mascota-validacion.jsonl").read_text(encoding="utf-8").strip()
        ev["toasts"] = toasts
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "mascota:" in x][-14:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        ev["memoria_en_disco"] = json.loads((app / "mascota-memoria.json").read_text(encoding="utf-8"))
        gb.quit_app()

    def _seguro():
        try:
            pasos()
        except Exception:
            import traceback
            ev["error_prueba"] = traceback.format_exc()
            gb.quit_app()
    orig = gb.build_gui

    def build():
        root = orig()
        root.after(2500, _seguro)
        return root
    gb.build_gui = build
    gb.maybe_onboarding = lambda: None
    gb.main()
    # memoria (d): «reinicio»: modulo nuevo sobre la misma carpeta, mismo dia
    gb2 = cargar(app, "gb_masc2")
    ev["mem_d_tras_reiniciar"] = {"celebra_otra_vez": gb2.mascota_tarea_aprobada(),
                                  "decir_lo_mismo": gb2.mascota_decir("¡Listo!")}
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os._exit(0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--falso":
        falso()
    else:
        main()
