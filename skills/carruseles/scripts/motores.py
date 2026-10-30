"""Motores de imagen para el carrusel tipo 2: qué hay en este PC y cuánto cuesta, SIN gastar nada al detectar.

  python motores.py                 -> reporte (texto) de motores; también lo deja en %LOCALAPPDATA%\\growi-carruseles\\motores.json
  python motores.py --json

Orden de preferencia: local ($0) > suscripción ya pagada (costo extra $0, gasta cuota del plan) > nada.
Las APIs de pago solo se REPORTAN (clave presente o no, nunca su valor): esta skill no tiene código para llamarlas,
así que no se pueden activar por accidente. Activarlas es una decisión de Leandro, con su OK y su presupuesto.

Detectar = leer el PATH, variables de entorno (solo el nombre), archivos de sesión (solo si existen), `codex features
list` (local) y puertos de 127.0.0.1. Ninguna llamada a internet.
"""

import importlib.util
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

from comun import DATOS, escribir_json, run

HOME = Path.home()
_SIN_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # un proxy en 127.0.0.1 intercepta localhost

APIS_PAGO = [  # (variable de entorno, servicio, qué es)
    ("GEMINI_API_KEY", "Google Gemini API", "imágenes con Gemini (Nano Banana): de pago por imagen en la API"),
    ("GOOGLE_API_KEY", "Google Gemini API", "misma API de Gemini con otro nombre de variable"),
    ("OPENAI_API_KEY", "OpenAI Images API", "gpt-image por API: de pago por imagen (aparte de ChatGPT Plus)"),
    ("FAL_KEY", "fal.ai", "Flux y otros por API: de pago"),
    ("REPLICATE_API_TOKEN", "Replicate", "modelos de imagen por API: de pago"),
    ("STABILITY_API_KEY", "Stability AI", "Stable Image por API: de pago"),
    ("BFL_API_KEY", "Black Forest Labs", "Flux por API: de pago"),
    ("IDEOGRAM_API_KEY", "Ideogram", "por API: de pago"),
    ("LEONARDO_API_KEY", "Leonardo", "por API: de pago"),
    ("HIGGSFIELD_API_KEY", "Higgsfield", "el «Higgs Field» que menciona Andrea Vega: créditos de pago"),
]


def _get(url, timeout=2):
    try:
        with _SIN_PROXY.open(url, timeout=timeout) as r:
            return r.status, r.read(200000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — cualquier fallo = no está
        return None, str(e)[:120]


def _gpu():
    if not shutil.which("nvidia-smi"):
        return None
    r = run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"], timeout=15)
    p = [x.strip() for x in (r.stdout or "").split(",")]
    return {"nombre": p[0], "vram_mib": int(p[1]), "usada_mib": int(p[2])} if len(p) >= 3 and p[1].isdigit() else None


def _codex():
    m = {"id": "codex", "nombre": "Codex CLI (image_gen integrado)", "tipo": "suscripción",
         "costo": "incluido en ChatGPT Plus ($20/mes ya pagado): $0 extra; gasta cuota del plan",
         "implementado": True, "disponible": False}
    exe = shutil.which("codex")
    if not exe:
        m["motivo"] = "codex no está en el PATH"
        return m
    if not (HOME / ".codex" / "auth.json").is_file():
        m["motivo"] = "codex sin sesión (falta ~/.codex/auth.json): `codex login`"
        return m
    r = run([exe, "features", "list"], timeout=60)
    fila = re.search(r"^image_generation\s+\S+\s+(true|false)", r.stdout or "", re.M)
    if not fila or fila.group(1) != "true":
        m["motivo"] = "la función image_generation de codex no está activa (`codex features list`)"
        return m
    m["disponible"] = True
    m["motivo"] = "sesión ChatGPT presente e image_generation=true; usa la herramienta integrada (no pide OPENAI_API_KEY)"
    return m


def detectar():
    motores = []
    est, cuerpo = _get("http://127.0.0.1:8188/system_stats")
    motores.append({"id": "comfyui", "nombre": "ComfyUI local (127.0.0.1:8188)", "tipo": "local", "costo": "$0",
                    "implementado": False, "disponible": False,
                    "motivo": ("responde, pero la skill aún no trae un flujo de ComfyUI: queda para la siguiente versión"
                               if est == 200 else "no responde en 8188 (no instalado o apagado)")})
    est, cuerpo = _get("http://127.0.0.1:7860/sdapi/v1/sd-models")
    motores.append({"id": "a1111", "nombre": "Stable Diffusion WebUI / Forge (127.0.0.1:7860, --api)", "tipo": "local",
                    "costo": "$0", "implementado": True, "disponible": est == 200,
                    "motivo": "responde con --api" if est == 200 else "no responde en 7860 (no instalado o sin --api)"})
    est, cuerpo = _get("http://127.0.0.1:11434/api/tags")
    imagen_ollama = []
    if est == 200:
        for mod in (json.loads(cuerpo).get("models") or []):
            caps = mod.get("capabilities") or []
            if "image" in caps or "image_generation" in caps:
                imagen_ollama.append(mod.get("name"))
    motores.append({"id": "ollama-imagen", "nombre": "Ollama (modelos de imagen)", "tipo": "local", "costo": "$0",
                    "implementado": False, "disponible": False,
                    "motivo": (f"modelos con capacidad de imagen: {', '.join(imagen_ollama)} (sin adaptador todavía)"
                               if imagen_ollama else ("Ollama responde, pero ningún modelo instalado genera imágenes"
                                                      if est == 200 else "Ollama no responde en 11434"))})
    hay = [n for n in ("diffusers", "torch") if importlib.util.find_spec(n)]
    motores.append({"id": "diffusers", "nombre": "Python diffusers + torch", "tipo": "local", "costo": "$0",
                    "implementado": False, "disponible": False,
                    "motivo": "instalados: " + ", ".join(hay) if hay else "diffusers y torch no están instalados"})
    motores.append(_codex())
    gem = shutil.which("gemini")
    motores.append({"id": "gemini-cli", "nombre": "Gemini CLI (sesión de Google)", "tipo": "suscripción",
                    "costo": "-", "implementado": False, "disponible": False,
                    "motivo": ("instalado" + (" con sesión" if (HOME / ".gemini" / "oauth_creds.json").is_file() else "")
                               + ": solo texto; generar imágenes pide la extensión nanobanana con GEMINI_API_KEY (de pago)")
                    if gem else "no instalado"})
    for var, servicio, que in APIS_PAGO:
        motores.append({"id": f"api-{var.lower()}", "nombre": servicio, "tipo": "pago", "costo": que,
                        "implementado": False, "disponible": False, "clave_presente": bool(os.environ.get(var)),
                        "motivo": (f"{var} está en el entorno: NO se activa sin el OK de Leandro"
                                   if os.environ.get(var) else f"{var} no está en el entorno")})
    motores.append({"id": "conectores-claude-ai", "nombre": "Conectores de claude.ai (Adobe Firefly, Gamma, Magic Patterns)",
                    "tipo": "pago", "costo": "créditos de cada servicio", "implementado": False, "disponible": False,
                    "motivo": "solo desde una sesión de Claude con esos conectores; gastan créditos: se reportan, no se usan"})
    rep = {"fecha": time.strftime("%Y-%m-%dT%H:%M:%S"), "gpu": _gpu(), "motores": motores,
           "elegido": elegir(motores), "gasto": "$0: la detección no generó ninguna imagen ni llamó a internet"}
    escribir_json(DATOS / "motores.json", rep)
    return rep


def elegir(motores, pedido=None):
    """-> id del motor a usar, o None. Nunca devuelve uno de pago."""
    usables = [m for m in motores if m["disponible"] and m["implementado"] and m["tipo"] != "pago"]
    if pedido:
        m = next((m for m in motores if m["id"] == pedido), None)
        if not m:
            raise RuntimeError(f"motor «{pedido}» desconocido")
        if m["tipo"] == "pago":
            raise RuntimeError(f"«{pedido}» es de pago: la skill no lo activa (regla de Leandro: ningún gasto sin su OK)")
        return pedido if m in usables else None
    for tipo in ("local", "suscripción"):
        for m in usables:
            if m["tipo"] == tipo:
                return m["id"]
    return None


def texto(rep):
    lineas = [f"Motores de imagen en este PC ({rep['fecha']}). Gasto de la detección: {rep['gasto']}."]
    if rep.get("gpu"):
        g = rep["gpu"]
        lineas.append(f"GPU: {g['nombre']}, {g['vram_mib']} MiB de VRAM ({g['usada_mib']} MiB en uso).")
    for tipo in ("local", "suscripción", "pago"):
        lineas.append(f"\n[{tipo}]")
        for m in rep["motores"]:
            if m["tipo"] == tipo:
                marca = "SÍ" if m["disponible"] else "no"
                lineas.append(f"  {marca:>2}  {m['nombre']} | costo: {m['costo']} | {m['motivo']}")
    lineas.append(f"\nElegido para el tipo 2: {rep['elegido'] or 'NINGUNO gratis: el tipo 2 queda bloqueado y se reporta'}")
    return "\n".join(lineas)


# ---------------------------------------------------------------- generar (solo motores sin costo extra)

def generar(motor, prompt, destino, prohibido=(), timeout=900):
    """Genera una imagen vertical 4:5 en `destino` (PNG). -> dict con motor, segundos y detalle."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if motor == "codex":
        det = _generar_codex(prompt, destino, prohibido, timeout)
    elif motor == "a1111":
        det = _generar_a1111(prompt, destino, prohibido, timeout)
    else:
        raise RuntimeError(f"no hay adaptador para «{motor}»")
    det.update({"motor": motor, "segundos": round(time.time() - t0, 1)})
    return det


def _generar_codex(prompt, destino, prohibido, timeout):
    trabajo = destino.parent / f"_codex-{destino.stem}"
    trabajo.mkdir(parents=True, exist_ok=True)
    evitar = ", ".join(["texto o letras dentro de la imagen", "logos", *prohibido])
    orden = (f"Genera UNA imagen con tu herramienta integrada de generación de imágenes (image_gen). No uses la CLI ni "
             f"ninguna API con clave. Imagen: {prompt}. Evita: {evitar}. Formato vertical 4:5. Después copia el PNG "
             "generado a ./imagen.png en esta carpeta y responde solo con la ruta.")
    inicio = time.time()
    r = run([shutil.which("codex") or "codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write",
             "-C", trabajo, orden], timeout=timeout)
    hecho = trabajo / "imagen.png"
    if not hecho.is_file():  # plan B: la que image_gen dejó en ~/.codex/generated_images durante esta corrida
        nuevas = [p for p in (HOME / ".codex" / "generated_images").rglob("*.png") if p.stat().st_mtime >= inicio - 1]
        if nuevas:
            hecho = max(nuevas, key=lambda p: p.stat().st_mtime)
    if not hecho.is_file():
        raise RuntimeError(f"codex no devolvió imagen (rc={r.returncode}): {(r.stderr or '')[-500:]}")
    shutil.copyfile(hecho, destino)
    tokens = re.search(r"tokens used\s*\n\s*([\d.,]+)", (r.stderr or "") + (r.stdout or ""))
    return {"tokens_codex": tokens.group(1) if tokens else None, "costo": "suscripción ChatGPT Plus: $0 extra"}


def _generar_a1111(prompt, destino, prohibido, timeout):  # escrito, no probado: no hay WebUI en este PC
    import base64
    cuerpo = json.dumps({"prompt": prompt, "negative_prompt": ", ".join(["text, letters, watermark, logo", *prohibido]),
                         "width": 864, "height": 1080, "steps": 28}).encode()
    req = urllib.request.Request("http://127.0.0.1:7860/sdapi/v1/txt2img", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    with _SIN_PROXY.open(req, timeout=timeout) as r:
        d = json.loads(r.read())
    destino.write_bytes(base64.b64decode(d["images"][0]))
    return {"costo": "$0 (local)"}


if __name__ == "__main__":
    rep = detectar()
    print(json.dumps(rep, ensure_ascii=False, indent=1) if "--json" in sys.argv else texto(rep))
