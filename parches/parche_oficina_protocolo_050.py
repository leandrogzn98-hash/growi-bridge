"""Parche t-oficina-protocolo-050 para growi-bridge.py: abrir/cerrar la oficina desde la app
(Ctrl+Shift+O, Ctrl+K y menu de la bandeja), subproceso con PID guardado, latido cada 5 s y
cierre limpio al salir. Solo aplica si encuentra cada ancla exacta una vez; conserva CRLF.
Hace .bak (growi-bridge.py.pre-oficina-protocolo.bak) antes de escribir.

  python parche_oficina.py <ruta a growi-bridge.py> [--seco]
"""
import shutil
import sys
from pathlib import Path

BLOQUE = r'''
# ---- Oficina 0.5.0 (t-oficina-protocolo-050): proceso APARTE, abrir y cerrar desde la app.
# Nunca se abre sola: solo con Ctrl+Shift+O, Ctrl+K «Abrir o cerrar la oficina» o el menu de la
# bandeja. La app la lanza como subproceso, guarda su PID (oficina.pid.json), le escribe un latido
# cada 5 s en share\outbox\bridge-latido.json y la cierra al salir: pide cerrar por el latido y,
# si no sale en 3 s, la mata. La oficina se cierra sola si el latido falta 15 s o este pid muere.
# Si la oficina muere, la app sigue (solo se anota en el Registro). Una sola oficina: la propia
# oficina toma el mutex Local\GrowiOficinaInstanciaUnica y la app no lanza otra si la suya vive.
OFICINA_LATIDO = OUTBOX / "bridge-latido.json"
OFICINA_PID_FILE = APP_DIR / "oficina.pid.json"
OFICINA_LATIDO_MS = 5000
_OFICINA = {"proc": None, "pid": None, "after": None, "inicio": None}
_OFICINA_CODIGOS = {0: "cerrada por el usuario", 2: "Bridge no disponible (autocierre)",
                    3: "ya había otra oficina abierta", 4: "la app pidió cerrarla",
                    5: "falta pygame-ce en ese Python"}


def _oficina_script():
    for c in (os.environ.get("GROWI_OFICINA_SCRIPT"), INBOX / "oficina" / "protocolo" / "oficina_proto.py",
              APP_DIR / "share" / "inbox" / "oficina" / "protocolo" / "oficina_proto.py",
              Path.home() / "growi-bridge" / "share" / "inbox" / "oficina" / "protocolo" / "oficina_proto.py"):
        if c and Path(c).is_file():
            return Path(c)
    return None


def _oficina_python():
    """(exe, env_extra, motivo). Pygame-ce comparte el interprete del Bridge: no hay pieza nueva."""
    try:
        s = load_settings()
    except Exception:
        s = {}
    base = Path(sys.executable)
    pyw = base.with_name("pythonw.exe") if base.with_name("pythonw.exe").is_file() else base
    exe = os.environ.get("GROWI_OFICINA_PYTHON") or s.get("oficina_python")
    if exe:
        return str(exe), {}, f"Python de Ajustes ({exe})"
    import importlib.util
    if importlib.util.find_spec("pygame") is not None:
        return str(pyw), {}, "pygame-ce en el Python del Bridge"
    d = os.environ.get("GROWI_OFICINA_PYGAME") or s.get("oficina_pygame_dir")
    if d and (Path(d) / "pygame").is_dir():
        return str(pyw), {"PYTHONPATH": str(d)}, f"pygame-ce de {d}"
    return None, {}, ("falta pygame-ce en el Python del Bridge (python -m pip install pygame-ce==2.5.8) "
                      "o la carpeta «oficina_pygame_dir» en settings.json")


def oficina_abierta():
    p = _OFICINA["proc"]
    return p is not None and p.poll() is None


def _oficina_latido(cerrar=False):
    d = {"pid": os.getpid(), "t": time.time(), "iso": _now_iso(), "oficina_pid": _OFICINA["pid"],
         "cerrar": bool(cerrar)}
    try:
        OUTBOX.mkdir(parents=True, exist_ok=True)
        tmp = OFICINA_LATIDO.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, OFICINA_LATIDO)
    except OSError as e:
        log(f"oficina: no se pudo escribir el latido ({e})")


def _oficina_olvidar():
    if _OFICINA["after"] is not None and _root is not None:
        try:
            _root.after_cancel(_OFICINA["after"])
        except Exception:
            pass
    _OFICINA.update(proc=None, pid=None, after=None, inicio=None)
    try:
        OFICINA_PID_FILE.unlink()
    except OSError:
        pass


def _oficina_tick():
    _OFICINA["after"] = None
    p = _OFICINA["proc"]
    if p is None:
        return
    rc = p.poll()
    if rc is not None:
        log(f"oficina: se cerró (pid {p.pid}, código {rc}: {_OFICINA_CODIGOS.get(rc, 'otro')}); la app sigue")
        _oficina_olvidar()
        return
    _oficina_latido()
    if _root is not None:
        try:
            _OFICINA["after"] = _root.after(OFICINA_LATIDO_MS, _oficina_tick)
        except Exception:
            pass


def oficina_abrir():
    """Lanza la oficina (subproceso). False si ya estaba abierta o no se puede."""
    if oficina_abierta():
        log(f"oficina: ya está abierta (pid {_OFICINA['pid']}); no lanzo otra")
        return False
    script = _oficina_script()
    if script is None:
        log("oficina: no encuentro oficina_proto.py (share\\inbox\\oficina\\protocolo\\); no se abre")
        return False
    exe, extra, motivo = _oficina_python()
    if exe is None:
        log(f"oficina: no se abre: {motivo}")
        return False
    _OFICINA["pid"] = None
    _oficina_latido()  # el primer latido ANTES de lanzarla (y borra un «cerrar» viejo)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **extra)
    cmd = [exe, str(script), "--share", str(SHARE), "--app", str(APP_DIR), "--bridge-pid", str(os.getpid()),
           "--latido", str(OFICINA_LATIDO)]
    try:
        p = subprocess.Popen(cmd, env=env, cwd=str(script.parent), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as e:
        log(f"oficina: no se pudo lanzar ({e})")
        return False
    _OFICINA.update(proc=p, pid=p.pid, inicio=time.time())
    try:
        OFICINA_PID_FILE.write_text(json.dumps({"pid": p.pid, "bridge_pid": os.getpid(), "inicio": _now_iso(),
                                                "cmd": cmd}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    log(f"oficina: abierta (pid {p.pid}, {motivo})")
    if _root is not None:
        try:
            _OFICINA["after"] = _root.after(OFICINA_LATIDO_MS, _oficina_tick)
        except Exception:
            pass
    return True


def oficina_cerrar(motivo="desde la app"):
    """Cierra la oficina: pide cerrar por el latido; si en 3 s no sale, terminate(); luego kill()."""
    p = _OFICINA["proc"]
    if p is None or p.poll() is not None:
        _oficina_olvidar()
        return False
    _oficina_latido(cerrar=True)
    como = "pidió cerrar"
    try:
        p.wait(3)
    except subprocess.TimeoutExpired:
        como = "no salió en 3 s: terminate()"
        p.terminate()
        try:
            p.wait(3)
        except subprocess.TimeoutExpired:
            como = "no salió: kill()"
            p.kill()
            try:
                p.wait(3)
            except subprocess.TimeoutExpired:
                pass
    log(f"oficina: cerrada {motivo} (pid {p.pid}, {como}, código {p.poll()})")
    _oficina_olvidar()
    return True


def oficina_alternar():
    return oficina_cerrar() if oficina_abierta() else oficina_abrir()


def _tray_oficina_label(_item=None):
    return "Cerrar oficina" if oficina_abierta() else "Abrir oficina"


'''

CAMBIOS = [
    # 1. el bloque, justo antes de quit_app
    ("\ndef quit_app():\n", BLOQUE + "\ndef quit_app():\n"),
    # 2. salir de la app cierra la oficina (antes que el resto)
    ('    log("saliendo de Growi Bridge...")\n    try:\n        atajos_salir()',
     '    log("saliendo de Growi Bridge...")\n    try:\n        oficina_cerrar("al salir de la app")\n'
     '    except Exception:\n        pass\n    try:\n        atajos_salir()'),
    # 3. bandeja
    ("        pystray.MenuItem(_tray_mascot_label, lambda: _root.after(0, toggle_mascot)),\n",
     "        pystray.MenuItem(_tray_mascot_label, lambda: _root.after(0, toggle_mascot)),\n"
     "        pystray.MenuItem(_tray_oficina_label, lambda: _root.after(0, oficina_alternar)),\n"),
    # 4. atajo Ctrl+Shift+O (solo con la ventana de la app enfocada; no es un atajo global)
    ('    root.bind_all("<Control-Key-0>", lambda _e: _show_page("recursos"))\n',
     '    root.bind_all("<Control-Key-0>", lambda _e: _show_page("recursos"))\n'
     '    root.bind_all("<Control-Shift-O>", lambda _e: oficina_alternar())  # t-oficina-protocolo-050\n'
     '    root.bind_all("<Control-Shift-o>", lambda _e: oficina_alternar())\n'),
    # 5. paleta Ctrl+K
    ('        C("aprobar", "Ver tareas que esperan tu aprobación",',
     '        C("oficina", "Abrir o cerrar la oficina", "oficina escena agentes pixel ver abrir cerrar",\n'
     '          oficina_alternar, chip="Ctrl+Shift+O",\n'
     '          more=[("Abrir la oficina", oficina_abrir), ("Cerrar la oficina", oficina_cerrar, True)]),\n'
     '        C("aprobar", "Ver tareas que esperan tu aprobación",'),
]


def main():
    ruta = Path(sys.argv[1])
    seco = "--seco" in sys.argv
    raw = ruta.read_bytes()
    crlf = b"\r\n" in raw
    txt = raw.decode("utf-8").replace("\r\n", "\n")
    if "t-oficina-protocolo-050" in txt:
        print("ya parcheado: no hago nada")
        return 1
    for viejo, nuevo in CAMBIOS:
        n = txt.count(viejo)
        if n != 1:
            print(f"ancla encontrada {n} veces (debe ser 1): {viejo[:70]!r}")
            return 2
        txt = txt.replace(viejo, nuevo)
    if seco:
        print("seco: todas las anclas encontradas una vez")
        return 0
    bak = ruta.with_name(ruta.name + ".pre-oficina-protocolo.bak")
    if not bak.exists():
        shutil.copy2(ruta, bak)
    out = txt.replace("\n", "\r\n") if crlf else txt
    ruta.write_bytes(out.encode("utf-8"))
    print(f"parcheado {ruta} (bak {bak.name}, crlf={crlf})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
