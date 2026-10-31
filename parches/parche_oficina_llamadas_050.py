"""Parche t-oficina-llamadas-050 sobre oficina/protocolo/oficina_proto.py: la llamada en curso se dibuja
desde oficina/llamadas/llamadas.py (fase real): linea punteada tenue gerente <-> jefe del departamento,
temporizador discreto (ambar a partir de 3 min), bocadillo del jefe y del gerente; ocupado con «posicion N de M».

  python parche_oficina_llamadas_050.py <oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-llamadas-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)


rep('import telefono as TF  # noqa: E402  (t-oficina-telefono-050: el telefono al gerente)\n',
    'import telefono as TF  # noqa: E402  (t-oficina-telefono-050: el telefono al gerente)\n'
    'sys.path.insert(0, str(AQUI.parent / "llamadas"))\n'
    'import llamadas as LL  # noqa: E402  (t-oficina-llamadas-050: la llamada que se ve = la invocacion real)\n')
rep('    # ---- telefono al gerente (t-oficina-telefono-050): una linea, sin historial\n', '''    # ---- llamada en curso (t-oficina-llamadas-050): solo si hay una fase real que mostrar
    _motores = set(((V["engines"]["datos"] or {}).get("motores") or {}).keys()) if isinstance(V["engines"]["datos"], dict) else set()
    _llam = None
    for _f in (fu["cola"] or {}).get("tareas") or []:
        if _f.get("estado") in ("en_curso", "en_cola", "esperando_aprobacion") or _f.get("proximo_intento"):
            _l = LL.llamada(_f, fu["cola"], fu["live"], fu["status"], _motores, ahora, fu["live_edad"])
            if _l["fase"] and (_llam is None or _l["fase"] in ("marcando", "timbre", "en_linea", "encendiendo", "buzon")):
                _llam = _l
                if _l["fase"] in ("marcando", "timbre", "en_linea", "encendiendo", "buzon"):
                    break
    if _llam:
        gx, gy = POS["growi"]
        jefe = _llam.get("jefe")
        if _llam["linea"] and jefe in POS:
            jx, jy = POS[jefe]
            n = 24
            for k in range(0, n, 2):  # linea punteada tenue
                a, b = k / n, (k + 1) / n
                pygame.draw.line(pantalla, C["linea"], (gx + 16 + (jx - gx) * a, gy + 10 + (jy - gy) * a),
                                 (gx + 16 + (jx - gx) * b, gy + 10 + (jy - gy) * b), 2)
            if _llam.get("jefe_dice"):
                texto(_llam["jefe_dice"], F12, C["texto"], jx - 4, jy - 18, 160)
        if _llam.get("duracion"):
            texto(_llam["duracion"], F13, C["ambar"] if _llam["ambar"] else C["suave"], gx + 40, gy + 20)
        linea_g = _llam.get("gerente") or ""
        if _llam["fase"] == "ocupado" and _llam.get("posicion") is None:
            linea_g = linea_g or "En cola, sin posición."
        if linea_g and not (TEL.bocadillo and time.time() - TEL.bocadillo[1] < 8):
            texto(f"[{_llam['fase']}] {linea_g}", F12, C["rojo"] if _llam["fase"] in ("no_contesta", "necesita_revision",
                  "suena_en_vacio") else C["texto"], 30, 524, W - 60)
    # ---- telefono al gerente (t-oficina-telefono-050): una linea, sin historial
''')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p}; marca t-oficina-llamadas-050")
