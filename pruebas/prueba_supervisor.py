"""Prueba del supervisor local (ESTADO-SUPERVISOR-LOCAL-046.md). No gasta: proveedor mock, sin correo real, estados
sintéticos en una carpeta temporal y un gateway falso en 127.0.0.1. Corre con el Python del supervisor:

  supervisor/.venv/Scripts/python.exe pruebas/prueba_supervisor.py      (Windows)
  supervisor/.venv/bin/python pruebas/prueba_supervisor.py              (Linux / macOS)
"""

import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import keyring
import keyring.backend
import yaml

REPO = Path(__file__).resolve().parent.parent
SUP = REPO / "supervisor"
sys.path.insert(0, str(SUP))
import evals  # noqa: E402
import supervisor as sv  # noqa: E402

OUT = REPO / "pruebas" / "evidencia" / "supervisor"
SECRETO = "sk-PRUEBA" + "x7Q2" * 6  # un secreto falso que nunca debe salir en prompt, correo, log ni YAML
ev = {"fecha": datetime.now().astimezone().isoformat(timespec="seconds"), "python": sys.version.split()[0]}


class LlaveroMemoria(keyring.backend.KeyringBackend):
    priority = 1
    datos = {}

    def get_password(self, s, u):
        return self.datos.get((s, u))

    def set_password(self, s, u, p):
        self.datos[(s, u)] = p

    def delete_password(self, s, u):
        self.datos.pop((s, u), None)


def config_prueba(tmp, proveedor="mock", **extra):
    c = yaml.safe_load((SUP / "supervisor-config.yaml").read_text(encoding="utf-8"))
    c["subgerente"].update(proveedor=proveedor, modelo=sv.proveedores.cargar(proveedor).MODELO_POR_DEFECTO,
                           clave={"origen": "entorno", "nombre": sv.proveedores.cargar(proveedor).CLAVE_POR_DEFECTO})
    c["bridge"].update(carpeta=str(tmp / "bridge"), share=str(tmp / "bridge" / "share"), logs=["growi-bridge.log"],
                       cadenas=["outbox/CADENA-ESTADO*.json"])
    c["datos"] = str(tmp / "datos")
    c["programacion"]["nombre_tarea"] = "GrowiSupervisor-prueba"
    for k, v in extra.items():
        c[k].update(v)
    p = tmp / f"config-{proveedor}.yaml"
    p.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return p, c


def correr_cli(*args, env=None):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    for k in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "RESEND_API_KEY"):
        e.pop(k, None)
    r = subprocess.run([sys.executable, str(SUP / "supervisor.py"), *args], capture_output=True, text=True,
                       encoding="utf-8", env=e, timeout=300)
    return {"codigo": r.returncode, "salida": r.stdout, "error": r.stderr}


def estado(tmp, gw, **montaje):
    import shutil
    shutil.rmtree(tmp / "bridge", ignore_errors=True)
    evals._montar(tmp / "bridge", datetime.now().astimezone(), **montaje)
    return gw


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="growi-supervisor-prueba-"))
    gw = evals.Gateway()
    gw.encender()
    # (a) py_compile
    ev["a_py_compile"] = {}
    for f in sorted(SUP.rglob("*.py")):
        if ".venv" in f.parts:
            continue
        try:
            py_compile.compile(str(f), doraise=True)
            ev["a_py_compile"][f.relative_to(REPO).as_posix()] = "ok"
        except py_compile.PyCompileError as e:
            ev["a_py_compile"][f.relative_to(REPO).as_posix()] = str(e)
    cfg_mock, _ = config_prueba(tmp, bridge={"puerto_gateway": gw.puerto})
    # (b) dry-run sano
    estado(tmp, gw)
    r = correr_cli("--config", str(cfg_mock), "--dry-run")
    ev["b_dry_run_sano"] = dict(r, primera_linea=r["salida"].splitlines()[0] if r["salida"] else "",
                                sin_correo="Correo que se enviaría" not in r["salida"],
                                sin_log_escrito=not (tmp / "datos" / "supervisor.log").exists())
    # (c) dry-run con necesita_decision (y un secreto falso metido en el motivo y en el log de la app)
    estado(tmp, gw, decision="t-espera-decision")
    rp = tmp / "bridge" / "share" / "outbox" / "runner-results" / "t-espera-decision.result.json"
    d = json.loads(rp.read_text(encoding="utf-8"))
    d["motivo_decision"] = f"falló con token={SECRETO} y Bearer {SECRETO}"
    rp.write_text(json.dumps(d), encoding="utf-8")
    r = correr_cli("--config", str(cfg_mock), "--dry-run")
    ev["c_dry_run_decision"] = dict(r, primera_linea=r["salida"].splitlines()[0] if r["salida"] else "",
                                    trae_correo="Correo que se enviaría" in r["salida"],
                                    secreto_en_salida=SECRETO in r["salida"] or "x7Q2x7Q2" in r["salida"])
    # (d) pasada real con el proveedor mock (estado sano: sin correo) -> veredicto + log local
    estado(tmp, gw)
    r = correr_cli("--config", str(cfg_mock))
    log = (tmp / "datos" / "supervisor.log").read_text(encoding="utf-8") if (tmp / "datos" / "supervisor.log").exists() else ""
    ev["d_pasada_mock"] = dict(r, log=log.splitlines())
    # (p) rastro auditable: hash del estado + veredicto + confianza
    ev["p_rastro"] = {"linea_turno": next((x for x in log.splitlines() if " TURNO " in x), None)}
    ev["p_rastro"]["ok"] = bool(ev["p_rastro"]["linea_turno"] and re.search(
        r"TURNO estado=[0-9a-f]{16} veredicto=\w+ confianza=[0-9.]+", ev["p_rastro"]["linea_turno"]))
    # (m) respuesta malformada -> FALLO_DE_JUICIO, reintento, sin correo (si intentara enviar, fallaría sin clave)
    (tmp / "datos" / "supervisor.log").unlink()
    estado(tmp, gw, decision="t-espera-decision")
    ev["m_fallo_de_juicio"] = {}
    for nombre, texto in (("texto libre", "Todo parece estar bien, no hay que hacer nada."),
                          ("otro schema", json.dumps({"veredicto": "NECESITA_DECISION", "alertas": ["x"]})),
                          ("confianza fuera de rango", json.dumps({"veredicto": "TODO_BIEN", "evidencia": [],
                                                                    "confianza": 7}))):
        r = correr_cli("--config", str(cfg_mock), env={"SUPERVISOR_MOCK_RESPUESTA": texto})
        log = (tmp / "datos" / "supervisor.log").read_text(encoding="utf-8")
        (tmp / "datos" / "supervisor.log").unlink()
        ev["m_fallo_de_juicio"][nombre] = {"codigo": r["codigo"], "error": r["error"], "log": log.splitlines(),
                                           "dos_intentos": "FALLO_DE_JUICIO intento 1" in log and
                                           "FALLO_DE_JUICIO intento 2" in log,
                                           "sin_correo": "enviadas=[]" in log and "Resend" not in r["error"]}
    # (n) gateway intermitente y (o) evals
    c = sv.cargar_config(cfg_mock)
    salida = []
    ev["o_evals_codigo"] = evals.correr(c, salida=salida.append)
    ev["o_evals"] = salida
    ev["n_intermitente"] = [x for x in evals.correr.ultimos if "intermitente" in x["caso"]]
    # (e-addendum) presupuesto: estado enorme se recorta; tope de llamadas abrevia el turno
    estado(tmp, gw, decision="t-espera-decision")
    (tmp / "bridge" / "growi-bridge.log").write_text("".join(
        f"{datetime.now().astimezone().isoformat(timespec='seconds')} runner: ERROR línea larga {'con texto normal ' * 12}n{i}\n"
        for i in range(200)), encoding="utf-8")
    c = sv.cargar_config(cfg_mock)
    c["datos"] = str(tmp / "datos-presupuesto")
    r1 = sv.pasada(c, modo="eval", esperar=lambda s: None)
    c["juez"]["max_llamadas_dia"] = 0
    r2 = sv.pasada(c, modo="eval", esperar=lambda s: None)
    ev["presupuesto"] = {"recorte": [x for x in r1["rastro"] if "presupuesto" in x],
                         "tope_llamadas": [x for x in r2["rastro"] if "presupuesto" in x], "fuente_con_tope": r2["fuente"]}
    # (f) otro proveedor sin clave: falla con mensaje claro; ollama sin servidor: error legible
    ev["f_otro_proveedor"] = {}
    for prov in ("deepseek", "openai", "anthropic", "gemini", "ollama"):
        p, _ = config_prueba(tmp, prov, bridge={"puerto_gateway": gw.puerto},
                             subgerente={"url": "http://127.0.0.1:9/api/chat"} if prov == "ollama" else {})
        r = correr_cli("--config", str(p))
        ev["f_otro_proveedor"][prov] = {"codigo": r["codigo"], "mensaje": r["error"].strip()}
    # (h) --configurar con entradas simuladas (llavero en memoria: el real no se toca)
    keyring.set_keyring(LlaveroMemoria())
    ruta_h = tmp / "configurado.yaml"
    ruta_h.write_text((SUP / "supervisor-config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    respuestas = iter(["openai", "", "llavero", "avisos@ejemplo.com", "yo@ejemplo.com", "30"])
    pantalla = []
    sv.configurar(ruta_h, entrada=lambda t: (pantalla.append(t), next(respuestas))[1],
                  secreto=lambda t: (pantalla.append(t), SECRETO)[1], salida=pantalla.append)
    yh = ruta_h.read_text(encoding="utf-8")
    ev["h_configurar"] = {"pantalla": pantalla, "yaml_valido": bool(sv.cargar_config(ruta_h)),
                          "subgerente": yaml.safe_load(yh)["subgerente"],
                          "reportes": yaml.safe_load(yh)["gerente_general"]["reportes"],
                          "clave_en_yaml": SECRETO in yh, "clave_en_pantalla": any(SECRETO in str(x) for x in pantalla),
                          "clave_en_llavero": LlaveroMemoria.datos.get(("growi-supervisor", "OPENAI_API_KEY")) == SECRETO}
    # (i) --verificar: sin clave falla con motivo; con mock, OK por punto
    p, _ = config_prueba(tmp, "deepseek", bridge={"puerto_gateway": gw.puerto})
    ev["i_verificar_sin_clave"] = correr_cli("--config", str(p), "--verificar")
    ev["i_verificar_mock"] = correr_cli("--config", str(cfg_mock), "--verificar")
    # (k) sin rutas C:\ en el código
    ev["k_rutas_c"] = [f"{f.name}:{i + 1}" for f in SUP.rglob("*") if f.suffix in (".py", ".ps1", ".sh", ".yaml")
                       and ".venv" not in f.parts and "_prueba" not in f.parts
                       for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines()) if re.search(r"[A-Za-z]:\\", ln)]
    gw.apagar()
    # secretos en cualquier rastro escrito
    todo = json.dumps(ev, ensure_ascii=False)
    ev["secreto_en_evidencia"] = SECRETO in todo
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    resumen = {
        "a": all(v == "ok" for v in ev["a_py_compile"].values()),
        "b": ev["b_dry_run_sano"]["primera_linea"] == "TODO_BIEN" and ev["b_dry_run_sano"]["sin_correo"],
        "c": ev["c_dry_run_decision"]["primera_linea"] == "NECESITA_DECISION" and ev["c_dry_run_decision"]["trae_correo"]
        and not ev["c_dry_run_decision"]["secreto_en_salida"],
        "d": ev["d_pasada_mock"]["codigo"] == 0 and any("FIN TODO_BIEN" in x for x in ev["d_pasada_mock"]["log"]),
        "f": all(v["codigo"] in (2, 3) and v["mensaje"] for v in ev["f_otro_proveedor"].values()),
        "h": ev["h_configurar"]["yaml_valido"] and not ev["h_configurar"]["clave_en_yaml"]
        and not ev["h_configurar"]["clave_en_pantalla"] and ev["h_configurar"]["clave_en_llavero"],
        "i": ev["i_verificar_sin_clave"]["codigo"] == 1 and "[FAIL] clave del proveedor" in ev["i_verificar_sin_clave"]["salida"],
        "k": not ev["k_rutas_c"],
        "m": all(v["dos_intentos"] and v["sin_correo"] for v in ev["m_fallo_de_juicio"].values()),
        "n": [x["correo"] for x in ev["n_intermitente"]] == [False, True],
        "o": ev["o_evals_codigo"] == 0,
        "p": ev["p_rastro"]["ok"],
        "presupuesto": bool(ev["presupuesto"]["recorte"]) and ev["presupuesto"]["fuente_con_tope"].startswith("reglas"),
        "sin_secretos": not ev["secreto_en_evidencia"],
    }
    ev["resumen"] = resumen
    (OUT / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False))
    return 0 if all(resumen.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
