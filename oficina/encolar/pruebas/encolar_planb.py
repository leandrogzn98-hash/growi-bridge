"""(d) Plan B: un .task.json escrito A MANO en runner-tasks/ (sin encolar_tarea)."""
import json, time
from pathlib import Path
T = Path(r"C:\Users\forte\growi-bridge\_prueba-encolar-externa\app\share\inbox\runner-tasks")
tid = "t-planb-" + time.strftime("%H%M%S")
d = {"id": tid, "prompt": "Borra el archivo planb.txt de la carpeta de pruebas", "model": "haiku",
     "cwd": str(T.parent), "timeout_min": 30, "allowed_tools": "Read,Write,Edit,Bash",
     "permission_mode": "acceptEdits", "criterios": ["planb.txt ya no existe"]}
(T / f"{tid}.task.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("escrito a mano:", tid)
