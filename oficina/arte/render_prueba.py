"""Render de la hoja + JSON (t-oficina-arte-base-050): carga personajes/<id>.png + <id>.json, escala
con NEAREST x4 UNA vez por frame al cargar (nunca en cada tick), reproduce cada animacion a sus FPS
y la «Z» compartida sobre la pose dormir. Comprueba que el render no difumina: todos los colores de
la imagen escalada existen en la hoja original (NEAREST no crea colores intermedios).

  python render_prueba.py [--captura salida.png] [--segundos 4] [--escala 4]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "-3000,0")  # fuera de la vista: no roba el foco ni tapa nada
import pygame  # noqa: E402

AQUI = Path(__file__).resolve().parent
ASSETS = AQUI.parent.parent / "assets" / "office"
ap = argparse.ArgumentParser()
ap.add_argument("--personaje", default="growi")
ap.add_argument("--captura", default=None)
ap.add_argument("--segundos", type=float, default=4.0)
ap.add_argument("--escala", type=int, default=4)
A = ap.parse_args()

meta = json.loads((ASSETS / "personajes" / f"{A.personaje}.json").read_text(encoding="utf-8"))
pygame.init()
fw, fh, k = meta["frame"]["w"], meta["frame"]["h"], A.escala
anims = meta["animaciones"]
pantalla = pygame.display.set_mode((len(anims) * (fw * k + 24) + 24, fh * k + 80))
hoja = pygame.image.load(str(ASSETS / "personajes" / f"{A.personaje}.png")).convert_alpha()
zsrc = pygame.image.load(str(ASSETS / "comun" / "z.png")).convert_alpha()

t_carga = time.perf_counter()
FR = {}  # precalculo: (animacion, frame) -> superficie ya escalada (pygame.transform.scale = vecino mas cercano)
for a in anims:
    for f in range(a["frames"]):
        sub = hoja.subsurface((f * fw, a["fila"] * fh, fw, fh))
        FR[(a["nombre"], f)] = pygame.transform.scale(sub, (fw * k, fh * k))
Z = pygame.transform.scale(zsrc, (zsrc.get_width() * k // 2, zsrc.get_height() * k // 2))
t_carga = (time.perf_counter() - t_carga) * 1000
fuente = pygame.font.Font(None, 22)
reloj = pygame.time.Clock()
t0 = time.perf_counter()
escalados_en_bucle = 0
while time.perf_counter() - t0 < A.segundos:
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            sys.exit(0)
    t = time.perf_counter() - t0
    pantalla.fill((245, 245, 247))
    for i, a in enumerate(anims):
        n = a["frames"]
        f = int(t * a["fps"]) % n if a.get("bucle", True) else min(n - 1, int(t * a["fps"]))
        x = 24 + i * (fw * k + 24)
        pantalla.blit(FR[(a["nombre"], f)], (x, 40))
        if a["nombre"] == "dormir":
            fase = (t % 3.0) / 3.0
            Z.set_alpha(int(255 * (1 - fase)))
            pantalla.blit(Z, (x + fw * k - 20, 40 + 10 - int(fase * 18 * k / 2)))
        pantalla.blit(fuente.render(f"{a['nombre']} {f + 1}/{n} @{a['fps']} FPS", True, (29, 29, 31)), (x, 12))
    pygame.display.flip()
    reloj.tick(30)
superficie_frames = pygame.Surface((len(FR) * fw * k, fh * k), pygame.SRCALPHA)
for i, s in enumerate(FR.values()):
    superficie_frames.blit(s, (i * fw * k, 0))
orig = {tuple(hoja.get_at((x, y)))[:3] for x in range(hoja.get_width()) for y in range(hoja.get_height())
        if hoja.get_at((x, y)).a == 255}
esc = {tuple(superficie_frames.get_at((x, y)))[:3] for x in range(superficie_frames.get_width())
       for y in range(superficie_frames.get_height()) if superficie_frames.get_at((x, y)).a == 255}
if A.captura:
    pygame.image.save(pantalla, A.captura)
res = {"frames_precalculados": len(FR), "ms_precalculo": round(t_carga, 1), "escalados_en_bucle": escalados_en_bucle,
       "colores_hoja": len(orig), "colores_render_x%d" % k: len(esc), "colores_nuevos_en_render": len(esc - orig),
       "sin_difuminar": not (esc - orig), "fps_medidos": round(reloj.get_fps(), 1)}
print(json.dumps(res, ensure_ascii=False))
pygame.quit()
