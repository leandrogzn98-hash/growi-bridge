# -*- coding: utf-8 -*-
"""Growi Bridge 0.6.0 'Harness' - Fase H1: Tools de motores para smolagents.

Cuatro Tools (subclases de smolagents.Tool) que envuelven los motores de IA
de Leandro. Reglas duras: nunca shell (siempre lista de args), nunca
lanzar excepcion (se devuelve 'ERROR: ...'), salida truncada a 8000 chars,
utf-8 con errors=replace.

Uso (autoprueba, llama a cada motor con 'Responde con una sola palabra: OK'):
    python growi-bridge-harness.py
"""
import json
import os
import shutil
import subprocess
import urllib.request

from smolagents import Tool

MAX_OUT = 8000

CLAUDE_BIN = r"C:\Users\forte\.local\bin\claude.exe"
# Verificado: @openai\codex es un DIRECTORIO (paquete npm con bin\codex.js), no
# un ejecutable. Se usa el shim codex.cmd de npm. Ese shim solo hace
# `node bin\codex.js %*`; pasar un prompt libre por cmd.exe es fragil (&, %, ")
# asi que, si hay node, se invoca node + codex.js directo (mismo efecto, sin
# cmd.exe) y el shim queda de respaldo.
CODEX_PKG = r"C:\Users\forte\AppData\Roaming\npm\node_modules\@openai\codex"
CODEX_JS = os.path.join(CODEX_PKG, "bin", "codex.js")
CODEX_SHIM = r"C:\Users\forte\AppData\Roaming\npm\codex.cmd"
AGY_BIN = r"C:\Users\forte\AppData\Local\agy\bin\agy.exe"
LLAMA_URL = "http://127.0.0.1:8080"


# H3: los motores corren SIN poder escribir ni ejecutar nada (solo devuelven texto).
# Cambiar esto exige pasar por permission-layer (modificar_archivos + confirmacion humana).
CLAUDE_SIN_ESCRITURA = ["--disallowedTools", "Edit,Write,NotebookEdit,Bash"]
CODEX_SANDBOX = ["--sandbox", "read-only"]


def args_claude(prompt):
    return [CLAUDE_BIN] + CLAUDE_SIN_ESCRITURA + ["-p", str(prompt)]


def args_codex(prompt, base):
    """base = [node, CODEX_JS] o [CODEX_SHIM]."""
    return list(base) + ["exec"] + CODEX_SANDBOX + [str(prompt)]


def _truncar(texto):
    texto = (texto or "").strip()
    if len(texto) > MAX_OUT:
        return texto[:MAX_OUT] + "\n[...truncado a %d caracteres]" % MAX_OUT
    return texto


def _correr(args, timeout, nombre):
    """Ejecuta args (lista, sin shell). Devuelve (ok, stdout, stderr); en fallo de lanzamiento (False, 'ERROR: ...', '')."""
    try:
        r = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return False, "ERROR: %s supero el tiempo limite (%ss)" % (nombre, timeout), ""
    except FileNotFoundError:
        return False, "ERROR: %s no encontrado en la ruta esperada" % nombre, ""
    except Exception as e:  # noqa: BLE001 - nunca lanzar
        return False, "ERROR: %s fallo al ejecutarse (%s: %s)" % (nombre, type(e).__name__, e), ""
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    return r.returncode == 0, out, err


def _ejecutar(nombre, args, timeout):
    ok, out, err = _correr(args, timeout, nombre)
    if not ok:
        if out.startswith("ERROR:"):
            return out
        return _truncar("ERROR: %s devolvio un fallo. %s" % (nombre, err or out))
    return _truncar(out) or "ERROR: %s no devolvio texto" % nombre


class ClaudeCLITool(Tool):
    name = "claude_cli"
    description = (
        "Motor Claude (CLI). Usalo para tareas complejas: razonamiento largo, "
        "analisis, codigo o redaccion que necesita la mayor calidad."
    )
    inputs = {"prompt": {"type": "string", "description": "Encargo completo para Claude."}}
    output_type = "string"

    def forward(self, prompt: str) -> str:
        try:
            if not os.path.isfile(CLAUDE_BIN):
                return "ERROR: claude.exe no encontrado en la ruta esperada"
            return _ejecutar("claude.exe", args_claude(prompt), 300)
        except Exception as e:  # noqa: BLE001
            return "ERROR: claude_cli fallo (%s: %s)" % (type(e).__name__, e)


class CodexCLITool(Tool):
    name = "codex_cli"
    description = (
        "Motor Codex (OpenAI CLI, modo exec). Usalo para tareas de programacion "
        "y revision de codigo."
    )
    inputs = {"prompt": {"type": "string", "description": "Encargo completo para Codex."}}
    output_type = "string"

    def forward(self, prompt: str) -> str:
        try:
            node = shutil.which("node")
            if node and os.path.isfile(CODEX_JS):
                args = args_codex(prompt, [node, CODEX_JS])
            elif os.path.isfile(CODEX_SHIM):
                args = args_codex(prompt, [CODEX_SHIM])
            else:
                return "ERROR: codex no encontrado en la ruta esperada"
            return _ejecutar("codex", args, 300)
        except Exception as e:  # noqa: BLE001
            return "ERROR: codex_cli fallo (%s: %s)" % (type(e).__name__, e)


class GeminiCLITool(Tool):
    name = "gemini_cli"
    description = (
        "Motor Gemini (agy). Usalo para tareas rapidas y baratas: resumenes, "
        "clasificacion, preguntas cortas."
    )
    inputs = {"prompt": {"type": "string", "description": "Encargo para Gemini."}}
    output_type = "string"

    def forward(self, prompt: str) -> str:
        try:
            if not os.path.isfile(AGY_BIN):
                return "ERROR: agy.exe no encontrado en la ruta esperada"
            ok, out, err = _correr([AGY_BIN, "-p", str(prompt)], 180, "agy.exe")
            if not ok:
                if out.startswith("ERROR:"):
                    return out
                bajo = (err + " " + out).lower()
                if any(k in bajo for k in ("login", "log in", "sign in", "authenticat", "re-auth")):
                    return "ERROR: agy necesita re-autenticacion manual"
                return _truncar("ERROR: agy.exe devolvio un fallo. %s" % (err or out))
            return _truncar(out) or "ERROR: agy.exe no devolvio texto"
        except Exception as e:  # noqa: BLE001
            return "ERROR: gemini_cli fallo (%s: %s)" % (type(e).__name__, e)


# Opener sin proxy: un proxy en 127.0.0.1 intercepta localhost (NO_PROXY).
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class LlamaLocalTool(Tool):
    name = "llama_local"
    description = (
        "Motor local llama-server (Hermes 3 8B, costo $0). Usalo para tareas "
        "simples y privadas que no necesitan un modelo grande."
    )
    inputs = {"prompt": {"type": "string", "description": "Encargo para el modelo local."}}
    output_type = "string"

    def forward(self, prompt: str) -> str:
        apagado = "ERROR: llama-server apagado (el Bridge lo arranca al usarlo)"
        try:
            try:
                with _OPENER.open(LLAMA_URL + "/health", timeout=2) as r:
                    if r.status != 200:
                        return apagado
            except Exception:  # noqa: BLE001
                return apagado
            cuerpo = json.dumps(
                {
                    "messages": [{"role": "user", "content": str(prompt)}],
                    "max_tokens": 1024,
                    "temperature": 0.2,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                LLAMA_URL + "/v1/chat/completions",
                data=cuerpo,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with _OPENER.open(req, timeout=120) as r:
                datos = json.loads(r.read().decode("utf-8", errors="replace"))
            texto = datos["choices"][0]["message"]["content"]
            return _truncar(texto) or "ERROR: llama_local no devolvio texto"
        except Exception as e:  # noqa: BLE001
            return "ERROR: llama_local fallo (%s: %s)" % (type(e).__name__, e)


HARNESS_MOTOR_TOOLS = [ClaudeCLITool(), CodexCLITool(), GeminiCLITool(), LlamaLocalTool()]


if __name__ == "__main__":
    for _t in HARNESS_MOTOR_TOOLS:
        _res = str(_t.forward("Responde con una sola palabra: OK"))
        _estado = "ERROR" if _res.startswith("ERROR") else "OK"
        print("%s: %s [%s]" % (_t.name, _res[:120].replace("\n", " "), _estado))
