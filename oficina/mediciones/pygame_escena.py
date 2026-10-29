"""La misma escena que godot_escena/ en Pygame-ce (respaldo, render por CPU): 16 sprites 32x48 (14 personajes + Runa +
vigilante), 4 fotogramas a 8 FPS, 30 FPS de juego; «reposo» y luego «animando». Cada segundo escribe una línea JSON en
--salida. La ventana nace fuera de pantalla y sin activarse (no roba el foco).

  python pygame_escena.py --salida=ruta.jsonl --reposo=20 --total=80
"""

import json
import math
import os
import sys
import time

os.environ["SDL_VIDEO_WINDOW_POS"] = "-16000,0"
os.environ["SDL_WINDOW_NO_ACTIVATION_WHEN_SHOWN"] = "1"
import pygame  # noqa: E402

N_SPRITES = 16
args = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
SALIDA, REPOSO, TOTAL = args.get("salida", ""), float(args.get("reposo", 20)), float(args.get("total", 80))


def escribir(d):
    linea = json.dumps(d, ensure_ascii=False)
    if not SALIDA:
        print(linea)
        return
    with open(SALIDA, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


pygame.init()
pantalla = pygame.display.set_mode((640, 360))
cuadros = []
for i in range(N_SPRITES):
    marcos = []
    for f in range(4):
        s = pygame.Surface((32, 48), pygame.SRCALPHA)
        c = pygame.Color(0)
        c.hsva = (360 * i / N_SPRITES, 60, 90, 100)
        s.fill(c)
        s.fill((242, 230, 204), (8, 2 + f, 16, 16))
        s.fill((25, 25, 25), (4 + f * 2, 40, 8, 8))
        marcos.append(s.convert_alpha())
    cuadros.append(marcos)
escribir({"evento": "inicio", "motor": "pygame-ce", "version": pygame.version.ver,
          "sdl": ".".join(map(str, pygame.get_sdl_version())), "driver": pygame.display.get_driver(),
          "sprites": N_SPRITES})
reloj = pygame.time.Clock()
t0 = time.perf_counter()
t_seg, frames, max_dt, lentos = 0.0, 0, 0.0, 0
while True:
    dt = reloj.tick(30) / 1000.0
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            sys.exit(0)
    t = time.perf_counter() - t0
    frames += 1
    max_dt = max(max_dt, dt)
    lentos += dt > 0.05
    animando = t > REPOSO
    f = int(t * 8) % 4 if animando else 0
    pantalla.fill((30, 30, 32))
    for i in range(N_SPRITES):
        x = 40 + (i % 8) * 72 + (math.sin(t * 1.5 + i) * 20 if animando else 0)
        pantalla.blit(cuadros[i][f], (x - 16, 90 + (i // 8) * 140 - 24))
    pygame.display.flip()
    t_seg += dt
    if t_seg >= 1.0:
        escribir({"t": round(t, 1), "fase": "animando" if animando else "reposo", "frames": frames,
                  "fps": round(reloj.get_fps(), 1), "peor_ms": round(max_dt * 1000, 1), "lentos": lentos})
        t_seg, frames, max_dt, lentos = 0.0, 0, 0.0, 0
    if t >= TOTAL:
        break
pygame.quit()
