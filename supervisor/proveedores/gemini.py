"""Google Gemini (API de Google AI Studio)."""

from ._http import post_json

MODELO_POR_DEFECTO = "gemini-2.5-flash"
CLAVE_POR_DEFECTO = "GEMINI_API_KEY"


def completar(prompt, *, modelo, clave, ajustes):
    base = ajustes.get("url") or "https://generativelanguage.googleapis.com/v1beta/models"
    d = post_json(f"{base}/{modelo}:generateContent", {"contents": [{"parts": [{"text": prompt}]}]},
                  {"x-goog-api-key": clave}, ajustes.get("tiempo_maximo_s", 60))
    return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
