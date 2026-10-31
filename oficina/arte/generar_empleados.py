"""Los 9 empleados por recoloreado + accesorio sobre el paper doll del spec 10 (t-oficina-empleados-050).
Sin corbata (solo los lideres la llevan). Un detalle identificador por personaje.

AVISO DE LICENCIA: BORRADOR de script (IA); el arte final lleva retoque humano pixel a pixel.

  python generar_empleados.py
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generar_skins as GS  # noqa: E402

CHAR = GS.CHAR
EMPLEADOS = {
    "sonny": {"nombre": "Sonny", "departamento": "claude", "plataforma": "Claude Code (Sonnet)", "rol": "empleado",
              "pelo": "corto", "colores": {"pelo": "#6B4A2E", "ropa": "#E89A7E", "piel": "#F2C9A0"},
              "notas": "Gorra naranja al revés + taza de café siempre en la mano. Estatura media."},
    "opus": {"nombre": "Opus", "departamento": "claude", "plataforma": "Claude Code (Opus)", "rol": "empleado",
             "pelo": "corto_lado", "estatura_px": 2,
             "colores": {"pelo": "#3B2A1E", "ropa": "#F2E6D8", "piel": "#E0B48A"},
             "notas": "+2 px más alto; gafas redondas grandes + bufanda naranja oscuro: aire de leer mucho."},
    "haiku": {"nombre": "Haiku", "departamento": "claude", "plataforma": "Claude Code (Haiku)", "rol": "pasante",
              "pelo": "corto", "estatura_px": -2, "colores": {"pelo": "#8A5A3A", "ropa": "#F4B79A", "piel": "#F2C9A0"},
              "notas": "Pasante: figura pequeña (−2 px) naranja claro con bloc de notas; escritorio pequeño en la esquina "
                       "de Claude. Revisor de último recurso: se le ve revisando solo cuando la revisión corre con Haiku."},
    "dex": {"nombre": "Dex", "departamento": "codex", "plataforma": "Codex", "rol": "empleado",
            "pelo": "corto_lado", "colores": {"pelo": "#2E2A26", "ropa": "#2E9E6E", "piel": "#C68E62"},
            "notas": "Sudadera verde; teclado mecánico bajo el brazo. El único empleado de Codex."},
    "blender": {"nombre": "Blender", "departamento": "especialistas", "plataforma": "Blender (herramienta de Bridge)",
                "rol": "especialista", "pelo": "corto", "colores": {"pelo": "#4A3324", "ropa": "#9AA0A6", "piel": "#E0B48A"},
                "notas": "Delantal gris; cubo 3D naranja/azul en la mano. Especialista: se sienta en el departamento que "
                         "ejecuta la tarea; si nadie lo usa, sala de espera."},
    "tripo": {"nombre": "Tripo", "departamento": "especialistas", "plataforma": "Tripo (skill, duda 16)",
              "rol": "especialista", "pelo": "recogido", "colores": {"pelo": "#232323", "ropa": "#9AA0A6", "piel": "#F2C9A0"},
              "notas": "Delantal gris; figurita blanca impresa en 3D (cohete pequeño). Se dibuja como especialista (skill), "
                       "no como motor (duda 16 sin decidir)."},
    "hermes_directo": {"nombre": "Hermes Directo", "departamento": "local", "plataforma": "llama-server (GGUF directo)",
                       "rol": "empleado", "pelo": "corto", "colores": {"pelo": "#232323", "ropa": "#7A4AB0", "piel": "#E0B48A"},
                       "notas": "Overol morado con chip dorado en el pecho (llama-server carga el GGUF directo). Mismo "
                                "modelo que Hermes Ollama: se distinguen por chip vs. gorra (intencional)."},
    "hermes_ollama": {"nombre": "Hermes Ollama", "departamento": "local", "plataforma": "Ollama", "rol": "empleado",
                      "pelo": "corto", "colores": {"pelo": "#232323", "ropa": "#9A6AD0", "piel": "#E0B48A"},
                      "notas": "Camisa morada, gorra blanca. Mismo modelo que Hermes Directo, distinto proceso."},
    "leandro": {"nombre": "Leandro", "departamento": "gerencia", "plataforma": "—", "rol": "presidente",
                "pelo": "corto", "colores": {"pelo": "#2E2A26", "ropa": "#052048", "piel": "#E0B48A"},
                "notas": "El dueño (avatar del jugador), fuera de los 14: camisa azul Summit #052048, jeans oscuros, "
                         "zapatillas blancas, pelo corto oscuro, rasgos neutros (sin intento de parecido). Sin corbata."},
    "mensajero": {"nombre": "Mensajero 3D", "departamento": "taller3d", "plataforma": "Meshy (sondeo del runner)",
                  "rol": "empleado", "pelo": "corto", "colores": {"pelo": "#4A3324", "ropa": "#B08A60", "piel": "#C68E62"},
                  "notas": "Gorra marrón + bandolera de mensajero; corre entre el buzón y los departamentos (es el sondeo del runner)."},
}
GORRA_N, GORRA_B, GORRA_M = (217, 119, 87, 255), (247, 247, 247, 255), (120, 84, 50, 255)


def accesorio(sid, anims, manos):
    n = max(a[1] for a in anims)
    im = Image.new("RGBA", (n * GS.FW, len(anims) * GS.FH), (0, 0, 0, 0))
    for fila, (anim, nf, _fps) in enumerate(anims):
        for f in range(nf):
            ox, oy = f * GS.FW, fila * GS.FH
            p = GS.pose(anim, f)
            cx, cy = GS.cabeza(p)
            t = GS.torso_top(p)
            mx, my = manos.get((anim, f, "d"), (23, t + 10))
            ix, iy = manos.get((anim, f, "i"), (7, t + 10))

            def px(x, y, c):
                if 0 <= x < GS.FW and 0 <= y < GS.FH:
                    im.putpixel((ox + x, oy + y), c)

            def r(x0, y0, x1, y1, c):
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        px(x, y, c)
            if sid in ("sonny", "hermes_ollama", "mensajero"):  # gorra (Sonny al reves: visera atras)
                c = {"sonny": GORRA_N, "hermes_ollama": GORRA_B, "mensajero": GORRA_M}[sid]
                r(cx - 8, cy - 10, cx + 8, cy - 7, c)
                vis = (cx + 6, cx + 11) if sid == "sonny" else (cx - 11, cx - 6)
                r(vis[0], cy - 7, vis[1], cy - 7, c)
            if sid == "sonny" and anim != "dormir":  # taza de cafe siempre en la mano
                r(mx - 1, my - 3, mx + 2, my + 1, (255, 246, 220, 255))
                px(mx + 3, my - 2, (154, 160, 166, 255))
            if sid == "opus":  # gafas redondas grandes + bufanda naranja oscuro
                for gx in (cx - 5, cx + 2):
                    r(gx - 1, cy - 1, gx + 3, cy - 1, (35, 35, 35, 255))
                    r(gx - 1, cy + 3, gx + 3, cy + 3, (35, 35, 35, 255))
                    r(gx - 1, cy, gx - 1, cy + 2, (35, 35, 35, 255))
                    r(gx + 3, cy, gx + 3, cy + 2, (35, 35, 35, 255))
                r(10, t - 1, 21, t + 1, (166, 82, 50, 255))
                r(18, t + 2, 19, t + 6, (166, 82, 50, 255))
            if sid == "haiku" and anim != "dormir":  # bloc de notas
                r(mx - 1, my - 4, mx + 2, my + 1, (255, 246, 220, 255))
                r(mx - 1, my - 4, mx + 2, my - 4, (217, 119, 87, 255))
            if sid == "dex":  # teclado mecanico bajo el brazo
                r(ix - 3, iy - 6, ix + 1, iy - 5, (35, 35, 35, 255))
                for k in range(ix - 3, ix + 2, 2):
                    px(k, iy - 6, (154, 160, 166, 255))
            if sid in ("blender", "tripo"):  # delantal gris (sobre la ropa)
                r(11, t + 2, 20, t + 12, (110, 114, 118, 255))
                r(12, t + 3, 19, t + 3, (154, 160, 166, 255))
                if anim != "dormir":
                    if sid == "blender":  # cubo 3D naranja/azul
                        r(mx - 1, my - 3, mx + 1, my - 1, (217, 119, 87, 255))
                        r(mx, my - 2, mx + 2, my, (66, 133, 244, 255))
                    else:  # figurita blanca: cohete pequeno
                        r(mx, my - 5, mx + 1, my, (247, 247, 247, 255))
                        px(mx, my - 6, (247, 247, 247, 255)), px(mx - 1, my, (154, 160, 166, 255))
                        px(mx + 2, my, (154, 160, 166, 255))
            if sid == "hermes_directo":  # chip dorado en el pecho
                r(14, t + 3, 17, t + 6, (212, 175, 55, 255))
                r(15, t + 4, 16, t + 5, (150, 120, 30, 255))
            if sid == "leandro":  # zapatillas blancas
                r(10, 46, 14, 47, (247, 247, 247, 255))
                r(17, 46, 21, 47, (247, 247, 247, 255))
            if sid == "mensajero":  # bandolera
                for k in range(0, 12):
                    px(10 + k, t + 1 + k, (90, 60, 35, 255))
                r(19, t + 10, 23, t + 13, (120, 84, 50, 255))
    return im


def escribir():
    manos = GS.generar_base(GS.ANIMS_STD)
    for sid, s in EMPLEADOS.items():
        d = CHAR / "skins" / sid
        d.mkdir(parents=True, exist_ok=True)
        accesorio(sid, GS.ANIMS_STD, manos).save(d / "accesorio.png")
        capas = {"cuerpo": "base:cuerpo", "pantalon": "base:pantalon", "ropa": "base:ropa", "brazos": "base:brazos",
                 "cara": "base:cara", "pelo_atras": f"base:pelo_{s['pelo']}_atras",
                 "pelo_frente": f"base:pelo_{s['pelo']}_frente", "accesorio": "accesorio"}
        sj = {"id": sid, "nombre": s["nombre"], "departamento": s["departamento"], "plataforma": s["plataforma"],
              "rol": s["rol"], "paleta": f"../../../palettes/{s['departamento']}.json", "capas": capas,
              "colores": s["colores"], "estatura_px": s.get("estatura_px", 0), "frame": {"w": 32, "h": 48},
              "ancla": [16, 47],
              "animaciones": [{"nombre": a, "frames": n, "fps": fps, "bucle": a != "celebrar"} for a, n, fps in GS.ANIMS_STD],
              "efectos_compartidos": {"dormir": "base:efectos/z", "duda": "base:efectos/duda", "aviso": "base:efectos/aviso"},
              "notas": s["notas"], "estado_arte": "BORRADOR generado por script (IA); retoque humano pendiente."}
        (d / "skin.json").write_text(json.dumps(sj, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    escribir()
    print("9 empleados escritos")
