"""Parche t-oficina-rendimiento-050 sobre oficina/protocolo/oficina_proto.py: escalera de degradacion (sensores
reales en un hilo), FPS 30/15/0 segun nivel / foco / minimizada, vagancia apagada desde el nivel 2, sprites
quietos desde el 3, DORMIDA en el 4 (sin render; sigue atendiendo eventos para despertar en < 1 s), CERRADA en
el 5 (sale con codigo 6), tecla A = modo ahorro (persistente), tecla Z = dormir, puntito de color y metricas.
Banderas de prueba (rotuladas): --sensores-falsos <json> (RAM/VRAM simuladas) y --sin-noche.

  python parche_oficina_rendimiento_050.py <oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-rendimiento-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)


rep('METRICAS = DATOS / f"metricas-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.jsonl"\n',
    'METRICAS = DATOS / f"metricas-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.jsonl"\n'
    '# t-oficina-rendimiento-050: datos de estado <= 50 MB con rotacion (solo las metricas propias, las mas viejas primero)\n'
    '_viejas = sorted(DATOS.glob("metricas-*.jsonl"), key=lambda q: q.stat().st_mtime)\n'
    'while _viejas and sum(q.stat().st_size for q in DATOS.glob("*") if q.is_file()) > 40 * 2 ** 20:\n'
    '    _q = _viejas.pop(0)\n'
    '    _q.unlink()\n'
    '    print(f"rotación: {_q.name} (datos de la oficina > 40 MB)", flush=True)\n')
rep('ap.add_argument("--sueno-min", type=float, default=None)',
    'ap.add_argument("--sensores-falsos", default=None)  # PRUEBA: JSON con ram_pct / vram_libre_mb simulados\n'
    'ap.add_argument("--sin-noche", action="store_true")  # PRUEBA: ignora el horario nocturno\n'
    'ap.add_argument("--sueno-min", type=float, default=None)')
rep('import bocadillos as BC  # noqa: E402  (t-oficina-bocadillos-050)\n',
    'import bocadillos as BC  # noqa: E402  (t-oficina-bocadillos-050)\n'
    'sys.path.insert(0, str(AQUI.parent / "rendimiento"))\n'
    'import rendimiento as RD  # noqa: E402  (t-oficina-rendimiento-050)\n')
rep('GB = BC.Gestor()\n',
    'GB = BC.Gestor()\n'
    'ESC = RD.Escalera(registro=lambda d_: (metrica(d_), log(f"nivel {d_[\'de\']} -> {d_[\'a\']}: {d_[\'motivo\']}")))\n'
    'SEN = RD.Sensores(os.getpid(), 1.0)\n'
    'SEN.arrancar()\n'
    'REND = {"ultimo_input": time.time(), "dormir": False, "dormida_desde": None, "nivel": 0, "fps": 30}\n')
# cualquier evento de entrada cuenta como «mirar» y despierta; A = ahorro; Z = dormir
rep('''    ahora = time.time()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:''', '''    ahora = time.time()
    if A.salir_a is not None and t >= A.salir_a and codigo is None:  # vale dormida y minimizada
        codigo, cierre_motivo = 0, f"--salir-a {A.salir_a}"
        break
    for e in pygame.event.get():
        if e.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN, pygame.MOUSEMOTION, pygame.TEXTINPUT):
            REND["ultimo_input"] = time.time()
            if REND["nivel"] == 4 and e.type != pygame.MOUSEMOTION:
                REND["dormir"] = False
                REND["despertar_t"] = time.time()  # el siguiente fotograma pintado mide el despertar
                _sw = dict(SEN.ultimo)
                if A.sensores_falsos:
                    try:
                        _sw.update(json.loads(Path(A.sensores_falsos).read_text(encoding="utf-8")))
                    except (OSError, ValueError):
                        pass
                ESC.despertar(dict(_sw, noche=False), time.time())
                REND["nivel"] = ESC.efectivo()
                log("despierta (entrada del usuario)")
        if e.type == pygame.KEYDOWN and e.key == pygame.K_a and not foco:
            ESC.ahorro = not ESC.ahorro
            log(f"modo ahorro {'activado' if ESC.ahorro else 'quitado'} (manual, persistente)")
            continue
        if e.type == pygame.KEYDOWN and e.key == pygame.K_z and not foco:
            REND["dormir"] = True
            log("dormir: lo pide el usuario")
            continue
        if e.type == pygame.QUIT:''')
# nivel antes de derivar: sensores reales (o falsos de prueba) + disparadores
rep('''    caido = _bridge_caido()
    if caido != caido_antes:''', '''    _sens = dict(SEN.ultimo)
    if A.sensores_falsos:
        try:
            _sens.update(json.loads(Path(A.sensores_falsos).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    _sens.update(sin_mirar_s=time.time() - REND["ultimo_input"], usuario_dormir=REND["dormir"],
                 noche=(not A.sin_noche) and RD.es_noche(datetime.now().hour))
    REND["nivel"] = ESC.paso(_sens, time.time())
    if REND["nivel"] >= 5:
        codigo, cierre_motivo = 6, f"cerrada por la escalera: {ESC.cambios[-1]['motivo'] if ESC.cambios else 'nivel 5'}"
        break
    OFV.vagancia_activa = REND["nivel"] < 2
    if REND["nivel"] == 4:  # DORMIDA: sin render; atiende eventos 4 veces por segundo para despertar rapido
        if REND["dormida_desde"] is None:
            REND["dormida_desde"] = time.time()
            metrica({"evento": "dormida", "motivo": ESC.cambios[-1]["motivo"] if ESC.cambios else ""})
        reloj.tick(4)
        continue
    REND["dormida_desde"] = None
    if not pygame.display.get_active():  # minimizada: 0 FPS, sin pintar nada (el proceso sigue y atiende el latido)
        continue
    caido = _bridge_caido()
    if caido != caido_antes:''')
# sprites quietos desde el nivel 3 (solo estados)
rep('''        dibujar_sprite(pid, nombre, depto, est[pid][0], t, ACTIVIDAD.get(pid))''',
    '''        dibujar_sprite(pid, nombre, depto, est[pid][0], 0.0 if REND["nivel"] >= 3 else t,
                       None if REND["nivel"] >= 3 else ACTIVIDAD.get(pid))''')
# puntito de color + metricas en vivo + boton de ahorro
rep('''    texto(f"Te necesitan: {_tn}", F15,''', '''    pygame.draw.circle(pantalla, RD.color(REND["nivel"]), (W - 446, 18), 6)
    texto(RD.metricas_texto(SEN.ultimo, REND["nivel"], reloj.get_fps(), "—"), F12, C["suave"], 20, 466, W - 40)
    texto(("Modo ahorro: ON (A)" if ESC.ahorro else "Modo ahorro (A)") + " · Dormir (Z)", F12,
          C["ambar"] if ESC.ahorro else C["suave"], W - 230, 76)
    texto(f"Te necesitan: {_tn}", F15,''')
# FPS segun nivel / foco / minimizada (30 es tope, no objetivo)
rep('''    dt = reloj.tick(30) / 1000.0''', '''    _f = RD.fps(REND["nivel"], pygame.key.get_focused(), not pygame.display.get_active())
    REND["fps"] = _f
    dt = reloj.tick(_f if _f else 4) / 1000.0''')
rep('''    pygame.display.flip()
''', '''    pygame.display.flip()
    if REND.get("despertar_t"):
        metrica({"evento": "despertar", "ms": round((time.time() - REND.pop("despertar_t")) * 1000, 1)})
''')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p}; marca t-oficina-rendimiento-050")
