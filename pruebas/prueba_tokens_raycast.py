"""Prueba de los tokens Raycast (ESTADO-TOKENS-RAYCAST.md).

Arranca la app REAL (main() de una COPIA, share/cola/token/mutex propios,
puerto de prueba 8797) con un tema y un DPI dados, con 4 tareas sembradas, y
mide: colores reales por pixel (ventana, tarjeta, borde, barra lateral), el
rojo #FF6363 en todas las paginas (solo botones primarios), el alto de fila de
Tareas, la fuente de los IDs y la fuente en uso. Capturas de Estado, Tareas y
Modelos.

  python pruebas/prueba_tokens_raycast.py oscuro 100
  python pruebas/prueba_tokens_raycast.py oscuro 150
  python pruebas/prueba_tokens_raycast.py claro 100
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
MODO = sys.argv[1] if len(sys.argv) > 1 else "oscuro"
DPI = sys.argv[2] if len(sys.argv) > 2 else "100"
NOMBRE = f"{MODO}-{DPI}"
OUT = REPO / "pruebas" / "evidencia" / "tokens-raycast"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-tokens-"))
    app = tmp / "app"
    shutil.copytree(REPO, app, ignore=shutil.ignore_patterns(".git", "pruebas", "__pycache__", "gate-calidad",
                                                              "specs", "*.log", "settings.json"))
    (app / "secret.txt").write_text("prueba-ajustes", encoding="utf-8")
    (app / "settings.json").write_text(json.dumps({
        "lane": "a", "onboarding_done": True, "guardrail": "delicado", "mascot": False, "auto_update": False,
        "copia_claude": False, "motor_local_parar_al_salir": False, "bridge_port": 8797, "on_close": "quit",
        "keep_awake": True, "apariencia": MODO}), encoding="utf-8")
    res = tmp / "share" / "outbox" / "runner-results"
    res.mkdir(parents=True)
    ahora = time.strftime("%Y-%m-%dT%H:%M:%S-04:00")
    for tid, est, costo in (("t-informe-ventas-0427", "aprobada", 0.42), ("t-ajustar-logo-0428", "en_curso", None),
                            ("t-borrar-copias-0428", "esperando_aprobacion", None),
                            ("t-traducir-manual-0426", "fallida", 0.11)):
        (res / f"{tid}.orquestacion.json").write_text(json.dumps({
            "raiz": tid, "estado": est, "motor": "claude", "ronda": 1, "costo_usd": costo, "actualizado": ahora,
            "tareas": [tid], "encargo": "tarea de prueba"}), encoding="utf-8")
    e = json.loads((app / "engines.json").read_text(encoding="utf-8"))  # como el smoke del gate
    for m in (e.get("motores") or {}).values():
        if isinstance(m, dict):
            m.pop("servidor", None)
            (m.get("autenticacion") or {}).pop("sesion_cli", None) if isinstance(m.get("autenticacion"), dict) else None
    (app / "engines.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaTokens",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"),
                      GROWI_BRIDGE_DPI="144" if DPI == "150" else "96")
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_tokens", app / "growi-bridge.py")
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

    def pixel(img, w, dx=6, dy=6):
        r = gb._root
        return "#%02X%02X%02X" % img.getpixel((w.winfo_rootx() - r.winfo_rootx() + dx,
                                              w.winfo_rooty() - r.winfo_rooty() + dy))[:3]

    def colores(w):
        out = []
        for opt in ("bg", "fg", "fg_color", "text_color", "background", "foreground"):
            try:
                v = w.cget(opt)
            except Exception:
                continue
            for x in (v if isinstance(v, (list, tuple)) else [v]):
                if isinstance(x, str) and x.startswith("#"):
                    out.append(x.upper())
        return out

    def textos_de(w):
        try:
            return str(w.cget("text"))[:40]
        except Exception:
            return ""

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        st = ttk_style()
        ev["tema"] = {"id": gb._TEMA["actual"]["id"], "fuente_en_uso": gb.FONT, "escala": gb.SCALE,
                      "tokens": {k: gb.THEME[k] for k in ("bg", "sidebar", "card", "line", "text", "muted", "blue",
                                                           "orange", "red", "green")},
                      "acento": gb._tema_fijo("accent"),
                      "boton_primario_fondo": st.lookup("Accent.TButton", "background")}
        rojos = []
        for pag in ("estado", "carpetas", "skills", "pantalla", "apis", "modelos", "tareas", "recursos",
                    "ajustes", "registro"):
            W["show_page"](pag)
            bombear(1.2)
            for w in _todos(r):
                try:
                    if not w.winfo_ismapped():
                        continue
                except Exception:
                    continue
                if any(c in ("#FF6363", "#FF7B7B") for c in colores(w)):
                    dueno, m = w, w
                    while m is not None:  # la etiqueta interna de un CTkButton es parte del botón
                        if "Button" in type(m).__name__:
                            dueno = m
                            break
                        m = getattr(m, "master", None)
                    if dueno is not w and any(x["w"] is dueno for x in rojos):
                        continue
                    rojos.append({"pagina": pag, "clase": type(dueno).__name__, "texto": textos_de(dueno),
                                  "w": dueno})
        for x in rojos:
            x.pop("w")
        ev["c_rojo_ff6363_fuera_de_boton"] = [x for x in rojos if "Button" not in x["clase"]]
        ev["c_rojo_ff6363_en_botones"] = sorted({f"{x['pagina']}: {x['texto']}" for x in rojos
                                                 if "Button" in x["clase"]})
        W["show_page"]("tareas")
        bombear(1.5)
        t = W["tasks_tree"]
        ids = t.get_children()
        b0, b1 = t.bbox(ids[0]), t.bbox(ids[1])
        ev["d_filas"] = {"rowheight_estilo_px": st.lookup("Tareas.Treeview", "rowheight"),
                         "alto_fila_medido_px": b1[1] - b0[1], "a_100_pct": round((b1[1] - b0[1]) / gb.SCALE, 1),
                         "estado_fila_0": t.set(ids[0], "estado")}
        ev["e_ids_monoespaciada"] = {"fuente_tabla_tareas": st.lookup("Tareas.Treeview", "font"),
                                     "id_fila_0": t.set(ids[0], "tarea")}
        from PIL import ImageGrab
        x, y = r.winfo_rootx(), r.winfo_rooty()
        img = ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True)
        img.save(OUT / f"{NOMBRE}-tareas.png")
        alto = r.winfo_height()
        card = next(w for w in _todos(r) if type(w) is gb.tk.Frame and w.winfo_ismapped()
                    and str(w["bg"]).upper() == gb.THEME["card"] and int(w.cget("highlightthickness")) == 1
                    and 0 < w.winfo_rooty() - r.winfo_rooty() < alto - 40 and w.winfo_width() > 200)
        ev["a_pixeles"] = {"ventana": pixel(img, W["tasks_summary"], 2, -3), "tarjeta": pixel(img, card, 8, 8),
                           "borde_tarjeta": pixel(img, card, 0, 10),
                           "barra_lateral": "#%02X%02X%02X" % img.getpixel((S0(12), r.winfo_height() // 2))[:3]}
        for pag in ("estado", "modelos"):
            W["show_page"](pag)
            bombear(1.5)
            x, y = r.winfo_rootx(), r.winfo_rooty()
            ImageGrab.grab((x, y, x + r.winfo_width(), y + r.winfo_height()), all_screens=True).save(
                OUT / f"{NOMBRE}-{pag}.png")
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "temas:" in x][-4:]
        ev["tracebacks_en_log"] = log.count("Traceback")
        (OUT / f"{NOMBRE}.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        gb.quit_app()

    def ttk_style():
        return gb.ttk.Style()

    def S0(px):
        return int(px * gb.SCALE)

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
