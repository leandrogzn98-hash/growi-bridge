"""Prueba de t-oficina-bocadillos-050: bocadillo real <= 140 con texto completo en el log (a), 4 a la vez -> 3
visibles y FIFO (b), 3 señales real/decorativo (c), resumen hablado con Hermes REAL via Ollama ($0) frente a la
primera frase literal (d), politica de avisos (e), log diario con resumen y retencion (f), contador (g)."""
import json
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "oficina" / "bocadillos"))
import bocadillos as BC  # noqa: E402

EV = R / "pruebas" / "evidencia" / "oficina-bocadillos-050"
EV.mkdir(parents=True, exist_ok=True)
OUT = {}
tmp = Path(tempfile.mkdtemp(prefix="oficina-log-"))
LOG = BC.LogDiario(tmp / "oficina")

# (a) respuesta real larga: bocadillo <= 140 (primera frase literal) y texto completo en el log
largo = ("La capital de Francia es París, una ciudad con más de dos millones de habitantes en su núcleo urbano y "
         "muchos más en su área metropolitana. Es conocida por la Torre Eiffel, el Louvre y Notre Dame. Además...")
ref = LOG.escribir("Sonnet", "Leandro", "bocadillo de respuesta", largo, tipo="respuesta", costo="$0.0123 · sonnet")
b = BC.Bocadillo("sonny", "respuesta", largo, depto="Claude", ref_log=ref, ahora=0)
corto = BC.Bocadillo("sonny", "respuesta", "Una sola frase muy larga " + "x" * 200, ahora=0)
OUT["a_corte"] = {"texto": corto.texto, "ok": len(corto.texto) == 140 and corto.texto.endswith("...")}
OUT["a_real"] = {"bocadillo": b.texto, "largo": len(b.texto), "estilo": BC.estilo("respuesta", "Claude"), "ref_log": ref,
                 "completo_en_log": largo in LOG.ruta().read_text(encoding="utf-8"), "duracion_s": b.dur,
                 "es_cita_literal": largo.startswith(b.texto.rstrip(".").rstrip()),
                 "ok": len(b.texto) <= 140 and largo.startswith(b.texto.removesuffix("...").rstrip())
                 and BC.estilo("respuesta", "Claude")["marca"] == "real"
                 and largo in LOG.ruta().read_text(encoding="utf-8")}

# (b) 4 personajes a la vez: 3 visibles, el 4.o espera; 3 por un mismo personaje: se descarta el mas viejo
g = BC.Gestor()
for i, a in enumerate(("sonny", "dex", "luma", "opus")):
    g.poner(BC.Bocadillo(a, "estado", f"Pasé a revisión ({a}).", ahora=0))
v0 = [x.agente for x in g.tick(0)]
v1 = [x.agente for x in g.tick(20)]
g2 = BC.Gestor()
for k in range(3):
    g2.poner(BC.Bocadillo("sonny", "estado", f"mensaje {k}", ahora=k))
OUT["b_cola"] = {"visibles_t0": v0, "visibles_t20": v1, "cola_sonny_tras_3": [x.completo for x in g2.colas["sonny"]],
                 "ok": len(v0) == 3 and "opus" in v1 and [x.completo for x in g2.colas["sonny"]] == ["mensaje 1", "mensaje 2"]}
g.fijar("opus", 21)
OUT["b_fijado"] = {"vivo_a_los_40s_fijado": g.visibles[0].vivo(45) if g.visibles else None}

# (c) tres señales
er, ed = BC.estilo("respuesta", "Codex"), BC.estilo("charla")
dec = BC.Bocadillo("dex", "charla", "qué calor hace hoy", ref_log="no-deberia")
ref_c = LOG.escribir("Dex", "nadie", "vagancia", "qué calor hace hoy", tipo="charla")
OUT["c_senales"] = {"real": er, "decorativo": ed, "decorativo_ref_log": dec.ref_log, "charla_en_log": ref_c,
                    "ok": er["forma"] == "dialogo" and ed["forma"] == "nube" and er["marca"] == "real" and ed["marca"] is None
                    and ed["italica"] and ed["origen"] == "charla de oficina" and dec.ref_log is None and ref_c is None}

# (d) resumen hablado con Hermes de verdad (Ollama local, $0): ¿cabe en 140 y es fiel? frente a la primera frase
TEXTO = ("Revisé los tres archivos del proyecto. El primero tiene dos funciones duplicadas que conviene unir. El "
         "segundo usa una librería vieja con un fallo de seguridad conocido y hay que actualizarla. El tercero está bien.")


def ollama(modelo, prompt):
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=json.dumps(
        {"model": modelo, "prompt": prompt, "stream": False, "options": {"temperature": 0.7}}).encode(),
        headers={"Content-Type": "application/json"})
    import os
    os.environ["NO_PROXY"] = "127.0.0.1"
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=120) as r:
        return json.loads(r.read())["response"]


try:
    tags = json.loads(urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        "http://127.0.0.1:11434/api/tags", timeout=5).read())
    modelo = next((m["name"] for m in tags.get("models", []) if "hermes" in m["name"].lower()), None)
except Exception as e:
    modelo, tags = None, {"error": str(e)}
pruebas = []
if modelo:
    for i in range(5):
        r = ollama(modelo, "Resume en UNA frase de máximo 140 caracteres, en español, lo que dice este texto. Responde "
                           "solo con la frase.\n\n" + TEXTO).strip()
        pruebas.append({"respuesta": r, "caracteres": len(r), "cabe": len(r) <= 140})
literal = BC.resumen_hablado(TEXTO)
OUT["d_resumen_hermes"] = {"modelo": modelo, "intentos": pruebas, "cumplen_140": sum(p["cabe"] for p in pruebas),
                           "primera_frase_literal": literal, "via_elegida": "primera frase literal" if not modelo or
                           sum(p["cabe"] for p in pruebas) < 5 else "resumen del modelo (5/5) o primera frase",
                           "ok": len(literal) <= 140}

# (e) politica de avisos: 3 que avisan (pero ya los avisa la app) y 5 que no
pol = {e: BC.politica_aviso(e, "t-1") for e in ("terminada", "esperando_aprobacion", "error", "aceptada", "encolada",
                                                 "charla", "progreso", "resumen")}
OUT["e_avisos"] = {"politica": pol, "texto": BC.texto_aviso("Diseño", "terminó", "el reporte de SalPro. [Revisar]"),
                   "ok": all(pol[e]["avisaria"] and not pol[e]["la_oficina_avisa"] and pol[e]["clave"] == f"t-1:{e}"
                             for e in ("terminada", "esperando_aprobacion", "error"))
                   and not any(pol[e]["avisaria"] for e in ("aceptada", "encolada", "charla", "progreso", "resumen"))}

# (f) log del dia: formato, resumen de 3 lineas, retencion 90 dias (se archiva, no se borra)
hoy = date.today()
LOG.escribir("Growi", "Codex", "llamada entre departamentos", "Cody acepta la tarea t-2", tipo="estado")
LOG.escribir("Codex", "Leandro", "bocadillo de estado", "terminó t-2", tipo="estado", costo="$0 extra (suscripción)")
LOG.escribir("Opus", "Leandro", "bocadillo de estado", "t-3 queda por aprobar", tipo="esperando")
LOG.escribir("Hermes Directo", "Growi", "llamada entre departamentos", "no contesta (reintento 1 de 3)", tipo="error")
res = LOG.cerrar_dia(hoy)
viejo = LOG.dir / f"{(hoy - timedelta(days=95)).isoformat()}.md"
viejo.write_text("# viejo\n", encoding="utf-8")
movidos = LOG.archivar(hoy)
OUT["f_log"] = {"archivo": LOG.ruta().name, "contenido": LOG.ruta().read_text(encoding="utf-8").splitlines()[:14],
                "resumen": res, "archivados": movidos, "sigue_en_archivo": (LOG.dir / "archivo" / viejo.name).exists(),
                "busqueda_codex": LOG.buscar("codex"),
                "ok": res is not None and len(res) == 3 and movidos == [viejo.name] and (LOG.dir / "archivo" / viejo.name).exists()}
(EV / "log-ejemplo.md").write_text(LOG.ruta().read_text(encoding="utf-8"), encoding="utf-8")

# (g) contador
OUT["g_contador"] = {"dos_esperando": BC.te_necesitan({"tareas": [{"estado": "esperando_aprobacion"},
                                                                  {"estado": "esperando_leandro"}, {"estado": "en_cola"}]}),
                     "sin_senal": BC.te_necesitan(None), "vacia": BC.te_necesitan({"tareas": []})}
OUT["g_ok"] = OUT["g_contador"] == {"dos_esperando": "2", "sin_senal": "—", "vacia": "0"}
OUT["todo_ok"] = all(v.get("ok", True) for v in OUT.values() if isinstance(v, dict)) and OUT["g_ok"]
(EV / "resultado.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) and "ok" in v else v) for k, v in OUT.items()
                  if k not in ("g_contador", "b_fijado")}, ensure_ascii=False))
print("hermes:", OUT["d_resumen_hermes"]["modelo"], OUT["d_resumen_hermes"]["cumplen_140"], "/", len(pruebas))
