"""QC automático del render: mira el MP4 final de verdad (no la configuración) y lo rechaza con diagnóstico.

  1. formato     1080x1920, 30 fps, con audio.
  2. duración    la del vídeo editado (suma de segmentos) con una tolerancia de 2 frames.
  3. subtítulos  en momentos con subtítulo, el fotograma final contra el editado sin subtítulos: lo que cambió es
                 la caja del subtítulo. Tiene que existir (visible) y caer entera dentro de la zona segura.
  4. audio       la envolvente del audio final contra la del editado: desfase <= 1 frame y misma señal.

  python qc.py <carpeta_del_trabajo> [--final otro.mp4]      (sale 0 si pasa, 1 si se rechaza)
"""

import argparse
import sys

from comun import asegurar_venv, escribir_json, leer_json, probe

ESCALA = 4  # los fotogramas se comparan a 270x480


def _frame_bytes(video, t, w, h):
    import subprocess
    import numpy as np
    from comun import OCULTO
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf",
                        f"scale={w // ESCALA}:{h // ESCALA}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=120, creationflags=OCULTO)
    n = (w // ESCALA) * (h // ESCALA) * 3
    return np.frombuffer(p.stdout[:n], dtype=np.uint8).reshape(h // ESCALA, w // ESCALA, 3).astype(int) \
        if len(p.stdout) >= n else None


def _caja_subtitulo(final, editado, t, w, h):
    """bbox (x0, y0, x1, y1) en px de 1080x1920 de lo que el render añadió sobre el editado, o None."""
    import numpy as np
    a, b = _frame_bytes(final, t, w, h), _frame_bytes(editado, t, w, h)
    if a is None or b is None:
        return None, "no se pudo leer el fotograma"
    m = np.abs(a - b).sum(axis=2) > 120
    filas = np.where(m.sum(axis=1) >= 6)[0]
    cols = np.where(m.sum(axis=0) >= 3)[0]
    if len(filas) < 4 or len(cols) < 10:
        return None, f"no hay subtítulo visible en t={t:.2f} s ({int(m.sum())} px cambiados)"
    return (int(cols[0] * ESCALA), int(filas[0] * ESCALA), int((cols[-1] + 1) * ESCALA),
            int((filas[-1] + 1) * ESCALA)), ""


def _envolvente(video, hop=0.005):
    import subprocess
    import numpy as np
    from comun import OCULTO
    sr = 8000
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True, timeout=600, creationflags=OCULTO)
    x = np.frombuffer(p.stdout, dtype=np.float32)
    n = int(sr * hop)
    k = len(x) // n
    if k < 10:
        return None
    return np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(axis=1))


def _inicios(video):
    """{"video": start_time, "audio": start_time} de los streams, en segundos."""
    import json
    from comun import run
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time", "-of", "json", video], timeout=60)
    out = {}
    for s in json.loads(r.stdout or "{}").get("streams", []):
        try:
            out.setdefault(s["codec_type"], float(s.get("start_time") or 0))
        except (TypeError, ValueError):
            pass
    return out


def _desfase(final, editado, max_s=0.6, hop=0.005):
    import numpy as np
    a, b = _envolvente(final, hop), _envolvente(editado, hop)
    if a is None or b is None:
        return None, 0.0
    L = min(len(a), len(b))
    a, b = a[:L] - a[:L].mean(), b[:L] - b[:L].mean()
    lags = range(-int(max_s / hop), int(max_s / hop) + 1)
    mejor, corr = 0, -1.0
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    for lag in lags:
        if lag >= 0:
            c = float(np.dot(a[lag:], b[:L - lag]))
        else:
            c = float(np.dot(a[:L + lag], b[-lag:]))
        if c > corr:
            mejor, corr = lag, c
    return round(mejor * hop, 3), round(corr / (na * nb + 1e-9), 3)


def qc(carpeta, final=None):
    carpeta = __import__("pathlib").Path(carpeta)
    props = leer_json(carpeta / "props.json")
    final = str(final or carpeta / "final.mp4")
    editado = str(carpeta / "editado.mp4")
    w, h, fps = props.get("ancho", 1080), props.get("alto", 1920), props.get("fps", 30)
    zona = props["estilo"].get("zona") or {"arriba": 220, "abajo": 380, "izquierda": 40, "derecha": 140}
    checks = []

    def check(nombre, ok, detalle):
        checks.append({"nombre": nombre, "ok": bool(ok), "detalle": detalle})

    pf, pe = probe(final), probe(editado)
    check("formato", pf["ancho"] == w and pf["alto"] == h and abs(pf["fps"] - fps) < 0.01 and pf["audio"],
          f"{pf['ancho']}x{pf['alto']} a {pf['fps']} fps, audio {'sí' if pf['audio'] else 'NO'} (esperado {w}x{h} a {fps})")
    esperada = props["duracion_s"]
    tol = max(0.1, 2 / fps)
    check("duración", abs(pf["duracion"] - esperada) <= tol,
          f"{pf['duracion']:.2f} s; esperada {esperada:.2f} s (±{tol:.2f}); editado {pe['duracion']:.2f} s")
    # Subtítulos: muestras fuera de los ganchos (el punch-in cambia toda la imagen).
    ganchos = props.get("ganchos") or []
    grupos = [g for g in props.get("subtitulos") or []
              if not any(x["inicio"] - 0.1 <= (g["inicio"] + g["fin"]) / 2 <= x["fin"] + 0.4 for x in ganchos)]
    paso = max(1, len(grupos) // 8)
    fallos, vistos = [], 0
    for g in grupos[::paso][:8]:
        t = (g["inicio"] + g["fin"]) / 2
        caja, por_que = _caja_subtitulo(final, editado, t, w, h)
        texto = " ".join(p["texto"] for p in g["palabras"])
        if caja is None:
            fallos.append(f"«{texto}»: {por_que}")
            continue
        x0, y0, x1, y1 = caja
        fuera = []
        if y0 < zona["arriba"]:
            fuera.append(f"arriba (y={y0} < {zona['arriba']})")
        if y1 > h - zona["abajo"]:
            fuera.append(f"abajo (y={y1} > {h - zona['abajo']})")
        if x0 < zona["izquierda"]:
            fuera.append(f"izquierda (x={x0})")
        if x1 > w - zona["derecha"]:
            fuera.append(f"derecha (x={x1} > {w - zona['derecha']})")
        if fuera:
            fallos.append(f"«{texto}» t={t:.2f} s fuera de la zona segura: {', '.join(fuera)}")
        else:
            vistos += 1
    check("subtítulos en pantalla", grupos and not fallos,
          (f"{vistos} muestra(s) visibles y dentro de la zona segura" if not fallos else "; ".join(fallos[:4]))
          if grupos else "no hay subtítulos que comprobar")
    lag, corr = _desfase(final, editado)
    # Desfase del contenedor: el audio empieza más tarde que el vídeo (lo respeta cualquier reproductor, pero la
    # envolvente extraída no lo ve).
    st = _inicios(final)
    cont = round(st.get("audio", 0.0) - st.get("video", 0.0), 3)
    check("audio sincronizado", lag is not None and abs(lag) <= 1 / fps and corr >= 0.6 and abs(cont) <= 1 / fps,
          f"desfase de la señal {lag if lag is not None else '?'} s, del contenedor {cont} s (máx {1 / fps:.3f} "
          f"cada uno), parecido {corr}")
    out = {"ok": all(c["ok"] for c in checks), "final": final, "checks": checks}
    out["diagnostico"] = "OK" if out["ok"] else "RECHAZADO: " + " | ".join(
        f"{c['nombre']}: {c['detalle']}" for c in checks if not c["ok"])
    escribir_json(carpeta / "qc.json", out)
    return out


if __name__ == "__main__":
    asegurar_venv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--final")
    a = ap.parse_args()
    r = qc(a.carpeta, a.final)
    print(r["diagnostico"])
    for c in r["checks"]:
        print(f"  [{'OK' if c['ok'] else 'FALLA'}] {c['nombre']}: {c['detalle']}")
    sys.exit(0 if r["ok"] else 1)
