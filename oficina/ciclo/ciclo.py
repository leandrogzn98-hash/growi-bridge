"""Oficina 0.5.0 — ciclo de vida, modo DEMO y aprobacion espacializada (t-oficina-ciclo-vida-050, spec 18).

Logica pura (sin pygame) que usa oficina_proto.py:
  - Demo: escribe fuentes SIMULADAS (marcadas «_ejemplo» y «_demo») en una carpeta propia de la
    oficina, nunca en el share del Bridge. Ni cola.db, ni encolar, ni borradores reales.
  - leer_pedidos(): los pedidos de aprobacion que la app publica en outbox\\aprobaciones\\ (solo lectura).
  - tarjeta(): el texto de la tarjeta del agente que espera en la mesa del gerente. Muestra el comando
    y el estado; NO tiene botones: aprobar es un acto de la app (Tareas) o de WhatsApp.
  - Caminantes: posicion dibujada de cada agente, que camina a velocidad fija hacia su objetivo.
  - Camara: la tecla N centra (con zoom) en el agente que espera; sin espera, no hace nada.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

DEMO_ETIQUETA = "DEMO — sin agentes reales"
VELOCIDAD_PX_S = 90.0      # paso de andar fijo (sin sprint), como el paseo del spec 14
CAMARA_ZOOM = 2.0
CAMARA_DURA_S = 8.0        # la camara vuelve sola a la oficina entera tras 8 s (o con Esc)
PEDIDOS_MAX = 60


def _iso(t):
    return datetime.fromtimestamp(t).astimezone().isoformat(timespec="seconds")


def _escribir(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


# ---- modo DEMO ------------------------------------------------------------------------------
class Demo:
    """Guion de 60 s que se repite. Todo lo que escribe lleva «_ejemplo: true» y «_demo»: la oficina
    lo rotula y no puede encolar mientras lo lee. Escribe SOLO en su carpeta (datos\\demo\\outbox)."""

    CICLO_S = 60.0

    def __init__(self, outbox):
        self.outbox = Path(outbox)
        self.t0 = time.time()
        self.escrituras = 0

    def _tareas(self, s, ahora):
        def t(id_, estado, motor, modelo=None, hace=20, **kw):
            d = {"id": id_, "estado": estado, "motor": motor, "creado_en": _iso(ahora - hace - 30),
                 "actualizado_en": _iso(ahora - hace), "raiz": id_}
            if modelo:
                d["modelo"] = modelo
            d.update(kw)
            return d
        fase_b = s >= 30
        tareas = [
            t("demo-informe", "terminada" if fase_b else "en_curso", "claude", "sonnet", hace=s - 30 if fase_b else 5),
            t("demo-refactor", "en_curso" if fase_b else "en_cola", "codex", hace=3),
            t("demo-borrar-copias", "esperando_aprobacion", "ollama", "hermes3:8b", hace=s + 40),
        ]
        if fase_b:
            tareas.append(t("demo-publicar", "esperando_aprobacion", "claude", "haiku", hace=s - 30))
        return tareas

    def paso(self, ahora=None):
        ahora = time.time() if ahora is None else ahora
        s = (ahora - self.t0) % self.CICLO_S
        tareas = self._tareas(s, ahora)
        marca = {"_ejemplo": True, "_demo": DEMO_ETIQUETA}
        en_curso = next((x for x in tareas if x["estado"] == "en_curso"), None)
        _escribir(self.outbox / "cola-live.json", dict(marca, actualizado=_iso(ahora), guardrail="normal",
                                                       cola_pendiente=sum(x["estado"] == "en_cola" for x in tareas),
                                                       tareas=tareas))
        _escribir(self.outbox / "runner-status.json",
                  dict(marca, last_poll=_iso(ahora), current={"id": en_curso["id"]} if en_curso else None))
        _escribir(self.outbox / "runner-live.json",
                  dict(marca, task_id=en_curso["id"] if en_curso else None,
                       estado="en curso" if en_curso else "terminado", actualizado=_iso(ahora)))
        for x in tareas:
            if x["estado"] != "esperando_aprobacion":
                continue
            p = self.outbox / "aprobaciones" / f"apr-{x['id']}.pedido.json"
            if not p.is_file():
                motivo, palabras = {
                    "demo-borrar-copias": ("borrar archivos (R2, del encargo)", ["borra las copias viejas de *.bak"]),
                    "demo-publicar": ("publicar en internet (R2, del encargo)", ["publica el post en la web"]),
                }.get(x["id"], ("acción sensible", ["—"]))
                _escribir(p, dict(marca, approval_id=f"apr-{x['id']}", tarea=x["id"], raiz=x["id"], nivel="R2",
                                  nivel_nombre="con tu sí", motivo=motivo, estado="pendiente",
                                  creado_en=x["creado_en"], se_puede_por_whatsapp=True,
                                  pedido=f"(DEMO) {palabras[0]}",
                                  acciones=[{"tipo": "demo", "nivel": "R2", "nombre": motivo, "palabras": palabras}]))
        self.escrituras += 1
        return tareas


# ---- pedidos de aprobacion (solo lectura) ---------------------------------------------------
def leer_pedidos(carpeta):
    """{tarea: pedido} de los pedidos PENDIENTES en outbox\\aprobaciones\\ (los mas recientes primero).
    La oficina solo los lee: no los cambia, no los borra, no los guarda en otro sitio."""
    out = {}
    d = Path(carpeta)
    try:
        archivos = sorted(d.glob("*.pedido.json"), key=lambda q: q.stat().st_mtime, reverse=True)[:PEDIDOS_MAX]
    except OSError:
        return out
    for q in archivos:
        try:
            p = json.loads(q.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(p, dict) and p.get("estado") == "pendiente" and p.get("tarea") and p["tarea"] not in out:
            out[p["tarea"]] = p
    return out


def _corta(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def tarjeta(fila, pedido, ahora=None):
    """Lineas de la tarjeta (titulo, cuerpo..., pie). Sin botones: el pie dice DONDE se aprueba."""
    ahora = time.time() if ahora is None else ahora
    tid = (fila or {}).get("id") or "—"
    if not pedido:
        return ["Espera tu aprobación",
                f"Tarea: {tid} · Comando: — (el pedido aún no está publicado en outbox\\aprobaciones)",
                "Se aprueba en la app: Tareas → Esperan tu aprobación",
                "Aquí no se aprueba ni se rechaza nada."]
    pal = []
    for a in pedido.get("acciones") or []:
        pal += [str(w) for w in (a.get("palabras") or []) if w]
    nivel = pedido.get("nivel") or "—"
    donde = ("Se aprueba en la app (Tareas) o por WhatsApp" if pedido.get("se_puede_por_whatsapp")
             else "Solo se aprueba en la app (Tareas), con el PC delante")
    desde = "—"
    try:
        desde = datetime.fromisoformat(pedido.get("creado_en")).strftime("%H:%M")
    except (TypeError, ValueError):
        pass
    return [f"Espera tu aprobación · {nivel}" + (f" ({pedido['nivel_nombre']})" if pedido.get("nivel_nombre") else ""),
            f"Tarea: {tid} · Quiere: {_corta(pedido.get('motivo'), 80)}",
            "Comando: " + (_corta(" · ".join(f"«{w}»" for w in pal), 90) if pal else "—"),
            f"Encargo: {_corta(pedido.get('pedido'), 90) or '—'}",
            f"Estado: {pedido.get('estado') or '—'} desde las {desde} · la oficina no la deniega por tiempo",
            f"{donde}. Aquí no se aprueba ni se rechaza nada."]


# ---- caminar a la mesa del gerente ----------------------------------------------------------
def puestos_gerente(gx, gy, n):
    """Donde esperan los que piden permiso: a la derecha de la mesa del gerente, en fila."""
    return [(gx + 62 + 56 * (i % 2), gy + 4 + 56 * (i // 2)) for i in range(n)]


class Caminantes:
    def __init__(self, casa):
        self.casa = dict(casa)              # pid -> (x, y) de su mesa
        self.pos = {k: tuple(map(float, v)) for k, v in casa.items()}
        self.objetivo = dict(self.casa)
        self.llego = {}                     # pid -> instante en que llego a la mesa del gerente

    def mandar(self, pid, xy):
        if self.objetivo.get(pid) != xy:
            self.objetivo[pid] = xy
            self.llego.pop(pid, None)

    def a_casa(self, pid):
        self.mandar(pid, self.casa[pid])

    def andando(self, pid):
        return self.pos[pid] != tuple(map(float, self.objetivo[pid]))

    def fuera(self, pid):
        return self.objetivo[pid] != self.casa[pid] or self.andando(pid)

    def paso(self, dt, ahora=None):
        ahora = time.time() if ahora is None else ahora
        for pid, (ox, oy) in self.objetivo.items():
            x, y = self.pos[pid]
            dx, dy = ox - x, oy - y
            dist = (dx * dx + dy * dy) ** 0.5
            paso = VELOCIDAD_PX_S * max(0.0, min(dt, 0.25))
            if dist <= paso or dist < 0.5:
                self.pos[pid] = (float(ox), float(oy))
                if (ox, oy) != self.casa[pid] and pid not in self.llego:
                    self.llego[pid] = ahora
            else:
                self.pos[pid] = (x + dx / dist * paso, y + dy / dist * paso)
        return self.pos


# ---- camara: N centra en el que espera ------------------------------------------------------
class Camara:
    def __init__(self):
        self.foco = None
        self.hasta = 0.0
        self.centro = None

    def siguiente(self, esperando, ahora=None):
        """Tecla N: el siguiente que espera (en orden); None si nadie espera (no hace nada)."""
        ahora = time.time() if ahora is None else ahora
        if not esperando:
            self.foco = None
            return None
        i = (esperando.index(self.foco) + 1) % len(esperando) if self.foco in esperando else 0
        self.foco, self.hasta = esperando[i], ahora + CAMARA_DURA_S
        return self.foco

    def soltar(self):
        self.foco = None

    def activa(self, esperando, ahora=None):
        ahora = time.time() if ahora is None else ahora
        if self.foco is not None and (ahora > self.hasta or self.foco not in esperando):
            self.foco = None
        return self.foco

    def recorte(self, mundo, xy, dt):
        """Rect (x, y, w, h) del mundo a ampliar CAMARA_ZOOM veces, centrado (con suavizado) en xy."""
        mx, my, mw, mh = mundo
        if self.centro is None:
            self.centro = (mx + mw / 2, my + mh / 2)
        k = min(1.0, dt * 6.0)
        cx = self.centro[0] + (xy[0] - self.centro[0]) * k
        cy = self.centro[1] + (xy[1] - self.centro[1]) * k
        self.centro = (cx, cy)
        w, h = mw / CAMARA_ZOOM, mh / CAMARA_ZOOM
        x = max(mx, min(mx + mw - w, cx - w / 2))
        y = max(my, min(my + mh - h, cy - h / 2))
        return int(x), int(y), int(w), int(h)
