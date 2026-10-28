"""Prueba del historial del portapapeles (ESTADO-PORTAPAPELES.md).

Copia aislada de growi-bridge.py. Usa el portapapeles REAL de Windows: guarda lo
que hubiera copiado antes y lo devuelve al terminar. Enciende el historial,
copia 3 textos de verdad (SetClipboardData), copia una «contraseña» y una
«clave», busca desde la paleta, copia de vuelta con Intro, marca «no guardar
nunca esto» y apaga el historial (que lo borra).

  python pruebas/prueba_portapapeles.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "portapapeles"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-pp-"))
    app = tmp / "app"
    app.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "onboarding_done": True}), encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"))
    spec = importlib.util.spec_from_file_location("gb_pp", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    gb.toast = lambda *a, **k: None
    ev = {"copia": str(tmp)}
    previo, _m = gb._pp_leer()  # lo que tenía copiado el usuario: se devuelve al final
    try:
        ev["por_defecto_apagado"] = gb.pp_activo()
        gb.pp_iniciar()
        gb._pp_poner("esto se copió con el historial APAGADO")
        time.sleep(1.6)
        ev["apagado_no_guarda"] = len(gb.pp_lista())
        # (a) encender y copiar 3 textos reales
        gb.pp_encender(True)
        textos = ["Precio para Aqualine: filtro X a 120 $", "Brief de Summit Maker: taller hands-on el sábado",
                  "Mensaje para Angelis: confirmo la sala del taller"]
        for t in textos:
            gb._pp_poner(t)
            time.sleep(1.6)
        ev["a_guardados"] = [(x["texto"], x["at"]) for x in gb.pp_lista()]
        # (c) una contraseña y una clave: no se guardan
        for t in ("Xk9#pL2$qW7!", "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx"):
            gb._pp_poner(t)
            time.sleep(1.6)
        ev["c_tras_secretos"] = len(gb.pp_lista())
        ev["c_secretos_guardados"] = [x["texto"] for x in gb.pp_lista() if x["texto"].startswith(("Xk9", "sk-ant"))]
        # (b) buscar desde la paleta e Intro = copiar de vuelta
        gb._pp_poner("otra cosa cualquiera")
        time.sleep(1.6)
        secciones = gb._palette_sections("summit taller")
        pp = [items for t, items in secciones if t.startswith("Portapapeles")]
        ev["b_paleta"] = [i["label"] for i in (pp[0] if pp else [])]
        if pp:
            pp[0][0]["fn"]()  # Intro
        time.sleep(0.3)
        ev["b_portapapeles_tras_intro"], _m = gb._pp_leer()
        # «no guardar nunca esto»
        x = next(i for i in gb.pp_lista() if i["texto"].startswith("Mensaje para Angelis"))
        gb.pp_borrar(x["id"], nunca=True)
        gb._pp_poner("Mensaje para Angelis: confirmo la sala del taller")
        time.sleep(1.6)
        ev["c_nunca_esto"] = [i["texto"] for i in gb.pp_lista() if i["texto"].startswith("Mensaje para Angelis")]
        # (e) todo local: el archivo no está en share\ y el puente no lo nombra
        try:
            gb.PP_FILE.relative_to(gb.SHARE)
            dentro_share = True
        except ValueError:
            dentro_share = False
        src = (app / "growi-bridge.py").read_text(encoding="utf-8")
        i = src.index("class BridgeHandler")
        fuente_puente = src[i:src.index("\nclass ", i + 10)]
        i = src.index("def config_exportar(")
        fuente_export = src[i:src.index("\ndef ", i + 10)]
        ev["e_local"] = {"archivo": str(gb.PP_FILE), "dentro_de_share": dentro_share,
                         "el_puente_lo_nombra": ("PP_FILE" in fuente_puente or "portapapeles" in fuente_puente),
                         "lo_exporta_config": "portapapeles" in fuente_export}
        # (d) apagar = borrar
        n = len(gb.pp_lista())
        gb.pp_encender(False, confirmar=False)
        ev["d_apagar"] = {"antes": n, "archivo_existe": gb.PP_FILE.exists(), "activo": gb.pp_activo()}
    finally:
        if previo is not None:
            gb._pp_poner(previo)  # el portapapeles del usuario, como estaba
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "portapapeles" in x][-12:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
