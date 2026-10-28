# @growi.titulo Archivos recientes
# @growi.descripcion Los 15 archivos más nuevos de Descargas y de los resultados de Growi; Enter abre el elegido
# @growi.modo lista
# @growi.icono reloj
# @growi.paquete Growi
# @growi.autor Plantilla de Growi Bridge (copiala y cambiala)
"""Plantilla del modo «lista»: imprime por stdout el JSON de estructura fija
{"items": [{"titulo", "subtitulo", "accion": {"tipo": "abrir"|"copiar", "valor"}}]}.
Solo lee fechas de archivos; no borra, no usa la red."""

import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Bridge lee la salida en UTF-8

aqui = Path(__file__).resolve().parent
carpetas = [Path.home() / "Downloads",
            Path(os.environ["GROWI_BRIDGE_SHARE"]) / "outbox" if os.environ.get("GROWI_BRIDGE_SHARE")
            else aqui.parent / "share" / "outbox"]
archivos = []
for c in carpetas:
    try:
        archivos += [p for p in c.iterdir() if p.is_file()]
    except OSError:
        pass
archivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
items = [{"titulo": p.name,
          "subtitulo": f"{p.parent.name} · {time.strftime('%d/%m %H:%M', time.localtime(p.stat().st_mtime))}",
          "accion": {"tipo": "abrir", "valor": str(p)}} for p in archivos[:15]]
print(json.dumps({"items": items}, ensure_ascii=False))
