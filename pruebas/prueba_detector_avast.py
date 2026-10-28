"""Prueba de lo que faltaba del detector de Avast (ESTADO-DETECTOR-AVAST.md):
Tailscale atascado en «Starting…» y el registro de caidas consultable.

Copia aislada de growi-bridge.py. tailscale status y los servicios de Avast
son los REALES de este PC; el paso del tiempo en «Starting…» se simula (no
se puede atascar Tailscale a proposito sin cortar el tunel en uso). El
reinicio del servicio NO se ejecuta: se comprueba que pregunta y que con
«No» no toca nada.

  python pruebas/prueba_detector_avast.py
"""
import importlib.util, json, os, shutil, sys, tempfile, time, tkinter as tk
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-avast-"))
    (tmp / "app").mkdir()
    for f in ("growi-bridge.py", "engines.json"):
        shutil.copy2(REPO / f, tmp / "app" / f)
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "tok"))
    spec = importlib.util.spec_from_file_location("gb_av", tmp / "app" / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    gb._root = tk.Tk()
    gb._root.withdraw()
    gb.toast = lambda t, c=None: ev.setdefault("toasts", []).append(t)
    ev = {}
    ev["real_tailscale_backend"] = gb.tailscale_backend()
    ev["real_avast_servicios"] = gb.avast_servicios()
    t0 = time.time()
    ev["paso_1_starting_min0"] = gb._ts_vigia("Starting", t0)
    ev["paso_2_starting_min3"] = gb._ts_vigia("Starting", t0 + 180)
    ev["paso_3_starting_min6"] = gb._ts_vigia("Starting", t0 + 360)
    ev["paso_4_running"] = gb._ts_vigia("Running", t0 + 420)
    ev["tunel_caidas_log"] = gb._ipx_lineas(gb.TUNEL_LOG)
    top = gb.tunel_caidas_ui()
    txt = [w for w in top.winfo_children() if w.winfo_class() == "Text"][0].get("1.0", "end").strip()
    ev["ventana_caidas"] = {"titulo": top.title(), "texto": txt.splitlines()}
    pregunta = {}
    gb.messagebox.askyesno = lambda t, m, **k: (pregunta.update(titulo=t, texto=m), False)[1]
    llamado = {"n": 0}
    orig = gb._run_capture
    gb._run_capture = lambda *a, **k: (llamado.__setitem__("n", llamado["n"] + 1), orig(*a, **k))[1]
    gb.tailscale_reiniciar_ui()
    ev["reiniciar_dijo_no"] = {"pregunta": pregunta, "comandos_lanzados": llamado["n"]}
    ev["log"] = [x for x in gb.LOG_FILE.read_text(encoding="utf-8").splitlines() if "salida:" in x][-5:]
    (REPO / "pruebas" / "evidencia" / "detector-avast" / "evidencia.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str), flush=True)
    os._exit(0)



if __name__ == "__main__":
    main()
