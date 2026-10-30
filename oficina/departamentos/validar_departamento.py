"""Valida la ficha de un departamento nuevo de la oficina (hoy: diseno-audiovisuales.json, t-oficina-depto-diseno-050).

Comprueba lo que se puede comprobar sin los specs 7/10/11: una líder con corbata y empleados sin ella, las 8
animaciones del sistema por personaje, identificadores únicos, que el color de corbata se distingue de los 4
departamentos, del gerente y de los tintes de pensamiento (ΔE CIE76 >= 20), los 5 servicios con su script real,
el pipeline de 4 pasos y la skill. Si existen plano.json, skin.json o validate_skins.py, dice si el
departamento ya está integrado; si no existen, lo marca FALTA (no lo inventa).

  python oficina/departamentos/validar_departamento.py [ficha.json]     (sale 0 si pasa)
"""

import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
ANIMACIONES = ["idle", "escribir", "caminar", "cafe", "telefono", "vagancia", "celebrar", "dormir"]  # spec 10
OCUPADOS = {  # corbatas y tintes ya usados (specs 9-11 y PALETA-Y-SKINS §2 y §15)
    "corbata Claude": "#D97757", "corbata Codex": "#00A67E", "corbata Gemini": "#4285F4",
    "corbata gerente (ámbar)": "#F5A623", "azul Summit": "#052048", "tinte amarillo": "#FFC53D",
    "tinte verde": "#34C759", "tinte blanco": "#F7F7F7", "tinte azul": "#007AFF", "tinte rojo": "#FF6363",
    "tinte negro": "#1A1A1C", "rubor": "#F2A0A8", "corbata Local (morado, aproximado)": "#7E57C2",
}
SERVICIOS = {"qc", "lotes", "costos", "marca", "repurposing"}


def _lab(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = lin(r), lin(g), lin(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(a, b):
    la, lb = _lab(a), _lab(b)
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5


def validar(ficha):
    d = json.loads(Path(ficha).read_text(encoding="utf-8"))
    res = []

    def check(nombre, ok, detalle, falta=False):
        res.append({"nombre": nombre, "estado": "FALTA" if falta else ("OK" if ok else "FALLA"), "detalle": detalle})

    ps = d.get("personajes") or []
    lideres = [p for p in ps if p.get("lider")]
    check("personajes", len(ps) == 3 and len(lideres) == 1,
          f"{len(ps)} personajes, {len(lideres)} líder(es): " + ", ".join(p["nombre"] for p in ps))
    check("corbatas", all(p.get("corbata") for p in lideres) and not any(p.get("corbata") for p in ps if not p.get("lider")),
          "la líder lleva corbata; los empleados no")
    malas = [p["id"] for p in ps if p.get("animaciones") != ANIMACIONES]
    check("8 animaciones", not malas, "todas con " + ", ".join(ANIMACIONES) if not malas else f"distintas en {malas}")
    ids = [p.get("identificador", "").split("(")[0].strip().lower() for p in ps]
    check("identificador único", len(set(ids)) == len(ids) and all(ids), "; ".join(ids))
    hexc = (d.get("corbata") or {}).get("hex", "")
    dist = sorted((round(delta_e(hexc, v), 1), k) for k, v in OCUPADOS.items())
    check("color de corbata distinto", dist[0][0] >= 20,
          f"{hexc}: el más cercano es {dist[0][1]} (ΔE {dist[0][0]}); siguiente {dist[1][1]} (ΔE {dist[1][0]})")
    check("color en la paleta de 24", False, "PALETA-Y-SKINS.md §1 no está en el PC: no se puede comprobar", falta=True)
    srv = {s["id"]: s for s in (d.get("fortalezas") or {}).get("servicios") or []}
    sin_script = [k for k, s in srv.items() if not (REPO / s.get("script", "")).is_file()]
    check("5 servicios", set(srv) == SERVICIOS and not sin_script,
          ", ".join(s["nombre"] for s in srv.values()) + (f"; sin script: {sin_script}" if sin_script else ""))
    pasos = " | ".join(p["paso"] for p in (d.get("fortalezas") or {}).get("pipeline") or [])
    check("pipeline", all(w in pasos for w in ("Whisper", "Claude", "Gemini", "Remotion")), pasos)
    check("skill", (REPO / (d.get("skill") or {}).get("ruta", "")).is_file(), (d.get("skill") or {}).get("ruta", ""))
    # Integración: solo si existen los archivos de los specs 7 y 10.
    planos = [p for p in REPO.rglob("plano.json") if ".git" not in p.parts]
    skins = [p for p in REPO.rglob("skin.json") if ".git" not in p.parts]
    vs = [p for p in REPO.rglob("validate_skins.py") if ".git" not in p.parts]
    if planos:
        txt = planos[0].read_text(encoding="utf-8")
        check("en plano.json", d["id"] in txt, str(planos[0]))
    else:
        check("en plano.json", False, "no existe plano.json (spec 7 sin ejecutar)", falta=True)
    if skins:
        txt = skins[0].read_text(encoding="utf-8")
        check("en skin.json", all(p["id"] in txt for p in ps), str(skins[0]))
    else:
        check("en skin.json", False, "no existe skin.json (spec 10 sin ejecutar)", falta=True)
    if not vs:
        check("validate_skins.py", False, "no existe (spec 10 sin ejecutar)", falta=True)
    return res


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ficha = sys.argv[1] if len(sys.argv) > 1 else AQUI / "diseno-audiovisuales.json"
    r = validar(ficha)
    for c in r:
        print(f"[{c['estado']}] {c['nombre']}: {c['detalle']}")
    fallas = [c for c in r if c["estado"] == "FALLA"]
    print(f"{sum(c['estado'] == 'OK' for c in r)} OK, {len(fallas)} FALLA, {sum(c['estado'] == 'FALTA' for c in r)} FALTA")
    sys.exit(1 if fallas else 0)
