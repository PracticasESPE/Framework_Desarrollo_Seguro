"""Pruebas de la fase 4 del motor (normalización del Security Gate 1)."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import Configuracion, obtener_configuracion
from orchestrator.gates.fase4 import (
    ErrorFase,
    ejecutar_fase4,
    guardar_resultado,
    publicar_resumen_en_actions,
    resumen_markdown,
)

EJEMPLOS = Path(__file__).parent / "datos" / "sarif"
runner = CliRunner()


@pytest.fixture
def salida(tmp_path) -> Path:
    """Carpeta de salida con los SARIF de ejemplo donde los deja el Gate 1."""
    carpeta = tmp_path / "salida"
    shutil.copytree(EJEMPLOS, carpeta / "security" / "sarif")
    return carpeta


def _config(salida: Path, **valores) -> Configuracion:
    return Configuracion(_env_file=None, directorio_salida=salida, **valores)


def test_lee_los_sarif_de_la_carpeta_del_gate1(salida):
    resultado = ejecutar_fase4(_config(salida))

    assert resultado.archivos_sarif == [
        "gitleaks.sarif",
        "hadolint.sarif",
        "semgrep.sarif",
        "trivy.sarif",
    ]
    assert resultado.total == 9
    assert resultado.por_severidad == {"critica": 1, "alta": 2, "media": 4, "baja": 2, "info": 0}
    assert resultado.por_herramienta == {"gitleaks": 1, "hadolint": 2, "semgrep oss": 2, "trivy": 4}


def test_sin_contrasena_de_neo4j_no_registra(salida):
    resultado = ejecutar_fase4(_config(salida))
    assert not resultado.registrado_en_grafo
    assert "NEO4J_PASSWORD" in resultado.motivo_sin_grafo


def test_sin_grafo_explicito(salida):
    resultado = ejecutar_fase4(_config(salida, neo4j_password="x"), usar_grafo=False)
    assert not resultado.registrado_en_grafo
    assert "--sin-grafo" in resultado.motivo_sin_grafo


def test_registra_en_neo4j_si_esta_configurado(salida, monkeypatch):
    llamadas = {}

    class Driver:
        def close(self):
            llamadas["cerrado"] = True

    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: Driver())
    monkeypatch.setattr("orchestrator.knowledge.crear_ejecucion", lambda driver, **kw: "ej-nueva")

    def registrar(driver, ejecucion_id, hallazgos, fase, base_datos):
        llamadas.update(ejecucion=ejecucion_id, total=len(hallazgos), fase=fase)
        return len(hallazgos)

    monkeypatch.setattr("orchestrator.knowledge.registrar_hallazgos", registrar)
    resultado = ejecutar_fase4(_config(salida, neo4j_password="x"))

    assert resultado.registrado_en_grafo
    assert resultado.ejecucion_id == "ej-nueva"
    assert llamadas == {"ejecucion": "ej-nueva", "total": 9, "fase": 4, "cerrado": True}


def test_neo4j_inalcanzable_es_un_error_si_se_pide_el_grafo(salida):
    config = _config(salida, neo4j_password="x", neo4j_uri="bolt://127.0.0.1:1")
    with pytest.raises(ErrorFase, match="Neo4j"):
        ejecutar_fase4(config, usar_grafo=True)


def test_sin_sarif_es_un_error(tmp_path):
    with pytest.raises(ErrorFase, match="gate1.sh"):
        ejecutar_fase4(_config(tmp_path))


def test_sarif_invalido_es_un_error(salida):
    (salida / "security" / "sarif" / "roto.sarif").write_text("{", encoding="utf-8")
    with pytest.raises(ErrorFase, match="roto.sarif"):
        ejecutar_fase4(_config(salida))


def test_guarda_el_resultado_en_json(salida):
    config = _config(salida)
    destino = guardar_resultado(ejecutar_fase4(config), config)

    assert destino == salida / "hallazgos" / "fase4.json"
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["total"] == 9
    assert datos["hallazgos"][0]["severidad"] in {"critica", "alta", "media", "baja", "info"}


def test_resumen_para_github_actions(salida, tmp_path, monkeypatch):
    texto = resumen_markdown(ejecutar_fase4(_config(salida)))
    assert "| critica | 1 |" in texto
    assert "| **total** | **9** |" in texto

    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert publicar_resumen_en_actions(texto) is False

    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    assert publicar_resumen_en_actions(texto) is True
    assert "Fase 4 en el motor" in resumen.read_text(encoding="utf-8")


# --- CLI ----------------------------------------------------------------------------------


@pytest.fixture
def entorno_cli(salida, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(salida))
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    obtener_configuracion.cache_clear()
    yield salida
    obtener_configuracion.cache_clear()


def test_cli_run_fase4(entorno_cli):
    resultado = runner.invoke(app, ["run", "--fase", "4", "--sin-grafo"])

    assert resultado.exit_code == 0, resultado.output
    assert "Hallazgos: 9" in resultado.output
    assert "critica: 1" in resultado.output
    assert (entorno_cli / "hallazgos" / "fase4.json").is_file()


def test_cli_run_fase4_con_otra_carpeta(entorno_cli, tmp_path):
    otra = tmp_path / "otra"
    otra.mkdir()
    shutil.copy(EJEMPLOS / "trivy.sarif", otra)
    resultado = runner.invoke(app, ["run", "--fase", "4", "--sarif", str(otra), "--sin-grafo"])

    assert resultado.exit_code == 0, resultado.output
    assert "Hallazgos: 4" in resultado.output


def test_cli_run_fase4_sin_sarif(entorno_cli, tmp_path):
    resultado = runner.invoke(app, ["run", "--fase", "4", "--sarif", str(tmp_path)])
    assert resultado.exit_code == 1
