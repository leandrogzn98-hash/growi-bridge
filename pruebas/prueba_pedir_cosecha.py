"""Prueba de «Pedir cosecha» (ESTADO-PEDIR-COSECHA.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada):
abre el formulario desde la paleta, pide sin token (FALTA, nada enviado), con
token (estimación real antes de enviar), da el OK (primero «no», luego «sí»)
y simula la respuesta de la VM. No corre Apify ni gasta nada.

  python pruebas/prueba_pedir_cosecha.py
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
OUT = REPO / "pruebas" / "evidencia" / "pedir-cosecha"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-cosecha-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaCosecha",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_cosecha", app / "growi-bridge.py")
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

    def textos_lista():
        out = []
        for f in gb._COS["lista"].winfo_children():
            out.append(" | ".join(_textos(f)))
        return out

    def boton(texto):
        def busca(w):
            for ch in w.winfo_children():
                if "Button" in type(ch).__name__ and str(ch.cget("text")) == texto:
                    return ch
                r_ = busca(ch)
                if r_ is not None:
                    return r_
            return None
        return busca(gb._COS["lista"])

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        os.environ.pop("TIKTOK_MS_TOKEN", None)
        preguntas = []
        RESP = [True]
        gb.messagebox.askyesno = lambda t, m, **k: (preguntas.append(m), RESP[0])[1]
        k = gb._COS["kit"]
        # (a) desde la paleta: Tareas con el formulario abierto
        gb.cosecha_abrir()
        bombear(1.0)
        ev["a_pagina"] = W.get("pagina_actual")
        ev["a_formulario_abierto"] = bool(gb._COS["form"].winfo_manager())
        ev["a_textos_formulario"] = _textos(gb._COS["form"])
        ev["a_actor_visible_sin_detalle"] = "GdWCkxBtKWOsKjdch" in " ".join(_textos(gb._COS["form"]))
        captura("1-formulario")
        # (e) sin token: TikTok queda FALTA y no se envia nada
        ev["e_linea_token"] = gb._COS["token"].cget("text")
        gb._COS["tema"].insert(0, "#recetasfaciles")
        gb._COS["n"].delete(0, "end")
        gb._COS["n"].insert(0, "500")
        gb._cosecha_estimar_ui()
        ev["e_estimacion_sin_token"] = gb._COS["est"].cget("text")
        gb._cosecha_crear_ui()
        bombear(0.5)
        ev["e_mensaje"] = gb._COS["msg"].cget("text")
        ev["e_lista"] = textos_lista()
        ev["e_archivos_para_la_vm"] = sorted(x.name for x in gb.COSECHA_OUT.glob("*")) if gb.COSECHA_OUT.exists() else []
        captura("2-sin-token")
        # (b) con token (la VM dice que lo tiene) y gasto del mes según la VM
        gb.COSECHA_IN.mkdir(parents=True, exist_ok=True)
        (gb.COSECHA_IN / "estado-vm.json").write_text(json.dumps(
            {"tiktok_ms_token": True, "apify": {"plan": "FREE", "usado_mes_usd": 0.6},
             "actualizado": gb._now_iso(), "nota": "simulado en la prueba"}), encoding="utf-8")
        gb.cosecha_abrir()
        gb._COS["tema"].delete(0, "end")
        gb._COS["tema"].insert(0, "#recetasfaciles")
        gb._cosecha_estimar_ui()
        ev["b_estimacion"] = gb._COS["est"].cget("text")
        ev["b_estimacion_datos"] = gb.cosecha_estimar("tiktok", 500)
        gb._cosecha_detalle()
        bombear(0.3)
        ev["b_detalle_tecnico"] = gb._COS["detalle"].cget("text")
        captura("3-estimacion")
        gb._cosecha_crear_ui()
        bombear(0.5)
        ev["b_mensaje"] = gb._COS["msg"].cget("text")
        ev["b_nada_enviado_sin_ok"] = sorted(x.name for x in gb.COSECHA_OUT.glob("*")) if gb.COSECHA_OUT.exists() else []
        # (c) el OK explícito: «no» primero, luego «sí»
        RESP[0] = False
        boton("Dar el OK y enviar").invoke()
        bombear(0.3)
        ev["c_dijo_no"] = {"pregunta": preguntas[-1],
                           "archivos": sorted(x.name for x in gb.COSECHA_OUT.glob("*")) if gb.COSECHA_OUT.exists() else []}
        RESP[0] = True
        boton("Dar el OK y enviar").invoke()
        bombear(0.5)
        arch = sorted(gb.COSECHA_OUT.glob("*.json"))
        ev["c_archivo_para_la_vm"] = [x.name for x in arch]
        ev["c_contenido"] = json.loads(arch[-1].read_text(encoding="utf-8")) if arch else None
        ev["c_lista"] = textos_lista()
        captura("4-enviado")
        pid = ev["c_contenido"]["id"]
        # (d) la VM devuelve el resultado
        (gb.COSECHA_IN / f"{pid}.resultado.json").write_text(json.dumps(
            {"id": pid, "resultados": 487, "costo_usd": 1.80,
             "dataset": "https://api.apify.com/v2/datasets/(simulado)/items", "terminado": gb._now_iso()}),
            encoding="utf-8")
        gb._cosecha_refrescar()
        bombear(0.5)
        ev["d_lista"] = textos_lista()
        ev["d_gasto_mes"] = gb.cosecha_gasto_mes()
        captura("5-resultado")
        # (d) uno enviado hace 3 h sin respuesta
        lista = gb._cosecha_leer()
        lista.append({"id": "cosecha-viejo", "red": "tiktok", "tema": "@cuenta1", "resultados": 100, "brief": "C2",
                      "estado": "enviado", "estimacion": gb.cosecha_estimar("tiktok", 100),
                      "enviado_at": (gb.datetime.now().astimezone() - gb.timedelta(hours=3)).isoformat(timespec="seconds")})
        gb._cosecha_guardar(lista)
        gb._cosecha_refrescar()
        bombear(0.5)
        ev["d_sin_respuesta"] = [x for x in textos_lista() if "@cuenta1" in x]
        gb._scroll_a(gb._COS["lista"])
        bombear(0.4)
        captura("6-sin-respuesta")
        # Instagram: sin tarifa conocida no se inventa
        ev["instagram"] = gb.cosecha_estimacion_txt(gb.cosecha_estimar("instagram", 300), "instagram")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "cosecha:" in x][-10:]
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
