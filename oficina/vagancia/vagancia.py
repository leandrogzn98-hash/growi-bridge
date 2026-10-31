"""Vagancia de la oficina (t-oficina-vagancia-050, spec 15 de 18). Decoracion honesta para agentes OCIOSOS.

Reglas de hierro, como codigo:
  R1 nunca finge trabajo: `badge()` devuelve SIEMPRE el estado real, aparte de la actividad (el render lo
     pinta como elemento separado del sprite).
  R2 retorno inmediato: `Oficina.evento_estado()` cancela la actividad en el acto (sin «terminar el cafe»)
     al primer cambio de estado real; se llama desde el mismo bucle que deriva estados (no sondea aparte).
  R3 no gasta: sin red, sin modelos, sin escribir en la cola; frases de una lista fija; decision = aritmetica.
  R4 «oficina seria»: un unico interruptor `vagancia_activa`; apagado, los ociosos quedan quietos con su badge.
  R5 no bloquea: puntos de interes con capacidad; ocupado = la actividad puntua 0.
Dormir NO es vagancia: un dormido no entra en el tick ni la vagancia lo despierta; «oficina seria» no lo toca.
"""
import json
import math
import random
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FRASES_JSON = AQUI / "frases.json"
NECESIDADES = {"cafeina": 2.0, "social": 3.0, "distraccion": 4.0, "orden": 1.5}  # pts por minuto ocioso
# id -> (necesidad, duracion min-max s, punto de interes o None, cooldown min, peso base)
ACTIVIDADES = {
    "cafe": ("cafeina", (60, 120), "cafe", 10, 10),
    "estirarse": ("cafeina", (20, 40), None, 3, 6),
    "ventana": ("cafeina", (45, 90), "ventana", 4, 8),
    "charlar": ("social", (60, 180), "pasillo", 5, 10),
    "celular": ("distraccion", (30, 90), None, 3, 8),
    "pelota": ("distraccion", (30, 60), None, 5, 6),
    "bano": ("orden", (60, 120), "bano", 15, 5),
    "pasear": ("orden", (30, 60), None, 0, 3),
}
APLAZADAS = {"A5": "consola (más animación)", "A7": "cartas (necesita 2 + mesa)",
             "A10": "papeles (puede parecer trabajo: R1)", "A11": "limpiar gafas (sustituto listo, aplazado)"}
COOLDOWN_GLOBAL_PLANTA_MIN = 10
RECENCIA = (60, 30, 10)
EVENTOS_RAROS = {"cafe_derramado": (0.02, "bueno..."), "pajaro_ventana": (0.05, "¡mira!"),
                 "flor_nueva": (0.03, "¡una flor!"), "duelo_miradas": (0.01, None), "bostezo_cadena": (0.04, None)}
# «todos disimulan» del gerente: ELIMINADO en la v1 (riesgo de violar R1). No existe en este archivo a proposito.
TICK_S = 5.0


def curva_horaria(hora):
    """Multiplicador por necesidad segun la hora local."""
    m = {k: 1.0 for k in NECESIDADES}
    if 8 <= hora < 10:
        m["cafeina"] = 1.6
    elif 13 <= hora < 15:
        m["cafeina"], m["distraccion"] = 1.4, 1.4
    elif hora >= 17:
        m["social"], m["distraccion"] = 1.5, 1.4
    return m


def badge(estado):
    """R1: el badge dice el estado REAL, haga lo que haga el sprite."""
    return estado.replace("_", " ")


class Agente:
    def __init__(self, aid, ahora, semilla):
        self.id = aid
        self.rng = random.Random(semilla)
        self.necesidad = {k: self.rng.uniform(40, 80) for k in NECESIDADES}
        self.ultimas = []
        self.cooldown = {}
        self.actividad = None  # (nombre, poi, fin)
        self.primer_tick = ahora + self.rng.uniform(3, 8)
        self.proximo_tick = self.primer_tick
        self.ultimo_bocadillo = -1e9


class Oficina:
    def __init__(self, pois_capacidad, fecha=None, registro_raros=None, frases=None):
        self.cap = dict(pois_capacidad)  # {poi: capacidad}; un poi que falta = sus actividades no existen
        self.uso = {p: set() for p in self.cap}
        self.agentes = {}
        self.vagancia_activa = True  # R4: el UNICO interruptor
        self.fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        self.registro_raros = registro_raros
        self.raros_ultimo = {}
        self.planta_global = -1e9
        self.frases = frases if frases is not None else cargar_frases()
        self.ultimo_bocadillo_oficina = -1e9
        self.historial = []  # (t, agente, actividad) para las pruebas

    # ---- ciclo de vida de un agente segun su estado real
    def evento_estado(self, aid, estado, ahora):
        """Llamar en cada fotograma con el estado derivado. R2: si no esta sin_tarea, cancela YA."""
        ag = self.agentes.get(aid)
        if estado != "sin_tarea":
            if ag and ag.actividad:
                self._liberar(ag)
                self.historial.append((ahora, aid, "INTERRUMPIDA:" + estado))
            self.agentes.pop(aid, None)  # dormido o trabajando: fuera del tick
            return None
        if ag is None:
            ag = self.agentes[aid] = Agente(aid, ahora, f"{aid}-{self.fecha}")
        return ag

    def actividad_de(self, aid):
        ag = self.agentes.get(aid)
        return ag.actividad[0] if ag and ag.actividad else None

    def _liberar(self, ag):
        if ag.actividad and ag.actividad[1] in self.uso:
            self.uso[ag.actividad[1]].discard(ag.id)
        ag.actividad = None

    def disponibles(self):
        return {a: v for a, v in ACTIVIDADES.items() if v[2] is None or v[2] in self.cap}

    def puntuar(self, ag, nombre, ahora, hora):
        nec, _dur, poi, _cd, base = ACTIVIDADES[nombre]
        if poi is not None and (poi not in self.cap or len(self.uso[poi]) >= self.cap[poi]):
            return 0.0  # R5 y degradacion: ocupado o inexistente
        con_quien = [o for o in self.agentes.values() if o is not ag]  # otro ocioso (sin tarea)
        if nombre == "charlar" and not con_quien:
            return 0.0  # A4 solo si hay con quien (otro ocioso libre o ya charlando)
        if ag.cooldown.get(nombre, -1e9) > ahora:
            return 0.0
        if ag.ultimas and ag.ultimas[-1] == nombre:
            return 0.0  # nunca dos veces seguidas
        s = base + (100 - ag.necesidad[nec]) * 0.5 * curva_horaria(hora)[nec]
        for i, n in enumerate(reversed(ag.ultimas[-3:])):
            if n == nombre:
                s -= RECENCIA[i]
        if any(o.actividad and o.actividad[0] == nombre for o in self.agentes.values() if o is not ag):
            s -= 25
        s += ag.rng.uniform(-10, 10)
        return max(0.0, s)

    def tick(self, ahora, hora=None):
        """Avanza a todos los ociosos. Devuelve eventos [(agente, tipo, dato)]."""
        hora = datetime.now().hour if hora is None else hora
        ev = []
        if not self.vagancia_activa:  # R4: quietos en su puesto (con su badge)
            for ag in self.agentes.values():
                self._liberar(ag)
            return ev
        for ag in list(self.agentes.values()):
            if ag.actividad and ahora >= ag.actividad[2]:
                fin = ag.actividad[0]
                self._liberar(ag)
                ag.cooldown[fin] = ahora + ACTIVIDADES[fin][3] * 60
                ag.necesidad[ACTIVIDADES[fin][0]] = min(100, ag.necesidad[ACTIVIDADES[fin][0]] + 45)
                ev.append((ag.id, "fin", fin))
            if ahora < ag.proximo_tick or ag.actividad:
                continue
            dt_min = TICK_S / 60
            for k, r in NECESIDADES.items():
                ag.necesidad[k] = max(0.0, ag.necesidad[k] - r * dt_min)
            ag.proximo_tick = ahora + TICK_S
            punt = sorted(((self.puntuar(ag, n, ahora, hora), n) for n in self.disponibles()), reverse=True)
            top = [(s, n) for s, n in punt[:3] if s > 0]
            if not top:
                elegida = self._comodin(ag)  # A12: el comodin universal; nunca congelado
            else:
                tot = sum(s for s, _ in top)
                x = ag.rng.uniform(0, tot)
                elegida = top[-1][1]
                for s, n in top:
                    x -= s
                    if x <= 0:
                        elegida = n
                        break
            nec, (d0, d1), poi, _cd, _b = ACTIVIDADES[elegida]
            if poi is not None:
                if poi not in self.cap or len(self.uso[poi]) >= self.cap[poi]:
                    elegida = self._comodin(ag)
                    poi, (d0, d1) = None, ACTIVIDADES[elegida][1]
                else:
                    self.uso[poi].add(ag.id)
            ag.actividad = (elegida, poi, ahora + ag.rng.uniform(d0, d1))
            ag.ultimas = (ag.ultimas + [elegida])[-3:]
            self.historial.append((ahora, ag.id, elegida))
            ev.append((ag.id, "empieza", elegida))
            ev += self._raro(ag, elegida, ahora)
            ev += self._bocadillo(ag, ahora)
        return ev

    @staticmethod
    def _comodin(ag):
        """Pasear, salvo que acabe de pasear: entonces estirarse (nunca dos veces seguidas la misma)."""
        return "estirarse" if ag.ultimas and ag.ultimas[-1] == "pasear" else "pasear"

    def _raro(self, ag, actividad, ahora):
        out = []
        cand = {"cafe": "cafe_derramado", "ventana": "pajaro_ventana", "charlar": "duelo_miradas",
                "estirarse": "bostezo_cadena", "pasear": "flor_nueva"}.get(actividad)
        if not cand or ahora - self.raros_ultimo.get(cand, -1e9) < 3600:
            return out
        p, frase = EVENTOS_RAROS[cand]
        if ag.rng.random() < p:
            self.raros_ultimo[cand] = ahora
            out.append((ag.id, "raro", cand))
            if self.registro_raros:
                with open(self.registro_raros, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"t": ahora, "agente": ag.id, "evento": cand, "frase": frase},
                                        ensure_ascii=False) + "\n")
        return out

    def _bocadillo(self, ag, ahora):
        """Max 1 decorativo por personaje cada 10 min y 1 en toda la oficina cada 3 min; casi siempre «...»."""
        if ahora - ag.ultimo_bocadillo < 600 or ahora - self.ultimo_bocadillo_oficina < 180:
            return []
        if ag.rng.random() > 0.3:
            return []
        ag.ultimo_bocadillo = self.ultimo_bocadillo_oficina = ahora
        lista = self.frases.get("charla", []) + self.frases.get("sueltas", [])
        return [(ag.id, "bocadillo", ag.rng.choice(lista) if lista and ag.rng.random() < 0.4 else "...")]


# ---- catalogo de frases (archivo de datos editable) y su prueba de fuego
EXCLUIR_PALABRAS = ("tarea", "ronda", "revis", "aprob", "error", "agente", "modelo", "prompt", "token", "costo",
                    "cliente", "entreg", "plazo", "corrig", "envi", "proces", "gener", "analiz", "claude", "codex",
                    "gemini", "hermes", "ollama", "runner", "cola", "trabaj", "list", "termin", "hecho")


def cargar_frases(ruta=FRASES_JSON):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"charla": [], "sueltas": ["..."]}


def prueba_de_fuego(frase):
    """None si pasa; motivo si podria leerse como estado de trabajo (y se elimina)."""
    f = frase.lower()
    if any(ch.isdigit() for ch in f):
        return "tiene un número"
    for w in EXCLUIR_PALABRAS:
        if w in f:
            return f"menciona «{w}»"
    import re
    if re.match(r"^\s*¡?\s*ya\s+\w+(é|ó|aste|amos|aron|í|ió)\b", f):
        return "«ya» + verbo de logro"
    if re.search(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\b", frase[1:]):
        return "posible nombre propio"
    return None
