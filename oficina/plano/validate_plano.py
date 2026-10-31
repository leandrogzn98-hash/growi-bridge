"""Validador de plano.json (t-oficina-plano-050, spec 7 de 18).

  python validate_plano.py [plano.json] [--json] [--autoprueba] [--png salida.png]

Comprueba: JSON valido y con sus claves; ids unicos; todo dentro de la rejilla; sin solapes entre
obstaculos (mesas, paredes, tablon, bandeja, mesa de despacho, buzones, puntos de interes); sillas y
accesos sobre baldosas libres; BFS desde la entrada (4 vecinos, sin teletransporte) hasta cada silla,
cada acceso, el frente del tablon, la silla del gerente y la mesa de Runa; los 14 personajes con su
silla y su mesa (Runa sin silla fija); tablon junto a la gerencia y telefono en la mesa del gerente;
los 5 puntos de interes con su capacidad (= sus accesos); taller 3D sin mesa de tecleo; Gemini en
obras con sus 2 sillas vacias con cartel. Sale con 1 al primer bloque con fallos y los lista todos.
"""
import copy
import json
import sys
from collections import deque
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CAP_MIN = {"cafe": 2, "ventana": 2, "bano": 1, "planta": 1, "pasillo": 1}
DEPTOS = ("claude", "local", "taller3d", "codex", "gemini")


class Plano:
    def __init__(self, d):
        self.d = d
        r = d["rejilla"]
        self.W, self.H = r["ancho"], r["alto"]


def _celdas(rect):
    return {(x, y) for x in range(rect["x"], rect["x"] + rect["w"]) for y in range(rect["y"], rect["y"] + rect["h"])}


def obstaculos(d):
    """[(id, rect)] de todo lo que no se puede pisar."""
    o = [(p["id"], p["rect"]) for p in d.get("paredes", [])]
    o += [(m["id"], m["rect"]) for m in d.get("mesas", [])]
    o += [(d["tablon"]["id"], d["tablon"]["rect"])]
    o += [(d["despacho"]["mesa"]["id"], d["despacho"]["mesa"]["rect"])]
    o += [(d["despacho"]["bandeja_entrada"]["id"], d["despacho"]["bandeja_entrada"]["rect"])]
    o += [(b["id"], b["rect"]) for b in d.get("taller3d", {}).get("buzones", [])]
    o += [(p["id"], p["rect"]) for p in d.get("puntos_interes", [])]
    return o


def bfs(W, H, bloqueadas, inicio):
    dist = {tuple(inicio): 0}
    q = deque([tuple(inicio)])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in bloqueadas and (nx, ny) not in dist:
                dist[(nx, ny)] = dist[(x, y)] + 1
                q.append((nx, ny))
    return dist


def _vecinas(rect):
    c = _celdas(rect)
    return {(x + dx, y + dy) for x, y in c for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - c


def validar(d):
    """-> (fallos, informe). fallos vacio = el plano pasa."""
    F, info = [], {}
    # 1. estructura
    for k in ("rejilla", "entrada", "departamentos", "mesas", "sillas", "personal", "despacho", "tablon",
              "telefono", "taller3d", "puntos_interes"):
        if k not in d:
            F.append(f"falta la clave «{k}»")
    if F:
        return F, info
    W, H = d["rejilla"]["ancho"], d["rejilla"]["alto"]
    if d["rejilla"].get("teletransporte"):
        F.append("rejilla.teletransporte debe ser false: no hay teletransporte")
    ids = [x["id"] for k in ("paredes", "puertas", "departamentos", "mesas", "sillas", "puntos_interes")
           for x in d.get(k, [])]
    ids += [d["tablon"]["id"], d["telefono"]["id"], d["despacho"]["mesa"]["id"], d["despacho"]["bandeja_entrada"]["id"]]
    ids += [b["id"] for b in d["taller3d"].get("buzones", [])]
    rep = sorted({i for i in ids if ids.count(i) > 1})
    if rep:
        F.append(f"ids repetidos: {', '.join(rep)}")
    # 2. dentro de la rejilla y sin solapes
    obs = obstaculos(d)
    ocup = {}
    for oid, r in obs:
        if r["w"] < 1 or r["h"] < 1:
            F.append(f"«{oid}»: rectángulo vacío ({r})")
            continue
        if r["x"] < 0 or r["y"] < 0 or r["x"] + r["w"] > W or r["y"] + r["h"] > H:
            F.append(f"«{oid}» se sale de la rejilla {W}x{H}: {r}")
        for c in _celdas(r):
            if c in ocup:
                F.append(f"solape: «{oid}» y «{ocup[c]}» comparten la baldosa {list(c)}")
                break
            ocup[c] = oid
    bloq = set(ocup)
    pisables = [("entrada", d["entrada"]["punto"])]
    pisables += [(s["id"], s["punto"]) for s in d["sillas"]]
    pisables += [(f"{p['id']} (acceso)", a) for p in d["puntos_interes"] for a in p.get("acceso", [])]
    pisables += [(f"{b['id']} (acceso)", a) for b in d["taller3d"].get("buzones", []) for a in b.get("acceso", [])]
    pisables += [("tablon (frente)", a) for a in d["tablon"].get("frente", [])]
    pisables += [(p["id"], p["punto"]) for p in d.get("puertas", [])]
    for pid, (x, y) in pisables:
        if not (0 <= x < W and 0 <= y < H):
            F.append(f"«{pid}» fuera de la rejilla: {[x, y]}")
        elif (x, y) in bloq:
            F.append(f"«{pid}» está encima de un obstáculo («{ocup[(x, y)]}») en {[x, y]}")
    sillas_p = [tuple(s["punto"]) for s in d["sillas"]]
    for s in {p for p in sillas_p if sillas_p.count(p) > 1}:
        F.append(f"dos sillas en la misma baldosa {list(s)}")
    if F:
        return F, info
    # 3. BFS desde la entrada
    dist = bfs(W, H, bloq, d["entrada"]["punto"])
    info["baldosas_alcanzables"] = len(dist)
    for pid, p in pisables:
        if tuple(p) not in dist:
            F.append(f"«{pid}» en {list(p)} no se alcanza a pie desde la entrada")
    rd = d["despacho"]["mesa"]["rect"]
    if not (_vecinas(rd) & set(dist)):
        F.append("la mesa de despacho de Runa no es alcanzable a pie (ninguna baldosa libre a su lado)")
    # 4. personal: 14 con silla y mesa, Runa sin silla fija
    pers = d["personal"]["personajes"]
    if len(pers) != 14:
        F.append(f"el personal debe tener 14 personajes, tiene {len(pers)}")
    mesas = {m["id"]: m for m in d["mesas"]}
    silla_de = {s["empleado"]: s for s in d["sillas"] if s.get("empleado")}
    for p in pers:
        s = silla_de.get(p["id"])
        if s is None:
            F.append(f"«{p['id']}» no tiene silla")
            continue
        m = mesas.get(s.get("mesa"))
        if m is None:
            F.append(f"la silla de «{p['id']}» no apunta a una mesa que exista ({s.get('mesa')})")
            continue
        if m.get("empleado") not in (p["id"], None) or (m.get("empleado") is None and p["id"] not in m.get("compartida_por", [])):
            F.append(f"la mesa «{m['id']}» no es de «{p['id']}»")
        if m["departamento"] != p["departamento"]:
            F.append(f"«{p['id']}» es de {p['departamento']} y su mesa está en {m['departamento']}")
        if not (_vecinas(m["rect"]) & {tuple(s["punto"])}):
            F.append(f"la silla de «{p['id']}» {s['punto']} no está pegada a su mesa «{m['id']}»")
    runa = next((x for x in d["personal"].get("fuera_del_personal", []) if x["id"] == "runa"), None)
    if runa is None:
        F.append("falta Runa en fuera_del_personal")
    elif runa.get("silla_fija") or "runa" in silla_de:
        F.append("Runa no tiene silla fija (casi siempre de pie o caminando)")
    for k in DEPTOS:
        if not any(x["id"] == k for x in d["departamentos"]):
            F.append(f"falta el departamento «{k}»")
    haiku = mesas.get("mesa_haiku")
    if not haiku or haiku["tipo"] != "escritorio_pequeno":
        F.append("Haiku debe tener un escritorio pequeño en la esquina de Claude")
    # 5. tablon junto a la gerencia, telefono en la mesa del gerente
    zg = next(x["zona"] for x in d["departamentos"] if x["id"] == "gerencia")
    tr = d["tablon"]["rect"]
    sep = max(tr["x"] - (zg["x"] + zg["w"]), zg["x"] - (tr["x"] + tr["w"]), tr["y"] - (zg["y"] + zg["h"]),
              zg["y"] - (tr["y"] + tr["h"]), 0)
    info["tablon_a_baldosas_de_gerencia"] = sep
    if sep > 2:
        F.append(f"el tablón está a {sep} baldosas de la gerencia (máximo 2): tiene que estar junto al gerente")
    tel = d["telefono"]
    mg = mesas.get(tel.get("en_mesa"))
    if tel.get("en_mesa") != "mesa_growi" or mg is None or tuple(tel["punto"]) not in _celdas(mg["rect"]):
        F.append("el teléfono tiene que estar sobre la mesa del gerente (mesa_growi)")
    # 6. puntos de interes con capacidad
    no_hay = {x["id"] for x in d.get("puntos_que_no_hay", [])}
    pis = {p["id"]: p for p in d["puntos_interes"]}
    for k, cap in CAP_MIN.items():
        if k in no_hay:
            continue
        p = pis.get(k)
        if p is None:
            F.append(f"falta el punto de interés «{k}» (si no lo hay, va en puntos_que_no_hay con su motivo)")
        elif p.get("capacidad") != cap and k != "pasillo":
            F.append(f"«{k}» debe tener capacidad {cap} (tiene {p.get('capacidad')})")
        elif not isinstance(p.get("capacidad"), int) or p["capacidad"] < 1:
            F.append(f"«{k}» sin capacidad válida")
        elif len(p.get("acceso", [])) != p["capacidad"]:
            F.append(f"«{k}»: capacidad {p['capacidad']} pero {len(p.get('acceso', []))} accesos (una baldosa por persona)")
    # 7. honestidad: taller 3D sin tecleo, Gemini en obras con 2 sillas vacias
    for m in d["mesas"]:
        if m["departamento"] == "taller3d" and m.get("tecleo"):
            F.append(f"«{m['id']}»: en el taller 3D nadie teclea (sus encargos se hacen fuera)")
    if len(d["taller3d"].get("buzones", [])) < 1 or not d["taller3d"].get("mensajero"):
        F.append("el taller 3D necesita su buzón de encargos y su mensajero")
    gem = next(x for x in d["departamentos"] if x["id"] == "gemini")
    if gem.get("estado") != "en_obras" or not gem.get("cartel"):
        F.append("Gemini es un local en obras con cartel")
    vac_g = [s for s in d["sillas"] if not s.get("empleado") and mesas.get(s.get("mesa"), {}).get("departamento") == "gemini"]
    if len(vac_g) != 2 or not all(s.get("cartel") for s in vac_g):
        F.append(f"Gemini debe tener 2 sillas vacías con cartel (tiene {len(vac_g)})")
    for m in d["mesas"]:
        if m["departamento"] == "gemini" and m.get("tecleo"):
            F.append(f"«{m['id']}»: en Gemini (en obras) nadie teclea")
    # 8. despacho: bandeja -> mesa de Runa -> puestos
    if not F:
        def dmin(rect):
            return min(dist[c] for c in _vecinas(rect) if c in dist)
        db, dr = dmin(d["despacho"]["bandeja_entrada"]["rect"]), dmin(rd)
        dpuestos = sorted(dist[tuple(s["punto"])] for s in d["sillas"] if s.get("empleado") in {p["id"] for p in pers})
        info["pasos_entrada_bandeja_runa_puesto_mediano"] = [db, dr, dpuestos[len(dpuestos) // 2]]
        if not db < dr < dpuestos[len(dpuestos) // 2]:
            F.append(f"la mesa de Runa debe quedar entre la bandeja y los puestos (pasos: bandeja {db}, Runa {dr}, "
                     f"puesto mediano {dpuestos[len(dpuestos) // 2]})")
        info["pasos_desde_entrada"] = {s["id"]: dist[tuple(s["punto"])] for s in d["sillas"]}
    info["obstaculos"] = len(obs)
    info["sillas"] = len(d["sillas"])
    info["personal"] = len(pers)
    return F, info


def autoprueba(d):
    """Rompe copias del plano y comprueba que el validador falla con el mensaje esperado."""
    casos = []

    def caso(nombre, mutar, espera):
        x = copy.deepcopy(d)
        mutar(x)
        f, _ = validar(x)
        casos.append({"caso": nombre, "falla": bool(f), "mensaje": f[:1], "ok": any(espera in m for m in f)})

    caso("solape mesa-punto", lambda x: x["puntos_interes"][0]["rect"].update(x=16, y=2), "solape")
    caso("silla encerrada", lambda x: x["paredes"].append(
        {"id": "muro", "rect": {"x": 36, "y": 0, "w": 1, "h": 9}}) or x["paredes"].append(
        {"id": "muro2", "rect": {"x": 37, "y": 0, "w": 1, "h": 9}}), "no se alcanza")
    caso("sin silla", lambda x: x.__setitem__("sillas", [s for s in x["sillas"] if s["empleado"] != "opus"]), "no tiene silla")
    caso("capacidad café", lambda x: x["puntos_interes"][0].update(capacidad=3), "capacidad")
    caso("teclea en taller", lambda x: next(m for m in x["mesas"] if m["id"] == "mesa_mensajero").update(tecleo=True),
         "nadie teclea")
    caso("teléfono fuera", lambda x: x["telefono"].update(punto=[30, 10]), "teléfono")
    caso("tablón lejos", lambda x: x["tablon"]["rect"].update(x=30, y=27), "tablón")
    caso("Runa con silla", lambda x: x["sillas"].append({"id": "silla_runa", "punto": [24, 16], "mesa": "mesa_despacho",
                                                          "empleado": "runa"}), "Runa")
    caso("JSON sin rejilla", lambda x: x.pop("rejilla"), "rejilla")
    caso("una silla de Gemini menos", lambda x: x.__setitem__(
        "sillas", [s for s in x["sillas"] if s["id"] != "silla_vacia_pro"]), "Gemini")
    return casos


def png(d, salida):
    """Dibuja el plano (sin arte: rectangulos) para revisarlo a ojo."""
    from PIL import Image, ImageDraw
    b = 20
    W, H = d["rejilla"]["ancho"], d["rejilla"]["alto"]
    im = Image.new("RGB", (W * b, H * b), (245, 245, 247))
    g = ImageDraw.Draw(im)
    col = {"gerencia": (245, 166, 35), "claude": (232, 131, 58), "codex": (46, 160, 90), "local": (140, 82, 200),
           "gemini": (160, 160, 160), "taller3d": (150, 105, 70), "despacho": (0, 122, 255),
           "especialistas": (90, 140, 160)}

    def r(rc, fill, outline=None):
        g.rectangle([rc["x"] * b, rc["y"] * b, (rc["x"] + rc["w"]) * b - 1, (rc["y"] + rc["h"]) * b - 1],
                    fill=fill, outline=outline)
    for dp in d["departamentos"]:
        c = col.get(dp["id"], (200, 200, 200))
        r(dp["zona"], tuple(int(v * 0.25 + 245 * 0.75) for v in c), c)
        g.text((dp["zona"]["x"] * b + 3, dp["zona"]["y"] * b + 2), dp["nombre"], fill=(29, 29, 31))
    for p in d["paredes"]:
        r(p["rect"], (60, 60, 64))
    for m in d["mesas"]:
        r(m["rect"], (180, 150, 110) if m.get("empleado") or m.get("compartida_por") else (215, 215, 215), (90, 70, 50))
    r(d["tablon"]["rect"], (29, 29, 31))
    r(d["despacho"]["mesa"]["rect"], (0, 122, 255))
    r(d["despacho"]["bandeja_entrada"]["rect"], (120, 170, 255))
    for bz in d["taller3d"]["buzones"]:
        r(bz["rect"], (150, 105, 70))
    for p in d["puntos_interes"]:
        r(p["rect"], (52, 199, 89))
        g.text((p["rect"]["x"] * b + 2, p["rect"]["y"] * b + 2), p["id"], fill=(0, 0, 0))
    for s in d["sillas"]:
        x, y = s["punto"]
        g.ellipse([x * b + 4, y * b + 4, x * b + b - 4, y * b + b - 4],
                  fill=(255, 59, 48) if s.get("empleado") else (255, 255, 255), outline=(29, 29, 31))
    x, y = d["entrada"]["punto"]
    g.rectangle([x * b, y * b, x * b + b - 1, y * b + b - 1], fill=(29, 29, 31))
    x, y = d["telefono"]["punto"]
    g.text((x * b + 4, y * b + 4), "T", fill=(255, 255, 255))
    im.save(salida)


def main():
    argv = sys.argv[1:]
    salida_png = argv[argv.index("--png") + 1] if "--png" in argv and argv.index("--png") + 1 < len(argv) else None
    args = [a for a in argv if not a.startswith("--") and a != salida_png]
    ruta = Path(args[0]) if args else AQUI / "plano.json"
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"FALLA: {ruta} no se puede leer como JSON ({type(e).__name__}: {e})")
        return 1
    f, info = validar(d)
    res = {"plano": str(ruta), "pasa": not f, "fallos": f, "informe": info}
    if "--autoprueba" in sys.argv:
        res["autoprueba"] = autoprueba(d)
    if salida_png:
        png(d, salida_png)
        res["png"] = salida_png
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("PASA" if not f else "FALLA")
        for m in f:
            print(f"  - {m}")
        for c in res.get("autoprueba", []):
            print(f"  autoprueba {c['caso']}: {'OK' if c['ok'] else 'NO DETECTADO'} {c['mensaje']}")
    return 0 if not f and all(c["ok"] for c in res.get("autoprueba", [])) else 1


if __name__ == "__main__":
    sys.exit(main())
