"""Prueba de t-oficina-telefono-050 contra una instancia aislada con el runner real (motor ollama, $0):
clasificacion (c), creacion real con tiempos (b), retencion con guardrail «siempre» (d), cola de 1 (e),
fuera de la oficina (f). Nunca toca la app instalada."""
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

R = Path(__file__).resolve().parents[2]
src = R / "pruebas" / "prueba_motor_generico_052.py"
ld = importlib.machinery.SourceFileLoader("p052", str(src))
sp = importlib.util.spec_from_loader("p052", ld)
p052 = importlib.util.module_from_spec(sp)
ld.exec_module(p052)
p052.REPO = R  # el worktree de la rama Claude (el arbol principal puede estar en otra rama)
p052.BASE = p052.REAL / "_prueba-telefono-050"
p052.APP = p052.BASE / "app"
p052.preparar()
s = json.loads((p052.APP / "settings.json").read_text(encoding="utf-8"))
s["guardrail"] = "siempre"
(p052.APP / "settings.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
gb = p052.cargar()
gb.messagebox.showinfo = lambda *a, **k: None
gb.POLL_SECONDS = 1
gb.state["runner"] = "corriendo"
stop = threading.Event()
threading.Thread(target=gb.runner_loop, args=(stop,), daemon=True).start()

os.environ["GROWI_BRIDGE_APP_DIR"] = str(p052.APP)
sys.path.insert(0, str(R / "oficina" / "encolar"))
sys.path.insert(0, str(R / "oficina" / "telefono"))
import encolar  # noqa: E402
import telefono as T  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-telefono-050"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}

# (c, f) clasificacion por reglas
casos = {"¿cómo va la cola?": "pregunta", "Pídele a ollama: responde solo con la palabra hola": "tarea",
         "Corrige lo de Codex: el título va en mayúsculas": "correccion", "Sí, apruébalo": "aprobacion",
         "¿quién ganó el partido anoche?": "fuera", "¿qué hora es?": "fuera",
         "Resume el informe de ventas en 5 puntos": "tarea"}
OUT["c_clasificacion"] = {k: {"esperado": v, "obtenido": T.clasificar(k)[0]} for k, v in casos.items()}
OUT["c_ok"] = all(x["esperado"] == x["obtenido"] for x in OUT["c_clasificacion"].values())

tel = T.Telefono(encolar_mod=encolar, cola=lambda: json.loads(gb.COLA_LIVE_FILE.read_text(encoding="utf-8"))
                 if gb.COLA_LIVE_FILE.exists() else None)


def esperar_colgado(tope=60):
    t0 = time.time()
    while tel.estado != "colgado" and time.time() - t0 < tope:
        time.sleep(0.1)


# (b, d) una tarea que el guardrail «siempre» retiene (borrar) y su id en el telefono
n0 = len(tel.confirmaciones)
t0 = time.time()
tel.enviar("Pídele a ollama: borra el archivo viejo.txt de la carpeta de pruebas")
muestras = []
while tel.estado != "colgado" and time.time() - t0 < 40:
    muestras.append((round(time.time() - t0, 2), tel.estado, (tel.bocadillo or ("",))[0][:60]))
    time.sleep(0.2)
mudo = 0.0
ult_cambio = 0.0
prev = None
for t, e, b in muestras:  # el hueco mas largo sin nada visible nuevo mientras «lee»
    if b != prev:
        mudo = max(mudo, t - ult_cambio)
        ult_cambio, prev = t, b
OUT["d_retenida"] = {"confirmacion": tel.confirmaciones[n0:], "hitos": tel.hitos, "max_s_sin_nada_visible": round(mudo, 2),
                     "ok": len(tel.confirmaciones) - n0 == 1 and "por aprobar" in tel.confirmaciones[-1][1]}
OUT["b_task_json"] = {"hitos": tel.hitos,
                      "archivo": any(p.name.startswith(tel.confirmaciones[-1][1].split(" ")[-6]) for p in [])}

# (b) una tarea que entra en cola (ollama, sin palabras sensibles): guardrail «siempre» solo retiene lo delicado
n0 = len(tel.confirmaciones)
tel.enviar("Pídele a ollama: responde solo con la palabra hola")
esperar_colgado()
tid = next((w for w in tel.confirmaciones[-1][1].split() if w.startswith("t-")), None)
existe = tid and any((d / f"{tid}.task.json").exists() for d in (gb.TASKS, gb.PROCESSING, gb.DONE, gb.WAITING))
OUT["b_en_cola"] = {"confirmacion": tel.confirmaciones[n0:], "hitos": tel.hitos, "task_json_existe": bool(existe),
                    "ok": bool(existe) and len(tel.confirmaciones) - n0 == 1 and "aprobar" not in tel.confirmaciones[-1][1]}

# (e) tres mensajes seguidos: el 1.o se lee, el 2.o espera, el 3.o no cabe; una confirmacion por mensaje
n0 = len(tel.confirmaciones)
r1 = tel.enviar("¿cómo va la cola?")
r2 = tel.enviar("¿qué hora es?")
r3 = tel.enviar("¿hay algo esperando aprobación?")
esperar_colgado()
conf = tel.confirmaciones[n0:]
OUT["e_cola_de_uno"] = {"respuestas_enviar": [r1, r2, r3], "confirmaciones": conf,
                        "ok": [r1, r2] == ["leyendo", "en_espera"] and r3 == "lleno" and len(conf) == 2}
# (f) fuera de la oficina
n0 = len(tel.confirmaciones)
tel.enviar("¿quién ganó el partido anoche?")
esperar_colgado()
OUT["f_fuera"] = {"confirmacion": tel.confirmaciones[n0:], "ok": tel.confirmaciones[-1][1] == "Eso no es de la oficina."}
n0 = len(tel.confirmaciones)
tel.enviar("Sí, apruébalo")
esperar_colgado()
OUT["no_aprueba"] = {"confirmacion": tel.confirmaciones[n0:], "ok": "en la app" in tel.confirmaciones[-1][1]}
stop.set()
OUT["todo_ok"] = all(v.get("ok") for k, v in OUT.items() if isinstance(v, dict) and "ok" in v) and OUT["c_ok"]
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) else v) for k, v in OUT.items() if k != "c_clasificacion"},
                 ensure_ascii=False))
sys.stdout.flush()
os._exit(0)
