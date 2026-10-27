"""Claude falso para probar el timeout de inactividad (no llama a nada real).

  colgado        no escribe nada nunca; lanza un hijo python que tambien
                 duerme (asi se prueba que se mata el arbol completo).
  lento <seg>    escribe un evento stream-json cada 2 s durante <seg> s y
                 termina con el mensaje final, como claude -p --output-format
                 stream-json.
"""

import json
import subprocess
import sys
import time


def emit(ev):
    print(json.dumps(ev), flush=True)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "colgado"
    if mode == "colgado":
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)  # growi-fake-hijo"])
        time.sleep(3600)
        return
    seg = float(sys.argv[2]) if len(sys.argv) > 2 else 45
    emit({"type": "system", "subtype": "init", "session_id": "fake-sesion", "model": "fake"})
    t0 = time.time()
    n = 0
    while time.time() - t0 < seg:
        n += 1
        emit({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"text": f"t{n}"}}})
        time.sleep(2)
    emit({"type": "assistant", "message": {"id": "m1", "model": "fake",
                                            "content": [{"type": "text", "text": f"hecho tras {n} eventos"}]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": f"hecho tras {n} eventos",
          "total_cost_usd": 0, "num_turns": 1, "session_id": "fake-sesion"})


if __name__ == "__main__":
    main()
