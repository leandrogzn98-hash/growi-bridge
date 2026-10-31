"""Deteccion honesta del personal de la oficina (t-oficina-empleados-050).

Un empleado solo «existe» si su modelo, motor, herramienta o skill esta instalado y se detecta en ESTE PC.
Si no, su silla esta vacia con cartel («sin instalar» con el motivo, o «sin señal» si no se pudo leer).
Fuentes (solo lectura): engines.json, runner-status.json (motores: disponible + motivo, lo escribe el runner),
las skills de Claude Code (~/.claude/skills/*/SKILL.md), las skills de Bridge (<app>/skills/*/SKILL.md) y,
para Blender, blender.exe (es una herramienta de Bridge, no una skill).

  python deteccion.py [--app <carpeta de la app>] [--json]
"""
import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

PERSONAL = [  # (id, departamento, como se detecta)
    ("growi", "gerencia", ("bridge",)),
    ("clau", "claude", ("motor", "claude")), ("sonny", "claude", ("modelo", "claude", "sonnet")),
    ("opus", "claude", ("modelo", "claude", "opus")), ("haiku", "claude", ("modelo", "claude", "haiku")),
    ("cody", "codex", ("motor", "codex")), ("dex", "codex", ("motor", "codex")),
    ("luma", "local", ("alguno", ("llama", "ollama"))), ("hermes_directo", "local", ("motor", "llama")),
    ("hermes_ollama", "local", ("motor", "ollama")),
    ("gemi", "gemini", ("motor", "gemini")),
    ("mensajero", "taller3d", ("motor", "meshy")),
    ("blender", "especialistas", ("herramienta", "blender")),
    ("tripo", "especialistas", ("skill", "tripo")),
]
SILLAS_VACIAS_FIJAS = [  # promesas honestas de que ahi falta gente (plano.json)
    ("silla_vacia_flash", "gemini", "Flash — por instalar"), ("silla_vacia_pro", "gemini", "Pro — por instalar"),
    ("silla_vacia_qwen", "local", "Qwen — en obras"), ("silla_vacia_gemma", "local", "Gemma — en obras"),
]


def _leer(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def skills_instaladas(app):
    out = {}
    for base, origen in ((Path.home() / ".claude" / "skills", "Claude Code"), (Path(app) / "skills", "Bridge")):
        for s in base.glob("*/SKILL.md"):
            out[s.parent.name.lower()] = f"skill de {origen} ({s.parent})"
    return out


def blender_exe():
    exe = shutil.which("blender")
    if exe:
        return exe
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if base:
            c = sorted(Path(base, "Blender Foundation").glob("Blender*/blender.exe"))
            if c:
                return str(c[-1])
    return None


def detectar(app, share=None, ahora=None):
    app = Path(app)
    share = Path(share) if share else app / "share"
    ahora = datetime.now().timestamp() if ahora is None else ahora
    engines = _leer(app / "engines.json") or {}
    motores_desc = engines.get("motores") or {}
    ids_desc = set(motores_desc) if isinstance(motores_desc, dict) else {m.get("id") for m in motores_desc}
    st = _leer(share / "outbox" / "runner-status.json")
    edad = None
    if st and st.get("last_poll"):
        try:
            edad = ahora - datetime.fromisoformat(st["last_poll"]).timestamp()
        except ValueError:
            edad = None
    mot = (st or {}).get("motores") or {}
    skills = skills_instaladas(app)
    res = {}
    for pid, depto, como in PERSONAL:
        tipo = como[0]
        if tipo == "bridge":
            ok, motivo = True, "es el Bridge (el orquestador)"
        elif tipo in ("motor", "modelo", "alguno"):
            nombres = como[1] if tipo == "alguno" else (como[1],)
            if st is None:
                ok, motivo = None, "runner-status.json ausente o roto: sin señal"
            else:
                vistos = [(n, mot.get(n)) for n in nombres]
                buenos = [n for n, m in vistos if m and m.get("disponible")]
                if buenos:
                    ok = True
                    motivo = "; ".join(f"{n}: {mot[n].get('motivo')}" for n in buenos)
                    if tipo == "modelo":
                        motivo += f" (modelo {como[2]}: lo da Claude Code; no se prueba el alias por separado)"
                else:
                    ok = False
                    motivo = "; ".join(f"{n}: " + ((m or {}).get("motivo") or ("no está en engines.json" if n not in ids_desc
                                                                               else "el runner no lo ha probado"))
                                       for n, m in vistos)
                if edad is not None and edad > 600 and ok:
                    motivo += f" (dato de hace {edad / 60:.0f} min)"
        elif tipo == "herramienta":
            exe = blender_exe()
            ok, motivo = (True, f"herramienta de Bridge: {exe}") if exe else (False, "no hay blender.exe en este PC")
        else:  # skill
            k = como[1]
            if k in skills:
                ok, motivo = True, skills[k]
            else:
                ok, motivo = False, (f"no hay skill «{k}» en ~/.claude/skills ni en las skills de Bridge "
                                     "(duda 16: ¿motor o skill? sin decidir)")
        silla = "ocupada" if ok else ("sin señal" if ok is None else "vacía · sin instalar")
        res[pid] = {"departamento": depto, "detectado": ok, "silla": silla, "motivo": motivo}
    if res.get("gemi", {}).get("detectado"):
        res["gemi"]["motivo"] += ("; departamento EN OBRAS: Gemi está (agy responde) pero sin empleados: "
                                  "Flash y Pro, sillas vacías")
    return {"personal": res, "sillas_vacias_fijas": [{"silla": s, "departamento": d, "cartel": c}
                                                     for s, d, c in SILLAS_VACIAS_FIJAS],
            "fuentes": {"engines": str(app / "engines.json"), "runner_status": str(share / "outbox" / "runner-status.json"),
                        "runner_status_edad_s": None if edad is None else round(edad), "skills": sorted(skills)}}


# ---- especialistas: se sientan en el departamento que ejecuta la tarea; si nadie los usa, sala de espera
DEPTO_DE_MOTOR = {"claude": "claude", "codex": "codex", "llama": "local", "ollama": "local", "gemini": "gemini",
                  "agy": "gemini"}


def silla_especialista(especialista, tarea):
    """-> (departamento, motivo). tarea = fila de cola-live con «herramienta» o «skills» y su motor (o None)."""
    if not tarea:
        return "especialistas", "sin tarea que lo use: sala de espera (visible, ocioso)"
    usa = set((tarea.get("skills") or [])) | ({(tarea.get("herramienta") or {}).get("nombre")}
                                               if isinstance(tarea.get("herramienta"), dict) else set())
    if especialista not in usa:
        return "especialistas", "la tarea no lo usa"
    depto = DEPTO_DE_MOTOR.get((tarea.get("motor") or "").lower())
    if depto is None:
        return "especialistas", f"motor {tarea.get('motor')!r} sin departamento: se queda en la sala"
    return depto, f"lo usa {tarea.get('id')} con {tarea.get('motor')}: se sienta en {depto}"


# ---- quien revisa: el personaje del motor/modelo de la revision (runner-live.revision), no «Haiku siempre»
def revisor_de(live):
    rev = (live or {}).get("revision") or {}
    motor, modelo = (rev.get("motor") or "").lower(), (rev.get("modelo") or "").lower()
    if not motor:
        return None
    if motor == "claude":
        return "haiku" if "haiku" in modelo else ("opus" if "opus" in modelo else "sonny")
    return {"codex": "dex", "llama": "hermes_directo", "ollama": "hermes_ollama", "gemini": "gemi"}.get(motor)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=str(Path.home() / "growi-bridge"))
    ap.add_argument("--json", action="store_true")
    A = ap.parse_args()
    d = detectar(A.app)
    if A.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        for pid, r in d["personal"].items():
            print(f"{pid:15s} {r['silla']:22s} {r['motivo'][:110]}")
