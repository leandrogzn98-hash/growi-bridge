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
A = ap.parse_args()

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
    return _per(P.PERIODO_LIVE_ACTIVO_S if activo else P.PERIODO_LIVE_REPOSO_S)()


def _leer_skills():
    return "ok", {"skills": P.skills_presentes(APP)}, "", 1


_estado_bridge = ["esperando", "", None]
F["runner-live"] = P.Fuente("runner-live", OUTBOX / "runner-live.json", _per_live,
                            marca=lambda d: d.get("actualizado"), limite=P.LIVE_FRESCO_S, registro=metrica)
F["cola-live"] = P.Fuente("cola-live", OUTBOX / "cola-live.json", _per(P.PERIODO_COLA_S),
                          marca=lambda d: d.get("actualizado"), limite=P.COLA_FRESCA_S, registro=metrica)
F["runner-status"] = P.Fuente("runner-status", OUTBOX / "runner-status.json", _per(P.PERIODO_STATUS_S),
                              marca=lambda d: d.get("last_poll"), limite=P.STATUS_FRESCO_S, registro=metrica)
F["engines"] = P.Fuente("engines", APP / "engines.json", lambda: P.PERIODO_CONFIG_S, registro=metrica)
F["skills"] = P.Fuente("skills", APP / "skills", lambda: P.PERIODO_CONFIG_S, leer=_leer_skills, registro=metrica)
F["latido"] = P.Fuente("latido", Path(A.latido) if A.latido else OUTBOX / "bridge-latido.json",
                       lambda: P.PERIODO_LATIDO_S)
LAT = P.Latido(F["latido"], A.bridge_pid)
for f in F.values():
    f.arrancar()
log(f"abierta: share={SHARE} app={APP} bridge_pid={A.bridge_pid} mutex={A.mutex} datos={DATOS}")

# ---- encolar: la UNICA escritura hacia el Bridge, por oficina\encolar\encolar.py (import en 2o plano)
BOR = P.Borradores(DATOS / "borradores.json")
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


def dibujar_sprite(pid, nombre, depto, est, t):
    x, y = POS[pid]
    col = DEPTO[depto][0]
    caja = pygame.Rect(x, y, 32, 48)
    if est == P.SIN_INSTALAR:  # silla vacia: solo el contorno
        pygame.draw.rect(pantalla, C["gris"], caja, 1)
        texto("vacía", F12, C["suave"], x + 2, y + 16)
    elif est == P.SIN_SENAL:  # quieto, gris, con «?»: nunca teclea
        pygame.draw.rect(pantalla, C["gris"], caja)
        texto("?", F18, C["panel"], x + 11, y + 10)
    else:
        dy = 0
        if est == P.TRABAJANDO:  # la UNICA animacion: hay un evento real (live fresco)
            dy = (int(t * 8) % 2)
        pygame.draw.rect(pantalla, col, caja.move(0, -dy))
        pygame.draw.rect(pantalla, (242, 230, 204), (x + 8, y + 3 - dy, 16, 14))  # cara
        if est == P.TRABAJANDO:
            on = int(t * 8) % 2
            pygame.draw.rect(pantalla, C["texto"], (x - 2, y + 50, 36, 5))  # teclado
            pygame.draw.rect(pantalla, C["panel"], (x + 4 + on * 14, y + 51, 8, 3))
        elif est == P.EN_COLA:
            pygame.draw.circle(pantalla, C["acento"], (x + 30, y + 2), 6)
            texto("…", F12, C["panel"], x + 25, y - 8)
    texto(nombre, F12, C["texto"], x - 6, y + 56, 80)
    col_e = {P.TRABAJANDO: C["acento"], P.EN_COLA: C["acento"], P.SIN_SENAL: C["suave"]}.get(est, C["suave"])
    texto(ROT[est], F12, col_e, x - 6, y + 70, 80)


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
caido_antes = None

while True:
    dt = reloj.tick(30) / 1000.0
    faulthandler.dump_traceback_later(1.0, repeat=False, file=_congelado)
    t = time.perf_counter() - t0
    ahora = time.time()
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            codigo, cierre_motivo = 0, "ventana cerrada por el usuario"
        elif e.type == pygame.MOUSEBUTTONDOWN:
            foco = caja_in.collidepoint(e.pos)
            (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()
        elif e.type == pygame.TEXTINPUT and foco:
            entrada = (entrada + e.text)[:500]
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_TAB:
                foco = not foco
                (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()
            elif foco and e.key == pygame.K_BACKSPACE:
                entrada = entrada[:-1]
            elif foco and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and entrada.strip():
                it = BOR.nuevo(entrada.strip())  # primero a disco: no se pierde aunque caiga todo
                log(f"encargo escrito: «{it['texto'][:60]}» -> " + (
                    "se envía" if _puede_enviar() else "borrador local, pendiente de enviar"))
                entrada = ""
                _enviar_pendientes()
            elif e.key == pygame.K_ESCAPE:
                foco = False
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
    V = {k: f.vista(ahora) for k, f in F.items()}
    est = P.derivar(V, "vivo" if eb == "vivo" else eb, ahora)
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
    ejemplo = any(v["ejemplo"] for v in V.values())
    if ejemplo:
        texto("DATOS DE EJEMPLO — no son del runner", F15, C["ambar"], 330, 8)
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
        dibujar_sprite(pid, nombre, depto, est[pid][0], t)
    # leyenda de motivos (de donde sale cada estado)
    pygame.draw.rect(pantalla, C["panel"], (0, 480, W, H - 480))
    pygame.draw.line(pantalla, C["linea"], (0, 480), (W, 480))
    texto(f"{len(P.ROSTER)} sprites (14 personajes + Runa + vigilante) · "
          f"{sum(1 for v in est.values() if v[0] == P.SIN_SENAL)} sin señal · motivo de Growi: {est['growi'][1]}",
          F12, C["suave"], 30, 488, W - 60)
    texto(f"Runa: {est['runa'][1]} · Sonny: {est['sonny'][1]}", F12, C["suave"], 30, 504, W - 60)
    if eb != "vivo":
        texto(f"Bridge no disponible — {motivo_b}" if eb == "no_disponible" else motivo_b,
              F13, C["texto"], 30, 520, W - 60)
    # encargos: primero a disco; si no hay Bridge, borrador visible «pendiente de enviar»
    texto("Pedirle algo (Tab para escribir, Enter para enviar). Nunca se finge enviado:", F12, C["suave"], 30, 540)
    y = 556
    for it in BOR.items[-3:]:
        s = it["estado"] if it["estado"] != "enviado" else f"enviado {it['id']} · {it.get('estado_cola') or '…'}"
        texto(f"• {it['texto'][:60]} — {s}", F12, C["ambar"] if it["estado"] != "enviado" else C["texto"],
              30, y, W - 60)
        y += 15
    pygame.draw.rect(pantalla, C["panel"], caja_in, border_radius=6)
    pygame.draw.rect(pantalla, C["acento"] if foco else C["linea"], caja_in, 1, border_radius=6)
    texto(entrada + ("|" if foco and int(t * 2) % 2 else ""), F13, C["texto"], caja_in.x + 8, caja_in.y + 5,
          caja_in.w - 16)
    if not _puede_enviar():
        texto("sin Bridge o sin runner: se guardará como borrador" if ENC["listo"] else "cargando encolado…",
              F12, C["suave"], 600, H - 40)
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
