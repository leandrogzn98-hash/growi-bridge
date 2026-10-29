"""Ayuda común: una llamada POST JSON con errores legibles (sin mostrar nunca la clave)."""

import requests


class ErrorProveedor(RuntimeError):
    pass


def post_json(url, cuerpo, cabeceras, tiempo_maximo):
    s = requests.Session()
    s.trust_env = url.startswith("https://")  # a 127.0.0.1 nunca por el proxy del sistema
    try:
        r = s.post(url, json=cuerpo, headers=cabeceras, timeout=tiempo_maximo)
    except requests.RequestException as e:
        raise ErrorProveedor(f"no se pudo llamar a {url.split('?')[0]}: {type(e).__name__}") from None
    if r.status_code >= 400:
        raise ErrorProveedor(f"{url.split('?')[0]} respondió {r.status_code}: {r.text[:200]}")
    return r.json()


def chat_compatible_openai(url, prompt, modelo, clave, tiempo_maximo):
    """Proveedores con la API de chat de OpenAI (OpenAI, DeepSeek...)."""
    d = post_json(url, {"model": modelo, "messages": [{"role": "user", "content": prompt}], "temperature": 0},
                  {"Authorization": f"Bearer {clave}"}, tiempo_maximo)
    return d["choices"][0]["message"]["content"]
