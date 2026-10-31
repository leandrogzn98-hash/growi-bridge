"""Parche t-oficina-vagancia-050 sobre oficina/protocolo/oficina_proto.py: los agentes sin tarea hacen vagancia
(oficina/vagancia/vagancia.py) en vez de la actividad simple del spec 8; la etiqueta muestra SIEMPRE el estado
real y, al lado, la actividad (R1); cada fotograma pasa el estado derivado a la vagancia (R2); tecla V =
«oficina seria» (R4), rotulado en pantalla. Dormir no entra en la vagancia.

  python parche_oficina_vagancia_050.py <oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-vagancia-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)


rep('import llamadas as LL  # noqa: E402  (t-oficina-llamadas-050: la llamada que se ve = la invocacion real)\n',
    'import llamadas as LL  # noqa: E402  (t-oficina-llamadas-050: la llamada que se ve = la invocacion real)\n'
    'sys.path.insert(0, str(AQUI.parent / "vagancia"))\n'
    'import vagancia as VG  # noqa: E402  (t-oficina-vagancia-050)\n')
rep('MEM = E.Memoria(registro=metrica)\n',
    'MEM = E.Memoria(registro=metrica)\n'
    '_PLANO = AQUI.parent / "plano" / "plano.json"\n'
    '_POIS = ({p_["id"]: p_["capacidad"] for p_ in json.loads(_PLANO.read_text(encoding="utf-8"))["puntos_interes"]}\n'
    '         if _PLANO.is_file() else {"cafe": 2, "pasillo": 3})\n'
    'OFV = VG.Oficina(_POIS, registro_raros=str(DATOS / "vagancia-raros.jsonl"))\n')
rep('''            if e.key == pygame.K_t and not foco:''', '''            if e.key == pygame.K_v and not foco:  # «oficina seria»: apaga la vagancia, no el sueño
                OFV.vagancia_activa = not OFV.vagancia_activa
                log(f"vagancia {'encendida' if OFV.vagancia_activa else 'apagada (oficina seria)'}")
                continue
            if e.key == pygame.K_t and not foco:''')
rep('''        elif e_ == E.SIN_TAREA:
            ACTIVIDAD[pid] = E.actividad_sin_tarea(pid, t)
''', '''        elif e_ == E.SIN_TAREA:
            ACTIVIDAD[pid] = E.actividad_sin_tarea(pid, t)
    for pid, (e_, _m) in est.items():  # R2: el estado real llega a la vagancia en el mismo fotograma
        if pid not in ("growi", "runa", "vigilante"):
            OFV.evento_estado(pid, e_, ahora)
    for _ag, _tipo, _dato in OFV.tick(ahora):
        if _tipo in ("raro", "bocadillo"):
            metrica({"evento": "vagancia_" + _tipo, "agente": _ag, "dato": _dato})
    for pid in list(ACTIVIDAD):
        _act = OFV.actividad_de(pid)
        if _act:
            ACTIVIDAD[pid] = _act
''')
rep('''        texto("Pulsa T (o el icono) para llamar al gerente.", F12, C["suave"], 30, H - 40)''',
    '''        texto("Pulsa T (o el icono) para llamar al gerente · V: "
              + ("vagancia encendida" if OFV.vagancia_activa else "oficina seria (vagancia apagada)"),
              F12, C["suave"], 30, H - 40)''')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p}; marca t-oficina-vagancia-050")
