"""Costos transparentes: estimación por vídeo ANTES de renderizar (y el real cuando el proveedor lo da).

Whisper y Remotion corren en el PC: $0. Lo que se paga es el director (si es `claude`) y los ojos (si es
`gemini`). Los tokens se estiman del texto real que se manda; los dólares solo si el precio está puesto en
estilos.json (costos.precio_usd_millon). Sin precio, el reporte lo dice; nunca inventa la cifra."""


import json

from comun import DATOS, ahora

HISTORIAL = DATOS / "costos-historial.jsonl"


def _usd(tokens, precio):
    return None if precio is None else round(tokens * float(precio) / 1e6, 5)


def anotar_real(paso, modelo, usd, tokens_entrada=None, tokens_salida=None):
    """Guarda un costo real medido (p. ej. total_cost_usd de claude -p) para estimar los siguientes."""
    if usd is None:
        return
    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORIAL, "a", encoding="utf-8") as f:
        f.write(json.dumps({"fecha": ahora(), "paso": paso, "modelo": modelo, "usd": usd,
                            "tokens_entrada": tokens_entrada, "tokens_salida": tokens_salida}) + "\n")


def _media_historica(paso, modelo):
    vals = []
    try:
        for ln in HISTORIAL.read_text(encoding="utf-8").splitlines():
            d = json.loads(ln)
            if d.get("paso") == paso and d.get("modelo") == modelo and isinstance(d.get("usd"), (int, float)):
                vals.append(d["usd"])
    except (OSError, ValueError):
        pass
    return (round(sum(vals) / len(vals), 5), len(vals)) if vals else (None, 0)


def estimar(estilo, duracion_s, prompt_director=None, motor_director="reglas", ojos=None, modelo=None):
    c = estilo["costos"]
    pr = c["precio_usd_millon"]
    lineas = [{"paso": "transcripción (Whisper local)", "tokens": 0, "usd": 0.0},
              {"paso": "pausas (ffmpeg silencedetect)", "tokens": 0, "usd": 0.0}]
    if motor_director == "claude":
        t_prompt = round(len(prompt_director or "") / c["caracteres_por_token"])
        t_in = t_prompt + int(c.get("sobrecarga_claude_p_tokens") or 0)
        t_out = c["salida_director_tokens"]
        u_in, u_out = _usd(t_in, pr.get("claude_entrada")), _usd(t_out, pr.get("claude_salida"))
        usd, fuente = (None if u_in is None or u_out is None else round(u_in + u_out, 5)), "precio configurado"
        if usd is None:
            usd, n = _media_historica("director", modelo)
            fuente = f"media de {n} corrida(s) real(es) de claude -p {modelo}" if n else None
        lineas.append({"paso": f"director (claude -p {modelo or ''})".replace(" )", ")"), "tokens_entrada": t_in,
                       "tokens_prompt": t_prompt, "tokens_salida": t_out, "tokens": t_in + t_out, "usd": usd,
                       "usd_fuente": fuente})
    else:
        lineas.append({"paso": "director (reglas locales)", "tokens": 0, "usd": 0.0})
    if ojos == "gemini":
        t_in = round(duracion_s * c["gemini_tokens_por_segundo"]) + 300
        u_in, u_out = _usd(t_in, pr.get("gemini_entrada")), _usd(400, pr.get("gemini_salida"))
        lineas.append({"paso": "ojos (Gemini ve el vídeo)", "tokens_entrada": t_in, "tokens_salida": 400,
                       "tokens": t_in + 400, "usd": None if u_in is None or u_out is None else round(u_in + u_out, 5)})
    lineas.append({"paso": "render (Remotion local)", "tokens": 0, "usd": 0.0})
    total_t = sum(x["tokens"] for x in lineas)
    sin_precio = [x["paso"] for x in lineas if x["usd"] is None]
    total_usd = None if sin_precio else round(sum(x["usd"] for x in lineas), 5)
    return {"lineas": lineas, "tokens_total": total_t, "usd_total": total_usd,
            "falta_precio": sin_precio,
            "resumen": (f"{total_t} tokens estimados; " + (f"${total_usd:.4f}" if total_usd is not None else
                        "USD sin calcular: falta el precio de " + ", ".join(sin_precio) + " en estilos.json"))
            if total_t else "0 tokens: todo local, $0"}
