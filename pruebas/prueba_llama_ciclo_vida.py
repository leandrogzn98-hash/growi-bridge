"""Prueba del ciclo de vida del servidor local (t-llama-ciclo-vida-048, ESTADO-LLAMA-CICLO-VIDA-048.md).

Tres partes, cada una con su evidencia en pruebas/evidencia/llama-ciclo-vida/:

  auditoria   grep: quien lanza llama-server y que todo pasa por ensure_llama_server().
  demanda     copia aislada de growi-bridge.py (share, cola y memoria propios) con el llama-server.exe REAL de la
              app instalada (solo se lee) en el puerto 8097, en modo router como el descriptor, pero con un GGUF
              diminuto (Qwen3-0.6B-Q8_0, ~0,7 GB) en vez de Hermes 3 8B (~5,2 GB): el PC está en uso y con poca
              RAM libre. Con el servidor parado, una petición por la ruta real de las tareas (_run_http_engine) lo
              arranca; una petición larga dura más que la inactividad y no se corta; al acabar, tras
              GROWI_LLAMA_INACTIVIDAD_MIN (0,25 = 15 s) el proceso desaparece y la RAM vuelve; otra petición lo
              vuelve a arrancar.
  app         la app REAL oculta (arnes_oculto: ninguna ventana se muestra ni roba el foco) con el bloque
              'servidor' puesto (puerto 8098): abrirla no crea ningún llama-server.exe.

  python pruebas/prueba_llama_ciclo_vida.py [auditoria|demanda|app]   (sin argumento: las tres)
"""

import csv
import ctypes
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "llama-ciclo-vida"
INSTALADA = Path(os.environ.get("GROWI_APP_INSTALADA", r"C:\Users\forte\growi-bridge"))
EXE = INSTALADA / "llama" / "llama-server.exe"
GGUF_PEQUENO = Path(os.environ.get("GROWI_GGUF_PRUEBA", str(INSTALADA / "_prueba-semaforo" / "gguf" /
                                                             "Qwen3-0.6B-Q8_0.gguf")))
MODELO = GGUF_PEQUENO.stem
INACTIVIDAD_MIN = "0.25"
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _guardar(nombre, ev):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{nombre}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def ram_libre_mb():
    class M(ctypes.Structure):
        _fields_ = [("l", ctypes.c_ulong), ("carga", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("libre", ctypes.c_ulonglong)] + [(f"x{i}", ctypes.c_ulonglong) for i in range(5)]
    m = M()
    m.l = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return round(m.libre / 2 ** 20)


def procesos_llama():
    """[(pid, MB)] de los llama-server.exe cuyo exe es el de la app instalada (no el de Ollama)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process llama-server -ErrorAction SilentlyContinue | "
                        "Select-Object Id,Path,WorkingSet64 | ConvertTo-Csv -NoTypeInformation"],
                       capture_output=True, text=True, timeout=60, creationflags=OCULTO)
    out = []
    for f in csv.DictReader(io.StringIO(r.stdout)):
        if os.path.normcase(f.get("Path") or "") == os.path.normcase(str(EXE)):
            out.append((int(f["Id"]), round(int(f["WorkingSet64"]) / 2 ** 20)))
    return out


# ------------------------------------------------------------------ auditoria

def auditoria():
    """Cada sitio del repo que arranca llama-server (Popen con su exe o las funciones que lo hacen) y por dónde
    pasa ahora."""
    src = (REPO / "growi-bridge.py").read_text(encoding="utf-8")
    lineas = src.splitlines()
    funcs = [(i + 1, m.group(1)) for i, ln in enumerate(lineas) if (m := re.match(r"def (\w+)\(", ln))]

    def func_de(n):
        f = None
        for ln, nombre in funcs:
            if ln > n:
                break
            f = nombre
        return f
    popen = [(i + 1, func_de(i + 1), ln.strip()) for i, ln in enumerate(lineas) if "subprocess.Popen(" in ln]
    llamadas = [(i + 1, func_de(i + 1), ln.strip()) for i, ln in enumerate(lineas)
                if re.search(r"\bensure_llama_server\(", ln) and not ln.lstrip().startswith("def ")]
    internas = [(i + 1, func_de(i + 1)) for i, ln in enumerate(lineas)
                if re.search(r"\b_ensure_llama_server_arrancar\(", ln) and not ln.lstrip().startswith("def ")]
    viejas = [i + 1 for i, ln in enumerate(lineas) if re.search(r"\b_llama_(ensure|arrancar)\(", ln)]
    # El Popen del servidor es el que usa el exe del descriptor (args = [str(exe)] + args del descriptor).
    i0 = next(n for n, f in funcs if f == "_ensure_llama_server_arrancar")
    i1 = next(n for n, f in funcs if n > i0)
    popen_srv = [p for p in popen if i0 <= p[0] < i1]
    otros_py = []
    for f in sorted(REPO.rglob("*")):
        if f.suffix.lower() not in (".py", ".bat", ".ps1", ".cmd", ".vbs", ".sh") or f.name == "growi-bridge.py":
            continue
        if any(p in f.parts for p in (".git", "__pycache__", ".venv", "_corridas", "evidencia")):
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"llama-server(\.exe)?", txt, re.I) and re.search(r"Popen|Start-Process|start ", txt):
            otros_py.append(str(f.relative_to(REPO)))
    ev = {"popen_del_servidor": popen_srv, "llamadas_a_ensure_llama_server": llamadas,
          "quien_llama_al_lanzador_interno": internas, "nombres_viejos_que_quedan": viejas,
          "otros_archivos_que_lanzan_llama_server": otros_py}
    ev["ok"] = (len(popen_srv) == 1 and [f for _n, f in internas] == ["ensure_llama_server"] and not viejas)
    _guardar("auditoria", ev)
    print(json.dumps(ev, ensure_ascii=True, indent=1))
    return ev["ok"]


# ------------------------------------------------------------------ demanda

def _engines_de_prueba(origen, tmp, puerto):
    """engines.json con el motor 'llama' apuntando al exe instalado (solo lectura), a un models\\ de la prueba
    con el GGUF pequeño y a otro puerto. El resto del descriptor (modo router, flags) se queda como está."""
    e = json.loads(origen.read_text(encoding="utf-8"))
    m = e["motores"]["llama"]
    txt = json.dumps(m, ensure_ascii=False).replace("127.0.0.1:8080", f"127.0.0.1:{puerto}")
    m = json.loads(txt)
    s = m["servidor"]
    a = s["args"]
    a[a.index("--models-dir") + 1] = str(tmp / "models")
    a[a.index("--models-preset") + 1] = str(tmp / "models-preset.ini")
    a[a.index("--port") + 1] = str(puerto)
    s.update(exe=str(EXE), gguf=str(tmp / "models" / GGUF_PEQUENO.name), models_dir=str(tmp / "models"),
             preset=str(tmp / "models-preset.ini"), log=str(tmp / "llama-server.log"))
    m["modelo"]["por_defecto"] = MODELO
    e["motores"]["llama"] = m
    return e


def _sembrar_modelo(tmp):
    (tmp / "models").mkdir(parents=True, exist_ok=True)
    dst = tmp / "models" / GGUF_PEQUENO.name
    try:
        os.link(GGUF_PEQUENO, dst)  # enlace duro: sin copiar 640 MB; el original no se toca
    except OSError:
        shutil.copy2(GGUF_PEQUENO, dst)
    (tmp / "models-preset.ini").write_text(
        "version = 1\n\n[*]\nn-gpu-layers = 99\nparallel = 1\n\n"
        f"[{MODELO}]\n; modelo diminuto solo para la prueba del ciclo de vida\nctx-size = 4096\nparallel = 1\n"
        "n-gpu-layers = 99\n", encoding="utf-8")


def demanda():
    ev = {"modelo_prueba": MODELO, "exe": str(EXE), "inactividad_min": float(INACTIVIDAD_MIN), "pasos": []}
    if not EXE.is_file() or not GGUF_PEQUENO.is_file():
        ev["error"] = f"falta {EXE if not EXE.is_file() else GGUF_PEQUENO}"
        _guardar("demanda", ev)
        print(ev["error"])
        return False
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-llama-vida-"))
    app = tmp / "app"
    app.mkdir()
    for f in ("growi-bridge.py", "riesgos.json", "models-catalog.json"):
        shutil.copy2(REPO / f, app / f)
    puerto = 8097
    (app / "engines.json").write_text(json.dumps(_engines_de_prueba(REPO / "engines.json", tmp, puerto),
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    _sembrar_modelo(tmp)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "guardrail": "nunca", "onboarding_done": True}),
                                       encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(tmp)]}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_LANE_A_DIR=str(tmp / "no-existe"), GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"),
                      GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"), GROWI_LLAMA_INACTIVIDAD_MIN=INACTIVIDAD_MIN)
    spec = importlib.util.spec_from_file_location("gb_llama_vida", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    gb.MODELS_DIR = tmp / "models"
    eng = gb.get_engine("llama")
    ev["copia"] = str(tmp)
    ev["config"] = {k: str(v) for k, v in gb.llama_cfg(eng).items()}

    def paso(que, **datos):
        datos.update(que=que, t=round(time.time() - t0, 1), ram_libre_mb=ram_libre_mb(), llama=procesos_llama())
        ev["pasos"].append(datos)
        print(json.dumps(datos, ensure_ascii=True), flush=True)
        return datos

    t0 = time.time()
    ok = True
    try:
        antes = paso("antes: servidor parado", health=gb._health(eng)[0])
        ok &= not antes["health"] and not antes["llama"]

        # (b) Una tarea normal al modelo local, por la ruta real (_run_http_engine), con el servidor parado.
        task = {"id": "prueba-llama-vida", "cwd": str(tmp), "timeout_min": 5, "modelo": None, "session_id": None,
                "prompt": "", "allowed_tools": None, "permission_mode": None}
        r = gb._base_result(task, "llama")
        t1 = time.time()
        gb._run_http_engine(task, "llama", eng, r, "/no_think Responde solo con la palabra: hola")
        b = paso("(b) primera petición con el servidor parado", segundos=round(time.time() - t1, 1),
                 respuesta=(r.get("result") or "")[:200], error=r.get("error"), carga=r.get("modelo_local_carga"),
                 avisos=r.get("avisos"))
        ok &= bool(b["llama"]) and not r.get("error") and bool((r.get("result") or "").strip())
        ram_cargado = b["ram_libre_mb"]

        # Petición larga (más que la inactividad): no se corta.
        url = gb._url_join(gb._srv_cfg(eng)["base"], "/v1/chat/completions")
        larga = {}

        def pedir():
            t = time.time()
            try:
                d = gb._http_local("POST", url, {"model": MODELO, "messages": [
                    {"role": "user", "content": "/no_think Cuenta del 1 al 3000, separados por comas."}],
                    "max_tokens": 3500, "ignore_eos": True, "stream": False}, timeout=300)
                larga.update(ok=True, tokens=(d.get("usage") or {}).get("completion_tokens"))
            except Exception as e:  # noqa: BLE001
                larga.update(ok=False, error=f"{type(e).__name__}: {e}")
            larga.update(segundos=round(time.time() - t, 1), fin=time.time())
        h = threading.Thread(target=pedir)
        h.start()
        vivos_durante = []
        while h.is_alive():
            vivos_durante.append(bool(procesos_llama()))
            time.sleep(3)
        lim_s = float(INACTIVIDAD_MIN) * 60
        c1 = paso("(c1) petición larga terminada", **larga, limite_inactividad_s=lim_s,
                  servidor_vivo_en_todo_momento=all(vivos_durante))
        ok &= larga.get("ok") and all(vivos_durante) and larga.get("segundos", 0) > lim_s
        ev["aviso_c1"] = "" if larga.get("segundos", 0) > lim_s else "la petición duró menos que la inactividad"

        # (c) Sin peticiones: se apaga solo tras la inactividad y la RAM vuelve.
        fin_peticion = larga["fin"]
        while procesos_llama() and time.time() - fin_peticion < lim_s + 90:
            time.sleep(1)
        apagado_tras = round(time.time() - fin_peticion, 1)
        time.sleep(2)
        c = paso("(c) tras la inactividad", apagado_tras_s=apagado_tras, health=gb._health(eng)[0],
                 apagado=gb.state.get("llama_autostop"))
        ok &= not c["llama"] and not c["health"] and apagado_tras >= lim_s
        ev["ram_liberada_mb"] = c["ram_libre_mb"] - ram_cargado

        # Rearranque: la siguiente petición lo levanta otra vez.
        r2 = gb._base_result(task, "llama")
        t2 = time.time()
        gb._run_http_engine(task, "llama", eng, r2, "/no_think Responde solo con la palabra: adios")
        d = paso("rearranque con otra petición", segundos=round(time.time() - t2, 1),
                 respuesta=(r2.get("result") or "")[:200], error=r2.get("error"))
        ok &= bool(d["llama"]) and not r2.get("error")
    except Exception as e:  # noqa: BLE001
        import traceback
        ev["error_prueba"] = traceback.format_exc()
        print(ev["error_prueba"])
        ok = False
    finally:
        fin = gb.srv_parar(eng, "fin de la prueba")
        paso("limpieza", parar=fin)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace") \
            if (app / "growi-bridge.log").is_file() else ""
        ev["log_motores"] = [ln for ln in log.splitlines() if "motores:" in ln][-40:]
        ev["ok"] = bool(ok)
        _guardar("demanda", ev)
    return bool(ok)


# ------------------------------------------------------------------ app

def app():
    """Abre la app REAL oculta (subproceso con el arnés) con el bloque 'servidor' puesto y cuenta los
    llama-server.exe antes, durante y después."""
    antes = procesos_llama()
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_app_oculta"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=600, creationflags=OCULTO)
    despues = procesos_llama()
    ev = {"antes": antes, "despues": despues, "salida": r.stdout[-3000:], "error": r.stderr[-2000:]}
    try:
        dentro = json.loads((OUT / "app-dentro.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        dentro = {}
    ev["dentro"] = dentro
    ev["ok"] = (not antes and not despues and dentro.get("llama_durante") == [] and dentro.get("app_abierta")
                and not dentro.get("puerto_escuchando") and not dentro.get("error_prueba"))
    _guardar("app", ev)
    print(json.dumps({k: ev[k] for k in ("antes", "despues", "ok")}, ensure_ascii=True))
    print(json.dumps(dentro, ensure_ascii=True, indent=1)[:2500])
    return ev["ok"]


def _app_oculta():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from arnes_oculto import correr

    def preparar(app_dir, tmp):
        (app_dir / "engines.json").write_text(json.dumps(_engines_de_prueba(REPO / "engines.json", tmp, 8098),
                                                         ensure_ascii=False, indent=1), encoding="utf-8")
        _sembrar_modelo(tmp)

    def pasos(h):
        gb = h.gb
        visto = []
        for _ in range(8):  # ~20 s con la app abierta: arranque, runner, panel de estado
            h.bombear(2.5)
            visto += procesos_llama()
        eng = gb.get_engine("llama")
        h.ev.update(app_abierta=True, llama_durante=visto, servidor_en_engines=bool(eng.get("servidor")),
                    puerto_escuchando=gb._health(eng)[0], procesos=gb.srv_procesos(eng),
                    log_motores=[ln for ln in h.log().splitlines() if "motores:" in ln][-20:])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "app-dentro.json").write_text(json.dumps(h.ev, ensure_ascii=False, indent=1, default=str),
                                             encoding="utf-8")
    correr("llama-ciclo-vida", pasos, puerto=8796, espera_ms=3000, preparar=preparar)


if __name__ == "__main__":
    que = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if que == "_app_oculta":
        _app_oculta()
    else:
        res = {}
        for nombre, f in (("auditoria", auditoria), ("app", app), ("demanda", demanda)):
            if que in ("todo", nombre):
                res[nombre] = f()
        print("RESULTADO", json.dumps(res))
        sys.exit(0 if all(res.values()) else 1)
