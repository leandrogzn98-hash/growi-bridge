"""Oficina 0.5.0 — PROTOTIPO del protocolo en Pygame-ce (t-oficina-protocolo-050, spec 5 de 18).

No es la oficina final: 16 sprites placeholder de 32x48 (cuadrados de color por departamento),
a 30 FPS, que muestran el estado DERIVADO de los archivos del Bridge (protocolo.py). Proceso
aparte: lo lanza el Bridge como subproceso (o se lanza a mano para probar), nunca un hilo de tkinter.

  python oficina_proto.py --share <carpeta share> --app <carpeta de la app> [--bridge-pid N]
                          [--datos <carpeta>] [--captura ruta.png@segundos] [--salir-a segundos]

Codigos de salida: 0 cerrada por el usuario · 2 «Bridge no disponible» (autocierre) ·
3 ya hay otra oficina abierta (mutex) · 4 la app pidio cerrarla · 5 falta pygame-ce.
"""
import argparse
import ctypes
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import protocolo as P  # noqa: E402
for _d in (AQUI.parent / "estados", AQUI / "estados"):
    if (_d / "estados.py").is_file():
        sys.path.insert(0, str(_d))
        break
import estados as E  # noqa: E402  (t-oficina-estados-050: derivar_estado, transiciones, dormir)
sys.path.insert(0, str(AQUI.parent / "telefono"))
import telefono as TF  # noqa: E402  (t-oficina-telefono-050: el telefono al gerente)
sys.path.insert(0, str(AQUI.parent / "llamadas"))
import llamadas as LL  # noqa: E402  (t-oficina-llamadas-050: la llamada que se ve = la invocacion real)
sys.path.insert(0, str(AQUI.parent / "vagancia"))
import vagancia as VG  # noqa: E402  (t-oficina-vagancia-050)
sys.path.insert(0, str(AQUI.parent / "bocadillos"))
import bocadillos as BC  # noqa: E402  (t-oficina-bocadillos-050)

ap = argparse.ArgumentParser()
ap.add_argument("--share", default=str(Path.home() / "growi-bridge" / "share"))
ap.add_argument("--app", default=None)
ap.add_argument("--bridge-pid", type=int, default=None)
ap.add_argument("--latido", default=None)
ap.add_argument("--datos", default=None)
ap.add_argument("--mutex", default=os.environ.get("GROWI_OFICINA_MUTEX") or "Local\\GrowiOficinaInstanciaUnica")
ap.add_argument("--captura", action="append", default=[])
ap.add_argument("--salir-a", type=float, default=None)
ap.add_argument("--pos", default=None)
ap.add_argument("--sueno-min", type=float, default=None)  # DEMO: acelera IDLE_SLEEP_MINUTES (se rotula)
A = ap.parse_args()
if A.sueno_min is not None:
    E.IDLE_SLEEP_MINUTES = A.sueno_min

SHARE = Path(A.share)
OUTBOX = SHARE / "outbox"
APP = Path(A.app) if A.app else SHARE.parent
DATOS = Path(A.datos) if A.datos else AQUI / "datos"
DATOS.mkdir(parents=True, exist_ok=True)
LOG = DATOS / "oficina-protocolo.log"
METRICAS = DATOS / f"metricas-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}.jsonl"
_mlock = threading.Lock()


def log(msg):
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} [oficina pid {os.getpid()}] {msg}"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass
    print(linea, flush=True)


def metrica(d):
    d = {"t": round(time.time(), 3), **d}
    with _mlock:
        try:
            with open(METRICAS, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        except OSError:
            pass


# ---- una sola instancia: mutex con nombre (antes de abrir ventana)
_mutex = None
try:
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = k32.CreateMutexW(None, False, A.mutex)
    err = k32.GetLastError()
    if err == 183 or (not _mutex and err == 5):
        log(f"ya hay una oficina abierta (mutex {A.mutex}): esta copia sale sin abrir ventana")
        metrica({"evento": "segunda_instancia_bloqueada", "mutex": A.mutex})
        sys.exit(3)
except AttributeError:
    pass

os.environ.setdefault("SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN", "0")
if A.pos:
    os.environ["SDL_VIDEO_WINDOW_POS"] = A.pos
try:
    import pygame
except ImportError:
    log("falta pygame-ce en este Python (python -m pip install pygame-ce==2.5.8): no se abre")
    sys.exit(5)

# ---- fuentes (cada una en su hilo)
F = {}


def _bridge_caido():
    """Bridge caido = sin latido 15 s, o runner-status viejo/ausente/roto: se lee como mucho cada 10 s."""
    return (_estado_bridge[0] == "no_disponible"
            or F["runner-status"].vista()["clase"] in ("viejo", "ausente", "roto"))


def _per(base):
    return lambda: max(base, P.PERIODO_SIN_BRIDGE_S) if _bridge_caido() else base


def _per_live():
    v = F["runner-live"].vista()
    d = v["datos"] if isinstance(v["datos"], dict) else {}
    activo = (v["clase"] in ("fresco", "viejo") and d.get("task_id") and d.get("estado") != "terminado"
              and (P.edad_iso(d.get("actualizado")) or 1e9) < P.LIVE_FRESCO_S * 4)
    # «Con tarea en curso» lo dicen tambien cola-live y runner-status (t-oficina-llamadas-050): mirarlo solo en
    # runner-live tardaba hasta 10 s en ver una llamada nueva (sin live todavia, se leia cada 10 s).
    if not activo and "cola-live" in F:
        cl = F["cola-live"].vista()["datos"]
        activo = isinstance(cl, dict) and any(x.get("estado") == "en_curso" for x in cl.get("tareas") or [])
    if not activo and "runner-status" in F:
        stt = F["runner-status"].vista()["datos"]
        activo = isinstance(stt, dict) and bool(stt.get("current"))
    return _per(P.PERIODO_LIVE_ACTIVO_S if activo else P.PERIODO_LIVE_REPOSO_S)()


def _leer_skills():
    return "ok", {"skills": P.skills_presentes(APP)}, "", 1


_estado_bridge = ["esperando", "", None]
RESULTS = OUTBOX / "runner-results"
APR_REG = OUTBOX / "aprobaciones-registro.jsonl"


def _leer_orq():
    """.orquestacion.json de las raices que salen en cola-live (pequenos; en su hilo, nunca en el render)
    y el canal de la ultima aprobacion de cada tarea (aprobaciones-registro.jsonl, las 400 ultimas)."""
    v = F["cola-live"].vista() if "cola-live" in F else {"datos": None}
    cola = v["datos"] if isinstance(v["datos"], dict) else {}
    orq = {}
    for t in cola.get("tareas") or []:
        raiz = t.get("raiz") or t.get("id")
        if raiz and raiz not in orq:
            est, d, _det, _n = P.leer_json(RESULTS / f"{raiz}.orquestacion.json")
            if est == "ok" and isinstance(d, dict):
                orq[raiz] = d
    apr = {}
    try:
        with open(APR_REG, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 200000))
            for linea in fh.read().decode("utf-8", "replace").splitlines()[-400:]:
                try:
                    d = json.loads(linea)
                except ValueError:
                    continue
                if d.get("evento") == "aprobada" and d.get("tarea"):
                    apr[d["tarea"]] = d.get("canal") or "app"
    except OSError:
        pass
    return "ok", {"orq": orq, "apr": apr}, "", 1
F["runner-live"] = P.Fuente("runner-live", OUTBOX / "runner-live.json", _per_live,
                            marca=lambda d: d.get("actualizado"), limite=P.LIVE_FRESCO_S, registro=metrica)
F["cola-live"] = P.Fuente("cola-live", OUTBOX / "cola-live.json", _per(P.PERIODO_COLA_S),
                          marca=lambda d: d.get("actualizado"), limite=P.COLA_FRESCA_S, registro=metrica)
F["runner-status"] = P.Fuente("runner-status", OUTBOX / "runner-status.json", _per(P.PERIODO_STATUS_S),
                              marca=lambda d: d.get("last_poll"), limite=P.STATUS_FRESCO_S, registro=metrica)
F["engines"] = P.Fuente("engines", APP / "engines.json", lambda: P.PERIODO_CONFIG_S, registro=metrica)
F["skills"] = P.Fuente("skills", APP / "skills", lambda: P.PERIODO_CONFIG_S, leer=_leer_skills, registro=metrica)
F["orq"] = P.Fuente("orq", RESULTS, lambda: 2, leer=_leer_orq, registro=metrica)
F["latido"] = P.Fuente("latido", Path(A.latido) if A.latido else OUTBOX / "bridge-latido.json",
                       lambda: P.PERIODO_LATIDO_S)
LAT = P.Latido(F["latido"], A.bridge_pid)
for f in F.values():
    f.arrancar()
log(f"abierta: share={SHARE} app={APP} bridge_pid={A.bridge_pid} mutex={A.mutex} datos={DATOS}")

# ---- encolar: la UNICA escritura hacia el Bridge, por oficina\encolar\encolar.py (import en 2o plano)
BOR = P.Borradores(DATOS / "borradores.json")
MEM = E.Memoria(registro=metrica)
_PLANO = AQUI.parent / "plano" / "plano.json"
_POIS = ({p_["id"]: p_["capacidad"] for p_ in json.loads(_PLANO.read_text(encoding="utf-8"))["puntos_interes"]}
         if _PLANO.is_file() else {"cafe": 2, "pasillo": 3})
GB = BC.Gestor()
LOGD = BC.LogDiario(APP / "oficina")
_ult_conf = [0]
OFV = VG.Oficina(_POIS, registro_raros=str(DATOS / "vagancia-raros.jsonl"))
TEL = TF.Telefono(cola=lambda: F["cola-live"].vista()["datos"] if "cola-live" in F else None, registro=metrica)
tel_abierto = False
tragar_t = False
ACTIVIDAD = {}
ENC = {"mod": None, "error": None, "listo": False, "enviando": False}


def _cargar_encolar():
    try:
        sys.path.insert(0, str(AQUI.parent / "encolar"))
        os.environ.setdefault("GROWI_BRIDGE_APP_DIR", str(APP))
        import encolar  # noqa: E402
        encolar.cargar_app(str(APP))
        ENC["mod"] = encolar
        log("encolado listo (encolar.py -> encolar_tarea de la app)")
    except BaseException as e:  # noqa: BLE001 (incluye SystemExit de un growi-bridge.py viejo)
        ENC["error"] = f"{type(e).__name__}: {e}"
        log(f"encolado NO disponible ({ENC['error']}): los encargos quedan como borrador")
    ENC["listo"] = True


if not os.environ.get("GROWI_OFICINA_SIN_ENCOLAR"):  # gancho de prueba
    threading.Thread(target=_cargar_encolar, daemon=True).start()


def _puede_enviar():
    return ENC["mod"] is not None and not _bridge_caido()


def _enviar_pendientes():
    if ENC["enviando"] or not _puede_enviar():
        return
    pend = BOR.pendientes()
    if not pend:
        return
    ENC["enviando"] = True

    def _hilo():
        try:
            for it in pend:
                if not _puede_enviar():
                    break
                r = ENC["mod"].encolar(it["texto"], [], model=None, ruta_app=str(APP), origen="oficina")
                if r.get("ok"):
                    BOR.marcar(it, estado="enviado", id=r.get("id"),
                               enviado=datetime.now().astimezone().isoformat(timespec="seconds"))
                    log(f"encargo enviado: {r.get('id')} («{it['texto'][:60]}»)")
                else:
                    BOR.marcar(it, error=r.get("error"))
                    log(f"encargo NO enviado, sigue de borrador: {r.get('error')}")
        except Exception as e:
            log(f"encolar falló ({type(e).__name__}: {e}); sigue de borrador")
        finally:
            ENC["enviando"] = False

    threading.Thread(target=_hilo, daemon=True).start()


def _seguir_enviados():
    """Estado real de lo enviado (cola.db en solo lectura). None = aun no registrada, NO «trabajando»."""
    if ENC["mod"] is None:
        return
    for it in [i for i in BOR.items if i.get("estado") == "enviado" and i.get("id")][-3:]:
        try:
            e = ENC["mod"].estado(it["id"], ruta_app=str(APP))
            it["estado_cola"] = e.get("estado") or "aún sin registrar en la cola"
        except Exception as ex:
            it["estado_cola"] = f"sin señal ({type(ex).__name__})"


# ---- ventana
pygame.init()
W, H = 1000, 660
pantalla = pygame.display.set_mode((W, H))
pygame.display.set_caption("Oficina Growi — prototipo de protocolo (Pygame-ce)")


def _fuente(t, bold=False):
    # Segoe UI directo del archivo: pygame.font.SysFont recorre todo el registro de fuentes y aqui
    # tardaba >8 s (medido): el primer fotograma no salia.
    windir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for nombre in (("segoeuib.ttf",) if bold else ()) + ("segoeui.ttf",):
        try:
            return pygame.font.Font(str(windir / nombre), t)
        except (OSError, FileNotFoundError):
            continue
    return pygame.font.Font(None, t + 4)


F12, F13, F15, F18, F28 = _fuente(12), _fuente(13), _fuente(15, True), _fuente(18, True), _fuente(30, True)
C = {"fondo": (245, 245, 247), "panel": (255, 255, 255), "texto": (29, 29, 31), "suave": (110, 110, 115),
     "linea": (220, 220, 225), "acento": (0, 122, 255), "verde": (52, 199, 89), "gris": (174, 174, 178),
     "rojo": (255, 59, 48), "ambar": (245, 166, 35)}
# Colores PROVISIONALES por departamento: los hex de PALETA-Y-SKINS §2 no estan en este PC (FALTA).
DEPTO = {"gerencia": ((245, 166, 35), "Gerencia"), "claude": ((232, 131, 58), "Claude"),
         "codex": ((46, 160, 90), "Codex"), "local": ((140, 82, 200), "Local"),
         "gemini": ((43, 92, 184), "Gemini (en obras)"), "taller3d": ((150, 105, 70), "Taller 3D"),
         "especialistas": ((90, 140, 160), "Sala de espera"), "despacho": ((0, 122, 255), "Despacho"),
         "noche": ((51, 89, 140), "Noche")}
ZONAS = [("gerencia", 30, 120, 120), ("despacho", 160, 120, 120), ("noche", 290, 120, 120),
         ("claude", 420, 120, 340), ("especialistas", 770, 120, 200),
         ("codex", 30, 300, 180), ("local", 220, 300, 260), ("gemini", 490, 300, 150),
         ("taller3d", 650, 300, 150)]
POS = {}
for depto, zx, zy, _w in ZONAS:
    miembros = [r for r in P.ROSTER if r[2] == depto]
    for i, r in enumerate(miembros):
        POS[r[0]] = (zx + 24 + i * 82, zy + 34)
ROT = {P.TRABAJANDO: "trabajando", P.EN_COLA: "en cola", P.SIN_TAREA: "sin tarea",
       P.SIN_SENAL: "sin señal", P.SIN_INSTALAR: "sin instalar"}


_TXT = {}  # (texto, fuente, color, ancho) -> superficie ya renderizada


def texto(s, f, col, x, y, ancho=None):
    # Cache de superficies + recorte por busqueda binaria: recortar de 2 en 2 con f.size() en cada
    # fotograma congelo el render ~950 ms al caer el Bridge (medido con faulthandler, 30 oct 2026).
    k = (s, id(f), col, ancho)
    sup = _TXT.get(k)
    if sup is None:
        if ancho and f.size(s)[0] > ancho:
            lo, hi = 4, len(s)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if f.size(s[:mid])[0] <= ancho:
                    lo = mid
                else:
                    hi = mid - 1
            s = s[:lo]
        if len(_TXT) > 600:
            _TXT.clear()
        sup = _TXT[k] = f.render(s, True, col)
    pantalla.blit(sup, (x, y))


def _edad(s):
    if s is None:
        return "—"
    return f"{s:.0f} s" if s < 120 else f"{s / 60:.0f} min"


_Z = None  # la «Z» flotante: UN sprite para todos los dormidos (no un frame por personaje)


def _z():
    global _Z
    if _Z is None:
        _Z = _fuente(16, True).render("Z", True, (90, 90, 110))
    return _Z


def dibujar_sprite(pid, nombre, depto, est, t, actividad=None):
    x, y = POS[pid]
    col = DEPTO[depto][0]
    caja = pygame.Rect(x, y, 32, 48)
    cara = (242, 230, 204)
    if est == P.SIN_INSTALAR:  # silla vacia: solo el contorno
        pygame.draw.rect(pantalla, C["gris"], caja, 1)
        texto("vacía", F12, C["suave"], x + 2, y + 16)
    elif est == E.SIN_SENAL:  # quieto, gris, con «?»: nunca teclea
        pygame.draw.rect(pantalla, C["gris"], caja)
        texto("?", F18, C["panel"], x + 11, y + 10)
    elif est == E.DORMIR:
        # encogido en la silla (6 px mas bajo), cabeza ladeada 3 px, ojos = dos rayitas,
        # respiracion lenta: el cuerpo sube y baja 1 px (periodo 4 s); la «Z» sube y se desvanece cada 3 s
        resp = 1 if (t % 4.0) < 2.0 else 0
        pygame.draw.rect(pantalla, col, (x, y + 6 - resp, 32, 42 + resp))
        pygame.draw.rect(pantalla, cara, (x + 11, y + 8 - resp, 16, 13))
        for ox in (14, 21):
            pygame.draw.line(pantalla, C["texto"], (x + ox, y + 14 - resp), (x + ox + 3, y + 14 - resp), 1)
        fase = ((t + (sum(map(ord, pid)) % 30) / 10.0) % 3.0) / 3.0
        z = _z()
        z.set_alpha(int(255 * (1 - fase)))
        pantalla.blit(z, (x + 26 + int(fase * 6), y - 2 - int(fase * 18)))
    else:
        dy = 0
        if est in (E.TRABAJANDO, E.EN_RONDA):  # animacion de trabajo: hay un evento real (live fresco)
            dy = (int(t * 8) % 2)
        elif est == E.SIN_TAREA:  # respiro: 1 px cada 2 s; estirarse: 2 px mas alto
            dy = 2 if actividad == "estirarse" else (1 if (t % 2.0) < 1.0 else 0)
        pygame.draw.rect(pantalla, col, caja.move(0, -dy))
        pygame.draw.rect(pantalla, cara, (x + 8, y + 3 - dy, 16, 14))  # cara
        if actividad == "parpadear":
            pygame.draw.line(pantalla, C["texto"], (x + 11, y + 9 - dy), (x + 21, y + 9 - dy), 1)
        if est in (E.TRABAJANDO, E.EN_RONDA):
            on = int(t * 8) % 2
            pygame.draw.rect(pantalla, C["texto"], (x - 2, y + 50, 36, 5))  # teclado
            pygame.draw.rect(pantalla, C["panel"], (x + 4 + on * 14, y + 51, 8, 3))
        marca = {E.EN_COLA: ("…", C["acento"]), E.ESPERANDO_APROBACION: ("!", C["ambar"]),
                 E.EN_REVISION: ("?", C["acento"]), E.EN_RONDA: ("↻", C["ambar"]), E.EN_PAUSA: ("II", C["suave"]),
                 E.TERMINADO: ("✓", C["verde"]), E.FALLIDO: ("×", C["rojo"])}.get(est)
        if marca:
            pygame.draw.circle(pantalla, marca[1], (x + 30, y + 2), 7)
            texto(marca[0], F12, C["panel"], x + 26, y - 7)
    texto(nombre, F12, C["texto"], x - 6, y + 56, 80)
    col_e = {E.TRABAJANDO: C["acento"], E.EN_COLA: C["acento"], E.ESPERANDO_APROBACION: C["ambar"],
             E.FALLIDO: C["rojo"], E.TERMINADO: C["verde"]}.get(est, C["suave"])
    etq = E.ETIQUETA.get(est) or ROT.get(est, est)
    if actividad and actividad not in ("respirar", "parpadear"):
        etq = f"{etq} · {actividad.replace('_', ' ')}"
    texto(etq, F12, col_e, x - 6, y + 70, 80)


# ---- vigia de fotogramas congelados: si un fotograma tarda mas de 1 s, faulthandler (hilo en C,
# funciona aunque alguien retenga el GIL) vuelca las pilas de todos los hilos a datos\congelado.txt
import faulthandler  # noqa: E402
_congelado = open(DATOS / "congelado.txt", "a", encoding="utf-8")

# ---- bucle (30 FPS)
reloj = pygame.time.Clock()
t0 = time.perf_counter()
capturas = []
for c in A.captura:
    ruta, _, seg = c.rpartition("@")
    capturas.append([float(seg), ruta, False])
entrada, foco = "", False
t_seg, frames, peor, lentos_f = 0.0, 0, 0.0, 0
codigo, cierre_t, cierre_motivo = None, None, ""
ultimo_envio, ultimo_seguir, ultimo_estados = 0.0, 0.0, {}
caja_in = pygame.Rect(30, H - 46, 560, 30)
icono_tel = pygame.Rect(W - 56, H - 56, 40, 40)
caido_antes = None
en_curso_antes = frozenset()

while True:
    dt = reloj.tick(30) / 1000.0
    faulthandler.dump_traceback_later(1.0, repeat=False, file=_congelado)
    t = time.perf_counter() - t0
    ahora = time.time()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            codigo, cierre_motivo = 0, "ventana cerrada por el usuario"
        elif e.type == pygame.MOUSEBUTTONDOWN:
            for _pid, (_x, _y) in POS.items():
                if pygame.Rect(_x, _y, 32, 48).collidepoint(e.pos) and MEM.despertar(_pid, "clic del jugador"):
                    log(f"{_pid} despierta: clic del jugador (T24)")
            if icono_tel.collidepoint(e.pos):
                tel_abierto = not tel_abierto
            foco = tel_abierto and caja_in.collidepoint(e.pos) or (tel_abierto and icono_tel.collidepoint(e.pos))
            (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()
        elif e.type == pygame.TEXTINPUT and foco:
            if tragar_t and e.text.lower() == "t":  # la T que abrio el telefono no se escribe
                tragar_t = False
                continue
            tragar_t = False
            entrada = (entrada + e.text)[:500]
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_v and not foco:  # «oficina seria»: apaga la vagancia, no el sueño
                OFV.vagancia_activa = not OFV.vagancia_activa
                log(f"vagancia {'encendida' if OFV.vagancia_activa else 'apagada (oficina seria)'}")
                continue
            if e.key == pygame.K_t and not foco:
                tel_abierto, foco, tragar_t = True, True, True  # el telefono: tecla T
                pygame.key.start_text_input()
                continue
            if e.key == pygame.K_TAB:
                foco = not foco
                tel_abierto = tel_abierto or foco
                (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()
            elif foco and e.key == pygame.K_BACKSPACE:
                entrada = entrada[:-1]
            elif foco and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and entrada.strip():
                if _puede_enviar():  # el telefono: el gerente lo clasifica y, si es tarea, la encola como la app
                    TEL.enc = ENC["mod"]
                    r_tel = TEL.enviar(entrada.strip())
                    log(f"telefono: «{entrada.strip()[:60]}» -> {r_tel}")
                else:
                    it = BOR.nuevo(entrada.strip())  # sin Bridge: borrador en disco, «pendiente de enviar»
                    log(f"encargo escrito sin Bridge: «{it['texto'][:60]}» -> borrador local, pendiente de enviar")
                entrada = ""
            elif e.key == pygame.K_ESCAPE:
                foco, tel_abierto = False, False
                pygame.key.stop_text_input()
    if codigo is not None and cierre_t is None:
        break

    # latido del Bridge (lectura ya hecha en su hilo: aqui solo se mira)
    eb, motivo_b, sin_lat = LAT.comprobar(ahora)
    if eb == "cerrar" and codigo is None:
        codigo, cierre_motivo = 4, motivo_b
        break
    if eb == "no_disponible":
        if cierre_t is None:
            cierre_t, cierre_motivo = t, motivo_b
            log(f"Bridge no disponible: {motivo_b}. La oficina se cierra sola en 3 s")
            metrica({"evento": "bridge_no_disponible", "motivo": motivo_b, "sin_latido_s": sin_lat})
            for f in F.values():
                f.ya()
        _estado_bridge[:] = ["no_disponible", motivo_b, sin_lat]
    else:
        _estado_bridge[:] = [eb, motivo_b, sin_lat]
    if cierre_t is not None and t - cierre_t >= 3.0:
        codigo = 2
        break

    caido = _bridge_caido()
    if caido != caido_antes:  # cambia el ritmo: las fuentes no esperan al final de su periodo viejo
        caido_antes = caido
        metrica({"evento": "ritmo", "bridge_caido": caido})
        for f in F.values():
            f.ya()
    _cl = F["cola-live"].vista()["datos"]
    _en_curso = frozenset(x.get("id") for x in (_cl or {}).get("tareas") or [] if x.get("estado") == "en_curso") \
        if isinstance(_cl, dict) else frozenset()
    if _en_curso - en_curso_antes:  # una tarea nueva arranca: runner-live se lee YA (no al final de sus 10 s)
        F["runner-live"].ya()
    en_curso_antes = _en_curso
    V = {k: f.vista(ahora) for k, f in F.items()}
    est_p = P.derivar(V, "vivo" if eb == "vivo" else eb, ahora)

    def _d(k):
        v = V[k]
        return v["datos"] if v["clase"] in ("fresco", "viejo") and isinstance(v["datos"], dict) else None
    fu = {"status": _d("runner-status"), "status_edad": V["runner-status"]["edad_contenido"],
          "live": _d("runner-live"), "live_edad": V["runner-live"]["edad_contenido"],
          "cola": _d("cola-live"), "cola_edad": V["cola-live"]["edad_contenido"], "latido_ok": eb == "vivo"}
    oq = V["orq"]["datos"] if isinstance(V["orq"]["datos"], dict) else {"orq": {}, "apr": {}}
    asig = E.asignar(fu["cola"], ahora)
    activas = [x for x in (fu["cola"] or {}).get("tareas") or [] if x.get("estado") in E.TAREA_ACTIVA]
    est = {}
    if activas:  # Runa (despacha la cola) y Growi (la orquesta) no estan «sin tarea» mientras haya cola viva
        for pid in ("runa", "growi"):
            MEM.despertar(pid, "la cola tiene trabajo", ahora)
            MEM.libre_desde[pid] = ahora
    for pid, _n, _dep, _tipo, _cl in P.ROSTER:
        if est_p[pid][0] == P.SIN_INSTALAR:
            est[pid] = est_p[pid]
            continue
        fila = asig.get(pid)
        tr = E.EstadoTarea(fila, orq=oq["orq"].get((fila or {}).get("raiz") or (fila or {}).get("id")),
                           live=fu["live"], ahora=ahora) if fila else None
        e_, m_, _t = MEM.paso({"id": pid, "rol": _tipo}, tr, fu, ahora, oq["apr"].get((fila or {}).get("id")))
        est[pid] = (e_, m_)
    for pid in E.comprobar_serie({k: v[0] for k, v in est.items()}):
        est[pid] = (E.SIN_SENAL, "dos agentes trabajando a la vez: el runner es serie")
        metrica({"evento": "fuera_de_tabla", "agente": pid, "motivo": "serie"})
    ACTIVIDAD.clear()
    for pid, (e_, _m) in est.items():
        if pid == "growi" and TEL.estado != "colgado":
            ACTIVIDAD[pid] = "al teléfono"
        elif pid == "growi" and e_ in (E.SIN_TAREA, E.SIN_SENAL):
            ACTIVIDAD[pid] = E.gerente_rutina(t, any(x.get("estado") in E.TAREA_ESPERA_HUMANO for x in activas),
                                              e_ == E.SIN_SENAL, [f"mesa_{k}" for k in ("clau", "dex", "luma")])[0]
        elif pid == "runa" and e_ == E.SIN_TAREA and activas:
            ACTIVIDAD[pid] = f"despachando {len(activas)}"
        elif e_ == E.SIN_TAREA:
            ACTIVIDAD[pid] = E.actividad_sin_tarea(pid, t)
    for pid, (e_, _m) in est.items():  # R2: el estado real llega a la vagancia en el mismo fotograma
        if pid not in ("growi", "runa", "vigilante"):
            OFV.evento_estado(pid, e_, ahora)
    for _ag, _tipo, _dato in OFV.tick(ahora):
        if _tipo in ("raro", "bocadillo"):
            metrica({"evento": "vagancia_" + _tipo, "agente": _ag, "dato": _dato})
        if _tipo == "bocadillo" and _dato and _dato != "...":
            GB.poner(BC.Bocadillo(_ag, "charla", _dato, ahora=ahora))  # nube, sin log
    for _c in TEL.confirmaciones[_ult_conf[0]:]:  # cada confirmacion del telefono: bocadillo + log con lo dicho
        _ref = LOGD.escribir("Leandro", "Growi", "teléfono al gerente", f"«{_c[0]}» → {_c[1]}", tipo="estado")
        GB.poner(BC.Bocadillo("growi", "aceptacion", _c[1], depto="Gerencia", ref_log=_ref, ahora=ahora))
    _ult_conf[0] = len(TEL.confirmaciones)
    for pid in list(ACTIVIDAD):
        _act = OFV.actividad_de(pid)
        if _act:
            ACTIVIDAD[pid] = _act
    cambios = {k: v[0] for k, v in est.items() if ultimo_estados.get(k) != v[0]}
    if cambios:
        metrica({"evento": "estados", "cambios": cambios})
        ultimo_estados.update(cambios)
    if ahora - ultimo_envio > P.PERIODO_SIN_BRIDGE_S:
        ultimo_envio = ahora
        _enviar_pendientes()
    if ahora - ultimo_seguir > 5:
        ultimo_seguir = ahora
        threading.Thread(target=_seguir_enviados, daemon=True).start()

    # ---- pintar
    pantalla.fill(C["fondo"])
    pygame.draw.rect(pantalla, C["panel"], (0, 0, W, 92))
    pygame.draw.line(pantalla, C["linea"], (0, 92), (W, 92))
    texto("Oficina Growi · prototipo de protocolo", F15, C["texto"], 20, 8)
    _tn = BC.te_necesitan(fu["cola"] if "fu" in dir() else None)
    texto(f"Te necesitan: {_tn}", F15, C["ambar"] if _tn not in ("0", "—") else C["suave"], W - 430, 8)
    ejemplo = any(v["ejemplo"] for v in V.values())
    if ejemplo:
        texto("DATOS DE EJEMPLO — no son del runner", F15, C["ambar"], 330, 8)
    if A.sueno_min is not None:
        texto(f"DEMO: se duermen a los {A.sueno_min * 60:.0f} s sin tarea", F13, C["ambar"], 600, 488)
    if eb == "vivo":
        pygame.draw.circle(pantalla, C["verde"], (W - 250, 18), 6)
        texto(f"Bridge: responde ({motivo_b})", F13, C["texto"], W - 238, 9)
    else:
        pygame.draw.circle(pantalla, C["gris"], (W - 250, 18), 6)
        texto(f"Bridge: {'no disponible' if eb == 'no_disponible' else 'esperando'}", F13, C["texto"], W - 238, 9)
    x = 20
    for k in ("runner-live", "cola-live", "runner-status", "engines", "skills"):
        v = V[k]
        col = {"fresco": C["texto"], "viejo": C["ambar"]}.get(v["clase"], C["suave"])
        lin1 = f"{k}: {v['clase']}" + (" · lectura lenta" if v["lento"] else "")
        lin2 = (f"bueno de hace {_edad(v['edad_lectura'])}"
                + (f" · dato de {_edad(v['edad_contenido'])}" if v["edad_contenido"] is not None else ""))
        lin3 = (f"última {v['ultima_ms']:.1f} ms · a tiempo {v['a_tiempo']}/{v['lecturas']}"
                if v["ultima_ms"] is not None else "sin leer aún")
        texto(lin1, F13, col, x, 32, 188)
        texto(lin2, F12, C["suave"], x, 50, 188)
        texto(lin3, F12, C["suave"], x, 66, 188)
        x += 194
    for depto, zx, zy, ancho in ZONAS:
        pygame.draw.rect(pantalla, C["panel"], (zx, zy, ancho, 160), border_radius=8)
        pygame.draw.rect(pantalla, C["linea"], (zx, zy, ancho, 160), 1, border_radius=8)
        pygame.draw.rect(pantalla, DEPTO[depto][0], (zx + 10, zy + 12, 10, 10))
        texto(DEPTO[depto][1], F13, C["texto"], zx + 26, zy + 7, ancho - 30)
    for pid, nombre, depto, _tipo, _cl in P.ROSTER:
        dibujar_sprite(pid, nombre, depto, est[pid][0], t, ACTIVIDAD.get(pid))
    # leyenda de motivos (de donde sale cada estado)
    pygame.draw.rect(pantalla, C["panel"], (0, 480, W, H - 480))
    pygame.draw.line(pantalla, C["linea"], (0, 480), (W, 480))
    texto(f"{len(P.ROSTER)} sprites (14 personajes + Runa + vigilante) · "
          f"{sum(1 for v in est.values() if v[0] == E.SIN_SENAL)} sin señal · motivo de Growi: {est['growi'][1]}",
          F12, C["suave"], 30, 488, W - 60)
    texto(f"Runa: {est['runa'][1]} · Sonny: {est['sonny'][1]}", F12, C["suave"], 30, 504, W - 60)
    if eb != "vivo":
        texto(f"Bridge no disponible — {motivo_b}" if eb == "no_disponible" else motivo_b,
              F13, C["texto"], 30, 520, W - 60)
    # encargos: primero a disco; si no hay Bridge, borrador visible «pendiente de enviar»
    # ---- llamada en curso (t-oficina-llamadas-050): solo si hay una fase real que mostrar
    _motores = set(((V["engines"]["datos"] or {}).get("motores") or {}).keys()) if isinstance(V["engines"]["datos"], dict) else set()
    _llam = None
    for _f in (fu["cola"] or {}).get("tareas") or []:
        if _f.get("estado") in ("en_curso", "en_cola", "esperando_aprobacion") or _f.get("proximo_intento"):
            _l = LL.llamada(_f, fu["cola"], fu["live"], fu["status"], _motores, ahora, fu["live_edad"])
            if _l["fase"] and (_llam is None or _l["fase"] in ("marcando", "timbre", "en_linea", "encendiendo", "buzon")):
                _llam = _l
                if _l["fase"] in ("marcando", "timbre", "en_linea", "encendiendo", "buzon"):
                    break
    if _llam:
        gx, gy = POS["growi"]
        jefe = _llam.get("jefe")
        if _llam["linea"] and jefe in POS:
            jx, jy = POS[jefe]
            n = 24
            for k in range(0, n, 2):  # linea punteada tenue
                a, b = k / n, (k + 1) / n
                pygame.draw.line(pantalla, C["linea"], (gx + 16 + (jx - gx) * a, gy + 10 + (jy - gy) * a),
                                 (gx + 16 + (jx - gx) * b, gy + 10 + (jy - gy) * b), 2)
            if _llam.get("jefe_dice"):
                texto(_llam["jefe_dice"], F12, C["texto"], jx - 4, jy - 18, 160)
        if _llam.get("duracion"):
            texto(_llam["duracion"], F13, C["ambar"] if _llam["ambar"] else C["suave"], gx + 40, gy + 20)
        linea_g = _llam.get("gerente") or ""
        if _llam["fase"] == "ocupado" and _llam.get("posicion") is None:
            linea_g = linea_g or "En cola, sin posición."
        if linea_g and not (TEL.bocadillo and time.time() - TEL.bocadillo[1] < 8):
            texto(f"[{_llam['fase']}] {linea_g}", F12, C["rojo"] if _llam["fase"] in ("no_contesta", "necesita_revision",
                  "suena_en_vacio") else C["texto"], 30, 524, W - 60)
    # ---- telefono al gerente (t-oficina-telefono-050): una linea, sin historial
    pygame.draw.rect(pantalla, C["acento"] if tel_abierto else C["panel"], icono_tel, border_radius=10)
    pygame.draw.rect(pantalla, C["linea"], icono_tel, 1, border_radius=10)
    texto("T", F18, C["panel"] if tel_abierto else C["texto"], icono_tel.x + 14, icono_tel.y + 8)
    if tel_abierto:
        gr = ((V["cola-live"]["datos"] or {}).get("guardrail") if isinstance(V["cola-live"]["datos"], dict) else None)
        texto(f"Teléfono al gerente · guardrail: {gr or '—'} · motor sugerido: {TEL.motor_sugerido()}"
              f"{' · Growi está leyendo…' if TEL.estado != 'colgado' else ''}", F12, C["suave"], 30, 540, W - 120)
        pygame.draw.rect(pantalla, C["panel"], caja_in, border_radius=6)
        pygame.draw.rect(pantalla, C["acento"] if foco else C["linea"], caja_in, 1, border_radius=6)
        texto(entrada + ("|" if foco and int(t * 2) % 2 else ""), F13, C["texto"], caja_in.x + 8, caja_in.y + 5,
              caja_in.w - 16)
        texto("Enviar ⏎", F13, C["acento"], caja_in.right + 10, caja_in.y + 6)
    else:
        texto("Pulsa T (o el icono) para llamar al gerente · V: "
              + ("vagancia encendida" if OFV.vagancia_activa else "oficina seria (vagancia apagada)"),
              F12, C["suave"], 30, H - 40)
    pend = BOR.pendientes()
    if pend:  # solo lo pendiente de enviar (sin Bridge), nunca un historial
        texto(f"{len(pend)} pendiente(s) de enviar: «{pend[-1]['texto'][:50]}»", F12, C["ambar"], 30, 556, W - 120)
    for _b in GB.tick(ahora):  # bocadillos con las 3 señales (t-oficina-bocadillos-050)
        if _b.agente not in POS:
            continue
        bx, by = POS[_b.agente]
        es = BC.estilo(_b.tipo, _b.depto)
        fnt = F12
        ancho = min(260, 16 + fnt.size(_b.texto)[0])
        caja = pygame.Rect(bx + 16 - ancho // 2, by - 40, ancho, 22)
        caja.x = max(4, min(W - ancho - 4, caja.x))  # dentro de la ventana (la cola sigue apuntando al sprite)
        if es["forma"] == "nube":  # pensamiento: borde ondulado, sin cola recta, gris italica
            for k in range(0, ancho, 10):
                pygame.draw.circle(pantalla, C["panel"], (caja.x + k + 5, caja.y + 2), 6)
                pygame.draw.circle(pantalla, es["borde"], (caja.x + k + 5, caja.y + 2), 6, 1)
            pygame.draw.rect(pantalla, C["panel"], caja, border_radius=11)
            pygame.draw.circle(pantalla, es["borde"], (bx + 18, by - 12), 3, 1)
            fnt.set_italic(True)
            texto(_b.texto, fnt, es["texto"], caja.x + 8, caja.y + 3, ancho - 12)
            fnt.set_italic(False)
        else:  # dialogo: borde solido de 2 px del departamento y cola recta al sprite
            pygame.draw.rect(pantalla, C["panel"], caja, border_radius=8)
            pygame.draw.rect(pantalla, es["borde"], caja, 2, border_radius=8)
            pygame.draw.polygon(pantalla, es["borde"], [(bx + 12, caja.bottom), (bx + 20, caja.bottom), (bx + 16, by - 8)])
            texto(_b.texto, fnt, es["texto"], caja.x + 8, caja.y + 3, ancho - 24)
            if es["marca"] == "real":
                pygame.draw.circle(pantalla, C["verde"], (caja.right - 8, caja.y + 11), 4)
    if False:
        gx, gy = POS["growi"]
        caja_b = pygame.Rect(gx - 10, gy - 34, min(560, 12 + F12.size(TEL.bocadillo[0])[0]), 22)
        pygame.draw.rect(pantalla, C["panel"], caja_b, border_radius=8)
        pygame.draw.rect(pantalla, C["texto"], caja_b, 1, border_radius=8)
        texto(TEL.bocadillo[0], F12, C["texto"], caja_b.x + 6, caja_b.y + 3, 548)
    elif TEL.estado != "colgado":
        gx, gy = POS["growi"]
        texto("…", F18, C["texto"], gx + 8, gy - 26)
    if cierre_t is not None:
        pygame.draw.rect(pantalla, (40, 40, 42), (W // 2 - 260, 200, 520, 110), border_radius=12)
        texto("Bridge no disponible", F28, C["panel"], W // 2 - 150, 214)
        texto(f"La oficina se cierra sola en {max(0, 3 - (t - cierre_t)):.0f} s", F13, C["panel"],
              W // 2 - 120, 262)
    pygame.display.flip()

    for c in capturas:
        if not c[2] and t >= c[0]:
            pygame.image.save(pantalla, c[1])
            c[2] = True
            log(f"captura {c[1]} a los {t:.1f} s")
    frames += 1
    peor = max(peor, dt)
    lentos_f += dt > 0.05
    t_seg += dt
    if t_seg >= 1.0:
        metrica({"fps": round(reloj.get_fps(), 1), "frames": frames, "peor_ms": round(peor * 1000, 1),
                 "frames_50ms": lentos_f, "bridge": eb,
                 "fuentes": {k: [V[k]["clase"], V[k]["lento"]] for k in V}})
        t_seg, frames, peor, lentos_f = 0.0, 0, 0.0, 0
    if A.salir_a is not None and t >= A.salir_a and codigo is None:
        codigo, cierre_motivo = 0, f"--salir-a {A.salir_a}"
        break

for f in F.values():
    f.parar()
resumen = {k: f.resumen() for k, f in F.items()}
metrica({"evento": "salida", "codigo": codigo, "motivo": cierre_motivo, "resumen": resumen})
log(f"cerrada (código {codigo}): {cierre_motivo}")
pygame.quit()
sys.exit(codigo or 0)
