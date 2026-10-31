"""t-oficina-motor-050: el proyecto se abre con Godot 4.7.2, lee los ajustes fijados y no escucha en ningun puerto."""
import json, subprocess, time, psutil
from pathlib import Path
R = Path(r"C:\Users\forte\source\growi-bridge")
EXE = R / "oficina/mediciones/_bin/Godot_v4.7.2-stable_win64_console.exe"
PROJ = R / "oficina/godot"
gd = PROJ / "_verif_ajustes.gd"
gd.write_text('''extends SceneTree
func _init():
\tvar k = ["application/run/low_processor_mode", "application/run/max_fps", "display/window/vsync/vsync_mode",
\t\t"rendering/renderer/rendering_method", "application/config/name"]
\tvar d = {}
\tfor x in k:
\t\td[x] = ProjectSettings.get_setting(x)
\td["version"] = Engine.get_version_info()["string"]
\tprint("AJUSTES " + JSON.stringify(d))
\tawait create_timer(3.0).timeout
\tquit()
''', encoding="utf-8")
p = subprocess.Popen([str(EXE), "--headless", "--path", str(PROJ), "--script", "res://_verif_ajustes.gd"],
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
time.sleep(1.5)
conns = []
try:
    pr = psutil.Process(p.pid)
    for c in pr.net_connections(kind="inet"):
        conns.append({"laddr": f"{c.laddr.ip}:{c.laddr.port}", "status": c.status})
except psutil.Error as e:
    conns = [f"error {e}"]
out, _ = p.communicate(timeout=60)
gd.unlink()
for extra in (".godot",):
    pass
linea = next((l for l in out.splitlines() if l.startswith("AJUSTES ")), None)
res = {"ajustes": json.loads(linea[8:]) if linea else None, "conexiones_godot": conns, "codigo": p.returncode,
       "escenas_tscn": [str(x.relative_to(PROJ)) for x in PROJ.rglob("*.tscn") if ".godot" not in x.parts]}
print(json.dumps(res, ensure_ascii=False, indent=1))
