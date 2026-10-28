"""Prueba del panel de Estado del gateway (ESTADO-PANEL-ESTADO-GATEWAY.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada) y,
desde su propio bucle de Tk, mira la pestaña Estado: las secciones con datos
reales, una comprobación lenta («comprobando…» sin congelar), un servicio
caído (llama-server) y una fuente que no responde (la cola), el detalle
técnico plegable y las acciones (ver la tarea, ir a Modelos, reintentar).

  python pruebas/prueba_panel_estado.py
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
OUT = REPO / "pruebas" / "evidencia" / "panel-estado"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-panel-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaPanel",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_panel", app / "growi-bridge.py")
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

    EN_UPDATE = [None]

    def vigia():
        import collections
        import threading
        import traceback
        mt = threading.main_thread().ident
        cuenta = collections.Counter()
        ev["congelado_muestras"] = cuenta
        while True:
            time.sleep(0.5)
            t = EN_UPDATE[0]
            if t and time.perf_counter() - t > 2:
                fr = sys._current_frames().get(mt)
                pila = [x for x in traceback.extract_stack(fr) if "growi-bridge.py" in x.filename]
                cuenta[" < ".join(f"{x.name}:{x.lineno}" for x in pila[::-1][:4]) or "(solo Tcl)"] += 1

    def bombear(seg, medir=None):
        fin = time.time() + seg
        while time.time() < fin:
            t0 = time.perf_counter()
            EN_UPDATE[0] = t0
            gb._root.update()
            EN_UPDATE[0] = None
            if medir is not None:
                medir.append((time.perf_counter() - t0) * 1000)
            time.sleep(0.03)

    def filas():
        out = {}
        for key, (a, b, *_r) in gb._GW["rows"].items():
            try:
                out[key] = (a.cget("text") + ": " + b.cget("text")) if b is not None else "## " + a.cget("text")
            except Exception:
                pass
        return out

    def botones():
        out = {}
        body = W.get("gw_body")
        for ch in body.winfo_children() + [n for c in body.winfo_children() for n in c.winfo_children()]:
            if "Button" in type(ch).__name__:
                out.setdefault(str(ch.cget("text")), []).append(ch)
        return out

    def esperar(cond, seg=20):
        fin = time.time() + seg
        while time.time() < fin and not cond():
            bombear(0.2)
        return cond()

    def pasos():
        import threading
        threading.Thread(target=vigia, daemon=True).start()
        pre = []
        t_pre = time.time()
        bombear(5, pre)
        ev["reposo_antes_ms"] = {"max": round(max(pre), 1), "n": len(pre), "s": round(time.time() - t_pre, 1)}
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        # el runner parado: la tarea de prueba no se ejecuta (solo se mira)
        gb.stop_runner()
        tid = "t-panel-prueba"
        gb.TASKS.mkdir(parents=True, exist_ok=True)
        (gb.TASKS / f"{tid}.task.json").write_text(json.dumps(
            {"id": tid, "prompt": "Dime cómo ordenarías mis Descargas (prueba del panel)", "motor": "ollama"},
            ensure_ascii=False), encoding="utf-8")
        ahora = gb._now_iso()
        gb._cola("INSERT OR REPLACE INTO tareas (id, archivo, estado, creado_en, actualizado_en, actualizado_ts) "
                 "VALUES (?, ?, ?, ?, ?, ?)", (tid, f"{tid}.task.json", "esperando_aprobacion", ahora, ahora,
                                                time.time()))
        # un cambio de motor de verdad: una superficie con un modelo que no existe vuelve a Automatico
        s = gb.load_settings()
        s["modelo_superficie"] = {"chat": "motor:inexistente"}
        gb.save_settings(s)
        ev["cambio_superficie"] = gb.superficie_modelo("chat", avisar=False)
        # (d) una comprobacion lenta: llama tarda 4 s en contestar
        orig_es = gb.engine_status

        import threading

        def lento(mid, *a, **k):
            if mid == "llama" and threading.current_thread() is not threading.main_thread():
                time.sleep(4)
            return orig_es(mid, *a, **k)
        gb.engine_status = lento
        W["show_page"]("estado")
        esperar(lambda: gb._GW["estado"] in ("contenido", "vacio"), 30)
        reposo = []
        bombear(2.0, reposo)
        ev["d_reposo_antes_ms"] = [round(x) for x in reposo]
        gb._GW_ESTADO_CACHE["motores"] = None
        tiempos = []
        t0 = time.time()
        gb._gw_reintentar()
        bombear(1.0, tiempos)
        esperar(lambda: "mot_comp" in gb._GW["rows"], 8)
        n_antes_scroll = len(tiempos)
        gb._scroll_a(W["gw_body"])
        bombear(0.3, tiempos)
        ev["d_muestras_ms"] = {"antes_de_desplazar": [round(x) for x in tiempos[:n_antes_scroll]],
                               "despues": [round(x) for x in tiempos[n_antes_scroll:]]}
        f = filas()
        ev["d_mientras_comprueba"] = {"s_desde_reintentar": round(time.time() - t0, 1),
                                      "motores": f.get("mot_comp"), "cola": f.get("cola_n"),
                                      "skills": f.get("sk"), "canales": f.get("can_chat")}
        captura("1-comprobando-motores")
        ok = esperar(lambda: "mot_comp" not in gb._GW["rows"] and any(k.startswith("m_") for k in gb._GW["rows"]), 15)
        bombear(0.5, tiempos)
        ev["d_motores_llegan"] = {"llegaron": ok, "s": round(time.time() - t0, 1)}
        ev["d_ventana_sin_congelar_ms"] = {"max": round(max(tiempos), 1), "n": len(tiempos),
                                           "p95": round(sorted(tiempos)[int(len(tiempos) * 0.95)], 1)}
        gb.engine_status = orig_es
        # (a) las secciones con datos reales
        f = filas()
        ev["a_secciones"] = [v for k, v in f.items() if v.startswith("## ")]
        ev["a_filas"] = f
        vista = " ".join(f.values())
        ev["a_sin_puertos_en_vista"] = {"127.0.0.1": "127.0.0.1" in vista, "8797": "8797" in vista,
                                        "token": "Bearer" in vista}
        gb._scroll_a(W["gw_body"])
        bombear(0.4)
        captura("2-panel-secciones")
        # (b) servicio caido: llama-server no esta corriendo en 127.0.0.1:8080
        ev["b_llama"] = f.get("m_llama")
        ev["b_boton_comprobar"] = "Comprobar" in botones()
        # (b) fuente que no responde: la cola
        orig_cr = gb.cola_resumen

        def cola_rota():
            raise gb.sqlite3.OperationalError("database is locked (simulado en la prueba)")
        gb.cola_resumen = cola_rota
        gb._gw_reintentar()
        esperar(lambda: "cola_err" in gb._GW["rows"], 10)
        ev["b_cola_sin_datos"] = filas().get("cola_err")
        ev["b_cola_reintentar"] = "Reintentar" in botones()
        gb._scroll_a(gb._GW["rows"]["cola_err"][0])
        bombear(0.4)
        captura("3-cola-sin-datos")
        gb.cola_resumen = orig_cr
        botones()["Reintentar"][0].invoke()
        ev["c_reintentar_vuelve"] = esperar(lambda: "cola_n" in gb._GW["rows"], 10)
        # detalle tecnico plegable
        botones()["Mostrar"][0].invoke()
        bombear(0.4)
        f = filas()
        ev["detalle_abierto"] = {k: v for k, v in f.items() if k.startswith("gw_")}
        gb._scroll_a(W["gw_body"])
        bombear(0.3)
        captura("4-detalle-tecnico")
        botones()["Ocultar"][0].invoke()
        bombear(0.3)
        ev["detalle_cerrado"] = "gw_port" not in gb._GW["rows"]
        # (c) acciones
        esperar(lambda: "Ver la tarea" in botones(), 8)
        botones()["Ver la tarea"][0].invoke()
        bombear(1.0)
        tree = W["tasks_tree"]
        ev["c_ver_tarea"] = {"pagina": W.get("pagina_actual"), "seleccion": list(tree.selection()),
                             "detalle": W["tasks_detail"].cget("text")[:200]}
        captura("5-ver-la-tarea")
        W["show_page"]("estado")
        bombear(0.5)
        botones()["Ir a Modelos"][0].invoke()
        bombear(0.8)
        ev["c_ir_a_modelos"] = W.get("pagina_actual")
        W["show_page"]("estado")
        bombear(0.5)
        t_antes = gb._GW_ESTADO_CACHE["t"]
        botones()["Comprobar"][0].invoke()
        esperar(lambda: gb._GW_ESTADO_CACHE["t"] > t_antes and "mot_comp" not in gb._GW["rows"], 15)
        ev["c_comprobar_de_nuevo"] = {"releido": gb._GW_ESTADO_CACHE["t"] > t_antes,
                                      "llama": filas().get("m_llama")}
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "gateway:" in x or "motores:" in x or "superficies:" in x][-12:]
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


if __name__ == "__main__":
    main()
