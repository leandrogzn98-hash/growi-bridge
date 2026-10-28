"""Tests del gate de calidad (gate-calidad.py): que bloquee solo lo real."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gate_calidad", RAIZ / "gate-calidad.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.fixture
def repo(tmp_path):
    """Un repo git minimo con un .py ya confirmado."""
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "viejo.py").write_text("import os\n\n\ndef f():\n    return no_definida\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    return tmp_path


def test_tocada():
    assert gate._tocada(None, 7)
    assert gate._tocada({3, 4}, 4)
    assert not gate._tocada({3, 4}, 5)


def test_transcript_saca_los_archivos_escritos(tmp_path):
    t = tmp_path / "t.jsonl"
    evs = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "a.py"}},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "leido.py"}},
        {"type": "tool_use", "name": "Write", "input": {"file_path": "b.py"}}]}}]
    t.write_text("\n".join(json.dumps(e) for e in evs) + "\nno es json\n", encoding="utf-8")
    assert gate._del_transcript(str(t)) == ["a.py", "b.py"]


def test_lineas_cambiadas(repo):
    (repo / "viejo.py").write_text("import os\n\nX = 1\n\ndef f():\n    return no_definida\n", encoding="utf-8")
    assert gate._lineas_cambiadas(repo, repo / "viejo.py", None) == {3}
    (repo / "nuevo.py").write_text("x = 1\n", encoding="utf-8")
    assert gate._lineas_cambiadas(repo, repo / "nuevo.py", None) is None  # nuevo: cuenta entero


def test_py_compile_bloquea(repo):
    f = repo / "roto.py"
    f.write_text("def f(:\n", encoding="utf-8")
    assert gate.ch_compile(repo, [f]).estado == "FALLA"


@pytest.mark.skipif(not gate._tiene("ruff"), reason="ruff no instalado")
def test_ruff_solo_bloquea_en_lineas_cambiadas(repo):
    # viejo.py ya tenia un nombre sin definir (linea 5): preexistente, no bloquea.
    viejo = repo / "viejo.py"
    c = gate.ch_ruff(repo, [viejo], {viejo.resolve(): set()})
    assert c.estado == "PASA" and any("preexistente" in a for a in c.avisos)
    nuevo = repo / "nuevo.py"
    nuevo.write_text("import sys\n\nprint(otra_sin_definir)\n", encoding="utf-8")
    c = gate.ch_ruff(repo, [nuevo], {nuevo.resolve(): None})
    assert c.estado == "FALLA" and "F821" in " ".join(c.detalle)
    assert any("F401" in a for a in c.avisos)  # import sin usar: estilo, aviso


def test_sin_py_cambiados_pasa_rapido(repo):
    (repo / "nota.md").write_text("hola\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(RAIZ / "gate-calidad.py"), "--sin-stdin"], cwd=repo,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("GATE: PASA")
    assert float(r.stdout.split("(")[1].split(" s")[0]) < 5


def test_mypy_ausente_no_bloquea(repo, monkeypatch):
    monkeypatch.setattr(gate, "_tiene", lambda m: False)
    c = gate.ch_mypy(repo, [repo / "viejo.py"], {})
    assert c.estado == "AVISO" and "FALTA" in c.detalle[0]


def test_sin_suite_no_bloquea(repo):
    assert gate.ch_pytest(repo, [repo / "viejo.py"]).estado == "OMITIDO"


def test_sesion_de_revision_no_corre(repo):
    (repo / "roto.py").write_text("def f(:\n", encoding="utf-8")
    env = dict(os.environ, GROWI_TAREA_ROL="revision")
    r = subprocess.run([sys.executable, str(RAIZ / "gate-calidad.py"), "--sin-stdin"], cwd=repo, env=env,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0 and r.stdout == ""
