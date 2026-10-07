from fastapi.testclient import TestClient

from orchestrator import __version__
from orchestrator.api import app

cliente = TestClient(app)


def test_salud():
    respuesta = cliente.get("/salud")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok", "version": __version__}


def test_fases():
    respuesta = cliente.get("/fases")
    assert respuesta.status_code == 200
    fases = respuesta.json()
    assert [f["numero"] for f in fases] == list(range(1, 12))
    assert [f["numero"] for f in fases if f["es_gate"]] == [4, 8, 11]


def test_configuracion_no_expone_secretos():
    respuesta = cliente.get("/configuracion")
    assert respuesta.status_code == 200
    claves = respuesta.json().keys()
    assert "neo4j_password" not in claves
    assert "gemini_api_key" not in claves
