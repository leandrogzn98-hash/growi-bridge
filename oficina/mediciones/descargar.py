"""Descarga lo que hace falta para medir (t-oficina-mediciones-050), en oficina/mediciones/_bin/ (fuera de git):
el editor de Godot (zip) y SOLO la plantilla de exportación de Windows del .tpz de plantillas (1,28 GB enteros),
leyendo el zip por rangos HTTP. Uso: python descargar.py 4.7.2-stable"""

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

BIN = Path(__file__).resolve().parent / "_bin"
VER = sys.argv[1] if len(sys.argv) > 1 else "4.7.2-stable"
BASE = f"https://github.com/godotengine/godot/releases/download/{VER}/"


class Rangos(io.RawIOBase):
    """Archivo remoto de solo lectura con seek, por peticiones HTTP Range."""

    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"))
        self.url, self.largo, self.pos = r.geturl(), int(r.headers["Content-Length"]), 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.largo + off}[whence]
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        if self.pos >= self.largo:
            return 0
        fin = min(self.pos + len(b), self.largo) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{fin}"})
        datos = urllib.request.urlopen(req).read()
        b[:len(datos)] = datos
        self.pos += len(datos)
        return len(datos)


BIN.mkdir(exist_ok=True)
editor = BIN / f"Godot_v{VER}_win64.exe"
if not editor.exists():
    print("editor ...")
    data = urllib.request.urlopen(BASE + f"Godot_v{VER}_win64.exe.zip").read()
    zipfile.ZipFile(io.BytesIO(data)).extractall(BIN)
plantilla = BIN / f"godot_{VER}_windows_release_x86_64.exe"
if not plantilla.exists():
    print("plantilla (solo windows_release_x86_64 del .tpz, por rangos) ...")
    z = zipfile.ZipFile(io.BufferedReader(Rangos(BASE + f"Godot_v{VER}_export_templates.tpz"), 8 * 1024 * 1024))
    nombre = next(n for n in z.namelist() if n.endswith("windows_release_x86_64.exe"))
    plantilla.write_bytes(z.read(nombre))
    print("  de", nombre)
for f in sorted(BIN.iterdir()):
    print(f.name, f.stat().st_size)
