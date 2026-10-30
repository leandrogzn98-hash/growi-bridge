"""Edita un crudo vertical de punta a punta. Es lo que corre la skill (a mano o como tarea del runner).

  python editar.py --crudo C:\\ruta\\crudo.mp4 --salida C:\\ruta\\trabajo [--estilo reel-ganchos] [--marca summit]
                   [--director reglas|claude] [--modelo haiku] [--ojos no|gemini] [--solo-cortes | --cortes cortes.json]

Pipeline: Whisper local -> silencedetect -> [Gemini mira] -> director (lista de cortes) -> COSTO ESTIMADO ->
ffmpeg (corte + -14 LUFS) -> Remotion (1080x1920, 30 fps, subtítulos palabra por palabra) -> QC -> reporte.
--solo-cortes para después de escribir cortes.md (para revisar la lista antes de renderizar); --cortes retoma con
una lista revisada. Sale 0 si el vídeo pasó el QC, 1 si se rechazó o falló, 2 si quedó esperando aprobación.
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

from comun import ahora, asegurar_venv, cargar_estilo, escribir_json, leer_json, probe


def _md_cortes(d, crudo):
    out = [f"# Lista de cortes — {Path(crudo).name}", "", f"Director: {d['motor']}. Gancho: «{d['gancho']}».",
           "Ganchos propuestos: " + " · ".join(f"«{g}»" for g in d["ganchos"]), "",
           "| Desde | Hasta | Seg | Qué se quita | Por qué |", "|---|---|---|---|---|"]
    for c in d["cortes"]:
        out.append(f"| {c['desde']:.2f} | {c['hasta']:.2f} | {c['segundos']:.2f} | {c['texto'] or '(silencio)'} | "
                   f"{c['motivo']} |")
    out += ["", "Se queda: " + ", ".join(f"{a:.2f}–{b:.2f}" for a, b in d["segmentos"])]
    return "\n".join(out) + "\n"


def editar(crudo, salida, estilo="reel-ganchos", marca=None, director="reglas", modelo="haiku", ojos="no",
           solo_cortes=False, cortes=None, recorte_previo=None):
    from costo import estimar
    import director as dirmod
    import render
    from qc import qc
    from transcribir import silencios, transcribir
    t0 = time.time()
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    rep = {"crudo": str(crudo), "estilo": estilo, "marca": marca, "director": director, "inicio": ahora(),
           "eventos": [], "estado": "en curso"}

    def ev(que, **datos):
        rep["eventos"].append(dict(datos, que=que, hora=ahora(), seg=round(time.time() - t0, 1)))
        escribir_json(salida / "reporte.json", rep)

    try:
        e, de_marca = cargar_estilo(estilo, marca)
        rep["marca_aplicada"] = de_marca
        info = probe(crudo)
        rep["crudo_info"] = info
        ev("crudo", **info)
        tr = transcribir(crudo, salida, e["whisper_modelo"])
        ev("transcripción", palabras=len(tr["palabras"]), modelo=tr["modelo"], segundos_whisper=tr["segundos"])
        sil = silencios(crudo, e["umbral_pausa_s"])
        ev("pausas", silencios=len(sil), umbral_s=e["umbral_pausa_s"])
        vision = None
        if ojos == "gemini":
            import ojos as ojosmod
            vision = ojosmod.mirar(crudo, salida, e)
            ev("ojos", **{k: v for k, v in vision.items() if k != "vision"})
        # Costo ANTES de gastar nada y antes del render.
        pal = tr["palabras"]
        prompt = dirmod.prompt_claude(dirmod._frases(pal, e["umbral_pausa_s"])) if director == "claude" else None
        est = estimar(e, info["duracion"], prompt, director, ojos if ojos == "gemini" else None, modelo)
        rep["costo_estimado"] = est
        escribir_json(salida / "costo.json", est)
        ev("costo estimado (antes de renderizar)", resumen=est["resumen"])
        if cortes:
            d = leer_json(cortes)
            ev("cortes aprobados", archivo=str(cortes))
        else:
            d = dirmod.dirigir(pal, sil, e, info["duracion"], director, modelo, vision)
            escribir_json(salida / "director.json", d)
            cr = d.get("costo_real") or {}
            if cr.get("usd") is not None:
                from costo import anotar_real
                anotar_real("director", modelo, cr["usd"], cr.get("tokens_entrada"), cr.get("tokens_salida"))
            (salida / "cortes.md").write_text(_md_cortes(d, crudo), encoding="utf-8")
            ev("lista de cortes", cortes=len(d["cortes"]), segmentos=len(d["segmentos"]), gancho=d["gancho"],
               costo_real=d.get("costo_real"))
        if solo_cortes:
            rep["estado"] = "esperando aprobación"
            ev("pausa", nota=f"revisa {salida / 'cortes.md'} y retoma con --cortes {salida / 'director.json'}")
            return rep
        dur = render.cortar(crudo, d["segmentos"], e, salida / "editado.mp4")
        ev("corte y audio", duracion_s=round(dur, 2), quitado_s=round(info["duracion"] - dur, 2))
        subs = render.subtitulos(pal, d["palabras_quitadas"], d["segmentos"], e, dur)
        sub = dict(e["subtitulo"], zoom_gancho=e["zoom_gancho"], zona=e["zona_segura"])
        props = {"video": "editado.mp4", "duracion_s": round(probe(salida / "editado.mp4")["duracion"], 3),
                 "fps": e["fps"], "ancho": e["ancho"], "alto": e["alto"], "subtitulos": subs, "estilo": sub,
                 "ganchos": [{"inicio": 0, "fin": e.get("gancho_s", 3.0), "texto": d["gancho"]}] if e["gancho"] else []}
        ev("render: inicio", grupos_subtitulo=len(subs), max_palabras=max((len(g["palabras"]) for g in subs), default=0))
        render.remotion(salida, props, salida / "final.mp4")
        ev("render: fin")
        q = qc(salida)
        rep["qc"] = q
        if not q["ok"]:
            (salida / "final.mp4").replace(salida / "final.RECHAZADO.mp4")
        ev("QC", ok=q["ok"], diagnostico=q["diagnostico"])
        rep["costo_real"] = {"director": d.get("costo_real"), "ojos": None if not vision else
                             {k: vision.get(k) for k in ("tokens_entrada", "tokens_salida")}}
        rep["estado"] = "listo" if q["ok"] else "rechazado por QC"
        rep["final"] = str(salida / ("final.mp4" if q["ok"] else "final.RECHAZADO.mp4"))
        rep["duracion_final_s"] = props["duracion_s"]
    except Exception as ex:  # noqa: BLE001 - el lote sigue con el siguiente vídeo
        rep["estado"] = "error"
        rep["error"] = f"{type(ex).__name__}: {ex}"
        rep["traza"] = traceback.format_exc()[-2000:]
    finally:
        rep["fin"] = ahora()
        rep["segundos"] = round(time.time() - t0, 1)
        escribir_json(salida / "reporte.json", rep)
        (salida / "reporte.md").write_text(reporte_md(rep), encoding="utf-8")
    return rep


def reporte_md(r):
    c = r.get("costo_estimado") or {}
    q = r.get("qc") or {}
    out = [f"# Reporte — {Path(r['crudo']).name}", "", f"- Estado: **{r['estado']}**",
           f"- Estilo: {r['estilo']}; marca: {r.get('marca') or '—'}; director: {r['director']}",
           f"- Costo estimado (antes de renderizar): {c.get('resumen', '—')}"]
    if r.get("marca_aplicada"):
        out.append("- Memoria de marca aplicada: " + "; ".join(r["marca_aplicada"]))
    if r.get("final"):
        out.append(f"- Final: `{r['final']}` ({r.get('duracion_final_s')} s; crudo "
                   f"{(r.get('crudo_info') or {}).get('duracion', 0):.1f} s)")
    if q:
        out.append(f"- QC: {q.get('diagnostico')}")
        out += [f"  - [{'OK' if x['ok'] else 'FALLA'}] {x['nombre']}: {x['detalle']}" for x in q.get("checks", [])]
    if r.get("error"):
        out.append(f"- Error: {r['error']}")
    out += ["", "## Pasos", ""] + [f"- {e['seg']:>6} s · {e['que']}" + (
        f": {json.dumps({k: v for k, v in e.items() if k not in ('que', 'hora', 'seg')}, ensure_ascii=False)}"
        if len(e) > 3 else "") for e in r.get("eventos", [])]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    asegurar_venv()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crudo", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--estilo", default="reel-ganchos")
    ap.add_argument("--marca")
    ap.add_argument("--director", choices=("reglas", "claude"), default="reglas")
    ap.add_argument("--modelo", default="haiku")
    ap.add_argument("--ojos", choices=("no", "gemini"), default="no")
    ap.add_argument("--solo-cortes", action="store_true")
    ap.add_argument("--cortes")
    a = ap.parse_args()
    r = editar(a.crudo, a.salida, a.estilo, a.marca, a.director, a.modelo, a.ojos, a.solo_cortes, a.cortes)
    print((Path(a.salida) / "reporte.md").read_text(encoding="utf-8"))
    sys.exit(2 if r["estado"] == "esperando aprobación" else 0 if r["estado"] == "listo" else 1)
