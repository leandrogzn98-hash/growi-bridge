"""Crudos de PRUEBA para la skill edicion-video (t-skill-edicion-video-060).

En el PC no hay ninguna toma de cámara cruda vertical (los verticales de Descargas son reels ya editados de
terceros). Estos crudos son SINTÉTICOS y lo dicen en pantalla: voz de Windows (SAPI, es-ES) con lo que tiene una
toma real de talking-head — pausas largas, muletillas («eh», «o sea», «este») y una frase repetida (falsa
salida + toma buena) — sobre un fondo vertical 1080x1920 con una «boca» (forma de onda) que se mueve con la voz.
El largo (repurposing) es horizontal 1920x1080, ~3 min, con varios temas.

  python pruebas/video/generar_crudos.py [carpeta]      (por defecto pruebas/video/crudos)
"""

import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
OCULTO = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def P(ms):
    return f'<break time="{ms}ms"/>'


CRUDOS = {
    # nombre: (voz, vertical, texto SSML)
    "crudo1-errores": ("Microsoft Helena Desktop", True,
        f"Hoy te cuento los tres errores que cometí, eh, grabando reels. {P(1400)}"
        f"Hoy te cuento los tres errores que más me costaron grabando reels. {P(900)}"
        f"El primero, o sea, el primero fue hablar sin guion. {P(700)}"
        f"Me perdía a mitad de la idea y tenía que repetir todo. {P(1200)}"
        f"El segundo, este, el segundo fue grabar con la luz de frente a la ventana. {P(800)}"
        f"Salía oscuro y con sombras. {P(1100)}"
        f"Y el tercero, el más caro: no revisar el audio antes de editar. {P(900)}"
        f"Si te sirvió, guárdalo y pruébalo en tu próximo video."),
    "crudo2-luz": ("Microsoft Laura", True,
        f"¿Sabías que la luz importa más que la cámara? {P(1000)}"
        f"Eh, con una ventana al lado, o sea, de lado, ya tienes una luz suave. {P(800)}"
        f"Pon el teléfono a la altura de los ojos. {P(1200)}"
        f"Pon el teléfono justo a la altura de los ojos y graba en vertical. {P(700)}"
        f"Así de simple."),
    "crudo3-ganchos": ("Microsoft Pablo", True,
        f"Tres segundos. {P(600)} Eso es lo que tienes para que no pasen de largo. {P(1000)}"
        f"Este, empieza con una pregunta o con un número. {P(900)}"
        f"Nada de saludos largos. {P(1300)}"
        f"Nada de saludos largos al principio. {P(800)}"
        f"Ve directo a la idea y cierra con una llamada a la acción."),
    "largo-podcast": ("Microsoft Helena Desktop", False,
        f"Bienvenidos a una charla larga sobre cómo producir contenido sin quemarse. {P(900)}"
        f"Primero hablemos de organización. {P(600)} La mayoría de creadores graba el mismo día que publica, "
        f"y eso, eh, eso los deja sin margen. {P(700)} Lo que funciona es grabar en bloque: "
        f"una tarde para cuatro videos. {P(900)} Así la semana queda resuelta y el estrés baja muchísimo. {P(1200)}"
        f"Segundo tema: los ganchos. {P(600)} ¿Por qué la gente deja de mirar en el segundo dos? {P(500)} "
        f"Porque el video empieza con un saludo. {P(700)} Empieza con el resultado, con una pregunta "
        f"o con un número concreto. {P(600)} Por ejemplo: tres errores que me costaron mil seguidores. {P(1200)}"
        f"Tercer tema: la edición. {P(600)} No hace falta un programa caro. {P(500)} Quita las pausas, "
        f"quita las muletillas y pon subtítulos grandes, palabra por palabra. {P(700)} "
        f"Eso solo ya sube la retención. {P(1200)}"
        f"Cuarto tema: medir. {P(600)} Mira la retención a los tres segundos y a la mitad del video. {P(500)} "
        f"Si cae al principio, el problema es el gancho. {P(500)} Si cae a la mitad, el problema es el ritmo. {P(1200)}"
        f"Para cerrar: constancia antes que perfección. {P(600)} Un video bueno cada semana vale más "
        f"que uno perfecto cada mes. {P(800)} Gracias por quedarte hasta el final."),
}


def sintetizar(voz, ssml, wav):
    doc = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="es-ES">'
           f'<voice name="{voz}">{ssml}</voice></speak>')
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(doc)
        xml = f.name
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.SpeakSsml([IO.File]::ReadAllText('{xml}', [Text.Encoding]::UTF8)); "
          "$s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=600, creationflags=OCULTO)
    Path(xml).unlink(missing_ok=True)


def video(wav, mp4, vertical):
    w, h = (1080, 1920) if vertical else (1920, 1080)
    cara = f"drawbox=x={w // 2 - 230}:y={h // 2 - 420}:w=460:h=560:color=#E8B48A:t=fill," \
           f"drawbox=x={w // 2 - 330}:y={h // 2 + 140}:w=660:h={h // 2}:color=#2F4E8C:t=fill"
    etiqueta = "drawtext=fontfile='C\:/Windows/Fonts/arialbd.ttf':text='CRUDO SINTETICO DE PRUEBA':x=(w-tw)/2:y=60:fontsize=36:fontcolor=white@0.6"
    fc = (f"color=c=#556677:s={w}x{h}:r=30[bg];[bg]{cara},{etiqueta}[base];"
          f"[0:a]showwaves=s=300x90:mode=cline:colors=#5A1E1E:rate=30[boca];"
          f"[base][boca]overlay=x={w // 2 - 150}:y={h // 2 - 40}:shortest=1[v]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-filter_complex", fc, "-map", "[v]", "-map",
                    "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a",
                    "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(mp4)], check=True, timeout=900,
                   creationflags=OCULTO)


def main():
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI / "crudos"
    dst.mkdir(parents=True, exist_ok=True)
    for nombre, (voz, vertical, ssml) in CRUDOS.items():
        mp4 = dst / f"{nombre}.mp4"
        if mp4.is_file():
            print("ya está", mp4)
            continue
        wav = dst / f"{nombre}.wav"
        sintetizar(voz, ssml, str(wav))
        video(wav, mp4, vertical)
        wav.unlink(missing_ok=True)
        print("listo", mp4)


if __name__ == "__main__":
    main()
