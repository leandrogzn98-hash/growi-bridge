"""DeepSeek (pago por uso, API compatible con la de OpenAI)."""

from ._http import chat_compatible_openai

MODELO_POR_DEFECTO = "deepseek-chat"
CLAVE_POR_DEFECTO = "DEEPSEEK_API_KEY"


def completar(prompt, *, modelo, clave, ajustes):
    url = ajustes.get("url") or "https://api.deepseek.com/chat/completions"
    return chat_compatible_openai(url, prompt, modelo, clave, ajustes.get("tiempo_maximo_s", 60))
