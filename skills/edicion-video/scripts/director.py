"""Paso 3: el director decide qué se queda. Claude NO ve el vídeo: lee el transcript con tiempos por palabra.

Dos motores:
  reglas  ($0, sin red) pausas > umbral, muletillas, repetición inmediata («el primero, el primero fue…») y toma
          repetida (dos frases casi iguales seguidas: se queda la última, que suele ser la buena).
  claude  `claude -p` (la suscripción de Claude Code) decide a nivel de frase qué tomas quitar y escribe 3 ganchos
          (curiosidad, contrario, con número; < 8 palabras). Las reglas de pausas y muletillas se aplican igual.
"""

import difflib
import json
import re
import shutil

from comun import norm, run

PUNTO = re.compile(r"[.?!…]$")


def _frases(pal, umbral):
    frases, act = [], []
    for i, w in enumerate(pal):
        if act and (w["inicio"] - pal[act[-1]]["fin"] >= umbral or PUNTO.search(pal[act[-1]]["texto"])):
            frases.append(act)
            act = []
        act.append(i)
    if act:
        frases.append(act)
    return [{"id": n, "idx": f, "inicio": pal[f[0]]["inicio"], "fin": pal[f[-1]]["fin"],
             "texto": " ".join(pal[i]["texto"] for i in f)} for n, f in enumerate(frases)]


def _muletillas(pal, estilo):
    """{idx: motivo} de las palabras que son muletilla."""
    siempre = [norm(m) for m in estilo["muletillas_siempre"]]
    cond = [norm(m) for m in estilo["muletillas"] if m not in estilo["muletillas_siempre"]]
    toks = [(norm(w["texto"]) or [""])[0] for w in pal]
    out = {}
    for lista, condicional in ((siempre, False), (cond, True)):
        for m in sorted(lista, key=len, reverse=True):
            k = len(m)
            for i in range(len(pal) - k + 1):
                if toks[i:i + k] != m or any(j in out for j in range(i, i + k)):
                    continue
                if condicional:
                    prev = pal[i - 1] if i else None
                    ult = pal[i + k - 1]
                    sig = pal[i + k] if i + k < len(pal) else None
                    entre_comas = (prev is None or prev["texto"].endswith(",")) or ult["texto"].endswith(",")
                    entre_pausas = ((prev is None or pal[i]["inicio"] - prev["fin"] > 0.25)
                                    or (sig is None or sig["inicio"] - ult["fin"] > 0.25))
                    if not (entre_comas or entre_pausas):
                        continue
                for j in range(i, i + k):
                    out[j] = f"muletilla «{' '.join(m)}»"
    return out


def _repeticiones(pal, quitar):
    """Falsa salida: «el segundo, este, el segundo fue…» -> quita la primera copia. Se busca en toda la secuencia
    (sin las muletillas ya quitadas), porque la pausa de la falsa salida suele partir la frase."""
    idx = [i for i in range(len(pal)) if i not in quitar]
    toks = [(norm(pal[i]["texto"]) or [""])[0] for i in idx]
    for k in (4, 3, 2, 1):
        i = 0
        while i + 2 * k <= len(toks):
            seguido = pal[idx[i + k]]["inicio"] - pal[idx[i + k - 1]]["fin"] < 2.5
            if seguido and toks[i:i + k] == toks[i + k:i + 2 * k] and all(toks[i:i + k]):
                for j in idx[i:i + k]:
                    quitar[j] = f"repetición inmediata «{' '.join(toks[i:i + k])}»"
                del toks[i:i + k]
                del idx[i:i + k]
            else:
                i += 1


def _tomas_repetidas(frases):
    """[(id_quitada, id_que_queda)]: una frase casi igual a una de las dos siguientes es una toma descartada."""
    out = []
    for a in frases:
        na = norm(a["texto"])
        for b in frases[a["id"] + 1:a["id"] + 3]:
            nb = norm(b["texto"])
            r = difflib.SequenceMatcher(None, na, nb).ratio()
            if len(na) >= 3 and (r >= 0.6 or na[:3] == nb[:3]):
                out.append((a["id"], b["id"], round(r, 2)))
                break
    return out


def _puntaje_gancho(t):
    n = norm(t)
    s = 0
    s += 3 if "?" in t or "¿" in t else 0
    s += 2 if any(x.isdigit() or x in ("uno", "dos", "tres", "cuatro", "cinco", "diez", "mil") for x in n) else 0
    s += 1 if any(x in ("nadie", "error", "errores", "secreto", "nunca", "deja", "importa") for x in n) else 0
    return s


def _ganchos_reglas(frases_vivas):
    orden = sorted(frases_vivas, key=lambda f: (-_puntaje_gancho(f["texto"]), f["inicio"]))
    out = []
    for f in orden[:3]:
        pal = f["texto"].replace("¿", "").split()
        out.append(" ".join(pal[:7]).rstrip(",.") + ("…" if len(pal) > 7 else ""))
    return out or ["(sin texto)"]


PROMPT = """Eres el director de edición de un reel vertical (talking-head). No ves el vídeo: tienes el transcript por frases con tiempos.
Tarea:
1. Marca las frases que sobran: tomas repetidas (si una idea se dice dos veces, quédate con la MEJOR toma, normalmente la última y más completa), falsas salidas y frases que no aportan.
2. Escribe 3 ganchos de menos de 8 palabras para los primeros 3 segundos: uno de curiosidad, uno contrario, uno con número. Que salgan del contenido real, sin inventar datos.
Responde SOLO con JSON, sin texto alrededor:
{"quitar": [{"id": <id>, "motivo": "<por qué>"}], "ganchos": ["<curiosidad>", "<contrario>", "<número>"], "gancho_elegido": <0-2>, "notas": "<una línea>"}

Frases:
"""


def prompt_claude(frases):
    return PROMPT + "\n".join(f'{f["id"]}. [{f["inicio"]:.1f}-{f["fin"]:.1f}s] {f["texto"]}' for f in frases)


def _claude(frases, modelo):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("no encuentro el CLI `claude` en el PATH")
    r = run([exe, "-p", prompt_claude(frases), "--model", modelo, "--output-format", "json"], timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p falló ({r.returncode}): {(r.stderr or r.stdout)[-400:]}")
    env = json.loads(r.stdout)
    txt = env.get("result") or ""
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise RuntimeError(f"claude no devolvió JSON: {txt[:200]}")
    d = json.loads(m.group(0))
    uso = env.get("usage") or {}
    return d, {"usd": env.get("total_cost_usd"), "tokens_entrada": (uso.get("input_tokens") or 0)
               + (uso.get("cache_read_input_tokens") or 0) + (uso.get("cache_creation_input_tokens") or 0),
               "tokens_salida": uso.get("output_tokens"), "modelo": modelo}


def dirigir(pal, sil, estilo, duracion, motor="reglas", modelo="haiku", vision=None):
    """-> dict con frases, palabras quitadas, segmentos a conservar (tiempo del crudo), lista de cortes y ganchos."""
    umbral, margen = estilo["umbral_pausa_s"], estilo["margen_s"]
    # Whisper estira a veces la última palabra dentro del silencio: se recorta al inicio del silencio.
    for w in pal:
        for a, b in sil:
            if w["inicio"] < a < w["fin"] <= b + 0.05:
                w["fin"] = round(a + 0.02, 3)
    frases = _frases(pal, umbral)
    quitar = _muletillas(pal, estilo)
    _repeticiones(pal, quitar)
    frases_quitadas = {}
    for a, b, r in _tomas_repetidas(frases):
        # Todo lo que va de la toma descartada a la buena (la falsa salida puede ocupar dos frases).
        for x in range(a, b):
            frases_quitadas[x] = f"toma repetida (se queda la frase {b}, parecido {r})"
    costo_real, ganchos, elegido, notas = None, None, 0, ""
    if motor == "claude":
        vivas = [dict(f, texto=" ".join(pal[i]["texto"] for i in f["idx"] if i not in quitar)) for f in frases]
        d, costo_real = _claude(vivas, modelo)
        frases_quitadas = {int(x["id"]): f"director: {x.get('motivo', '')}" for x in d.get("quitar") or []
                           if str(x.get("id", "")).isdigit() and int(x["id"]) < len(frases)}
        ganchos, elegido, notas = d.get("ganchos") or None, int(d.get("gancho_elegido") or 0), d.get("notas") or ""
    for fid, motivo in frases_quitadas.items():
        for i in frases[fid]["idx"]:
            quitar.setdefault(i, motivo)
    vivas = [i for i in range(len(pal)) if i not in quitar]
    if not vivas:
        raise RuntimeError("el director no dejó ninguna palabra")
    # Segmentos: palabras conservadas seguidas; un hueco >= umbral o una palabra quitada en medio abre otro.
    segs, act = [], [vivas[0]]
    for i in vivas[1:]:
        p = act[-1]
        if i == p + 1 and pal[i]["inicio"] - pal[p]["fin"] < umbral:
            act.append(i)
        else:
            segs.append(act)
            act = [i]
    segs.append(act)
    segmentos = []
    for s in segs:
        a = max(0.0, pal[s[0]]["inicio"] - margen)
        b = pal[s[-1]]["fin"] + margen
        if segmentos and a < segmentos[-1][1]:
            a = segmentos[-1][1]
        segmentos.append([round(a, 3), round(b, 3)])
    cortes, t = [], 0.0
    for a, b in segmentos + [[None, None]]:
        fin = a if a is not None else duracion
        if fin - t > 0.05:
            dentro = sorted({quitar[i] for i in range(len(pal)) if i in quitar
                             and pal[i]["inicio"] >= t - 0.01 and pal[i]["fin"] <= fin + 0.01})
            cortes.append({"desde": round(t, 3), "hasta": round(fin, 3), "segundos": round(fin - t, 2),
                           "texto": " ".join(pal[i]["texto"] for i in range(len(pal)) if i in quitar
                                             and pal[i]["inicio"] >= t - 0.01 and pal[i]["fin"] <= fin + 0.01),
                           "motivo": "; ".join(dentro) or f"pausa de {fin - t:.2f} s"})
        if b is not None:
            t = b
    frases_vivas = [dict(f, texto=" ".join(pal[i]["texto"] for i in f["idx"] if i not in quitar))
                    for f in frases if any(i not in quitar for i in f["idx"])]
    if not ganchos:
        ganchos = _ganchos_reglas(frases_vivas)
    return {"motor": motor, "frases": frases, "palabras_quitadas": {str(k): v for k, v in sorted(quitar.items())},
            "segmentos": segmentos, "cortes": cortes, "ganchos": ganchos,
            "gancho": ganchos[min(elegido, len(ganchos) - 1)], "notas": notas, "costo_real": costo_real,
            "vision": vision}
