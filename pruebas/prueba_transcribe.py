"""Prueba de la herramienta transcribe (ESTADO-TRANSCRIBE-WHISPER.md).

Copia aislada de growi-bridge.py (share, cola.db y memoria propios). Lo REAL:
la ficha medida en este PC (faster-whisper, ffmpeg y el modelo en la caché de
Hugging Face) y una tarea «Transcribe <video>» por el runner real. Como en
este PC no está faster-whisper (no se pudo instalar en la sesión), el
progreso, la cancelación y lo PARCIAL se prueban con un trabajador FALSO que
habla el mismo protocolo (marcado «simulado» en cada línea), sobre un audio
real de 60 s hecho con ffmpeg. No transcribe nada de verdad.

  python pruebas/prueba_transcribe.py
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "transcribe"

FALSO = r'''import json, subprocess, sys, time
archivo, salida, idioma, modelo, ffmpeg = sys.argv[1:6]
r = subprocess.run([ffmpeg, "-nostdin", "-v", "error", "-i", archivo, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                   capture_output=True, check=True)
dur = len(r.stdout) / 4 / 16000.0
print(json.dumps({"evento": "audio", "duracion": dur}), flush=True)
print(json.dumps({"evento": "idioma", "idioma": "es", "probabilidad": 0.99}), flush=True)
with open(salida, "w", encoding="utf-8") as f:
    t = 0.0
    while t < dur:
        f.write(f"[{int(t):02d}s] segmento simulado (no es una transcripción real)\n")
        f.flush()
        t = min(dur, t + 10)
        print(json.dumps({"evento": "progreso", "hasta": t, "duracion": dur}), flush=True)
        time.sleep(0.6)
print(json.dumps({"evento": "fin"}), flush=True)
'''


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-transcribe-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_trs", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    gb.toast = lambda *a, **k: None
    ev = {"copia": str(tmp)}
    # un audio REAL de 60 s (voz no: un tono; sirve para medir progreso y cortes)
    clip = work / "clip-prueba.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=60", "-q:a", "6", str(clip)], check=True)
    ev["audio"] = {"archivo": str(clip), "bytes": clip.stat().st_size}
    # (e) + (b) la ficha REAL de este PC
    f = gb.transcribe_ficha(fresca=True)
    ev["ficha_real"] = f
    # una tarea REAL por el runner: sin faster-whisper lo dice, no inventa
    t = {"id": "t-trs-real", "cwd": str(work), "revisar": False, "prompt": f"Transcribe {clip}"}
    tf = gb.TASKS / "t-trs-real.task.json"
    tf.write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
    gb._process_one_impl(tf)
    r = json.loads((gb.RESULTS / "t-trs-real.result.json").read_text(encoding="utf-8"))
    ev["tarea_real"] = {k: r.get(k) for k in ("status", "error", "motor", "cost_usd", "herramienta")}
    # (d) el protocolo con un trabajador FALSO: completa, y luego cancelada a mitad
    gb.TRANSCRIBE_WORKER = FALSO
    ficha_sim = dict(f, disponible=True, motivo=None, python=sys.executable, ffmpeg=shutil.which("ffmpeg"))
    tarea = {"id": "t-trs-sim", "cwd": str(work), "prompt": f"Transcribe {clip}"}
    pasos = []
    t0 = time.time()

    def mirar():
        while time.time() - t0 < 12:
            if gb.state.get("paso"):
                pasos.append((round(time.time() - t0, 1), gb.state["paso"]))
            time.sleep(0.5)
    th = threading.Thread(target=mirar, daemon=True)
    th.start()
    res = gb.transcribe_correr(tarea, {"archivo": str(clip), "idioma": "es"}, ficha=ficha_sim)
    final = clip.with_name("clip-prueba.transcripcion.txt")
    ev["d_completa_simulada"] = {"status": res["status"], "idioma_detectado": res.get("idioma_detectado"),
                                 "transcripcion": res.get("transcripcion"),
                                 "archivo": final.read_text(encoding="utf-8")[:400] if final.exists() else None,
                                 "progreso_visto": sorted(set(p for _t, p in pasos))[:8]}
    final.unlink(missing_ok=True)
    gb._RUN["stop"] = False
    threading.Timer(2.2, lambda: gb._RUN.update(stop=True)).start()
    res = gb.transcribe_correr(dict(tarea, id="t-trs-cancel"), {"archivo": str(clip), "idioma": "es"}, ficha=ficha_sim)
    gb._RUN["stop"] = False
    parcial = clip.with_name("clip-prueba.transcripcion.PARCIAL.txt")
    ev["d_cancelada_simulada"] = {"status": res["status"], "error": res.get("error"),
                                  "transcripcion": res.get("transcripcion"),
                                  "queda_tmp": clip.with_name("clip-prueba.transcripcion.tmp").exists(),
                                  "queda_completa": final.exists(),
                                  "parcial": parcial.read_text(encoding="utf-8")[:500] if parcial.exists() else None}
    # (a) desde la paleta: elegir el archivo -> tarea en la cola
    gb.filedialog.askopenfilename = lambda **k: str(clip)
    tid = gb.transcribe_ui()
    ev["paleta_tarea"] = json.loads((gb.TASKS / f"{tid}.task.json").read_text(encoding="utf-8")) if tid else None
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "transcrib" in x or "idioma" in x][-12:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
