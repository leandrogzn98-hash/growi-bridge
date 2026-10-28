"""Prueba del banner de la nube fiel al runner (ESTADO-ESTADO-BANNER-NUBE.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8797). Pone la última ejecución del runner (en memoria; el
latido la escribe en runner-status.json, que es lo que lee el probe) y los
fallos del sondeo, y deja que la ventana se repinte SOLA (cada ~5 s).

  python pruebas/prueba_banner_nube.py
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
OUT = REPO / "pruebas" / "evidencia" / "banner-nube"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-banner-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaBanner",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_banner", app / "growi-bridge.py")
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

    def _todos(w):
        out = [w]
        for ch in w.winfo_children():
            out += _todos(ch)
        return out

    def foto(nombre):
        r = gb._root
        r.attributes("-topmost", False)
        r.attributes("-topmost", True)
        r.lift()
        bombear(0.5)
        captura(nombre)

    def leer(nombre):
        b = W["cloud_banner"]
        ev[nombre] = {"probe": gb.runner_modelo_probe(), "banner_visible": bool(b.winfo_ismapped()),
                      "texto": W["cloud_banner_txt"].cget("text") if b.winfo_ismapped() else "",
                      "raya": W["cloud_banner_raya"].cget("bg"), "nube_fallos": gb._AV.get("nube_fallos"),
                      "conn_state_del_mapa": gb.conn_state()}

    def ultima(motor, modelo, status="ok", error=""):
        gb._ULTIMA["d"] = {"tarea": "t-prueba-banner", "motor": motor, "modelo": modelo, "status": status,
                           "error": error, "at": gb._now_iso()}
        gb.runner_heartbeat()

    def esperar_en_vivo():
        bombear(6.5)  # sin llamar a nada: el tic de la ventana (cada ~5 s) repinta el banner

    def pasos():
        r = gb._root
        r.deiconify()
        W["show_page"]("estado")
        bombear(1.0)
        # (a) el runner en Opus: sin banner aunque el mapa diga otra cosa
        ultima("claude", "claude-opus-5-5")
        gb._AV["rows"]["claude"] = dict(gb._AV["rows"].get("claude") or {}, estado="falla")
        gb._after_availability()  # un fallo suelto del sondeo (antes bastaba para alarmar)
        esperar_en_vivo()
        leer("a_opus_un_fallo_suelto")
        foto("a-opus-sin-banner")
        # (b) el runner en un modelo local: informa, no alarma, y nombra el modelo
        ultima("llama", "hermes-3-8b-q4_k_m")
        esperar_en_vivo()
        leer("b_local")
        foto("b-local-informa")
        # (c1) nube inalcanzable de verdad: la última ejecución en la nube falló por red
        ultima("claude", "claude-opus-5-5", "error", "API Error: Connection error (getaddrinfo failed)")
        esperar_en_vivo()
        leer("c1_nube_fallo_red")
        foto("c-nube-inalcanzable")
        # (c2) o el sondeo falla dos veces seguidas (la 2.ª es la comprobación)
        ultima("claude", "claude-opus-5-5")
        gb._AV["nube_fallos"] = 0
        for _i in range(2):  # el fallo y la comprobación que también falla
            gb._AV["rows"]["claude"] = dict(gb._AV["rows"].get("claude") or {}, estado="falla")
            gb._after_availability()
        esperar_en_vivo()
        leer("c2_sondeo_falla_dos_veces")
        foto("c2-sondeo-falla-dos-veces")
        # (d) la nube vuelve: el banner se quita solo, en vivo
        gb._AV["rows"]["claude"] = dict(gb._AV["rows"].get("claude") or {}, estado="ok", ruta="directo")
        gb._after_availability()
        esperar_en_vivo()
        leer("d_nube_vuelve")
        foto("d-nube-vuelve")
        # (e) el estado no se puede leer: runner-status.json roto, y sin latido
        st = gb.OUTBOX / "runner-status.json"
        st.write_text("{roto", encoding="utf-8")
        ev["e_archivo_roto"] = gb.runner_modelo_probe()
        gb.PROBE_VIEJO_S = -1  # simula un runner sin latido (el archivo vuelve a escribirse solo)
        gb.runner_heartbeat()
        esperar_en_vivo()
        leer("e_sin_latido")
        foto("e-no-se-pudo-leer")
        gb.PROBE_VIEJO_S = 180
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
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
