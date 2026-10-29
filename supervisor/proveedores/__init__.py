"""Adaptadores de proveedor del subgerente.

Cada proveedor es un módulo de esta carpeta con:
  MODELO_POR_DEFECTO  modelo que propone el asistente --configurar
  CLAVE_POR_DEFECTO   nombre de la variable de entorno / entrada del llavero ("" = no usa clave)
  completar(prompt, *, modelo, clave, ajustes) -> str

Para añadir un proveedor basta con crear <nombre>.py con eso: el núcleo lo carga por nombre.
"""

import importlib
import pkgutil
from pathlib import Path


def disponibles():
    """Nombres de los proveedores de esta carpeta (los que empiezan por _ son ayudas internas)."""
    return sorted(m.name for m in pkgutil.iter_modules([str(Path(__file__).parent)]) if not m.name.startswith("_"))


def cargar(nombre):
    if nombre not in disponibles():
        raise ValueError(f"proveedor «{nombre}» desconocido; los que hay: {', '.join(disponibles())}")
    return importlib.import_module(f"{__name__}.{nombre}")
