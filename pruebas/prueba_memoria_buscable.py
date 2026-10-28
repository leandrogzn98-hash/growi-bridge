"""Prueba de la memoria buscable (ESTADO-MEMORIA-BUSCABLE.md).

Memoria de PRUEBA (notas con fechas, una de hace 60 dias) en %TEMP%, y una
medida de tiempo sobre una COPIA de la memoria real del PC (de esa solo se
guardan cifras, nunca su texto: es personal).

  python pruebas/prueba_memoria_buscable.py
"""
import importlib.util, json, os, shutil, sys, tempfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-memb-"))
    (tmp / "app").mkdir()
    mem = tmp / "memory"
    mem.mkdir()
    hoy = date.today()
    viejo = (hoy - timedelta(days=60)).isoformat()
    (mem / "MEMORY.md").write_text(
        f"# Memoria\n\n## {(hoy - timedelta(days=10)).isoformat()} — Clientes\n- Aqualine paga a 30 días.\n"
        "- Aqualine prefiere WhatsApp.\n\n## Sin fecha\n- Aqualine usa logo azul.\n", encoding="utf-8")
    (mem / f"{viejo}.md").write_text(f"# Nota {viejo}\n- Reunión con Aqualine: precio viejo 120 $.\n",
                                     encoding="utf-8")
    (mem / f"{hoy.isoformat()}.md").write_text(f"# Nota {hoy.isoformat()}\n- Aqualine pidió el diseño nuevo.\n"
                                               "- Aqualine paga a 30 días.\n", encoding="utf-8")
    shutil.copy2(REPO / "growi-bridge.py", tmp / "app" / "growi-bridge.py")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "tok"), GROWI_BRIDGE_MEMORIA=str(mem))
    spec = importlib.util.spec_from_file_location("gb_memb", tmp / "app" / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    ev = {}
    secs = gb._palette_sections("qué sé de Aqualine")
    ev["a_paleta_que_se_de_aqualine"] = [(t, [i["label"] for i in it]) for t, it in secs]
    hits, med = gb.mem_buscar_ordenado("Aqualine")
    ev["bc_resultados_ordenados"] = [{k: h[k] for k in ("texto", "origen", "fecha", "refuerzo", "dias", "puntos")}
                                     for h in hits]
    ev["c_el_viejo_sigue"] = any(h["fecha"] == viejo for h in hits)
    ev["c_el_viejo_va_abajo"] = hits[-1]["fecha"] in (viejo, None)
    r = gb.mem_recuerda("recuerda esto: Aqualine cambia de contacto el lunes")
    r2 = gb.mem_recuerda("recuerda esto para siempre: Aqualine factura en dólares")
    ev["d_recuerda_esto"] = [{k: x.get(k) for k in ("ok", "destino", "ruta", "mensaje")} for x in (r, r2)]
    ev["d_en_el_archivo"] = ["cambia de contacto" in Path(r["ruta"]).read_text(encoding="utf-8"),
                             "factura en dólares" in Path(r2["ruta"]).read_text(encoding="utf-8")]
    # contexto de grupo: MEMORY.md no se carga
    texto = gb.mem_bloque_prompt({"id": "t-grupo", "prompt": "x", "canal": "whatsapp-grupo", "motor": "claude"})
    texto_priv = gb.mem_bloque_prompt({"id": "t-priv", "prompt": "x", "motor": "claude"})
    ev["grupo_sin_MEMORY"] = {"grupo_trae_MEMORY": "MEMORY.md" in texto and "Aqualine paga" in texto.split("Nota de hoy")[0],
                              "privada_trae_MEMORY": "Aqualine prefiere" in texto_priv}
    # (e) medida sobre una COPIA de la memoria real (solo cifras)
    real = Path.home() / "growi-bridge" / "memory"
    if real.is_dir():
        copia = tmp / "memoria-real-copia"
        shutil.copytree(real, copia)
        gb.MEMORY_DIR = copia
        medidas = {}
        for q in ("growi", "claude", "proxy"):
            h, m = gb.mem_buscar_ordenado(q)
            medidas[q] = {"resultados": len(h), **m, "con_fecha": sum(1 for x in h if x["fecha"])}
        ev["e_memoria_real_medidas"] = medidas
    out = REPO / "pruebas" / "evidencia" / "memoria-buscable" / "evidencia.json"
    out.write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
