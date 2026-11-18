"""Configuración común de las pruebas."""

import pytest

from orchestrator.config import obtener_configuracion

# En CI estas variables apuntan al Neo4j de la ejecución; las pruebas unitarias no deben
# heredarlas, porque cambiarían su comportamiento (por ejemplo, registrar en el grafo).
_VARIABLES_DE_NEO4J = ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "NEO4J_DATABASE")
# En CI el workflow expone las credenciales del bot; ninguna prueba debe enviar mensajes reales.
_VARIABLES_DE_TELEGRAM = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


@pytest.fixture(autouse=True)
def aislar_de_neo4j(request, monkeypatch):
    for variable in _VARIABLES_DE_TELEGRAM:
        monkeypatch.delenv(variable, raising=False)
    if request.node.get_closest_marker("integracion") is None:
        for variable in _VARIABLES_DE_NEO4J:
            monkeypatch.delenv(variable, raising=False)
    obtener_configuracion.cache_clear()
    yield
    obtener_configuracion.cache_clear()
