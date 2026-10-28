"""Prueba de la rúbrica, el doble juez y la calibración del revisor (ESTADO-RUBRICA-REVISOR.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada) y
corre tareas por el runner real (_process_one_impl). El EJECUTOR es falso
(escribe notas.txt). Los jueces: el de (a) es REAL (la cadena del revisor:
llama-server no está -> Ollama local, $0); los «claude» de (b) y (c) son
falsos (este archivo con --juez <modelo>): «roto» devuelve un JSON que no
cumple el esquema, «hermes-simulado» aprueba y «haiku» rechaza. No gasta.

  python pruebas/prueba_rubrica_revisor.py
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
OUT = REPO / "pruebas" / "evidencia" / "rubrica-revisor"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-rubrica-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaRubrica",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_rubrica", app / "growi-bridge.py")
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

    def bombear(seg):
        fin = time.time() + seg
        while time.time() < fin:
            gb._root.update()
            time.sleep(0.03)

    def captura_top(nombre):
        from PIL import ImageGrab
        t = gb._REVUI["top"]
        t.update()
        x, y = t.winfo_rootx(), t.winfo_rooty()
        ImageGrab.grab((x, y, x + t.winfo_width(), y + t.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def pasos():
        r = gb._root
        r.deiconify()
        gb.stop_runner()  # las tareas de la prueba se corren aquí, una a una
        work = tmp / "trabajo"
        work.mkdir(exist_ok=True)
        s = gb.load_settings()
        s["guardrail"] = "nunca"
        gb.save_settings(s)
        gb.save_folders([str(work)])

        def ejecutor(task):  # el EJECUTOR es falso: escribe lo que el encargo pide (sin red)
            res = gb._base_result(task, task["motor"])
            if "notas.txt" in task["prompt"]:
                (work / "notas.txt").write_text("Soleado por la mañana.\nNublado a mediodía.\nLluvia de noche.\n",
                                                encoding="utf-8")
            res.update(status="ok", finished_at=gb._now_iso(), duration_s=0.1, cost_usd=0.0,
                       result="Hecho [ejecutor simulado]: escribí notas.txt con tres líneas.")
            return res
        gb._run_task_motor = ejecutor
        # los jueces «claude» son falsos (este mismo archivo con --juez <modelo>); Ollama es REAL
        gb._build_cli_cmd = lambda task, mid, eng, prompt, abilities=True: [
            sys.executable, str(Path(__file__).resolve()), "--juez", str(task.get("modelo") or ""), prompt]
        gb._swap_args = lambda c, old, new: list(c)
        orig_rev = gb._rev_cfg

        def correr(tid, prompt, orden=None, **extra):
            gb._rev_cfg = (lambda: dict(orig_rev(), orden=orden)) if orden else orig_rev
            t = {"id": tid, "cwd": str(work), "motor": "claude", "prompt": prompt}
            t.update(extra)
            f = gb.TASKS / f"{tid}.task.json"
            f.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
            gb._process_one_impl(f)
            gb._rev_cfg = orig_rev
            fam = gb.load_family(tid) or {}
            rv_f = gb.RESULTS / f"{tid}.revision.json"
            rv = json.loads(rv_f.read_text(encoding="utf-8")) if rv_f.exists() else {}
            return fam, rv

        # (a) + (d) revisión REAL con la cadena (llama no está -> Ollama local, $0)
        fam, rv = correr("t-rub-real", "Escribe en notas.txt tres líneas sobre el clima de hoy.",
                         criterios=["notas.txt tiene tres líneas sobre el clima"])
        prompt_juez = gb._RUN.get("rev_prompt") or ""
        i = prompt_juez.find("LA OBRA")
        ev["a_real"] = {"estado": fam.get("estado"), "veredicto": rv.get("veredicto"),
                        "veredictos": [{k: v.get(k) for k in ("motor", "modelo", "estado", "aprobado", "puntuacion",
                                                              "que_falta_items", "costo_usd", "segundos", "tokens")}
                                       for v in rv.get("veredictos") or []],
                        "cadena_revisor": rv.get("cadena_revisor")}
        ev["d_el_juez_ve_la_obra"] = prompt_juez[i:i + 600] if i >= 0 else None
        ev["a_rubrica_en_el_prompt"] = prompt_juez[prompt_juez.find("RÚBRICA"):prompt_juez.find("RÚBRICA") + 500]
        # (b) un juez que devuelve un JSON que no cumple el esquema -> «sin revisión», nunca aprobado
        fam, rv = correr("t-rub-roto", "Escribe en notas.txt tres líneas sobre el clima de hoy.",
                         orden=[{"motor": "claude", "modelo": "roto"}],
                         criterios=["notas.txt tiene tres líneas sobre el clima"])
        ev["b_json_roto"] = {"estado": fam.get("estado"), "decision": rv.get("decision"), "veredicto": rv.get("veredicto"),
                             "aprobado": rv.get("aprobado"), "error": str(rv.get("error") or "")[:300]}
        # (c) tarea R2 (enviar un correo), el primer juez aprueba, un check falla -> Haiku -> no coinciden
        fam, rv = correr("t-rub-r2", "Envía un correo a ana@ejemplo.com con el resumen y escribe notas.txt con tres "
                                     "líneas.", orden=[{"motor": "claude", "modelo": "hermes-simulado"}],
                         criterios=[{"tipo": "existe", "archivo": "informe.txt"},
                                    "notas.txt tiene tres líneas"])
        ev["c_r2_desacuerdo"] = {"estado": fam.get("estado"), "decision": rv.get("decision"), "nivel": rv.get("nivel"),
                                 "veredicto": rv.get("veredicto"), "motivo": rv.get("motivo_decision"),
                                 "segundo_juez": rv.get("segundo_juez"),
                                 "veredictos": [{k: v.get(k) for k in ("rol", "motor", "modelo", "aprobado")}
                                                for v in rv.get("veredictos") or []]}
        # R0: nunca Haiku
        fam, rv = correr("t-rub-r0", "Escribe en notas.txt tres líneas sobre el clima de hoy.",
                         orden=[{"motor": "claude", "modelo": "hermes-simulado"}],
                         criterios=[{"tipo": "existe", "archivo": "informe.txt"},
                                    "notas.txt tiene tres líneas"])
        ev["c_r0_sin_haiku"] = {"nivel": rv.get("nivel"), "segundo_juez": rv.get("segundo_juez")}
        # (e) calibración: corrijo la revisión real (yo la rechazo)
        ev["e_etiqueta"] = gb.calib_etiquetar("t-rub-real", "rechazado", "prueba: el clima no es de hoy")
        res = gb.calib_resumen(escribir=True)
        ev["e_calibracion"] = {"casos": res["casos"], "total": res["total"], "propuesta": gb.calib_propuesta(res)}
        # (f) costo medido por juez
        ev["f_costos"] = {f"{k[0]}:{k[1]}": v for k, v in gb.revisor_costos().items()}
        cmd = next(c for c in gb._PALETTE_CMDS if c["id"] == "revisor")
        cmd["fn"]()
        bombear(1.5)
        top = gb._REVUI["top"]
        top.attributes("-topmost", True)
        ev["vista"] = {"calib": gb._REVUI["calib"].cget("text"), "propuesta": gb._REVUI["prop"].cget("text"),
                       "costos": [w.cget("text") for w in gb._REVUI["costos"].winfo_children()]}
        captura_top("1-revisor")
        top.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "revisión" in x or "segundo juez" in x or "calibración" in x][-14:]
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
    gb.main()
    print(json.dumps(ev, ensure_ascii=False, indent=1))
    os._exit(0)


def juez():
    """Un juez «claude» falso: contesta como el CLI (stream-json) sin costo."""
    modelo = sys.argv[2] if len(sys.argv) > 2 else ""
    if modelo == "roto":
        txt = '{"aprobado": "quizás", "puntuacion": {"completitud": 9}}'
    elif modelo == "haiku":
        txt = json.dumps({"puntuacion": {"completitud": 2, "correccion": 3, "no_regresion": 4, "evidencia": 2},
                          "aprobado": "no", "que_falta": [{"falta": "no existe informe.txt",
                                                            "arreglo": "crear informe.txt con el resumen del correo"}],
                          "evidencia": ["informe.txt no existe"]}, ensure_ascii=False)
    else:
        txt = json.dumps({"puntuacion": {"completitud": 5, "correccion": 5, "no_regresion": 5, "evidencia": 5},
                          "aprobado": "si", "que_falta": [], "evidencia": ["notas.txt"]}, ensure_ascii=False)
    for e in ({"type": "system", "subtype": "init", "session_id": "j", "model": modelo or "falso"},
              {"type": "result", "subtype": "success", "is_error": False, "result": txt, "num_turns": 1,
               "session_id": "j"}):
        print(json.dumps(e, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--juez":
        juez()
    else:
        main()
