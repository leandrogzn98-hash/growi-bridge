"""Ollama en este equipo ($0, sin clave)."""

from ._http import post_json

MODELO_POR_DEFECTO = "hermes3:8b"
CLAVE_POR_DEFECTO = ""


def completar(prompt, *, modelo, clave, ajustes):
    url = ajustes.get("url") or "http://127.0.0.1:11434/api/chat"
    d = post_json(url, {"model": modelo, "stream": False, "messages": [{"role": "user", "content": prompt}]},
                  {}, ajustes.get("tiempo_maximo_s", 120))
    return d["message"]["content"]
