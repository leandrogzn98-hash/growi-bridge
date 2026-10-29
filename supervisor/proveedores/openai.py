"""OpenAI (pago por uso)."""

from ._http import chat_compatible_openai

MODELO_POR_DEFECTO = "gpt-4o-mini"
CLAVE_POR_DEFECTO = "OPENAI_API_KEY"


def completar(prompt, *, modelo, clave, ajustes):
    url = ajustes.get("url") or "https://api.openai.com/v1/chat/completions"
    return chat_compatible_openai(url, prompt, modelo, clave, ajustes.get("tiempo_maximo_s", 60))
