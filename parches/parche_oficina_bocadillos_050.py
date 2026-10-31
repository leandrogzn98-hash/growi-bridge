"""Parche t-oficina-bocadillos-050 sobre oficina/protocolo/oficina_proto.py: bocadillos por el Gestor (FIFO 2 por
personaje, 3 visibles), con las 3 señales (dialogo + punto verde «real» / nube gris italica), contador
«Te necesitan: N» arriba (sin señal = «—»), y log diario <app>/oficina/AAAA-MM-DD.md (telefono y transiciones;
la charla no va). La oficina no emite avisos propios: la app ya avisa (ver bocadillos.politica_aviso).

  python parche_oficina_bocadillos_050.py <oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-bocadillos-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)


rep('import vagancia as VG  # noqa: E402  (t-oficina-vagancia-050)\n',
    'import vagancia as VG  # noqa: E402  (t-oficina-vagancia-050)\n'
    'sys.path.insert(0, str(AQUI.parent / "bocadillos"))\n'
    'import bocadillos as BC  # noqa: E402  (t-oficina-bocadillos-050)\n')
rep('OFV = VG.Oficina(',
    'GB = BC.Gestor()\n'
    'LOGD = BC.LogDiario(APP / "oficina")\n'
    '_ult_conf = [0]\n'
    'OFV = VG.Oficina(')
# transiciones -> log (una linea por estado) ; vagancia -> nube (sin log)
rep('''    for _ag, _tipo, _dato in OFV.tick(ahora):
        if _tipo in ("raro", "bocadillo"):
            metrica({"evento": "vagancia_" + _tipo, "agente": _ag, "dato": _dato})''',
    '''    for _ag, _tipo, _dato in OFV.tick(ahora):
        if _tipo in ("raro", "bocadillo"):
            metrica({"evento": "vagancia_" + _tipo, "agente": _ag, "dato": _dato})
        if _tipo == "bocadillo" and _dato and _dato != "...":
            GB.poner(BC.Bocadillo(_ag, "charla", _dato, ahora=ahora))  # nube, sin log
    for _c in TEL.confirmaciones[_ult_conf[0]:]:  # cada confirmacion del telefono: bocadillo + log con lo dicho
        _ref = LOGD.escribir("Leandro", "Growi", "teléfono al gerente", f"«{_c[0]}» → {_c[1]}", tipo="estado")
        GB.poner(BC.Bocadillo("growi", "aceptacion", _c[1], depto="Gerencia", ref_log=_ref, ahora=ahora))
    _ult_conf[0] = len(TEL.confirmaciones)''')
# el bocadillo del telefono se pinta por el gestor (y no a mano)
rep('''    if TEL.bocadillo and time.time() - TEL.bocadillo[1] < 8:
        gx, gy = POS["growi"]''', '''    for _b in GB.tick(ahora):  # bocadillos con las 3 señales (t-oficina-bocadillos-050)
        if _b.agente not in POS:
            continue
        bx, by = POS[_b.agente]
        es = BC.estilo(_b.tipo, _b.depto)
        fnt = F12
        ancho = min(260, 16 + fnt.size(_b.texto)[0])
        caja = pygame.Rect(bx + 16 - ancho // 2, by - 40, ancho, 22)
        caja.x = max(4, min(W - ancho - 4, caja.x))  # dentro de la ventana (la cola sigue apuntando al sprite)
        if es["forma"] == "nube":  # pensamiento: borde ondulado, sin cola recta, gris italica
            for k in range(0, ancho, 10):
                pygame.draw.circle(pantalla, C["panel"], (caja.x + k + 5, caja.y + 2), 6)
                pygame.draw.circle(pantalla, es["borde"], (caja.x + k + 5, caja.y + 2), 6, 1)
            pygame.draw.rect(pantalla, C["panel"], caja, border_radius=11)
            pygame.draw.circle(pantalla, es["borde"], (bx + 18, by - 12), 3, 1)
            fnt.set_italic(True)
            texto(_b.texto, fnt, es["texto"], caja.x + 8, caja.y + 3, ancho - 12)
            fnt.set_italic(False)
        else:  # dialogo: borde solido de 2 px del departamento y cola recta al sprite
            pygame.draw.rect(pantalla, C["panel"], caja, border_radius=8)
            pygame.draw.rect(pantalla, es["borde"], caja, 2, border_radius=8)
            pygame.draw.polygon(pantalla, es["borde"], [(bx + 12, caja.bottom), (bx + 20, caja.bottom), (bx + 16, by - 8)])
            texto(_b.texto, fnt, es["texto"], caja.x + 8, caja.y + 3, ancho - 24)
            if es["marca"] == "real":
                pygame.draw.circle(pantalla, C["verde"], (caja.right - 8, caja.y + 11), 4)
    if False:
        gx, gy = POS["growi"]''')
# contador «Te necesitan: N» arriba
rep('''    texto("Oficina Growi · prototipo de protocolo", F15, C["texto"], 20, 8)''',
    '''    texto("Oficina Growi · prototipo de protocolo", F15, C["texto"], 20, 8)
    _tn = BC.te_necesitan(fu["cola"] if "fu" in dir() else None)
    texto(f"Te necesitan: {_tn}", F15, C["ambar"] if _tn not in ("0", "—") else C["suave"], W - 430, 8)''')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p}; marca t-oficina-bocadillos-050")
