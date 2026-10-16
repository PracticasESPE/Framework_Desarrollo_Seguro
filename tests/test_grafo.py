"""Pruebas del esquema de Neo4j.

Las pruebas de integración necesitan Neo4j levantado con docker compose y se activan con
la variable NEO4J_INTEGRACION=1; las demás usan un driver simulado.
"""

import os
from types import SimpleNamespace

import neo4j
import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import Configuracion, obtener_configuracion
from orchestrator.knowledge import (
    ErrorGrafo,
    aplicar_esquema,
    conectar,
    estado_esquema,
    leer_sentencias,
    resumen_grafo,
    scripts_esquema,
)

runner = CliRunner()


class Registro(dict):
    def data(self):
        return dict(self)


class DriverSimulado:
    def __init__(self, falla_en: str | None = None):
        self.consultas: list[tuple[str, str]] = []
        self.falla_en = falla_en
        self.cerrado = False

    def execute_query(self, consulta, database_="neo4j"):
        self.consultas.append((consulta, database_))
        if self.falla_en and self.falla_en in consulta:
            raise neo4j.exceptions.ClientError("sintaxis no válida")
        if consulta.startswith("SHOW CONSTRAINTS"):
            filas = [
                Registro(name="cwe_id", type="UNIQUENESS", labelsOrTypes=["CWE"], properties=["id"])
            ]
        elif "UNWIND labels(n)" in consulta:
            filas = [
                Registro(etiqueta="Ejecucion", total=1),
                Registro(etiqueta="Hallazgo", total=9),
            ]
        elif "type(r)" in consulta:
            filas = [Registro(relacion="REGISTRA", total=9)]
        elif consulta.startswith("SHOW INDEXES"):
            filas = [
                Registro(
                    name="cwe_id",
                    type="RANGE",
                    labelsOrTypes=["CWE"],
                    properties=["id"],
                    state="ONLINE",
                    owningConstraint="cwe_id",
                )
            ]
        else:
            filas = []
        return SimpleNamespace(records=filas)

    def close(self):
        self.cerrado = True


# --- Scripts de graph/ --------------------------------------------------------------------


def test_scripts_en_orden():
    assert [s.name for s in scripts_esquema()] == ["01_restricciones.cypher", "02_indices.cypher"]


def test_todas_las_sentencias_son_idempotentes_y_sin_comentarios():
    sentencias = [s for script in scripts_esquema() for s in leer_sentencias(script)]

    assert len(sentencias) == 21
    for sentencia in sentencias:
        assert sentencia.startswith(("CREATE CONSTRAINT", "CREATE INDEX"))
        assert "IF NOT EXISTS" in sentencia
        assert "//" not in sentencia
        assert ";" not in sentencia


def test_nombres_de_restricciones_e_indices_unicos():
    nombres = [s.split()[2] for script in scripts_esquema() for s in leer_sentencias(script)]
    assert len(nombres) == len(set(nombres))


def test_etiquetas_del_modelo_de_trazabilidad_cubiertas():
    texto = "\n".join(s for script in scripts_esquema() for s in leer_sentencias(script))
    for etiqueta in (
        "Requisito",
        "Decision",
        "Componente",
        "Hallazgo",
        "Iteracion",
        "ResultadoGate",
        "Regla",
        "Patron",
        "CWE",
        "Control",
    ):
        assert f"(n:{etiqueta})" in texto


def test_leer_sentencias_separa_por_punto_y_coma(tmp_path):
    script = tmp_path / "x.cypher"
    script.write_text("// comentario\nCREATE INDEX a\nFOR (n:A) ON (n.x);\n\n// otro\nRETURN 1;\n")
    assert leer_sentencias(script) == ["CREATE INDEX a\nFOR (n:A) ON (n.x)", "RETURN 1"]


# --- Aplicación del esquema ---------------------------------------------------------------


def test_aplicar_esquema_ejecuta_todo_en_la_base_indicada():
    driver = DriverSimulado()
    assert aplicar_esquema(driver, base_datos="pruebas") == 21
    assert all(base == "pruebas" for _, base in driver.consultas)
    assert driver.consultas[0][0].startswith("CREATE CONSTRAINT patron_id")


def test_aplicar_esquema_informa_la_sentencia_fallida():
    with pytest.raises(ErrorGrafo, match="02_indices.cypher"):
        aplicar_esquema(DriverSimulado(falla_en="hallazgo_severidad"))


def test_aplicar_esquema_sin_scripts(tmp_path):
    with pytest.raises(ErrorGrafo, match="No hay scripts"):
        aplicar_esquema(DriverSimulado(), carpeta=tmp_path)


def test_estado_esquema():
    estado = estado_esquema(DriverSimulado())
    assert estado["restricciones"][0]["name"] == "cwe_id"
    assert estado["indices"][0]["owningConstraint"] == "cwe_id"


def test_resumen_grafo():
    resumen = resumen_grafo(DriverSimulado())
    assert resumen == {"nodos": {"Ejecucion": 1, "Hallazgo": 9}, "relaciones": {"REGISTRA": 9}}


def test_cli_grafo_resumen(monkeypatch):
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: DriverSimulado())
    resultado = runner.invoke(app, ["grafo", "resumen"])

    assert resultado.exit_code == 0, resultado.output
    assert "Hallazgo: 9" in resultado.output
    assert "REGISTRA: 9" in resultado.output


def test_conectar_exige_la_contrasena():
    with pytest.raises(ErrorGrafo, match="NEO4J_PASSWORD"):
        conectar(Configuracion(_env_file=None))


def test_conectar_con_neo4j_apagado():
    config = Configuracion(_env_file=None, neo4j_uri="bolt://127.0.0.1:1", neo4j_password="x")
    with pytest.raises(ErrorGrafo, match="docker compose"):
        conectar(config)


# --- CLI ----------------------------------------------------------------------------------


def test_cli_grafo_esquema(monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    resultado = runner.invoke(app, ["grafo", "esquema"])

    assert resultado.exit_code == 0
    assert "21 sentencias" in resultado.output
    assert driver.cerrado


def test_cli_grafo_estado(monkeypatch):
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: DriverSimulado())
    resultado = runner.invoke(app, ["grafo", "estado"])

    assert resultado.exit_code == 0
    assert "Restricciones (1)" in resultado.output
    assert "cwe_id: RANGE ['CWE'] ['id'] ONLINE (de cwe_id)" in resultado.output


def test_cli_grafo_sin_conexion(monkeypatch):
    def falla(config):
        raise ErrorGrafo("sin conexión")

    monkeypatch.setattr("orchestrator.knowledge.conectar", falla)
    resultado = runner.invoke(app, ["grafo", "esquema"])
    assert resultado.exit_code == 1


# --- Integración con Neo4j real -------------------------------------------------------------


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_esquema_en_neo4j():
    config = obtener_configuracion()
    driver = conectar(config)
    try:
        aplicar_esquema(driver, config.neo4j_database)
        # Se puede aplicar dos veces sin error.
        aplicar_esquema(driver, config.neo4j_database)
        estado = estado_esquema(driver, config.neo4j_database)
    finally:
        driver.close()

    restricciones = {r["name"] for r in estado["restricciones"]}
    indices = {i["name"]: i for i in estado["indices"]}
    assert {"cwe_id", "hallazgo_ejecucion", "requisito_ejecucion"} <= restricciones
    assert indices["hallazgo_severidad"]["state"] == "ONLINE"
