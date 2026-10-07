from typer.testing import CliRunner

from orchestrator import __version__
from orchestrator.cli import app

runner = CliRunner()


def test_ayuda_lista_los_comandos():
    resultado = runner.invoke(app, ["--help"])
    assert resultado.exit_code == 0
    for comando in ("run", "fases", "config", "api"):
        assert comando in resultado.output


def test_version():
    resultado = runner.invoke(app, ["--version"])
    assert resultado.exit_code == 0
    assert __version__ in resultado.output


def test_fases_lista_las_once():
    resultado = runner.invoke(app, ["fases"])
    assert resultado.exit_code == 0
    assert "Security Gate 1" in resultado.output
    assert len(resultado.output.strip().splitlines()) == 11


def test_run_con_una_fase():
    resultado = runner.invoke(app, ["run", "--fase", "4"])
    assert resultado.exit_code == 0
    assert "Fase 4" in resultado.output
    assert "Fase 5" not in resultado.output


def test_run_rechaza_fase_inexistente():
    resultado = runner.invoke(app, ["run", "--fase", "12"])
    assert resultado.exit_code != 0


def test_run_rechaza_documento_inexistente():
    resultado = runner.invoke(app, ["run", "no_existe.pdf"])
    assert resultado.exit_code != 0


def test_config_no_revela_secretos(monkeypatch):
    from orchestrator.config import obtener_configuracion

    monkeypatch.setenv("NEO4J_PASSWORD", "valor-de-prueba")
    obtener_configuracion.cache_clear()
    try:
        resultado = runner.invoke(app, ["config"])
    finally:
        obtener_configuracion.cache_clear()
    assert resultado.exit_code == 0
    assert "valor-de-prueba" not in resultado.output
    assert "neo4j_password_definida: True" in resultado.output
