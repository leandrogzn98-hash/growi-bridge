"""(b)/(c)/(f) lado OTRO PROCESO: importa oficina\\encolar\\encolar.py y encola
contra la copia aislada (GROWI_BRIDGE_APP_DIR). Sin ventana, sin red.
Uso: python encolar_desde_fuera.py <prompt> <criterio> <model> [esperar_s]"""
import json
import os
import sys
import time

os.environ["GROWI_BRIDGE_APP_DIR"] = r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app"
for k in ("GROWI_BRIDGE_SHARE", "GROWI_BRIDGE_COLA"):
    os.environ.pop(k, None)
sys.path.insert(0, r"C:\Users\forte\growi-bridge\share\inbox\oficina\encolar")
import encolar  # noqa: E402
import psutil  # noqa: E402

prompt, criterio, model = sys.argv[1], sys.argv[2], sys.argv[3]
esperar_s = int(sys.argv[4]) if len(sys.argv) > 4 else 0
p = psutil.Process()
t0 = time.time()
gb = encolar.cargar_app()
t_imp = time.time() - t0
r = encolar.encolar(prompt, [criterio] if criterio else None, model=model)
out = {"pid": os.getpid(), "import_s": round(t_imp, 2), "rss_mb": round(p.memory_info().rss / 2**20, 1),
       "ok": r["ok"], "id": r.get("id"), "archivo": r.get("archivo"), "engine": r.get("engine"),
       "error": r.get("error"), "sockets_de_este_proceso": [str(c) for c in p.net_connections()]}
if r["ok"] and esperar_s:
    st, vistos = encolar.esperar(r["id"], timeout_s=esperar_s)
    res = st.get("resultado") or {}
    out.update(estado_final=st["estado"], cambios=vistos,
               resultado={k: res.get(k) for k in ("estado", "motor", "reporte", "cost_usd", "duracion_s")},
               sockets_al_final=[str(c) for c in p.net_connections()])
print(json.dumps(out, ensure_ascii=False, indent=1))
