# -*- coding: utf-8 -*-
"""Growi Bridge 0.6.0 'Harness' - Fase H2: loop agentico con smolagents.

Usuario -> Router (heuristica gratis) -> CodeAgent con las 4 Tools de motores
-> loop piensa/actua/observa/corrige (max 10 pasos) -> harness-state.json
en cada paso -> resultado.

Uso:
    python harness.py [--sesion ID] "tu tarea en lenguaje natural"

H3: cada llamada a un motor pasa por permission-layer.py (lista blanca de acciones,
confirmacion humana, audit-log.json con cadena de hashes). Codigo de salida 4 = bloqueado.

Reglas: sin gasto en el router (solo palabras clave); max_steps estricto;
solo escribe harness-state.json junto a este archivo.
"""
import importlib.util
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

from smolagents import ChatMessage, CodeAgent, MessageRole, Model
from smolagents.memory import ActionStep

AQUI = os.path.dirname(os.path.abspath(__file__))
# Fase 4: el estado puede ser por ejecución (GROWI_HARNESS_ESTADO lo fija
# quien lanza: harness-state-<raíz>.json para encargos, harness-state-
# <tarea>.json para lanzamientos sueltos). Sin la variable, la ruta de
# siempre. Escribir el propio estado es la contabilidad del harness: NO
# pasa por la capa de permisos (exención I12 de la Fase 4).
STATE_PATH = os.environ.get("GROWI_HARNESS_ESTADO") or os.path.join(AQUI, "harness-state.json")
MAX_STEPS = 10
MAX_STEPS_PLAN = 6  # el planificador no necesita más: divide y termina
MAX_PROMPT = 24000  # limite de linea de comandos de Windows ~32k
PODA_DESPUES = 2  # observaciones con mas de N pasos de antiguedad -> marcador


def _cargar_tools():
    ruta = os.path.join(AQUI, "growi-bridge-harness.py")
    spec = importlib.util.spec_from_file_location("growi_bridge_harness", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cargar_quota():
    ruta = os.path.join(AQUI, "quota-tracker.py")
    spec = importlib.util.spec_from_file_location("quota_tracker", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.QuotaTracker()


def _cargar_permisos():
    """Capa de permisos (H3). Fail closed: si no carga, el harness no ejecuta nada."""
    try:
        ruta = os.path.join(AQUI, "permission-layer.py")
        spec = importlib.util.spec_from_file_location("permission_layer", ruta)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["permission_layer"] = mod
        spec.loader.exec_module(mod)
        return mod, mod.nueva_capa(os.environ.get("GROWI_SESION"),
                                   cuenta=os.environ.get("GROWI_CUENTA_ID") or None)
    except Exception as e:  # noqa: BLE001
        return None, "%s: %s" % (type(e).__name__, e)


permission_layer, CAPA = _cargar_permisos()  # CAPA = CapaPermisos, o texto del error si fallo
PERMISOS_OK = permission_layer is not None
MSG_FAIL_CLOSED = "BLOQUEADO: la capa de permisos no se pudo cargar (%s); el harness no ejecuta nada" % (
    CAPA if not PERMISOS_OK else "")

quota_tracker = _cargar_quota()
# Fase 2/4: si el proceso nace con GROWI_CUENTA_ID, la cuota se anota por
# (motor, cuenta) y la capa de permisos clasifica y audita por cuenta.
# La variable solo la fijan el monolito y el relevo; main() la valida
# contra el registro antes de ejecutar nada (salida 4 si no cuadra).
# Sin la variable, el comportamiento es el de siempre.
CUENTA_HARNESS = os.environ.get("GROWI_CUENTA_ID") or None
RAIZ_HARNESS = os.environ.get("GROWI_RAIZ") or None
TAREA_HARNESS = os.environ.get("GROWI_TAREA_ID") or None
try:
    TIEMPO_MAX_S = float(os.environ.get("GROWI_TIEMPO_MAX_S") or 0) or None
except ValueError:
    TIEMPO_MAX_S = None
INICIO_HARNESS = time.time()
_H1 = _cargar_tools()
TOOLS = list(_H1.HARNESS_MOTOR_TOOLS)
TOOL_POR_NOMBRE = {t.name: t for t in TOOLS}


def _con_permiso(tool):
    """Envuelve tool.forward: TODA llamada a un motor (del router o del codigo del agente)
    pasa por verificar_permiso -> ejecutar -> audit log. El chequeo es codigo, no prompt."""
    original = tool.forward

    def forward(prompt=None, *args, **kwargs):
        if not PERMISOS_OK:
            return MSG_FAIL_CLOSED
        return CAPA.ejecutar_con_permiso(tool.name, str(prompt), original, "consulta_motor")

    tool.forward = forward


for _t in TOOLS:
    _con_permiso(_t)


# ----------------------------------------------------------------- Router
_SIMPLES = ("explica", "resume", "resumen", "clasifica", "define", "que es", "traduce", "lista")
_COMPLEJAS = ("codigo", "implementa", "arquitectura", "debug", "refactor", "programa", "script", "bug")


def _norm(texto):
    t = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def clasificar(tarea):
    """'complejo' si hay palabras de codigo/arquitectura; si no 'simple'. Gratis."""
    t = _norm(tarea)
    if any(k in t for k in _COMPLEJAS):
        return "complejo"
    if PERMISOS_OK:  # H3: lo que exige confirmacion humana solo existe en claude/codex -> cadena compleja
        try:
            clases, _ = permission_layer.clasificar_tarea(tarea, cuenta=CUENTA_HARNESS)
            if any(c in permission_layer.ACCIONES_ESCRITURA for c in clases):
                return "complejo"
        except Exception:  # noqa: BLE001
            pass
    return "simple"


# Cadena de motores por clase: el primero que no devuelva ERROR gana.
CADENAS = {
    "simple": ["gemini_cli", "gemini_cli", "llama_local"],
    "complejo": ["claude_cli", "codex_cli"],
}


# --------------------------------------------------------- Estado en disco
class Estado:
    def __init__(self, tarea):
        self.datos = {
            "version": "1.0",
            "timestamp": "",
            "current_task": str(tarea)[:300],
            "active_motor": "",
            "step": 0,
            "max_steps": MAX_STEPS,
            "status": "working",
            "last_output": "",
            # Fase 4: identidad de la ejecución y marcas por paso, para
            # que la supervisión distinga «trabajando» de «colgado».
            "cuenta": CUENTA_HARNESS,
            "raiz": RAIZ_HARNESS,
            "tarea_id": TAREA_HARNESS,
            "pasos": [],
        }

    def anotar_paso(self, n, motor, ok):
        pasos = self.datos.setdefault("pasos", [])
        pasos.append({"n": n, "ts": time.time(), "motor": motor,
                      "ok": bool(ok)})
        del pasos[:-50]

    def escribir(self, **cambios):
        self.datos.update(cambios)
        self.datos["timestamp"] = datetime.now().astimezone().isoformat(timespec="seconds")
        self.datos["last_output"] = str(self.datos["last_output"])[:200]
        try:  # cuotas reales (0 si no hay uso); un fallo del tracker nunca rompe el estado
            self.datos["quotas"] = quota_tracker.para_estado(cuenta=CUENTA_HARNESS)
        except Exception:  # noqa: BLE001
            self.datos.setdefault("quotas", {})
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.datos, f, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_PATH)


# ------------------------------------------------------ Modelo = el Router
class RouterModel(Model):
    """Modelo de smolagents que delega cada generacion en un motor CLI/local."""

    def __init__(self, clase, estado):
        super().__init__(model_id="growi-router")
        self.clase = clase
        self.estado = estado
        self.motor_activo = ""
        self.historial = []  # (motor, ok)

    @staticmethod
    def _texto(msg):
        c = msg.content if hasattr(msg, "content") else msg.get("content")
        if isinstance(c, list):
            c = "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
        return str(c or "")

    def _aplanar(self, messages):
        partes = []
        for m in messages:
            rol = m.role if hasattr(m, "role") else m.get("role")
            rol = getattr(rol, "value", rol)
            etiqueta = {"system": "SISTEMA", "user": "USUARIO", "assistant": "ASISTENTE",
                        "tool-call": "ASISTENTE", "tool-response": "OBSERVACION"}.get(str(rol), str(rol).upper())
            partes.append("[%s]\n%s" % (etiqueta, self._texto(m)))
        partes.append("[ASISTENTE]\nContinua con el siguiente paso (Thought: y un bloque <code>...</code>).")
        prompt = "\n\n".join(partes)
        if len(prompt) > MAX_PROMPT:  # conserva sistema/tarea (inicio) y lo reciente (final)
            mitad = MAX_PROMPT // 2
            prompt = prompt[:mitad] + "\n[...recortado...]\n" + prompt[-mitad:]
        return prompt

    def generate(self, messages, stop_sequences=None, response_format=None, tools_to_call_from=None, **kwargs):
        if TIEMPO_MAX_S and time.time() - INICIO_HARNESS > TIEMPO_MAX_S:
            raise RuntimeError("tiempo máximo de la tarea alcanzado "
                               "(%d s)" % TIEMPO_MAX_S)
        prompt = self._aplanar(messages)
        ultimo_error = "sin motores"
        for nombre in CADENAS[self.clase]:
            self.motor_activo = nombre
            self.estado.escribir(active_motor=nombre.replace("_cli", "").replace("_local", ""))
            salida = TOOL_POR_NOMBRE[nombre].forward(prompt)
            try:
                quota_tracker.registrar_uso(nombre, 1, cuenta=CUENTA_HARNESS)
            except Exception:  # noqa: BLE001
                pass
            ok = not str(salida).startswith(("ERROR", "BLOQUEADO"))
            self.historial.append((nombre, ok))
            if ok:
                texto = str(salida)
                for s in stop_sequences or []:  # los CLI no respetan stop: se corta aqui
                    i = texto.find(s)
                    if i > 0:
                        texto = texto[:i] + (s if s.strip() in ("</code>", "```") else "")
                return ChatMessage(role=MessageRole.ASSISTANT, content=texto)
            ultimo_error = salida
        return ChatMessage(role=MessageRole.ASSISTANT,
                           content="Thought: ningun motor respondio (%s).\n<code>\nfinal_answer(%r)\n</code>"
                           % (str(ultimo_error)[:120], "ERROR: " + str(ultimo_error)[:200]))


# --------------------------------------------------------------- System prompt
SYSTEM_PROMPT = """Eres Growi, un agente que resuelve tareas escribiendo Python en ciclos Thought / Code / Observation.
Cada respuesta: una linea 'Thought:' y UN bloque de codigo abierto con '{{code_block_opening_tag}}' y cerrado con '{{code_block_closing_tag}}'.
Usa print() para ver resultados; aparecen como 'Observation:' en el siguiente paso.
Termina siempre con final_answer(respuesta) en espanol. Si la tarea es simple y puedes responderla tu mismo, llama directo a final_answer sin usar herramientas.
Herramientas (motores de IA; solo si hacen falta):
{%- for tool in tools.values() %}
- {{ tool.to_code_prompt() }}
{%- endfor %}
Reglas: sin imports innecesarios; si una herramienta devuelve 'ERROR:', prueba otra o responde con lo que tengas; no inventes datos.
"""


def _plantillas():
    import importlib.resources
    import yaml
    base = yaml.safe_load(importlib.resources.files("smolagents.prompts").joinpath("code_agent.yaml").read_text(encoding="utf-8"))
    base["system_prompt"] = SYSTEM_PROMPT
    return base


# ------------------------------------------------------------ Callbacks
def _podar(memory_step, agent):
    """Observaciones viejas -> marcador (ahorra tokens)."""
    n = memory_step.step_number
    for paso in agent.memory.steps:
        if isinstance(paso, ActionStep) and paso.step_number <= n - PODA_DESPUES and paso.observations:
            if not paso.observations.startswith("[observacion podada"):
                paso.observations = "[observacion podada: %d caracteres]" % len(paso.observations)


def construir_agente(tarea, clase=None):
    estado = Estado(tarea)
    clase = clase or clasificar(tarea)
    modelo = RouterModel(clase, estado)

    def cb_estado(memory_step, agent=None):
        salida = memory_step.observations or ""
        if getattr(memory_step, "action_output", None) is not None:
            salida = str(memory_step.action_output)
        estado.anotar_paso(memory_step.step_number, modelo.motor_activo,
                           getattr(memory_step, "error", None) is None)
        estado.escribir(step=memory_step.step_number, last_output=salida.strip(), status="working")
        if agent is not None:
            _podar(memory_step, agent)

    agente = CodeAgent(
        tools=TOOLS,
        model=modelo,
        add_base_tools=False,
        max_steps=MAX_STEPS,
        executor_type="local",
        additional_authorized_imports=[],  # H3: el codigo del agente no puede importar os/shutil/pathlib/subprocess
        prompt_templates=_plantillas(),
        step_callbacks=[cb_estado],
        verbosity_level=0,
    )
    return agente, modelo, estado


# ------------------------------------------- Fase 4: cuenta y planificador
def _cargar_cuentas():
    ruta = os.path.join(AQUI, "cuentas.py")
    spec = importlib.util.spec_from_file_location("cuentas", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validar_cuenta_entorno():
    """La GROWI_CUENTA_ID que fijó el monolito/relevo tiene que cuadrar
    con el registro: la cuenta existe, está habilitada y es del carril de
    este proceso. Devuelve None si todo cuadra (o si no hay variable:
    comportamiento histórico) y el texto del error en caso contrario."""
    if not CUENTA_HARNESS:
        return None
    try:
        mod = _cargar_cuentas()
        reg = mod.cargar(AQUI)
    except Exception as e:  # noqa: BLE001
        return "no se pudo leer el registro de cuentas (%s: %s)" % (
            type(e).__name__, e)
    cta = mod.cuenta(reg, CUENTA_HARNESS)
    if cta is None:
        return "la cuenta «%s» no existe en el registro" % CUENTA_HARNESS
    if not cta.get("habilitada", True):
        return "la cuenta «%s» está deshabilitada" % CUENTA_HARNESS
    carril = os.environ.get("GROWI_BRIDGE_LANE") or "a"
    if cta.get("carril") != carril:
        return ("la cuenta «%s» es del carril %s y este harness corre en "
                "el carril %s" % (CUENTA_HARNESS, cta.get("carril"),
                                  carril))
    return None


PROMPT_PLANIFICADOR = """Eres el planificador de Growi Bridge. Tu único trabajo es DIVIDIR un encargo del dueño en subtareas claras; no ejecutas nada.
Responde con final_answer y SOLO el JSON del plan, sin texto antes ni después. Formato:
{"subtareas": [{"prompt": "qué hay que hacer, completo y autocontenido", "motor": null, "archivos": [], "git": null, "timeout_min": 30, "depende_de": [], "prueba_fisica": null}]}
Reglas: entre 1 y 12 subtareas; cada prompt debe entenderse sin leer las demás; "depende_de" lleva las posiciones (1..N) que deben terminar antes; "motor" solo si un motor concreto es imprescindible (si no, null); si una parte exige medir el rendimiento de toda la PC o abrir el proyecto/el juego para probarlo, márcala con "prueba_fisica": {"clase": "medicion"|"ejecutar_proyecto"|"abrir_programa", "detalle": "...", "duracion_est_min": 15, "impacto": "..."}.
"""


def _plantillas_plan():
    base = _plantillas()
    base["system_prompt"] = PROMPT_PLANIFICADOR
    return base


def ejecutar_plan(tarea):
    """Modo --planificar: el mismo loop con el prompt de planificación,
    sin herramientas (no ejecuta nada: las herramientas de escritura
    están denegadas por la capa y aquí ni siquiera se ofrecen) y con
    MAX_STEPS_PLAN pasos. La única salida válida es el final_answer con
    el JSON del plan; quien llama lo valida entero."""
    estado = Estado(tarea)
    if not PERMISOS_OK:  # fail closed, como ejecutar()
        estado.escribir(status="error", last_output=MSG_FAIL_CLOSED)
        return MSG_FAIL_CLOSED, RouterModel(clasificar(tarea), estado)
    modelo = RouterModel(clasificar(tarea), estado)

    def cb_estado(memory_step, agent=None):
        salida = memory_step.observations or ""
        if getattr(memory_step, "action_output", None) is not None:
            salida = str(memory_step.action_output)
        estado.anotar_paso(memory_step.step_number, modelo.motor_activo,
                           getattr(memory_step, "error", None) is None)
        estado.escribir(step=memory_step.step_number,
                        last_output=salida.strip(), status="working")

    agente = CodeAgent(
        tools=[],
        model=modelo,
        add_base_tools=False,
        max_steps=MAX_STEPS_PLAN,
        executor_type="local",
        additional_authorized_imports=[],
        prompt_templates=_plantillas_plan(),
        step_callbacks=[cb_estado],
        verbosity_level=0,
    )
    estado.escribir(status="working", last_output="planificando")
    try:
        resultado = agente.run(str(tarea))
        texto = str(resultado)
        malo = texto.startswith("ERROR")
        estado.escribir(status="error" if malo else "done",
                        step=max(estado.datos["step"], 1),
                        last_output=texto)
        if PERMISOS_OK:
            try:  # la planificación también queda auditada por cuenta
                permission_layer.registrar(
                    "harness", tarea, "error" if malo else "ok", None, 0.0,
                    "planificar", cuenta=CUENTA_HARNESS)
            except Exception:  # noqa: BLE001
                pass
        return texto, modelo
    except Exception as e:  # noqa: BLE001
        texto = "ERROR: %s: %s" % (type(e).__name__, e)
        estado.escribir(status="error", last_output=texto)
        return texto, modelo


def ejecutar(tarea):
    agente, modelo, estado = construir_agente(tarea)
    if not PERMISOS_OK:  # fail closed
        estado.escribir(status="error", last_output=MSG_FAIL_CLOSED)
        return MSG_FAIL_CLOSED, modelo
    decision, tool = CAPA.verificar_tarea(tarea, CADENAS[modelo.clase])
    if not decision.permitido:
        CAPA.registrar_bloqueo(tool, tarea, decision)
        texto = decision.mensaje()
        estado.escribir(status="error", last_output=texto)
        return texto, modelo
    estado.escribir(status="working", last_output="clase=%s" % modelo.clase)
    try:
        resultado = agente.run(str(tarea))
        texto = str(resultado)
        malo = texto.startswith("ERROR")
        estado.escribir(status="error" if malo else "done", step=max(estado.datos["step"], 1), last_output=texto)
        return texto, modelo
    except Exception as e:  # noqa: BLE001
        texto = "ERROR: %s: %s" % (type(e).__name__, e)
        estado.escribir(status="error", last_output=texto)
        return texto, modelo


def main(argv):
    args = list(argv[1:])
    planificar = False
    if "--planificar" in args:
        planificar = True
        args = [a for a in args if a != "--planificar"]
    if not args or not " ".join(args).strip() or (args[0] == "--sesion" and len(args) < 3):
        print('Uso: python harness.py [--sesion ID] [--planificar] "tu tarea en lenguaje natural"')
        return 2
    if len(args) >= 2 and args[0] == "--sesion":  # misma sesion = una sola confirmacion humana
        os.environ["GROWI_SESION"] = args[1]
        if PERMISOS_OK:
            permission_layer.nueva_capa(args[1], cuenta=CUENTA_HARNESS)
            globals()["CAPA"] = permission_layer._DEFECTO
        args = args[2:]
    tarea = " ".join(args)
    error_cuenta = validar_cuenta_entorno()
    if error_cuenta:  # Fase 4: cuenta que no cuadra -> salida 4 sin ejecutar
        texto = "BLOQUEADO: GROWI_CUENTA_ID no válida: %s" % error_cuenta
        try:
            Estado(tarea).escribir(status="error", last_output=texto)
        except Exception:  # noqa: BLE001
            pass
        print(texto)
        return 4
    if planificar:
        texto, modelo = ejecutar_plan(tarea)
        print(texto)
    else:
        texto, modelo = ejecutar(tarea)
        print("[clase=%s motores=%s]" % (modelo.clase, ",".join("%s:%s" % (m, "ok" if o else "fallo") for m, o in modelo.historial)))
        print(texto)
    if texto.startswith("BLOQUEADO"):
        return 4
    return 1 if texto.startswith("ERROR") else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main(sys.argv))
