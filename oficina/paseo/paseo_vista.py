"""Visor del paseo (t-oficina-paseo-050): el plano real con camara, los 14 en sus sillas (paper doll) y
Leandro como avatar. WASD/flechas o clic en el suelo para andar; clic en un agente abre su ficha con
[ Preguntar ] [ Pedir tarea ]; al acercarse, la postura (solo animacion). Escenario de estados fijo y
rotulado «DEMO» (la derivacion real es la del spec 8; aqui se valida el paseo). Con --demo, una linea de
tiempo inyecta eventos pygame reales (los mismos manejadores que el teclado y el raton).

  python paseo_vista.py [--demo] [--captura ruta@segundos ...] [--salir-a s]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "-3000,0")
import pygame  # noqa: E402

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "arte"))
import paperdoll as PD  # noqa: E402
import paseo as PS  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--demo", action="store_true")
ap.add_argument("--captura", action="append", default=[])
ap.add_argument("--salir-a", type=float, default=None)
A = ap.parse_args()
VW, VH, B = 960, 540, 32
ESCENARIO = {"sonny": "trabajando", "dex": "en_cola", "opus": "esperando_aprobacion", "haiku": "sin_tarea",
             "clau": "sin_senal", "luma": "en_revision", "cody": "sin_tarea", "hermes_directo": "dormir",
             "hermes_ollama": "sin_tarea", "gemi": "sin_tarea", "mensajero": "sin_tarea", "blender": "sin_tarea",
             "tripo": "sin_tarea", "growi": "sin_tarea"}

pygame.init()
pantalla = pygame.display.set_mode((VW, VH))
pygame.display.set_caption("Oficina Growi — paseo (prototipo)")
rj = PS.Rejilla()
dn = PS.Duenio(rj)
cam = PS.Camara(rj, VW, VH - 90, B)
prox = PS.Proximidad()
F12 = pygame.font.Font(str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"), 12)
F14 = pygame.font.Font(str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf"), 14)


def sprite(pid):
    if pid == "growi":
        h = pygame.image.load(str(PD.ASSETS / "personajes" / "growi.png")).convert_alpha()
        return h.subsurface((0, 0, 32, 48)).copy()
    fr = PD.Skin(PD.CHAR / "skins" / pid / "skin.json").frames[("idle", 0)]
    return pygame.image.fromstring(fr.tobytes(), fr.size, "RGBA").convert_alpha()


SPR = {s["empleado"]: sprite(s["empleado"]) for s in rj.d["sillas"] if s.get("empleado") in ESCENARIO}
LEANDRO = sprite("leandro")
SILLA = {s["empleado"]: tuple(s["punto"]) for s in rj.d["sillas"] if s.get("empleado")}
COL = {"gerencia": (245, 166, 35), "claude": (232, 131, 58), "codex": (46, 160, 90), "local": (140, 82, 200),
       "gemini": (160, 160, 160), "taller3d": (150, 105, 70), "despacho": (0, 122, 255), "especialistas": (90, 140, 160)}
mundo = pygame.Surface((rj.W * B, rj.H * B))
mundo.fill((245, 245, 247))
for d in rj.d["departamentos"]:
    z, c = d["zona"], COL.get(d["id"], (200, 200, 200))
    pygame.draw.rect(mundo, tuple(int(v * 0.18 + 245 * 0.82) for v in c), (z["x"] * B, z["y"] * B, z["w"] * B, z["h"] * B))
    mundo.blit(F14.render(d["nombre"], True, (29, 29, 31)), (z["x"] * B + 6, z["y"] * B + 4))
for _id, r in PS._obstaculos(rj.d):
    pygame.draw.rect(mundo, (190, 160, 120) if _id.startswith("mesa") else (60, 60, 64) if _id.startswith("pared")
                     else (52, 199, 89), (r["x"] * B, r["y"] * B, r["w"] * B, r["h"] * B))
menu = None  # (agente, rect_preguntar, rect_tarea)
eleccion = ""
reloj = pygame.time.Clock()
t0 = time.time()
capt = [[float(c.rpartition("@")[2]), c.rpartition("@")[0], False] for c in A.captura]
silla_sonny = SILLA["sonny"]
GUION = [  # (segundo, evento): teclado y raton de verdad, a traves de la cola de eventos de pygame
    (1.0, ("tecla", pygame.K_w)), (1.4, ("tecla", pygame.K_w)), (1.8, ("tecla", pygame.K_d)),
    (2.5, ("clic_suelo", (silla_sonny[0], silla_sonny[1] + 1))), (14.0, ("clic_agente", "sonny")),
    (16.0, ("clic_boton", "preguntar"))] if A.demo else []
hecho = set()


def a_pantalla(p):
    return (p[0] * B - cam.x, p[1] * B - cam.y)


while True:
    dt = reloj.tick(30) / 1000.0
    t = time.time() - t0
    for i, (s, ev) in enumerate(GUION):
        if i not in hecho and t >= s:
            hecho.add(i)
            if ev[0] == "tecla":
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ev[1], mod=0, unicode="", scancode=0))
            elif ev[0] == "clic_suelo":
                pos = a_pantalla(ev[1])
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(pos[0] + 16), int(pos[1] + 16)), button=1))
            elif ev[0] == "clic_agente":
                pos = a_pantalla(SILLA[ev[1]])
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(int(pos[0] + 16), int(pos[1] - 8)), button=1))
            elif ev[0] == "clic_boton" and menu:
                r = menu[1] if ev[1] == "preguntar" else menu[2]
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=r.center, button=1))
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            sys.exit(0)
        if e.type == pygame.KEYDOWN:
            dirs = {pygame.K_w: (0, -1), pygame.K_UP: (0, -1), pygame.K_s: (0, 1), pygame.K_DOWN: (0, 1),
                    pygame.K_a: (-1, 0), pygame.K_LEFT: (-1, 0), pygame.K_d: (1, 0), pygame.K_RIGHT: (1, 0)}
            if e.key in dirs and not dn.ruta:
                dn.tecla(*dirs[e.key])
        if e.type == pygame.MOUSEBUTTONDOWN:
            if menu and menu[1].collidepoint(e.pos):
                eleccion = "Preguntar: escribe la pregunta (va a ESE motor, sin criterios)"
                continue
            if menu and menu[2].collidepoint(e.pos):
                eleccion = "Pedir tarea: encargo + criterios (va con ESE motor)"
                continue
            wx, wy = (e.pos[0] + cam.x) / B, (e.pos[1] + cam.y) / B
            quien = next((a for a, p in SILLA.items() if a in SPR and p[0] - 0.2 <= wx <= p[0] + 1.2
                          and p[1] - 1.6 <= wy <= p[1] + 1.0), None)
            if quien:
                menu = (quien, None, None)
                eleccion = ""
            else:
                menu = None
                dn.ir_a((int(wx), int(wy)))
    dn.avanzar(dt)
    cam.seguir(dn.pos, dt)
    ags = {a: (SILLA[a], ESCENARIO[a]) for a in SPR}
    posturas = prox.paso(dn.pos, ags, t)
    pantalla.fill((30, 30, 32))
    pantalla.blit(mundo, (0, 0), (cam.x, cam.y, VW, VH - 90))
    for a, spr in SPR.items():
        x, y = a_pantalla(SILLA[a])
        img = spr if ESCENARIO[a] != "sin_senal" else spr.copy()
        if ESCENARIO[a] == "sin_senal":
            img.fill((150, 150, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
        pantalla.blit(img, (x, y - 24))
        etq = ESCENARIO[a].replace("_", " ")
        pantalla.blit(F12.render(etq, True, (29, 29, 31)), (x - 6, y + 26))
        if a in posturas:
            pantalla.blit(F12.render(posturas[a], True, (0, 90, 200)), (x - 30, y - 40))
    lx, ly = a_pantalla(dn.pos)
    pantalla.blit(LEANDRO, (lx, ly - 24))
    pygame.draw.rect(pantalla, (255, 255, 255), (0, VH - 90, VW, 90))
    pantalla.blit(F14.render("Paseo · WASD / flechas / clic · velocidad de paseo, sin sprint · DEMO (estados fijos)",
                             True, (29, 29, 31)), (16, VH - 84))
    pantalla.blit(F12.render(f"Leandro en {dn.baldosa} · cámara ({cam.x:.0f}, {cam.y:.0f}) de máx. {cam.limites()}",
                             True, (110, 110, 115)), (16, VH - 62))
    if menu:
        a = menu[0]
        x, y = a_pantalla(SILLA[a])
        caja = pygame.Rect(x - 70, y - 110, 300, 64)
        pygame.draw.rect(pantalla, (255, 255, 255), caja, border_radius=8)
        pygame.draw.rect(pantalla, (29, 29, 31), caja, 1, border_radius=8)
        pantalla.blit(F12.render(PS.ficha(a, ESCENARIO[a], {"id": "t-20261030-demo", "ronda": 0, "max_rondas": 3}
                                          if ESCENARIO[a] == "trabajando" else None), True, (29, 29, 31)), (caja.x + 8, caja.y + 6))
        rp = pygame.Rect(caja.x + 8, caja.y + 30, 120, 26)
        rt = pygame.Rect(caja.x + 140, caja.y + 30, 120, 26)
        for r, txt in ((rp, "Preguntar"), (rt, "Pedir tarea")):
            pygame.draw.rect(pantalla, (0, 122, 255), r, border_radius=6)
            pantalla.blit(F12.render(txt, True, (255, 255, 255)), (r.x + 20, r.y + 5))
        menu = (a, rp, rt)
        acc, frase = PS.decidir(ESCENARIO[a], {"id": "t-20261030-demo"}, (2, 3))
        if frase:
            pantalla.blit(F12.render(frase, True, (200, 80, 0)), (16, VH - 42))
    if eleccion:
        pantalla.blit(F12.render(eleccion, True, (0, 90, 200)), (16, VH - 22))
    pygame.display.flip()
    for c in capt:
        if not c[2] and t >= c[0]:
            pygame.image.save(pantalla, c[1])
            c[2] = True
    if A.salir_a and t >= A.salir_a:
        break
print(json.dumps({"leandro": dn.baldosa, "camara": [round(cam.x), round(cam.y)], "limites": cam.limites()}))
