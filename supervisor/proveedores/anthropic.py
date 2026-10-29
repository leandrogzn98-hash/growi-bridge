"""Anthropic, API de mensajes (pago por uso; es una cuenta de API, no la suscripción de Claude Code)."""

from ._http import post_json

MODELO_POR_DEFECTO = "claude-haiku-5-5"
CLAVE_POR_DEFECTO = "ANTHROPIC_API_KEY"


def completar(prompt, *, modelo, clave, ajustes):
    url = ajustes.get("url") or "https://api.anthropic.com/v1/messages"
    d = post_json(url, {"model": modelo, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]},
                  {"x-api-key": clave, "anthropic-version": "2023-06-01"}, ajustes.get("tiempo_maximo_s", 60))
    return "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
