"""Prueba de MCP Streamable HTTP (ESTADO-MCP-STREAMABLE-HTTP.md).

Copia aislada de growi-bridge.py (share, cola, token propios; puerto de
prueba 8797 → MCP en 8817). Lo REAL: el servidor MCP de Bridge en 127.0.0.1
(peticiones HTTP de verdad: sin token, Origin ajeno, cabecera que no coincide,
GET), el cliente contra el servidor MCP PÚBLICO de DeepWiki (solo lectura) y la
acción sensible por MCP pasando por el runner (motor falso: no se llama a nadie).

  python pruebas/prueba_mcp.py
"""

import importlib.util
import json
import os
import shutil
import socket
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "pruebas" / "evidencia" / "mcp"


def post(url, cuerpo, cab):
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                 headers=dict({"Content-Type": "application/json",
                                               "Accept": "application/json, text/event-stream"}, **cab))
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        r = op.open(req, timeout=20)
        return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-mcp-"))
    app, work = tmp / "app", tmp / "trabajo"
    app.mkdir()
    work.mkdir()
    for f in ("growi-bridge.py", "engines.json", "riesgos.json"):
        shutil.copy2(REPO / f, app / f)
    (app / "settings.json").write_text(json.dumps({"lane": "a", "onboarding_done": True, "guardrail": "delicado",
                                                   "mcp_servidor": True}), encoding="utf-8")
    (app / "folders.json").write_text(json.dumps({"allowed_roots": [str(work)]}), encoding="utf-8")
    (work / "viejo.txt").write_text("x", encoding="utf-8")
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "token"), GROWI_BRIDGE_MEMORIA=str(tmp / "memoria"),
                      GROWI_BRIDGE_PORT="8797")
    spec = importlib.util.spec_from_file_location("gb_mcp", app / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    for d in (gb.TASKS, gb.RESULTS, gb.OUTBOX):
        d.mkdir(parents=True, exist_ok=True)
    gb.cola_init()
    LLAMADAS = []
    real = gb._run_task_motor

    def falso(task):
        if gb.mcp_de_tarea(task):  # la herramienta MCP corre de verdad (no es un motor)
            return real(task)
        LLAMADAS.append(task["id"])
        r = gb._base_result(task, task["motor"])
        r.update(status="ok", result="hecho [simulado]", finished_at=gb._now_iso(), duration_s=0.1)
        return r
    gb._run_task_motor = falso
    ev = {"copia": str(tmp)}
    ev["servidor_arranca"] = gb.mcp_servidor_arrancar()
    url = f"http://127.0.0.1:{gb.mcp_puerto()}/mcp"
    tok, _o = gb.gateway_token(crear=False)
    meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "prueba", "version": "1"},
            "io.modelcontextprotocol/clientCapabilities": {}}
    lista = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}}
    buenas = {"Authorization": f"Bearer {tok}", "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"}
    # (b) loopback + token + Origin
    ev["b_sin_token"] = post(url, lista, {k: v for k, v in buenas.items() if k != "Authorization"})
    ev["b_origin_ajeno"] = post(url, lista, dict(buenas, Origin="https://atacante.example"))
    ev["b_cabecera_no_coincide"] = post(url, lista, dict(buenas, **{"Mcp-Method": "tools/call"}))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
    try:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10)
        ev["b_get"] = "200 (mal)"
    except urllib.error.HTTPError as e:
        ev["b_get"] = e.code
    code, body = post(url, lista, buenas)
    ev["b_con_token"] = {"http": code, "herramientas": [t["name"] for t in json.loads(body)["result"]["tools"]]}
    ev["b_escucha_en"] = gb._MCP["server"].server_address
    s = socket.socket()
    s.settimeout(2)
    ip_lan = socket.gethostbyname(socket.gethostname())
    try:
        s.connect((ip_lan, gb.mcp_puerto()))
        ev["b_desde_la_lan"] = f"conecta por {ip_lan} (mal)"
    except OSError as e:
        ev["b_desde_la_lan"] = f"no conecta por {ip_lan}: {type(e).__name__}"
    finally:
        s.close()
    # el cliente de Bridge contra el servidor de Bridge (era vigente)
    res, err, era = gb.mcp_llamar(url, "tools/call", {"name": "bridge_cola", "arguments": {}}, token=tok)
    ev["cliente_contra_bridge"] = {"era": era, "error": err, "resultado": res}
    # (c) cliente contra un servidor MCP REAL (DeepWiki, público, solo lectura) con interruptor por herramienta
    tools, err = gb.mcp_herramientas_cliente("deepwiki")
    ev["c_deepwiki_herramientas"] = {"error": err, "era": "2025-06-18 (legado)" if gb._MCP["legado"] else "2026-07-28",
                                     "tools": [(n, a) for n, _d, a in tools]}
    if tools:
        apagar = next((n for n, _d, _a in tools if n == "ask_wiki_question"), tools[0][0])
        gb.mcp_herramienta_interruptor("deepwiki", apagar, False)
        ev["c_apagada_no_se_usa"] = gb.mcp_usar("deepwiki", apagar, {"repoName": "x/y", "question": "?"})
        ev["c_tras_apagar"] = [(n, a) for n, _d, a in gb.mcp_herramientas_cliente("deepwiki")[0]]
        f = gb.TASKS / "t-mcp-deepwiki.task.json"
        f.write_text(json.dumps({"id": "t-mcp-deepwiki", "cwd": str(work), "revisar": False,
                                 "prompt": "Estructura de la wiki del SDK de Python de MCP",
                                 "herramienta": {"id": "mcp", "servidor": "deepwiki", "tool": "read_wiki_structure",
                                                 "args": {"repoName": "modelcontextprotocol/python-sdk"}}}),
                     encoding="utf-8")
        gb._process_one_impl(f)
        r = json.loads((gb.RESULTS / "t-mcp-deepwiki.result.json").read_text(encoding="utf-8"))
        ev["c_desde_el_runner"] = {"status": r.get("status"), "motor": r.get("motor"), "error": r.get("error"),
                                   "resultado": str(r.get("result") or "")[:500]}
    # (d) una acción sensible por MCP: espera aprobación; un R3 por MCP se deniega
    for nombre, prompt in (("r2", f"Borra el archivo {work}\\viejo.txt."),
                           ("r3", f"Borra en masa todo con rm -rf {work}.")):
        cuerpo = {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                  "params": {"name": "bridge_encolar_tarea", "arguments": {"prompt": prompt}, "_meta": meta}}
        code, body = post(url, cuerpo, dict(buenas, **{"Mcp-Method": "tools/call", "Mcp-Name": "bridge_encolar_tarea"}))
        tid = json.loads(body)["result"]["structuredContent"]["tarea"]
        gb._process_one_impl(gb.TASKS / f"{tid}.task.json")
        fam = gb.load_family(tid) or {}
        ev[f"d_{nombre}"] = {"http": code, "tarea": tid, "estado": fam.get("estado"),
                             "aprobacion": (fam.get("aprobacion") or {}).get("estado"),
                             "motivo": str(fam.get("motivo_decision") or (fam.get("aprobacion") or {}).get("motivo") or "")[:200],
                             "motor_llamado": tid in LLAMADAS}
    gb.mcp_servidor_parar()
    log = (app / "growi-bridge.log").read_text(encoding="utf-8", errors="replace")
    ev["log"] = [x for x in log.splitlines() if "mcp:" in x or "MCP" in x][-14:]
    ev["tracebacks_en_log"] = log.count("Traceback")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
