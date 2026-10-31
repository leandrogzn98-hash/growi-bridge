"""Telefono al gerente (t-oficina-telefono-050, spec 12 de 18).

Unico canal de texto del dueno en la oficina: todo va al gerente, que es un router con cara, no un chatbot.
- Clasificacion SIN modelo, por reglas: pregunta / tarea / correccion / aprobacion / fuera de la oficina.
- La tarea se crea EXACTAMENTE como la app: oficina/encolar/encolar.py -> encolar_tarea() de growi-bridge.py
  (mismo .task.json; cola.db y guardrail los pone el runner al recogerlo).
- Una confirmacion por mensaje; si llega otro mientras el gerente «lee», espera (maximo 1 en espera).
- La animacion de leer dura lo que tarda la tarea real en existir (archivo + fila en cola.db). Si a los 3 s
  no ha pasado nada visible, el gerente dice «Dame un momento, estoy revisando.»; nunca 5 s mudo.
- La oficina NO aprueba: un «apruébalo» recibe «Aprobar es en la app».
Sin historial: el telefono guarda solo el ultimo mensaje y su confirmacion.
"""
import re
import sys
from pathlib import Path
import threading
import time
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "llamadas"))
import llamadas as LL  # noqa: E402  (t-oficina-llamadas-050)

RE_URGENTE = re.compile(r"\burgent", re.I)
RE_NO = re.compile(r"^\s*(no|nop|mejor no|d[eé]jalo|cancela)\b", re.I)
TOPE_EN_COLA = 3

DEPTOS = {  # palabra del encargo -> (departamento, model del task)
    "claude": ("Claude", None), "opus": ("Claude", "opus"), "sonnet": ("Claude", "sonnet"), "haiku": ("Claude", "haiku"),
    "codex": ("Codex", "motor:codex"), "local": ("Local", "motor:llama"), "hermes": ("Local", "motor:llama"),
    "ollama": ("Local", "motor:ollama"), "gemini": ("Gemini", "motor:gemini"), "meshy": ("Taller 3D", "motor:meshy"),
    "3d": ("Taller 3D", "motor:meshy"),
}
RE_APRUEBA = re.compile(r"^\s*(s[ií]|ok|dale|apru[eé]b|aprob|autoriz|adelante|hazlo)\b", re.I)
RE_CORRIGE = re.compile(r"\b(corrig|corrige|c[aá]mbia|arregl|otra vez|rehaz|vuelve a|no era eso|fall[oó])", re.I)
RE_PREGUNTA = re.compile(r"(\?\s*$|^\s*(qu[eé]|c[oó]mo|cu[aá]nt|cu[aá]l|qui[eé]n|d[oó]nde|hay|est[aá]n?|va|van)\b)", re.I)
RE_TRABAJO = re.compile(r"\b(tarea|cola|encargo|agente|departamento|runner|revisi[oó]n|aprob|pendiente|trabaj|"
                        r"oficina|estado|terminad|fall|claude|codex|local|gemini|hermes|haiku|opus|sonnet|plan)", re.I)
RE_HORA = re.compile(r"\b(hora|qu[eé] d[ií]a|fecha)\b", re.I)
RE_VERBO = re.compile(r"^\s*(haz|crea|escribe|resume|revisa|busca|prepara|genera|traduce|analiza|redacta|arma|"
                      r"limpia|ordena|mira|lee|pasa|manda|sube|baja|renombra|convierte|calcula|dime cu[aá]l)", re.I)


def departamento_de(texto, por_defecto=("Claude", None)):
    t = texto.lower()
    for k, v in DEPTOS.items():
        if re.search(rf"\b{k}\b", t):
            return v
    return por_defecto


def clasificar(texto):
    """-> (clase, detalle). clase: aprobacion | correccion | pregunta | tarea | fuera. Solo reglas."""
    t = (texto or "").strip()
    if not t:
        return "vacio", None
    if RE_APRUEBA.match(t):
        return "aprobacion", None
    if RE_CORRIGE.search(t) and not RE_PREGUNTA.search(t):
        return "correccion", departamento_de(t)
    if RE_PREGUNTA.search(t) and not RE_VERBO.match(t):
        if RE_TRABAJO.search(t):
            return "pregunta", None
        return "fuera", "hora" if RE_HORA.search(t) else None
    return "tarea", departamento_de(t)


def resumen_cola(cola):
    """Respuesta hablada a «¿cómo va todo?» armada desde cola-live (sin modelo)."""
    if not isinstance(cola, dict):
        return "No veo la cola ahora mismo (sin señal)."
    ts = cola.get("tareas") or []
    n = {k: sum(1 for x in ts if x.get("estado") == k) for k in ("en_curso", "en_cola", "esperando_aprobacion",
                                                               "esperando_leandro", "terminada", "fallida")}
    partes = []
    if n["en_curso"]:
        cur = next(x for x in ts if x.get("estado") == "en_curso")
        partes.append(f"trabajando en {cur['id']} ({cur.get('motor')})")
    if n["en_cola"]:
        partes.append(f"{n['en_cola']} en cola")
    if n["esperando_aprobacion"] + n["esperando_leandro"]:
        partes.append(f"{n['esperando_aprobacion'] + n['esperando_leandro']} esperando tu aprobación en la app")
    if n["terminada"] or n["fallida"]:
        partes.append(f"{n['terminada']} terminadas y {n['fallida']} fallidas en los últimos 15 min")
    return ("Todo tranquilo: no hay nada en marcha." if not partes else "Ahora mismo: " + "; ".join(partes) + ".")


class Telefono:
    """Estado del telefono para el render. `enviar()` nunca bloquea: el trabajo va en un hilo.
    estado: colgado | leyendo | esperando_turno; bocadillo: lo que dice el gerente (UNA confirmacion por mensaje)."""

    ESPERA_VISIBLE_S = 3.0  # a los 3 s sin nada, «Dame un momento»: nunca 5 s mudo
    TOPE_S = 20.0           # si la tarea no aparece en 20 s, el gerente cuelga con el error real

    def __init__(self, encolar_mod=None, cola=lambda: None, guardrail=lambda: None, registro=None, reloj=time.time):
        self.enc = encolar_mod
        self.cola = cola
        self.guardrail = guardrail
        self.reg = registro or (lambda d: None)
        self.reloj = reloj
        self.lock = threading.Lock()
        self.estado = "colgado"
        self.actual = None       # el mensaje que el gerente esta leyendo
        self.en_espera = None    # maximo 1 en espera
        self.bocadillo = None    # (texto, desde)
        self.ultimo_motor = None
        self.confirmaciones = []  # (texto_del_mensaje, confirmacion): para la prueba de «una por mensaje»
        self.hitos = []
        self.por_confirmar = None  # (texto, criterios, depto, model, clase): «¿lo dejo en espera igual?»

    def motor_sugerido(self):
        return self.ultimo_motor or "Claude"

    def enviar(self, texto, criterios=None):
        texto = (texto or "").strip()
        if not texto:
            return "vacio"
        with self.lock:
            if self.estado == "leyendo":
                if self.en_espera is not None:
                    return "lleno"  # el gerente esta con uno y hay uno esperando: el telefono no acepta mas
                self.en_espera = (texto, criterios)
                return "en_espera"
            self.estado, self.actual = "leyendo", (texto, criterios)
        threading.Thread(target=self._atender, daemon=True).start()
        return "leyendo"

    def _decir(self, texto_msg, frase):
        with self.lock:
            self.bocadillo = (frase, self.reloj())
            self.confirmaciones.append((texto_msg, frase))
        self.reg({"evento": "telefono", "mensaje": texto_msg[:80], "respuesta": frase})

    def _atender(self):
        while True:
            texto, criterios = self.actual
            t0 = self.reloj()
            self.hitos = [("enviado", 0.0)]
            clase, det = clasificar(texto)
            if self.por_confirmar is not None:  # la respuesta al «¿lo dejo en espera igual?»
                pend, self.por_confirmar = self.por_confirmar, None
                if clase == "aprobacion":
                    self._encolar(pend[0], pend[1], pend[2], pend[3], pend[4], t0, confirmado=True)
                else:
                    self._decir(texto, "Vale, no lo encolo.")
            elif clase == "aprobacion":
                self._decir(texto, "Aprobar es en la app (Tareas) o por WhatsApp con su código; desde la oficina no.")
            elif clase == "fuera":
                self._decir(texto, (f"Son las {datetime.now():%H:%M}." if det == "hora" else "Eso no es de la oficina."))
            elif clase == "pregunta":
                self._decir(texto, resumen_cola(self.cola()))
            else:  # tarea o correccion: se encola como la app
                depto, model = det
                self._encolar(texto, criterios, depto, model, clase, t0)
            with self.lock:
                if self.en_espera is None:
                    self.estado, self.actual = "colgado", None
                    return
                self.actual, self.en_espera = self.en_espera, None

    def _encolar(self, texto, criterios, depto, model, clase, t0, confirmado=False):
        if self.enc is None:
            self._decir(texto, "No puedo encolar ahora (el encolado no está disponible): lo guardo de borrador.")
            return
        n = LL.en_cola_de(self.cola(), depto)
        if n >= TOPE_EN_COLA and not confirmado:  # spec 13: con 3 o mas en cola, avisa y espera el si/no
            self.por_confirmar = (texto, criterios, depto, model, clase)
            self._decir(texto, f"{depto} tiene {n} en cola. ¿Lo dejo en espera igual? (sí / no)")
            return
        urgente = bool(RE_URGENTE.search(texto))
        aviso = threading.Timer(self.ESPERA_VISIBLE_S, lambda: self._aviso_espera(texto))
        aviso.start()
        try:
            r = (self.enc.encolar(texto, criterios=criterios or [], model=model, urgente=True) if urgente
                 else self.enc.encolar(texto, criterios=criterios or [], model=model))
        except Exception as e:  # nunca tumbar la oficina
            r = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        self.hitos.append(("task_json", round(self.reloj() - t0, 2)))
        if not r.get("ok"):
            aviso.cancel()
            self._decir(texto, f"No pude crearla: {r.get('error')}")
            return
        tid = r["id"]
        self.ultimo_motor = depto
        est = None
        while self.reloj() - t0 < self.TOPE_S:  # la cola la registra el runner al recogerla (>= 2 s)
            est = (self.enc.estado(tid) or {}).get("estado")
            if est:
                break
            time.sleep(0.25)
        # El runner apunta la tarea «en_cola» y medio segundo despues decide (guardrail -> retenida, o la toma).
        # Medido: confirmar en el primer estado decia «en cola» a una tarea que el guardrail retenia.
        t_reg = self.reloj()
        while est == "en_cola" and self.reloj() - t_reg < 3.0:
            time.sleep(0.25)
            est = (self.enc.estado(tid) or {}).get("estado") or est
        aviso.cancel()
        self.hitos.append(("cola_db", round(self.reloj() - t0, 2), est))
        verbo = ("le paso tu corrección a" if clase == "correccion" else "llamo a")
        if urgente:
            verbo = "! urgente: " + verbo  # adelanta en la cola, no interrumpe a nadie
        if est in ("esperando_aprobacion", "esperando_leandro"):
            frase = f"Voy, {verbo} {depto}. {tid} queda por aprobar: apruébala en la app."
        elif est:
            frase = f"Voy, {verbo} {depto}. {tid} {est.replace('_', ' ')}."
        else:
            frase = f"Voy, {verbo} {depto}. {tid} escrita; el runner aún no la recoge (¿está parado?)."
        self._decir(texto, frase)

    def _aviso_espera(self, texto):
        with self.lock:
            if self.estado == "leyendo":
                self.bocadillo = ("Dame un momento, estoy revisando.", self.reloj())
                self.hitos.append(("aviso_espera", None))
