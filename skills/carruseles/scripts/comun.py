"""Lo que comparten los scripts de la skill carruseles: rutas, Chrome headless, JSON, marcas (brandbook + correcciones)."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
MARCAS_SEMILLA = SKILL / "marcas"  # brandbooks que viajan con la skill (los escribe una persona)
_LOCAL = Path(os.environ.get("LOCALAPPDATA") or Path.home())
DATOS = Path(os.environ.get("GROWI_CARRUSELES_DATOS") or _LOCAL / "growi-carruseles")
MARCAS = DATOS / "marcas"  # correcciones del usuario, por PC: se superponen al brandbook semilla
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)
ANCHO, ALTO = 1080, 1350

for _s in (sys.stdout, sys.stderr):  # la consola de Windows no es UTF-8 por defecto
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# Primero Chrome Headless Shell (el que instala skills\edicion-video\instalar.ps1): en este PC el Chrome y el Edge
# normales con --headless=new salen con código 0 sin escribir nada (visto el 29 oct 2026).
_SHELL = "chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe"
CHROMES = [os.environ.get("GROWI_CARRUSELES_CHROME") or "",
           str(_LOCAL / "growi-video" / "remotion" / "node_modules" / ".remotion" / _SHELL),
           str(DATOS / _SHELL),
           r"C:\Program Files\Google\Chrome\Application\chrome.exe",
           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

# Dónde buscar los archivos de fuente que pide el brandbook (se copian a la carpeta del carrusel).
CARPETAS_FUENTES = [_LOCAL / "Microsoft" / "Windows" / "Fonts",
                    Path(os.environ.get("WINDIR") or r"C:\Windows") / "Fonts", SKILL / "fuentes"]


def leer_json(p, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def escribir_json(p, d):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def slug(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "sin-nombre"


def run(args, timeout=120, cwd=None, env=None):
    """Proceso oculto y sin shell. -> CompletedProcess (texto en UTF-8)."""
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, cwd=cwd, env=env, creationflags=OCULTO)


def chrome():
    for c in CHROMES:
        if c and Path(c).is_file():
            return c
    raise RuntimeError("No encontré Chrome Headless Shell. Corre skills\\edicion-video\\instalar.ps1 o pon la ruta en "
                       "GROWI_CARRUSELES_CHROME.")


def chrome_headless(url, *extra, timeout=90):
    """Una pasada de Chrome headless con un perfil temporal (no toca el Chrome de Leandro)."""
    perfil = tempfile.mkdtemp(prefix="growi-carrusel-")
    exe = chrome()
    modo = [] if "headless-shell" in exe else ["--headless=new"]
    try:
        return run([exe, *modo, "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                    "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                    "--force-device-scale-factor=1", f"--window-size={ANCHO},{ALTO}",
                    "--allow-file-access-from-files", "--virtual-time-budget=6000",
                    f"--user-data-dir={perfil}", *extra, url], timeout=timeout)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)


# ---------------------------------------------------------------- marcas

def _mezclar(base, encima):
    for k, v in (encima or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mezclar(base[k], v)
        else:
            base[k] = v
    return base


def ruta_semilla(nombre_o_ruta):
    p = Path(nombre_o_ruta)
    return p if p.suffix else MARCAS_SEMILLA / f"{slug(nombre_o_ruta)}.json"


def cargar_marca(nombre_o_ruta):
    """Brandbook semilla (skills\\carruseles\\marcas\\<marca>.json o una ruta) + las correcciones guardadas en el PC
    (%LOCALAPPDATA%\\growi-carruseles\\marcas\\<marca>.json). -> dict con la marca efectiva; 'correcciones' trae el
    historial y 'aplicado' la lista legible de lo que las correcciones cambiaron."""
    p = ruta_semilla(nombre_o_ruta)
    base = leer_json(p)
    if base is None:
        disponibles = ", ".join(sorted(x.stem for x in MARCAS_SEMILLA.glob("*.json")))
        raise RuntimeError(f"No hay brandbook «{nombre_o_ruta}». Disponibles: {disponibles}")
    over = leer_json(MARCAS / f"{slug(base.get('marca') or p.stem)}.json", {}) or {}
    marca = _mezclar(json.loads(json.dumps(base)), over.get("ajustes") or {})
    marca["correcciones"] = over.get("correcciones") or []
    marca["aplicado"] = list(over.get("aplicado") or [])
    marca["_ruta"] = str(p)
    return marca


def pendientes_marca(marca):
    """Campos del brandbook que dicen [PENDIENTE…]: sin ellos no se diseña (no se inventan colores ni fuentes)."""
    faltan = []
    for grupo in ("colores", "fuentes"):
        for k, v in (marca.get(grupo) or {}).items():
            if not v or "PENDIENTE" in str(v):
                faltan.append(f"{grupo}.{k}")
    return faltan


def buscar_fuente(nombre, peso):
    """Archivo .ttf/.otf de la familia (el variable vale para cualquier peso). -> Path o None"""
    clave = re.sub(r"\s+", "", nombre).lower()
    candidatos = []
    for carpeta in CARPETAS_FUENTES:
        if carpeta.is_dir():
            for f in carpeta.iterdir():
                n = re.sub(r"[\s_]+", "", f.stem).lower()
                if f.suffix.lower() in (".ttf", ".otf") and n.startswith(clave):
                    candidatos.append(f)
    if not candidatos:
        return None
    for f in candidatos:
        if re.search(r"(^|[-_])vf$|variable", f.stem.lower()):
            return f
    nombre_peso = {400: "regular", 500: "medium", 600: "semibold", 700: "bold"}.get(peso, "regular")
    for f in candidatos:
        resto = f.stem.lower()[len(clave):]
        if nombre_peso in resto and not (nombre_peso == "bold" and ("semibold" in resto or "extrabold" in resto)):
            return f
    return candidatos[0]


# ---------------------------------------------------------------- color y texto

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum_rgb(r, g, b):
    lin = [c / 255 / 12.92 if c / 255 <= 0.03928 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(l1, l2):
    a, b = max(l1, l2), min(l1, l2)
    return (a + 0.05) / (b + 0.05)


def palabras(texto):
    """Palabras de verdad (sin la puntuación suelta). '**' de resalte no cuenta."""
    return [w for w in re.findall(r"[^\s*]+", texto or "") if re.search(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", w)]
