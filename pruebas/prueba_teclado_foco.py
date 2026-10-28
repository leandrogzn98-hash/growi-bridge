"""Prueba del teclado y el foco (ESTADO-TECLADO-FOCO.md).

Arranca la app REAL (main() de una COPIA de growi-bridge.py en %TEMP%, con
share, cola, token, mutex y puerto de prueba 8797; no toca la instalada) y la
maneja SOLO con el teclado de verdad (SendInput): Alt+1..9/0, «?», flechas e
Intro en Tareas y en la paleta, Tab con el anillo de foco en tres páginas y
Esc en la paleta, la cajita y un diálogo.

  python pruebas/prueba_teclado_foco.py
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
OUT = REPO / "pruebas" / "evidencia" / "teclado-foco"
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
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-teclado-"))
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
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MUTEX="Local\\GrowiBridgePruebaTeclado",
                      GROWI_BRIDGE_PORT="8797", GROWI_BRIDGE_LANE="a",
                      GROWI_BRIDGE_CLAUDE_PROJECTS=str(tmp / "cp"))
    sys.argv = [str(app / "growi-bridge.py")]
    spec = importlib.util.spec_from_file_location("gb_teclado", app / "growi-bridge.py")
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

    def vk(*codigos):
        """Pulsa una combinación con teclas virtuales de verdad (SendInput)."""
        for c in codigos:
            u32.keybd_event(c, 0, 0, 0)
            time.sleep(0.03)
        for c in reversed(codigos):
            u32.keybd_event(c, 0, 2, 0)
            time.sleep(0.03)
        bombear(0.35)

    ALT, CTRL, TAB, ESC, ENTER, ABAJO, ARRIBA = 0x12, 0x11, 0x09, 0x1B, 0x0D, 0x28, 0x26

    def anillos():
        n = 0
        for m in gb._FOCO["marcos"].values():
            try:
                if all(x.winfo_exists() and x.winfo_manager() for x in m):
                    n += 1
            except Exception:
                pass
        return n

    def pasos():
        r = gb._root
        r.deiconify()
        r.lift()
        r.attributes("-topmost", True)
        r.focus_force()
        bombear(0.5)
        raton(*centro(W["power_label"]))  # un clic en un sitio inocuo: la ventana pasa al frente (Windows)
        bombear(0.5)
        gb.stop_runner()
        # dos tareas en la lista (no se ejecutan: el runner está parado)
        gb.TASKS.mkdir(parents=True, exist_ok=True)
        for i in (1, 2):
            (gb.TASKS / f"t-teclado-{i}.task.json").write_text(json.dumps(
                {"id": f"t-teclado-{i}", "prompt": f"Tarea de prueba {i} para el teclado", "motor": "claude"},
                ensure_ascii=False), encoding="utf-8")
        W["power_canvas"].focus_set()
        bombear(0.3)
        # (a) Alt + 1..9 y 0
        ev["a_alt"] = {}
        for i in list(range(1, 10)) + [0]:
            vk(ALT, 0x30 + i)
            ev["a_alt"][f"Alt+{i}"] = W.get("pagina_actual")
        # (b) «?» abre la lista buscable; Esc la cierra; «?» con la búsqueda vacía también
        W["show_page"]("estado")
        bombear(0.3)
        W["power_canvas"].focus_set()
        bombear(0.2)
        teclas("?")
        bombear(0.8)
        t = gb._ATJ.get("top")
        ev["b_abierta"] = bool(t is not None and t.winfo_exists())
        ev["b_filas"] = len(gb._ATJ["lista"].get_children()) if ev["b_abierta"] else 0
        teclas("tareas")
        bombear(0.6)
        ev["b_buscar_tareas"] = [gb._ATJ["lista"].item(x, "values") for x in gb._ATJ["lista"].get_children()]
        from PIL import ImageGrab
        x, y = t.winfo_rootx(), t.winfo_rooty()
        ImageGrab.grab((x, y, x + t.winfo_width(), y + t.winfo_height()), all_screens=True).save(
            OUT / "1-lista-atajos.png")
        vk(ESC)
        ev["b_esc_la_cierra"] = gb._ATJ.get("top") is None or not gb._ATJ["top"].winfo_exists()
        W["power_canvas"].focus_set()
        bombear(0.2)
        teclas("?")
        bombear(0.6)
        teclas("?")
        bombear(0.6)
        ev["b_interrogacion_la_cierra"] = gb._ATJ.get("top") is None
        # «?» dentro de un campo de texto se escribe, no abre nada
        W["show_page"]("tareas")
        bombear(0.4)
        W["ask_text"].focus_set()
        bombear(0.2)
        teclas("?")
        bombear(0.4)
        ev["b_en_un_campo_se_escribe"] = {"texto": W["ask_text"].get("1.0", "end").strip(),
                                          "lista_abierta": gb._ATJ.get("top") is not None}
        W["ask_text"].delete("1.0", "end")
        # (c) Tareas: flechas + Intro, sin ratón
        gb._tasks_fp[0] = None
        gb._refresh_tasks_ui()
        tree = W["tasks_tree"]
        tree.focus_set()
        bombear(0.4)
        sel1 = list(tree.selection())
        vk(ABAJO)
        sel2 = list(tree.selection())
        vk(ENTER)
        ev["c_tareas"] = {"al_entrar": sel1, "tras_abajo": sel2,
                          "detalle_tras_intro": W["tasks_detail"].cget("text")[:160]}
        gb._scroll_a(tree)
        bombear(0.4)
        captura("2-tareas-foco-en-la-lista")
        # (c) la paleta: Ctrl+K, escribir, flechas, Intro
        vk(CTRL, 0x4B)
        bombear(0.6)
        ev["c_paleta_abierta"] = gb._palette.get("win") is not None
        teclas("ir a carpetas")
        bombear(0.5)
        vk(ENTER)
        bombear(0.6)
        ev["c_paleta_intro"] = {"pagina": W.get("pagina_actual"), "paleta_cerrada": gb._palette.get("win") is None}
        # (d) un solo anillo de foco: Tab en tres páginas
        ev["d_foco"] = {"color": gb.foco_color(), "contraste_con_fondo": gb._FOCO["contraste"]}
        for pag, nombre in (("estado", "3-foco-estado"), ("tareas", "4-foco-tareas"), ("ajustes", "5-foco-ajustes")):
            W["show_page"](pag)
            bombear(0.8)
            r.focus_force()
            {"estado": W["power_canvas"], "tareas": W["tasks_tree"]}.get(pag, r).focus_set()
            bombear(0.2)
            for _ in range(3 if pag != "ajustes" else 6):
                vk(TAB)
            w = r.focus_get()
            ev["d_foco"][pag] = {"widget": str(w), "clase": w.winfo_class() if w else None,
                                 "anillos_visibles": anillos(),
                                 "anillo_propio": bool(w is not None and (hasattr(w, "_focus") or
                                                                          "highlightthickness" in w.keys()))}
            if w is not None:
                gb._scroll_a(w)
                bombear(0.4)
                gb._foco_pintar()
                bombear(0.2)
            captura(nombre)
        # (e) Esc cierra la paleta, la cajita y un diálogo
        vk(CTRL, 0x4B)
        bombear(0.5)
        vk(ESC)
        ev["e_paleta"] = gb._palette.get("win") is None
        if gb._mascot.get("win") is None:
            gb.toggle_mascot()  # la cajita sale de la mascota
            bombear(1.5)
        gb.open_prompt_box()
        bombear(0.8)
        cj = [t for t in r.winfo_children() if isinstance(t, gb.tk.Toplevel) and t.winfo_exists()
              and t.title() == "Escríbeme"]
        if cj:
            raton(*centro(cj[0]))  # al frente, como cuando la abres con el ratón
            bombear(0.4)
        ev["e_cajita_foco"] = str(r.focus_get())
        cajas = [t for t in r.winfo_children() if isinstance(t, gb.tk.Toplevel) and t.winfo_exists()
                 and t.title() == "Escríbeme"]
        n_antes, titulos_antes = len(cajas), [c.title() for c in cajas]
        vk(ESC)
        bombear(0.4)
        cajas2 = [t for t in r.winfo_children() if isinstance(t, gb.tk.Toplevel) and t.winfo_exists()
                  and t.title() == "Escríbeme"]
        ev["e_cajita"] = {"ventanas_antes": n_antes, "despues": len(cajas2),
                          "titulos_antes": titulos_antes, "titulos_despues": [c.title() for c in cajas2]}
        gb.politicas_ui()
        bombear(1.2)
        top = gb._POLUI["top"]
        top.focus_force()
        gb._POLUI["carpeta"].focus_set()
        bombear(0.4)
        vk(ESC)
        bombear(0.5)
        try:
            ev["e_dialogo"] = not top.winfo_exists()
        except Exception:
            ev["e_dialogo"] = True
        r.attributes("-topmost", False)
        log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
        ev["log"] = [x for x in log.splitlines() if "teclado" in x][-12:]
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
