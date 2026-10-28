"""Prueba de la voz con ElevenLabs (ESTADO-VOZ-ELEVENLABS.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada). La
copia NO tiene clave de ElevenLabs: se comprueba que lo dice y no finge, que
sin aprobación no se genera nada ni se llama a ElevenLabs, y el aviso del 80 %
con un contador SIMULADO (marcado así). No gasta cuota.

  python pruebas/prueba_voz.py
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
OUT = REPO / "pruebas" / "evidencia" / "voz-elevenlabs"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-voz-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaVoz",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_voz", app / "growi-bridge.py")
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
        t = gb._VOZUI["top"]
        t.update()
        x, y = t.winfo_rootx(), t.winfo_rooty()
        ImageGrab.grab((x, y, x + t.winfo_width(), y + t.winfo_height()), all_screens=True).save(OUT / f"{nombre}.png")

    def pasos():
        r = gb._root
        r.deiconify()
        preguntas = []
        RESP = [False]
        gb.messagebox.askyesno = lambda t, m, **k: (preguntas.append(m), RESP[0])[1]
        carpeta = tmp / "proyecto-anuncio"
        # 1) SIN CLAVE (la copia no tiene ninguna): la ventana lo dice y no finge
        ev["proveedor_en_claves"] = gb.CRED_PROVIDERS["elevenlabs"]["label"]
        ev["sin_clave_estado"] = gb.voz_estado()
        cmd = next(c for c in gb._PALETTE_CMDS if c["id"] == "voz")
        cmd["fn"]()
        bombear(1.2)
        top = gb._VOZUI["top"]
        top.attributes("-topmost", True)
        ev["sin_clave_ventana"] = {"cuota": gb._VOZUI["cuota"].cget("text"),
                                   "boton_narrar": str(gb._VOZUI["narrar"].cget("state"))}
        captura_top("1-sin-clave")
        ev["sin_clave_narrar_aprobada"] = gb.voz_narrar("Hola, esto es una prueba.", "x", "x", "eleven_v4",
                                                        str(carpeta), aprobado=True)
        # 2) (c) sin aprobación no se genera nada (ni se llama a ElevenLabs)
        llamadas = []
        orig_open = gb._cred_open
        gb._cred_open = lambda req, timeout: (llamadas.append(req.full_url), orig_open(req, timeout))[1]
        ev["c_sin_aprobar"] = gb.voz_narrar("Hola, esto es una prueba.", "x", "x", "eleven_v4", str(carpeta),
                                            aprobado=False)
        ev["c_llamadas_a_elevenlabs"] = llamadas
        ev["c_archivos"] = sorted(p.name for p in carpeta.glob("*")) if carpeta.exists() else []
        gb._cred_open = orig_open
        # 3) (d) el aviso del 80 % con un contador SIMULADO (8.200 de 10.000) y el sí/no por la ventana
        sim = {"clave": True, "usados": 8200, "limite": 10000, "pct": 82.0, "error": None,
               "fuente": "SIMULADO en la prueba (no hay clave)"}
        sim["aviso"] = gb.voz_aviso(sim)
        gb.voz_estado = lambda: dict(sim)
        gb.voz_voces = lambda: ([("voz-es-1", "Lucía (simulada)", True), ("voz-en-1", "Adam (simulada)", False)], None)
        gb._voz_refrescar()
        gb._VOZUI["texto"].insert("1.0", "Bienvenidos al taller de Summit Maker. Hoy armamos un agente en una hora.")
        bombear(0.5)
        ev["d_aviso_80"] = {"umbral_pct": gb.VOZ_AVISO_PCT, "cuota": gb._VOZUI["cuota"].cget("text"),
                            "aviso": gb._VOZUI["aviso"].cget("text"), "nota_voz": gb._VOZUI["voz_nota"].cget("text")}
        RESP[0] = False
        gb._voz_narrar_ui()
        bombear(0.4)
        ev["c_por_la_ventana_dijo_no"] = {"pregunta": preguntas[-1] if preguntas else None,
                                          "mensaje": gb._VOZUI["msg"].cget("text"),
                                          "archivos": sorted(p.name for p in carpeta.glob("*")) if carpeta.exists() else []}
        gb._VOZUI["voz"].current(1)
        gb._voz_nota()
        bombear(0.3)
        ev["voz_no_espanola"] = gb._VOZUI["voz_nota"].cget("text")
        gb._VOZUI["voz"].current(0)
        gb._voz_nota()
        bombear(0.3)
        captura_top("2-aviso-80-simulado")
        top.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "voz:" in x][-6:]
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
