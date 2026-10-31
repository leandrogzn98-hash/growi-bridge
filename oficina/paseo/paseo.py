"""Paseo del dueño (t-oficina-paseo-050, spec 14 de 18). Logica pura, sin render:
- Rejilla y obstaculos de plano.json; camino A* de 4 vecinos (las mesas se rodean; no hay teletransporte).
- Andar: velocidad de paseo fija (VEL_BALDOSAS_S), sin sprint; WASD/flechas mueven una baldosa si esta libre.
- Camara: sigue al dueño con suavizado y nunca muestra fuera del plano.
- Proximidad: SOLO postura (no escribe nada); dura <= 10 s y no se re-dispara hasta alejarse > 1 s.
- Clic para hablar: [Preguntar] / [Pedir tarea], tabla por estado; la tarea se crea con ESE motor.
"""
import heapq
import json
import math
import random
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PLANO = AQUI.parent / "plano" / "plano.json"
VEL_BALDOSAS_S = 3.0        # paso de paseo (~1 m/s con baldosas de ~0,35 m de dibujo): no hay sprint
RADIO_PROX = 3.0            # 1,5 mesas (~2 m del plano) en baldosas
PROX_MAX_S = 10.0
ALEJARSE_S = 1.0
RESPUESTA_MAX = 280

# personaje -> (motor del task, nombre para el bocadillo, departamento)
MOTOR_DE = {"growi": (None, "Growi", "Gerencia"), "clau": ("sonnet", "Clau", "Claude"),
            "sonny": ("sonnet", "Sonnet", "Claude"), "opus": ("opus", "Opus", "Claude"),
            "haiku": ("haiku", "Haiku", "Claude"), "cody": ("motor:codex", "Cody", "Codex"),
            "dex": ("motor:codex", "Dex", "Codex"), "luma": ("motor:llama", "Luma", "Local"),
            "hermes_directo": ("motor:llama", "Hermes Directo", "Local"),
            "hermes_ollama": ("motor:ollama", "Hermes Ollama", "Local"), "gemi": ("motor:gemini", "Gemi", "Gemini"),
            "mensajero": ("motor:meshy", "Mensajero 3D", "Taller 3D")}
FRASES_ACEPTA = ("Me pongo en ello.", "Voy con eso.", "Lo hago ahora.", "Hecho, empiezo.", "Marchando.")


class Rejilla:
    def __init__(self, plano=None):
        self.d = plano or json.loads(PLANO.read_text(encoding="utf-8"))
        r = self.d["rejilla"]
        self.W, self.H = r["ancho"], r["alto"]
        self.bloq = set()
        for _id, rc in _obstaculos(self.d):
            for x in range(rc["x"], rc["x"] + rc["w"]):
                for y in range(rc["y"], rc["y"] + rc["h"]):
                    self.bloq.add((x, y))

    def libre(self, p):
        x, y = p
        return 0 <= x < self.W and 0 <= y < self.H and (x, y) not in self.bloq

    def camino(self, a, b):
        """A* de 4 vecinos; [] si b no es alcanzable. Nunca atraviesa obstaculos."""
        a, b = tuple(a), tuple(b)
        if not self.libre(b):
            return []
        abiertos = [(0, a)]
        g = {a: 0}
        de = {}
        while abiertos:
            _f, cur = heapq.heappop(abiertos)
            if cur == b:
                out = [cur]
                while cur in de:
                    cur = de[cur]
                    out.append(cur)
                return out[::-1]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cur[0] + dx, cur[1] + dy)
                if self.libre(n) and g[cur] + 1 < g.get(n, 1e9):
                    g[n] = g[cur] + 1
                    de[n] = cur
                    heapq.heappush(abiertos, (g[n] + abs(n[0] - b[0]) + abs(n[1] - b[1]), n))
        return []


def _obstaculos(d):
    o = [(p["id"], p["rect"]) for p in d.get("paredes", [])] + [(m["id"], m["rect"]) for m in d.get("mesas", [])]
    o += [(d["tablon"]["id"], d["tablon"]["rect"]), (d["despacho"]["mesa"]["id"], d["despacho"]["mesa"]["rect"]),
          (d["despacho"]["bandeja_entrada"]["id"], d["despacho"]["bandeja_entrada"]["rect"])]
    o += [(b["id"], b["rect"]) for b in d.get("taller3d", {}).get("buzones", [])]
    o += [(p["id"], p["rect"]) for p in d.get("puntos_interes", [])]
    return o


class Duenio:
    """El avatar de Leandro. Posicion continua en baldosas; anda por el camino a VEL_BALDOSAS_S."""

    def __init__(self, rejilla, pos=None):
        self.rj = rejilla
        self.pos = list(pos or rejilla.d["entrada"]["punto"])
        self.ruta = []

    @property
    def baldosa(self):
        return (int(round(self.pos[0])), int(round(self.pos[1])))

    def ir_a(self, destino):
        self.ruta = self.rj.camino(self.baldosa, destino)[1:]
        return bool(self.ruta) or self.baldosa == tuple(destino)

    def tecla(self, dx, dy):
        """WASD/flechas: una baldosa en esa direccion si esta libre (una pared no se atraviesa)."""
        n = (self.baldosa[0] + dx, self.baldosa[1] + dy)
        if self.rj.libre(n):
            self.ruta = [n]
            return True
        return False

    def avanzar(self, dt):
        paso = VEL_BALDOSAS_S * dt
        while paso > 0 and self.ruta:
            tx, ty = self.ruta[0]
            dx, dy = tx - self.pos[0], ty - self.pos[1]
            dist = math.hypot(dx, dy)
            if dist <= paso:
                self.pos = [float(tx), float(ty)]
                self.ruta.pop(0)
                paso -= dist
            else:
                self.pos[0] += dx / dist * paso
                self.pos[1] += dy / dist * paso
                paso = 0


class Camara:
    """Centrada en el dueño con suavizado; nunca enseña nada fuera del plano."""

    def __init__(self, rejilla, vista_w, vista_h, baldosa_px, suavizado=6.0):
        self.rj, self.vw, self.vh, self.b, self.k = rejilla, vista_w, vista_h, baldosa_px, suavizado
        self.x = self.y = 0.0

    def limites(self):
        return max(0, self.rj.W * self.b - self.vw), max(0, self.rj.H * self.b - self.vh)

    def seguir(self, pos, dt):
        mx, my = self.limites()
        objx = min(mx, max(0, (pos[0] + 0.5) * self.b - self.vw / 2))
        objy = min(my, max(0, (pos[1] + 0.5) * self.b - self.vh / 2))
        a = 1 - math.exp(-self.k * dt)
        self.x += (objx - self.x) * a
        self.y += (objy - self.y) * a
        self.x, self.y = min(mx, max(0, self.x)), min(my, max(0, self.y))
        return self.x, self.y


POSTURA = {"sin_tarea": "endereza la espalda y mira su pantalla vacía", "en_cola": "endereza la espalda y hojea sus papeles",
           "trabajando": "teclea más rápido", "esperando_aprobacion": "levanta la mano un poco más y te mira",
           "gerente": "levanta la vista del tablón y asiente"}
NO_REACCIONA = ("sin_senal", "en_revision", "dormir")


class Proximidad:
    """Postura al acercarse: pura animacion; no genera eventos ni escribe archivos."""

    def __init__(self):
        self.inicio, self.lejos_desde, self.agotado = {}, {}, set()

    def paso(self, duenio_pos, agentes, ahora):
        """agentes: {id: (pos, estado)}. -> {id: postura} de los que reaccionan ahora."""
        out = {}
        for aid, (pos, est) in agentes.items():
            cerca = math.hypot(duenio_pos[0] - pos[0], duenio_pos[1] - pos[1]) <= RADIO_PROX
            if not cerca:
                self.lejos_desde.setdefault(aid, ahora)
                if ahora - self.lejos_desde[aid] > ALEJARSE_S:  # se alejo de verdad: puede volver a reaccionar
                    self.inicio.pop(aid, None)
                    self.agotado.discard(aid)
                continue
            self.lejos_desde.pop(aid, None)
            clave = "gerente" if aid == "growi" else est
            if est in NO_REACCIONA or clave not in POSTURA or aid in self.agotado:
                continue
            t0 = self.inicio.setdefault(aid, ahora)
            if ahora - t0 > PROX_MAX_S:
                self.agotado.add(aid)
                continue
            out[aid] = POSTURA[clave]
        return out


def ficha(aid, estado, tarea=None, posicion=None):
    _m, nombre, depto = MOTOR_DE.get(aid, (None, aid, "—"))
    t = f"{nombre} (Depto. {depto}) — {estado.replace('_', ' ')}"
    if tarea:
        t += f" · Tarea: {tarea.get('id')}"
        if tarea.get("ronda") is not None:
            t += f" · ronda {tarea.get('ronda', 0)}/{tarea.get('max_rondas', 3)}"
    if posicion:
        t += f" · posición {posicion[0]} de {posicion[1]}"
    return t


def decidir(estado, tarea_actual=None, posicion=None, despues_de_esto=False):
    """Tabla por estado al hacer clic (§5.5). -> (accion, frase). accion: crear | crear_detras | despertar |
    rechazar | sin_senal | crear_despues."""
    if estado == "sin_senal":
        return "sin_senal", "Sin señal: no sé si este agente está."
    if estado == "dormir":
        return "despertar", "(se despierta con un sobresalto y se estira)"
    if estado == "esperando_aprobacion":
        tid = (tarea_actual or {}).get("id", "una tarea")
        if despues_de_esto:
            return "crear_despues", "Queda en cola para después de la revisión."
        return "rechazar", (f"No puedo: tengo {tid} esperando tu aprobación. Apruébala o recházala en el tablón "
                            "y seguimos. (Puedes decir «después de esto».)")
    if estado in ("trabajando", "en_cola", "en_revision", "en_ronda", "en_pausa"):
        tid = (tarea_actual or {}).get("id", "otra tarea")
        pos = f" (posición {posicion[0]} de {posicion[1]})" if posicion else ""
        return "crear_detras", f"Estoy con {tid}; lo tuyo va detrás{pos}."
    return "crear", None  # sin_tarea, terminado, fallido


class Frases:
    """Frases cortas y variadas: nunca la misma dos veces seguidas."""

    def __init__(self, semilla=None):
        self.r = random.Random(semilla)
        self.ultima = None

    def acepta(self):
        f = self.r.choice([x for x in FRASES_ACEPTA if x != self.ultima])
        self.ultima = f
        return f


def respuesta_bocadillo(nombre, result):
    """«Sonnet dice: …» con los primeros 280 caracteres, el costo y si hay «ver completo»."""
    txt = " ".join(str(result.get("result") or result.get("error") or "").split())
    corto = txt if len(txt) <= RESPUESTA_MAX else txt[:RESPUESTA_MAX] + "..."
    costo = result.get("cost_usd")
    c = f" · ${costo:.4f}" if isinstance(costo, (int, float)) else " · costo: sin dato"
    return {"texto": f"{nombre} dice: {corto}{c}", "ver_completo": len(txt) > RESPUESTA_MAX,
            "detalle": {k: result.get(k) for k in ("result", "cost_usd", "num_turns", "session_id", "status")}}


class Hablar:
    """Clic en un agente: crea la tarea real con ESE motor, segun la tabla por estado. enc = encolar.py."""

    def __init__(self, enc, frases=None):
        self.enc, self.frases = enc, frases or Frases()

    def pedir(self, aid, modo, texto, estado, tarea_actual=None, posicion=None, criterios=None, despues_de_esto=False):
        motor, nombre, _d = MOTOR_DE.get(aid, (None, aid, "—"))
        acc, frase = decidir(estado, tarea_actual, posicion, despues_de_esto)
        if acc in ("sin_senal", "rechazar", "despertar"):
            return {"accion": acc, "frase": frase, "id": None}
        if motor is None:
            return {"accion": "rechazar", "frase": "Para pedirme algo, usa el teléfono (T).", "id": None}
        kw = {"model": motor}
        if acc == "crear_despues":
            kw["despues_de"] = (tarea_actual or {}).get("id")
        crit = [] if modo == "preguntar" else (criterios or [])  # pregunta = sin criterios (sin rondas)
        r = self.enc.encolar(texto, criterios=crit, **kw)
        if not r.get("ok"):
            return {"accion": "error", "frase": f"No pude: {r.get('error')}", "id": None}
        return {"accion": acc, "frase": frase, "id": r["id"], "nombre": nombre, "modo": modo}

    def confirmar(self, pedido, estado_en_cola):
        """La frase de aceptacion SOLO cuando la tarea existe de verdad en la cola."""
        if pedido.get("id") and estado_en_cola in ("en_cola", "esperando_aprobacion", "en_curso"):
            base = pedido.get("frase")
            return base if pedido["accion"] in ("crear_detras", "crear_despues") else self.frases.acepta()
        return None


def recordatorios(desde_espera, ahora, ya_avisado):
    """Esperando aprobacion es pegajoso: bocadillo cada 5 min (una vez por tramo) y un toast a los 30 min (uno)."""
    t = ahora - desde_espera
    ev = []
    tramo = int(t // 300)
    if tramo >= 1 and ("bocadillo", tramo) not in ya_avisado:
        ya_avisado.add(("bocadillo", tramo))
        ev.append(("bocadillo", "Te espero en revisión."))
    if t >= 1800 and ("toast",) not in ya_avisado:
        ya_avisado.add(("toast",))
        ev.append(("toast", "Hay una tarea esperando tu aprobación desde hace 30 min."))
    return ev
