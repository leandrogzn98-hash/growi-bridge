"""Prueba del brief de reunión (ESTADO-BRIEF-REUNION.md).

Copia aislada de growi-bridge.py (memoria propia con líneas DE PRUEBA, marcadas
así: no son las de Leandro). El calendario es un archivo iCal local con dos
eventos dentro de 30 min (uno con persona y otro sin ella), leído por la misma
función que lee la dirección secreta de Google Calendar.

  python pruebas/prueba_brief.py
"""

import importlib.util
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "brief"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-brief-"))
    app, mem = tmp / "app", tmp / "memoria"
    app.mkdir()
    mem.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "onboarding_done": True}), encoding="utf-8")
    (mem / "MEMORY.md").write_text(
        "# Memoria (LÍNEAS DE PRUEBA, no son las de Leandro)\n"
        "- William prefiere que le escriban por la mañana.\n\n"
        "## 2026-10-20 Reunión con William (Aqualine)\n"
        "- Acordamos 3 anuncios por mes para Aqualine.\n"
        "- Pendiente: enviar el guion del anuncio 2.\n"
        "- Cobrado: $150 por octubre.\n\n"
        "## 2026-09-15 Llamada con William\n"
        "- Hablamos del catálogo de filtros.\n", encoding="utf-8")
    (mem / "2026-10-25.md").write_text("# 2026-10-25\n- William confirmó que paga el 1 de noviembre.\n",
                                       encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MEMORIA=str(mem))
    spec = importlib.util.spec_from_file_location("gb_brief", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    gb.RESULTS.mkdir(parents=True, exist_ok=True)
    gb.toast = lambda *a, **k: None
    gb._family_update("t-william-guion", encargo="Escribe el guion del anuncio 2 para William (Aqualine)",
                      estado="aprobada")
    ev = {"copia": str(tmp)}
    # (d) sin calendario conectado: lo dice y no inventa
    b = gb.brief_generar("William")
    ev["d_sin_calendario"] = {"fuentes": b["fuentes"], "texto": gb.brief_texto(b)}
    # (a)+(b) la tarjeta, cada dato con su origen; lo que no tiene fecha no entra
    ev["a_tarjeta"] = {k: b.get(k) for k in ("ultima_vez", "acordado", "pendiente", "cobro", "tareas", "sin_origen")}
    ev["b_todos_con_origen"] = all(i.get("origen") for k in ("acordado", "pendiente", "cobro") for i in b[k])
    ev["b_el_dato_sin_fecha_no_entra"] = not any("por la mañana" in i["texto"] for k in ("acordado", "pendiente",
                                                                                         "cobro", "hablado")
                                                 for i in b[k])
    ev["paleta"] = [(t, [i["label"] for i in it]) for t, it in gb._palette_sections("brief para la reunión con William")]
    # (c) un evento con persona dentro de 30 min → su brief; uno sin persona → nada
    ahora = datetime.now().astimezone()
    t1 = (ahora + timedelta(minutes=30)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ics = tmp / "calendario.ics"
    ics.write_text("\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0",
        "BEGIN:VEVENT", "UID:ev-william", f"DTSTART:{t1}", "SUMMARY:Llamada con William (Aqualine)",
        "ATTENDEE;CN=William:mailto:william@example.com", "END:VEVENT",
        "BEGIN:VEVENT", "UID:ev-foco", f"DTSTART:{t1}", "SUMMARY:Bloque de foco", "END:VEVENT",
        "END:VCALENDAR", ""]), encoding="utf-8")
    s = gb.load_settings()
    s["calendario_ics"] = str(ics)
    gb.save_settings(s)
    hechos, err = gb.brief_vigia_paso(ahora)
    ev["c_30_min_antes"] = {"eventos_en_la_ventana": [(e.get("titulo"), e["personas"], e["inicio"].isoformat())
                                                      for e in gb.calendario_eventos(ahora, ahora + timedelta(hours=1))[0]],
                            "briefs": [Path(h).name for h in hechos], "error": err,
                            "contenido": Path(hechos[0]).read_text(encoding="utf-8") if hechos else None}
    ev["c_segunda_vuelta_no_repite"] = gb.brief_vigia_paso(ahora)[0]
    b2 = gb.brief_generar("William")
    ev["con_calendario"] = {"fuentes": b2["fuentes"], "calendario": b2.get("calendario")}
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "brief:" in x][-8:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (OUT / "brief-william.txt").write_text(ev["d_sin_calendario"]["texto"], encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
