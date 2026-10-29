"""Evals del juez: estados sintéticos del Bridge con el veredicto esperado de cada uno.

Cada caso monta una instalación falsa del Bridge en una carpeta temporal (runner-status.json, resultados, cadenas,
log de la app) y, si hace falta, un gateway falso en 127.0.0.1. Luego corre una pasada en modo «eval»: el modelo y el
debounce como en una pasada real, pero sin correo y sin tocar la memoria de verdad. Pasa si el veredicto y el correo
(sí/no) son los esperados.

  python supervisor.py --evals                      con el proveedor del YAML
  python evals.py [proveedor] [modelo]              p. ej. «python evals.py mock» u «python evals.py ollama hermes3:8b»
"""

import copy
import http.server
import json
import socket
import sys
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

import supervisor as sv


class Gateway:
    """/gateway/salud falso que se puede encender y apagar."""

    def __init__(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.puerto = s.getsockname()[1]
        self.srv = None

    def encender(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok": true}')

            def log_message(self, *a):
                pass
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", self.puerto), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def apagar(self):
        if self.srv:
            self.srv.shutdown()
            self.srv.server_close()
            self.srv = None


def _montar(raiz, ahora, latido=True, cadena_detenida=None, decision=None):
    out = raiz / "share" / "outbox"
    (out / "runner-results").mkdir(parents=True)
    (raiz / "growi-bridge.log").write_text(f"{ahora.isoformat(timespec='seconds')} puente: escuchando\n",
                                           encoding="utf-8")  # log reciente = la app debería estar abierta
    if latido:
        (out / "runner-status.json").write_text(json.dumps({"last_poll": ahora.isoformat(), "current": None}),
                                                encoding="utf-8")
    if cadena_detenida:
        (out / "CADENA-ESTADO-PRUEBA.json").write_text(json.dumps(
            {"fase": "fase-prueba", "detenido": cadena_detenida, "ultimo_enviado": "t-prueba"}), encoding="utf-8")
    if decision:
        (out / "runner-results" / f"{decision}.result.json").write_text(json.dumps(
            {"id": decision, "estado": "necesita_decision", "status": "ok",
             "finished_at": (ahora - timedelta(hours=1)).isoformat(),
             "motivo_decision": "tres rondas sin aprobar la revisión"}), encoding="utf-8")


# (nombre, montaje, gateway antes del debounce, gateway después, veredicto esperado, correo esperado)
CASOS = [
    ("sano", {}, True, True, "TODO_BIEN", False),
    ("cadena detenida", {"cadena_detenida": "t-prueba sin resultado claro"}, True, True, "NECESITA_DECISION", True),
    ("gateway intermitente (1ª pasada: vuelve solo)", {}, False, True, "NECESITA_DECISION", False),
    ("gateway intermitente (2ª pasada: persiste)", {}, False, False, "NECESITA_DECISION", True),
    ("necesita_decision sin atender", {"decision": "t-espera-decision"}, True, True, "NECESITA_DECISION", True),
]


def correr(cfg, salida=print, casos=CASOS):
    ok_total = True
    resultados = []
    for nombre, montaje, gw_antes, gw_despues, v_esp, correo_esp in casos:
        with tempfile.TemporaryDirectory(prefix="growi-eval-") as tmp:
            raiz, ahora = Path(tmp), datetime.now().astimezone()
            _montar(raiz / "bridge", ahora, **montaje)
            gw = Gateway()
            c = copy.deepcopy(cfg)
            c["bridge"].update(carpeta=str(raiz / "bridge"), share=str(raiz / "bridge" / "share"),
                               puerto_gateway=gw.puerto, logs=["growi-bridge.log"],
                               cadenas=["outbox/CADENA-ESTADO*.json"])
            c["datos"] = str(raiz / "datos")
            if gw_antes:
                gw.encender()

            def esperar(_seg, gw=gw, gw_antes=gw_antes, gw_despues=gw_despues):
                if gw_despues and not gw_antes:
                    gw.encender()
                elif gw_antes and not gw_despues:
                    gw.apagar()
            try:
                r = sv.pasada(c, modo="eval", esperar=esperar)
            except Exception as e:  # noqa: BLE001 - un caso que revienta es un caso que falla
                r = {"veredicto": f"ERROR {type(e).__name__}: {sv.sin_secretos(e)}", "correo": None, "rastro": []}
            finally:
                gw.apagar()
            correo = r.get("correo") is not None
            ok = r["veredicto"] == v_esp and correo == correo_esp
            ok_total &= ok
            resultados.append({"caso": nombre, "ok": ok, "veredicto": r["veredicto"], "esperado": v_esp,
                               "correo": correo, "correo_esperado": correo_esp, "confianza": r.get("confianza"),
                               "rastro": r.get("rastro")})
            salida(f"[{'PASA' if ok else 'FALLA'}] {nombre}: veredicto {r['veredicto']} (esperado {v_esp}), "
                   f"correo {'sí' if correo else 'no'} (esperado {'sí' if correo_esp else 'no'}), "
                   f"confianza {r.get('confianza')}")
    salida(f"Evals del juez ({cfg['subgerente']['proveedor']} / {cfg['subgerente']['modelo']}): "
           f"{sum(x['ok'] for x in resultados)}/{len(resultados)}")
    correr.ultimos = resultados
    return 0 if ok_total else 1


if __name__ == "__main__":
    cfg = sv.cargar_config(sv.CONFIG_POR_DEFECTO)
    if len(sys.argv) > 1:
        cfg["subgerente"]["proveedor"] = sys.argv[1]
        cfg["subgerente"]["modelo"] = sys.argv[2] if len(sys.argv) > 2 else \
            sv.proveedores.cargar(sys.argv[1]).MODELO_POR_DEFECTO
        cfg["subgerente"]["clave"] = {"origen": "entorno",
                                      "nombre": sv.proveedores.cargar(sys.argv[1]).CLAVE_POR_DEFECTO}
    sys.exit(correr(cfg))
