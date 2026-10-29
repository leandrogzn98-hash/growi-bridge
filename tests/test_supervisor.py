"""Juez del supervisor local: schema estricto, sin secretos y recorte por presupuesto. Necesita pyyaml/keyring/requests
(el entorno supervisor/.venv); sin ellos se salta. La prueba completa es pruebas/prueba_supervisor.py."""

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("yaml")
pytest.importorskip("keyring")
pytest.importorskip("requests")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "supervisor"))
import supervisor as sv  # noqa: E402


@pytest.mark.parametrize("texto", [
    "Todo bien, no hay nada que hacer.",
    json.dumps({"veredicto": "TODO_BIEN", "evidencia": []}),
    json.dumps({"veredicto": "TODO_BIEN", "evidencia": [], "confianza": 0.5, "extra": 1}),
    json.dumps({"veredicto": "QUIZAS", "evidencia": [], "confianza": 0.5}),
    json.dumps({"veredicto": "TODO_BIEN", "evidencia": "no es lista", "confianza": 0.5}),
    json.dumps({"veredicto": "TODO_BIEN", "evidencia": [], "confianza": 1.5}),
    json.dumps({"veredicto": "TODO_BIEN", "evidencia": [], "confianza": True}),
])
def test_schema_invalido(texto):
    assert sv.validar_veredicto(texto)[0] is None


def test_schema_valido_y_bloque_de_codigo():
    d = {"veredicto": "NECESITA_DECISION", "evidencia": ["cadena detenida"], "confianza": 0.8}
    assert sv.validar_veredicto(json.dumps(d))[0] == d
    assert sv.validar_veredicto("```json\n" + json.dumps(d) + "\n```")[0] == d


def test_sin_secretos():
    t = sv.sin_secretos("token=abc123 Bearer abcdefghijklmnop sk-abcdefghijklmnopqrstu " + "f" * 40)
    assert "abc123" not in t and "abcdefghijklmnop" not in t and "f" * 40 not in t


def test_recorte_por_presupuesto():
    est = {"hora": "x", "log_errores_nuevos": [f"línea de error número {i} con texto" for i in range(500)]}
    corto, aviso = sv.recortar_estado(est, 2000)
    assert aviso and len(json.dumps(corto, ensure_ascii=False, indent=1)) <= 2000
    assert sv.recortar_estado({"hora": "x"}, 2000) == ({"hora": "x"}, None)
