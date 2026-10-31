"""Parche t-oficina-estados-050 sobre oficina/protocolo/oficina_proto.py: el prototipo deriva con la
maquina de estados del spec 8 (oficina/estados/estados.py): 11 estados, tabla de 24 transiciones,
dormir con la «Z» compartida y respiracion de 1 px, clic para despertar (T24), rutina del gerente
y actividades sin tarea. P.derivar queda solo para «sin instalar» (deteccion: spec 11).

  python parche_oficina_estados_050.py <ruta a oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-estados-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:90])
    s = s.replace(old, new)


rep('import protocolo as P  # noqa: E402\n',
    'import protocolo as P  # noqa: E402\n'
    'for _d in (AQUI.parent / "estados", AQUI / "estados"):\n'
    '    if (_d / "estados.py").is_file():\n'
    '        sys.path.insert(0, str(_d))\n'
    '        break\n'
    'import estados as E  # noqa: E402  (t-oficina-estados-050: derivar_estado, transiciones, dormir)\n')
rep('ap.add_argument("--pos", default=None)\n',
    'ap.add_argument("--pos", default=None)\n'
    'ap.add_argument("--sueno-min", type=float, default=None)  # DEMO: acelera IDLE_SLEEP_MINUTES (se rotula)\n')
rep('A = ap.parse_args()\n',
    'A = ap.parse_args()\n'
    'if A.sueno_min is not None:\n'
    '    E.IDLE_SLEEP_MINUTES = A.sueno_min\n')

rep('_estado_bridge = ["esperando", "", None]\n', '''_estado_bridge = ["esperando", "", None]
RESULTS = OUTBOX / "runner-results"
APR_REG = OUTBOX / "aprobaciones-registro.jsonl"


def _leer_orq():
    """.orquestacion.json de las raices que salen en cola-live (pequenos; en su hilo, nunca en el render)
    y el canal de la ultima aprobacion de cada tarea (aprobaciones-registro.jsonl, las 400 ultimas)."""
    v = F["cola-live"].vista() if "cola-live" in F else {"datos": None}
    cola = v["datos"] if isinstance(v["datos"], dict) else {}
    orq = {}
    for t in cola.get("tareas") or []:
        raiz = t.get("raiz") or t.get("id")
        if raiz and raiz not in orq:
            est, d, _det, _n = P.leer_json(RESULTS / f"{raiz}.orquestacion.json")
            if est == "ok" and isinstance(d, dict):
                orq[raiz] = d
    apr = {}
    try:
        with open(APR_REG, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 200000))
            for linea in fh.read().decode("utf-8", "replace").splitlines()[-400:]:
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("evento") == "aprobada" and d.get("tarea"):
                    apr[d["tarea"]] = d.get("canal") or "app"
    except OSError:
        pass
    return "ok", {"orq": orq, "apr": apr}, "", 1
''')
rep('F["latido"] = P.Fuente(',
    'F["orq"] = P.Fuente("orq", RESULTS, lambda: 2, leer=_leer_orq, registro=metrica)\n'
    'F["latido"] = P.Fuente(')
rep('BOR = P.Borradores(DATOS / "borradores.json")\n',
    'BOR = P.Borradores(DATOS / "borradores.json")\n'
    'MEM = E.Memoria(registro=metrica)\n'
    'ACTIVIDAD = {}\n')

ini = 'def dibujar_sprite(pid, nombre, depto, est, t):\n'
i = s.index(ini)
j = s.index("\n\n\n", i)
s = s[:i] + '''_Z = None  # la «Z» flotante: UN sprite para todos los dormidos (no un frame por personaje)


def _z():
    global _Z
    if _Z is None:
        _Z = _fuente(16, True).render("Z", True, (90, 90, 110))
    return _Z


def dibujar_sprite(pid, nombre, depto, est, t, actividad=None):
    x, y = POS[pid]
    col = DEPTO[depto][0]
    caja = pygame.Rect(x, y, 32, 48)
    cara = (242, 230, 204)
    if est == P.SIN_INSTALAR:  # silla vacia: solo el contorno
        pygame.draw.rect(pantalla, C["gris"], caja, 1)
        texto("vacía", F12, C["suave"], x + 2, y + 16)
    elif est == E.SIN_SENAL:  # quieto, gris, con «?»: nunca teclea
        pygame.draw.rect(pantalla, C["gris"], caja)
        texto("?", F18, C["panel"], x + 11, y + 10)
    elif est == E.DORMIR:
        # encogido en la silla (6 px mas bajo), cabeza ladeada 3 px, ojos = dos rayitas,
        # respiracion lenta: el cuerpo sube y baja 1 px (periodo 4 s); la «Z» sube y se desvanece cada 3 s
        resp = 1 if (t % 4.0) < 2.0 else 0
        pygame.draw.rect(pantalla, col, (x, y + 6 - resp, 32, 42 + resp))
        pygame.draw.rect(pantalla, cara, (x + 11, y + 8 - resp, 16, 13))
        for ox in (14, 21):
            pygame.draw.line(pantalla, C["texto"], (x + ox, y + 14 - resp), (x + ox + 3, y + 14 - resp), 1)
        fase = ((t + (sum(map(ord, pid)) % 30) / 10.0) % 3.0) / 3.0
        z = _z()
        z.set_alpha(int(255 * (1 - fase)))
        pantalla.blit(z, (x + 26 + int(fase * 6), y - 2 - int(fase * 18)))
    else:
        dy = 0
        if est in (E.TRABAJANDO, E.EN_RONDA):  # animacion de trabajo: hay un evento real (live fresco)
            dy = (int(t * 8) % 2)
        elif est == E.SIN_TAREA:  # respiro: 1 px cada 2 s; estirarse: 2 px mas alto
            dy = 2 if actividad == "estirarse" else (1 if (t % 2.0) < 1.0 else 0)
        pygame.draw.rect(pantalla, col, caja.move(0, -dy))
        pygame.draw.rect(pantalla, cara, (x + 8, y + 3 - dy, 16, 14))  # cara
        if actividad == "parpadear":
            pygame.draw.line(pantalla, C["texto"], (x + 11, y + 9 - dy), (x + 21, y + 9 - dy), 1)
        if est in (E.TRABAJANDO, E.EN_RONDA):
            on = int(t * 8) % 2
            pygame.draw.rect(pantalla, C["texto"], (x - 2, y + 50, 36, 5))  # teclado
            pygame.draw.rect(pantalla, C["panel"], (x + 4 + on * 14, y + 51, 8, 3))
        marca = {E.EN_COLA: ("…", C["acento"]), E.ESPERANDO_APROBACION: ("!", C["ambar"]),
                 E.EN_REVISION: ("?", C["acento"]), E.EN_RONDA: ("↻", C["ambar"]), E.EN_PAUSA: ("II", C["suave"]),
                 E.TERMINADO: ("✓", C["verde"]), E.FALLIDO: ("×", C["rojo"])}.get(est)
        if marca:
            pygame.draw.circle(pantalla, marca[1], (x + 30, y + 2), 7)
            texto(marca[0], F12, C["panel"], x + 26, y - 7)
    texto(nombre, F12, C["texto"], x - 6, y + 56, 80)
    col_e = {E.TRABAJANDO: C["acento"], E.EN_COLA: C["acento"], E.ESPERANDO_APROBACION: C["ambar"],
             E.FALLIDO: C["rojo"], E.TERMINADO: C["verde"]}.get(est, C["suave"])
    etq = E.ETIQUETA.get(est) or ROT.get(est, est)
    if actividad and actividad not in ("respirar", "parpadear"):
        etq = f"{etq} · {actividad.replace('_', ' ')}"
    texto(etq, F12, col_e, x - 6, y + 70, 80)''' + s[j:]

rep('''        elif e.type == pygame.MOUSEBUTTONDOWN:
            foco = caja_in.collidepoint(e.pos)''', '''        elif e.type == pygame.MOUSEBUTTONDOWN:
            for _pid, (_x, _y) in POS.items():
                if pygame.Rect(_x, _y, 32, 48).collidepoint(e.pos) and MEM.despertar(_pid, "clic del jugador"):
                    log(f"{_pid} despierta: clic del jugador (T24)")
            foco = caja_in.collidepoint(e.pos)''')

rep('    est = P.derivar(V, "vivo" if eb == "vivo" else eb, ahora)\n', '''    est_p = P.derivar(V, "vivo" if eb == "vivo" else eb, ahora)

    def _d(k):
        v = V[k]
        return v["datos"] if v["clase"] in ("fresco", "viejo") and isinstance(v["datos"], dict) else None
    fu = {"status": _d("runner-status"), "status_edad": V["runner-status"]["edad_contenido"],
          "live": _d("runner-live"), "live_edad": V["runner-live"]["edad_contenido"],
          "cola": _d("cola-live"), "cola_edad": V["cola-live"]["edad_contenido"], "latido_ok": eb == "vivo"}
    oq = V["orq"]["datos"] if isinstance(V["orq"]["datos"], dict) else {"orq": {}, "apr": {}}
    asig = E.asignar(fu["cola"], ahora)
    activas = [x for x in (fu["cola"] or {}).get("tareas") or [] if x.get("estado") in E.TAREA_ACTIVA]
    est = {}
    if activas:  # Runa (despacha la cola) y Growi (la orquesta) no estan «sin tarea» mientras haya cola viva
        for pid in ("runa", "growi"):
            MEM.despertar(pid, "la cola tiene trabajo", ahora)
            MEM.libre_desde[pid] = ahora
    for pid, _n, _dep, _tipo, _cl in P.ROSTER:
        if est_p[pid][0] == P.SIN_INSTALAR:
            est[pid] = est_p[pid]
            continue
        fila = asig.get(pid)
        tr = E.EstadoTarea(fila, orq=oq["orq"].get((fila or {}).get("raiz") or (fila or {}).get("id")),
                           live=fu["live"], ahora=ahora) if fila else None
        e_, m_, _t = MEM.paso({"id": pid, "rol": _tipo}, tr, fu, ahora, oq["apr"].get((fila or {}).get("id")))
        est[pid] = (e_, m_)
    for pid in E.comprobar_serie({k: v[0] for k, v in est.items()}):
        est[pid] = (E.SIN_SENAL, "dos agentes trabajando a la vez: el runner es serie")
        metrica({"evento": "fuera_de_tabla", "agente": pid, "motivo": "serie"})
    ACTIVIDAD.clear()
    for pid, (e_, _m) in est.items():
        if pid == "growi" and e_ in (E.SIN_TAREA, E.SIN_SENAL):
            ACTIVIDAD[pid] = E.gerente_rutina(t, any(x.get("estado") in E.TAREA_ESPERA_HUMANO for x in activas),
                                              e_ == E.SIN_SENAL, [f"mesa_{k}" for k in ("clau", "dex", "luma")])[0]
        elif pid == "runa" and e_ == E.SIN_TAREA and activas:
            ACTIVIDAD[pid] = f"despachando {len(activas)}"
        elif e_ == E.SIN_TAREA:
            ACTIVIDAD[pid] = E.actividad_sin_tarea(pid, t)
''')
rep('        dibujar_sprite(pid, nombre, depto, est[pid][0], t)\n',
    '        dibujar_sprite(pid, nombre, depto, est[pid][0], t, ACTIVIDAD.get(pid))\n')
rep('        texto("DATOS DE EJEMPLO — no son del runner", F15, C["ambar"], 330, 8)\n',
    '        texto("DATOS DE EJEMPLO — no son del runner", F15, C["ambar"], 330, 8)\n'
    '    if A.sueno_min is not None:\n'
    '        texto(f"DEMO: se duermen a los {A.sueno_min * 60:.0f} s sin tarea", F13, C["ambar"], 600, 488)\n')
s = s.replace('if v[0] == P.SIN_SENAL)} sin señal', 'if v[0] == E.SIN_SENAL)} sin señal')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p} (crlf={crlf}); marca t-oficina-estados-050")
