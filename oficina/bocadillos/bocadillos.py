"""Bocadillos, avisos y log diario de la oficina (t-oficina-bocadillos-050, spec 16 de 18).

- Bocadillo: <= 140 caracteres (cita: resumen del modelo o PRIMERA FRASE LITERAL cortada con «...»); duracion
  2 s + 60 ms/caracter (3-10 s) con fade de 300 ms; clic lo fija 30 s. El texto completo vive en el log.
- Cola: FIFO de 2 por personaje, 1 visible por personaje, 3 visibles en toda la oficina.
- Real vs decorativo con 3 señales: forma (dialogo / nube), marca (punto verde «real» / gris italica), origen
  (log trazable / «charla de oficina»).
- Avisos: la oficina NO tiene cola propia. La app ya avisa de terminada/fallida/necesita decision (una vez por
  raiz+estado) y de «esperando aprobacion» (popup del guardrail): la oficina no repite. La cola compartida
  con dedup oficina<->app NO existe (duda 20): `politica_aviso()` dice que avisaria y con que clave.
- Log diario oficina/AAAA-MM-DD.md: quien, a quien, cuando, por que canal; respuesta completa; la charla no va;
  resumen de 3 lineas al cerrar el dia; retencion 90 dias y luego oficina/archivo/ (se mueve, no se borra).
"""
import re
import shutil
import time
from datetime import date, datetime, timedelta
from pathlib import Path

MAX_CAR = 140
COLA_POR_AGENTE = 2
VISIBLES_MAX = 3
FIJADO_S = 30
RETENCION_DIAS = 90
COLOR_DEPTO = {"Claude": (232, 131, 58), "Codex": (46, 160, 90), "Local": (140, 82, 200), "Gemini": (66, 133, 244),
               "Taller 3D": (150, 105, 70), "Gerencia": (245, 166, 35), "Despacho": (0, 122, 255)}
TIPOS = ("respuesta", "aceptacion", "esperando", "estado", "error", "charla")


def resumen_hablado(texto, n=MAX_CAR):
    """Via segura (no depende de que el modelo resuma): la PRIMERA FRASE LITERAL, cortada a n con «...»."""
    t = " ".join(str(texto or "").split())
    m = re.match(r"(.+?[.!?…])(\s|$)", t)
    frase = m.group(1) if m else t
    return frase if len(frase) <= n else frase[: n - 3].rstrip() + "..."


def duracion(texto):
    return min(10.0, max(3.0, 2.0 + 0.06 * len(texto or "")))


def estilo(tipo, depto=None):
    """Las 3 señales redundantes. -> dict(forma, borde, marca, texto_color, italica, origen)."""
    if tipo == "charla":
        return {"forma": "nube", "borde": (174, 174, 178), "marca": None, "texto": (120, 120, 125), "italica": True,
                "origen": "charla de oficina", "cola_recta": False}
    borde = {"esperando": (245, 166, 35), "estado": (174, 174, 178), "error": (255, 59, 48)}.get(
        tipo, COLOR_DEPTO.get(depto or "", (29, 29, 31)))
    return {"forma": "dialogo", "borde": borde, "marca": "real" if tipo == "respuesta" else
            ("reloj" if tipo == "esperando" else None), "texto": (29, 29, 31), "italica": False,
            "origen": "log", "cola_recta": True}


class Bocadillo:
    def __init__(self, agente, tipo, texto, depto=None, ref_log=None, ahora=None):
        assert tipo in TIPOS, tipo
        self.agente, self.tipo, self.depto = agente, tipo, depto
        self.completo = str(texto or "")
        self.texto = self.completo if len(self.completo) <= MAX_CAR else resumen_hablado(self.completo)
        self.ref_log = None if tipo == "charla" else ref_log
        self.desde = None
        self.dur = duracion(self.texto)
        self.fijado_hasta = None
        self.creado = time.time() if ahora is None else ahora

    def alfa(self, ahora):
        """Opacidad con fade de 300 ms al entrar y al salir (1 = opaco)."""
        if self.desde is None:
            return 0.0
        t = ahora - self.desde
        if self.fijado_hasta and ahora < self.fijado_hasta:
            return 1.0
        return max(0.0, min(1.0, t / 0.3, (self.dur - t) / 0.3))

    def vivo(self, ahora):
        if self.fijado_hasta and ahora < self.fijado_hasta:
            return True
        return self.desde is None or ahora - self.desde < self.dur


class Gestor:
    """Colas por personaje y limite global de visibles."""

    def __init__(self):
        self.colas = {}
        self.visibles = []

    def poner(self, b):
        c = self.colas.setdefault(b.agente, [])
        c.append(b)
        while len(c) > COLA_POR_AGENTE:  # llega un tercero: se descarta el mas viejo
            c.pop(0)

    def tick(self, ahora):
        self.visibles = [b for b in self.visibles if b.vivo(ahora)]
        for ag in list(self.colas):
            if len(self.visibles) >= VISIBLES_MAX:
                break
            if any(b.agente == ag for b in self.visibles) or not self.colas[ag]:
                continue
            b = self.colas[ag].pop(0)
            b.desde = ahora
            self.visibles.append(b)
        return list(self.visibles)

    def fijar(self, agente, ahora):
        for b in self.visibles:
            if b.agente == agente:
                b.fijado_hasta = ahora + FIJADO_S
                return True
        return False

    def soltar(self, ahora):
        for b in self.visibles:
            b.fijado_hasta = None


# ---- avisos: politica (la cola compartida no existe: duda 20)
AVISA = {"terminada", "esperando_aprobacion", "error"}
NO_AVISA = {"aceptada", "encolada", "charla", "progreso", "resumen"}
LO_AVISA_LA_APP = {"terminada": "_watch_families: un toast por raiz+estado (aprobada / sin revisión / necesita "
                                "decisión / fallida)",
                   "esperando_aprobacion": "popup del guardrail (uno por evento, agrupado)",
                   "error": "_watch_families (fallida / necesita decisión)"}


def politica_aviso(evento, tarea_id):
    """-> dict(avisaria, la_oficina_avisa, motivo, clave). La oficina hoy no emite ninguno: o lo avisa la app,
    o el evento no se avisa, o falta la cola compartida para deduplicar."""
    clave = f"{tarea_id}:{evento}"
    if evento in NO_AVISA:
        return {"avisaria": False, "la_oficina_avisa": False, "motivo": "no se avisa (§5.7)", "clave": None}
    if evento in AVISA:
        return {"avisaria": True, "la_oficina_avisa": False, "clave": clave,
                "motivo": f"ya lo avisa la app ({LO_AVISA_LA_APP[evento]}): la oficina no lo repite"}
    return {"avisaria": False, "la_oficina_avisa": False, "motivo": "evento desconocido", "clave": None}


def texto_aviso(actor, accion, objeto):
    """Actor + acción + objeto en menos de 15 palabras."""
    t = f"{actor} {accion} {objeto}".strip()
    p = t.split()
    return " ".join(p[:14]) + ("…" if len(p) > 14 else "")


# ---- log diario
class LogDiario:
    def __init__(self, carpeta):
        self.dir = Path(carpeta)
        self.dir.mkdir(parents=True, exist_ok=True)

    def ruta(self, dia=None):
        return self.dir / f"{(dia or date.today()).isoformat()}.md"

    def escribir(self, quien, a_quien, canal, texto, tipo="estado", costo=None, ahora=None):
        """La charla decorativa NO va al log. Devuelve la referencia (archivo#linea) o None."""
        if tipo == "charla":
            return None
        ahora = datetime.now() if ahora is None else ahora
        p = self.ruta(ahora.date())
        if not p.exists():
            p.write_text(f"# Oficina — {ahora.date().isoformat()}\n\n", encoding="utf-8")
        linea = f"- {ahora:%H:%M:%S} · {quien} → {a_quien} · {canal} · {tipo}: {' '.join(str(texto).split())}"
        if costo:
            linea += f" · costo: {costo}"
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(linea + "\n")
        n = sum(1 for _ in open(p, encoding="utf-8"))
        return f"{p.name}#{n}"

    def cerrar_dia(self, dia):
        """Resumen de 3 lineas arriba del dia (tareas cerradas, pendientes, errores)."""
        p = self.ruta(dia)
        if not p.exists():
            return None
        lineas = p.read_text(encoding="utf-8").splitlines()
        cuerpo = [x for x in lineas if x.startswith("- ")]
        cerradas = sum(1 for x in cuerpo if re.search(r"· estado: (terminó|aprobad)", x))
        errores = sum(1 for x in cuerpo if "· error:" in x)
        pendientes = sum(1 for x in cuerpo if "· esperando:" in x)
        resumen = ["## Resumen del día", f"1. Tareas cerradas: {cerradas}.",
                   f"2. Pendientes de tu aprobación: {pendientes}.", f"3. Errores: {errores}.", ""]
        out = [lineas[0], ""] + resumen + [x for x in lineas[1:] if x and not x.startswith(("## Resumen", "1. ", "2. ", "3. "))]
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
        return resumen[1:4]

    def archivar(self, hoy=None):
        """Mas de 90 dias: se MUEVEN a oficina/archivo/ (no se borran)."""
        hoy = hoy or date.today()
        arch = self.dir / "archivo"
        movidos = []
        for p in self.dir.glob("????-??-??.md"):
            try:
                d = date.fromisoformat(p.stem)
            except ValueError:
                continue
            if (hoy - d) > timedelta(days=RETENCION_DIAS):
                arch.mkdir(exist_ok=True)
                shutil.move(str(p), str(arch / p.name))
                movidos.append(p.name)
        return movidos

    def buscar(self, texto, dia=None):
        p = self.ruta(dia)
        return [x for x in p.read_text(encoding="utf-8").splitlines() if texto.lower() in x.lower()] if p.exists() else []


def te_necesitan(cola):
    """«Te necesitan: N» desde cola-live; sin señal = «—», nunca 0."""
    if not isinstance(cola, dict) or not isinstance(cola.get("tareas"), list):
        return "—"
    return str(sum(1 for x in cola["tareas"] if x.get("estado") in ("esperando_aprobacion", "esperando_leandro")))
