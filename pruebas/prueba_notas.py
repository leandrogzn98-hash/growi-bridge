"""Prueba de las notas (ESTADO-NOTAS-OBSIDIAN.md): Markdown con frontmatter,
nota diaria, [[wikilinks]] + backlinks + pendientes, plantillas, duplicados,
busqueda, comandos de la paleta, captura, grafo filtrado y espejo con conflicto.

  python pruebas/prueba_notas.py
"""
import importlib.util, json, os, shutil, sys, tempfile, time, tkinter as tk
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "notas"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-notas-"))
    (tmp / "app").mkdir()
    shutil.copy2(REPO / "growi-bridge.py", tmp / "app" / "growi-bridge.py")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "tok"), GROWI_BRIDGE_NOTAS=str(tmp / "notas"))
    spec = importlib.util.spec_from_file_location("gb_notas", tmp / "app" / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    root = tk.Tk()
    root.geometry("200x100+0+0")
    gb._root = root
    toasts = []
    gb.toast = lambda t, c=None: toasts.append(t)
    gb.messagebox.showinfo = lambda *a, **k: toasts.append("info: " + str(a[1])[:120])
    ev = {}
    # (a) markdown + frontmatter + diaria
    gb.nota_crear("Aqualine", "proyecto", etiquetas=("cliente",), proyecto="Aqualine")
    gb.nota_crear("Kickoff Aqualine", "reunion", proyecto="Aqualine",
                  cuerpo="Reunión de arranque con [[Aqualine]]. Ver [[Presupuesto 2027]].\n\n")
    gb.nota_crear("Idea logo", "idea", etiquetas=("diseño",), proyecto="Aqualine", cuerpo="Relacionada con [[Aqualine]].\n")
    gb.nota_crear("Summit Maker", "proyecto", proyecto="Summit Maker")
    p_diaria = gb.nota_diaria()
    ev["a_archivo_kickoff"] = (tmp / "notas" / "Kickoff Aqualine.md").read_text(encoding="utf-8")
    ev["a_diaria"] = p_diaria.name
    # (b) backlinks y pendientes
    idx = gb.notas_indice()
    ev["b_backlinks_aqualine"] = idx["backlinks"]["Aqualine"]
    ev["b_pendientes"] = idx["pendientes"]
    ev["b_no_se_creo_vacia"] = not (tmp / "notas" / "Presupuesto 2027.md").exists()
    # (d) duplicados: avisa, no fusiona
    ok, out, par = gb.nota_crear("Aqualin", None)
    ev["d_duplicado"] = {"creada": ok, "parecidas": par, "aqualine_intacta": (tmp / "notas" / "Aqualine.md").exists()}
    # (d) comandos desde la paleta
    ev["d_paleta"] = {q: [(t, [i["label"] for i in it]) for t, it in gb._palette_sections(q)]
                      for q in ("nota de reunión: Revisión semanal", "enlaza Summit Maker con Aqualine",
                                "resume la nota Kickoff Aqualine")}
    for q in ("enlaza Summit Maker con Aqualine",):
        gb._palette_sections(q)[0][1][0]["fn"]()
    ev["d_enlace_hecho"] = gb.notas_indice()["backlinks"]["Aqualine"]
    ev["d_resumen"] = gb.nota_resumir("Kickoff Aqualine")
    ev["d_captura"] = gb.nota_capturar("Llamar a Aqualine el lunes", origen="chat de Tareas").read_text(
        encoding="utf-8").splitlines()[-1]
    # (e) busqueda
    ev["e_buscar"] = {q: [(x["titulo"], x["donde"]) for x in gb.notas_buscar(q)] for q in ("aqualine", "diseño", "arranque")}
    # (c) grafo filtrado + capturas
    g_all = gb.notas_grafo()
    g_p = gb.notas_grafo(proyecto="Summit Maker")
    ev["c_grafo_todo"] = {"nodos": [n["titulo"] for n in g_all["nodos"]], "aristas": g_all["aristas"],
                          "pendientes": list(g_all["pendientes"])}
    ev["c_grafo_filtro_summit"] = {"nodos": [n["titulo"] for n in g_p["nodos"]], "aristas": g_p["aristas"]}
    from PIL import ImageGrab
    def cap(w, nombre):
        w.update(); time.sleep(0.4); w.update()
        x, y = w.winfo_rootx(), w.winfo_rooty()
        ImageGrab.grab((x, y, x + w.winfo_width(), y + w.winfo_height()), all_screens=True).save(OUT / nombre)
    top = gb.notas_grafo_ui()
    top.attributes("-topmost", True)
    cap(top, "1-grafo.png")
    top.destroy()
    nt = gb.notas_ui()
    nt.attributes("-topmost", True)
    gb._widgets["notas_ui"]["abrir"]("Aqualine")
    cap(nt, "2-notas-aqualine-backlinks.png")
    ev["b_panel_backlinks"] = gb._widgets["notas_ui"]["back"].cget("text")
    nt.destroy()
    # (f) espejo: subir, cambiar en el espejo, conflicto en los dos lados
    esp = tmp / "OneDrive-notas"
    r1 = gb.notas_espejo_sync(esp)
    (esp / "Idea logo.md").write_text((esp / "Idea logo.md").read_text(encoding="utf-8") + "\n- desde el espejo\n",
                                      encoding="utf-8")
    r2 = gb.notas_espejo_sync(esp)
    (esp / "Aqualine.md").write_text("cambio en el espejo\n", encoding="utf-8")
    (tmp / "notas" / "Aqualine.md").write_text((tmp / "notas" / "Aqualine.md").read_text(encoding="utf-8") +
                                               "\n- cambio local\n", encoding="utf-8")
    r3 = gb.notas_espejo_sync(esp)
    ev["f_espejo"] = {"primera": {k: v for k, v in r1.items()}, "cambio_en_espejo": r2, "conflicto": r3,
                      "local_conserva_su_cambio": "cambio local" in (tmp / "notas" / "Aqualine.md").read_text(encoding="utf-8"),
                      "espejo_conserva_el_suyo": (esp / "Aqualine.md").read_text(encoding="utf-8").startswith("cambio en el espejo")}
    ev["toasts"] = toasts
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str)[:6000], flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
