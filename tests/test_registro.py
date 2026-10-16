"""Pruebas del registro de ejecuciones y hallazgos en Neo4j.

Las pruebas de integración necesitan Neo4j levantado con docker compose y se activan con
la variable NEO4J_INTEGRACION=1; las demás usan un driver simulado.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import neo4j
import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.gates import leer_carpeta_sarif, leer_sarif
from orchestrator.knowledge import (
    ErrorGrafo,
    conectar,
    crear_ejecucion,
    finalizar_ejecucion,
    listar_hallazgos,
    registrar_hallazgos,
    ultima_ejecucion,
)
from orchestrator.knowledge.registro import nuevo_id_ejecucion

EJEMPLOS = Path(__file__).parent / "datos" / "sarif"
runner = CliRunner()


class Registro(dict):
    def data(self):
        return dict(self)


class DriverSimulado:
    """Guarda las consultas y responde a las de lectura con datos fijos."""

    def __init__(self, existe=True, falla=False):
        self.consultas: list[tuple[str, dict, str]] = []
        self.existe = existe
        self.falla = falla
        self.cerrado = False

    def execute_query(self, consulta, parametros=None, database_="neo4j"):
        self.consultas.append((consulta, parametros or {}, database_))
        if self.falla:
            raise neo4j.exceptions.ClientError("restricción violada")
        if "count(e) AS total" in consulta:
            filas = [Registro(total=1 if self.existe else 0)]
        elif "ORDER BY e.fecha DESC" in consulta:
            filas = [Registro(id="ej-ultima")] if self.existe else []
        elif "SET e.estado" in consulta:
            filas = [Registro(id=parametros["id"])] if self.existe else []
        elif "RETURN h.herramienta" in consulta:
            filas = [
                Registro(
                    herramienta="trivy",
                    regla_id="CVE-2026-10001",
                    severidad="critica",
                    archivo="services/usuarios/package-lock.json",
                    linea_inicio=1204,
                    cwe=[],
                    huella="x",
                )
            ]
        else:
            filas = []
        return SimpleNamespace(records=filas)

    def close(self):
        self.cerrado = True

    def consulta_con(self, texto):
        return next(c for c in self.consultas if texto in c[0])


def test_id_de_ejecucion_legible_y_unico():
    primero, segundo = nuevo_id_ejecucion(), nuevo_id_ejecucion()
    assert primero.startswith("ej-") and primero != segundo


def test_crear_ejecucion():
    driver = DriverSimulado()
    ejecucion_id = crear_ejecucion(driver, documento="tienda.pdf", base_datos="b", version="abc123")

    consulta, parametros, base = driver.consultas[0]
    assert "CREATE (e:Ejecucion" in consulta
    assert parametros["id"] == ejecucion_id
    assert parametros["documento"] == "tienda.pdf"
    assert parametros["version_conocimiento"] == "abc123"
    assert parametros["fecha"].tzinfo is not None
    assert base == "b"


def test_registrar_hallazgos_envia_todo_en_una_consulta():
    driver = DriverSimulado()
    hallazgos = leer_carpeta_sarif(EJEMPLOS)

    assert registrar_hallazgos(driver, "ej-1", hallazgos, fase=4) == 9

    consulta, parametros, _ = driver.consulta_con("UNWIND $hallazgos")
    assert "MERGE (h:Hallazgo {ejecucion_id: $ejecucion_id, huella: dato.huella})" in consulta
    assert "MERGE (e)-[:REGISTRA]->(h)" in consulta
    assert "MERGE (h)-[:ES]->(c)" in consulta
    assert parametros["ejecucion_id"] == "ej-1"
    assert parametros["fase"] == 4
    assert len(parametros["hallazgos"]) == 9
    assert {d["severidad"] for d in parametros["hallazgos"]} == {"critica", "alta", "media", "baja"}


def test_registrar_sin_hallazgos_no_toca_la_base():
    driver = DriverSimulado()
    assert registrar_hallazgos(driver, "ej-1", []) == 0
    assert driver.consultas == []


def test_registrar_en_ejecucion_inexistente():
    with pytest.raises(ErrorGrafo, match="No existe la ejecución"):
        registrar_hallazgos(
            DriverSimulado(existe=False), "ej-x", leer_sarif(EJEMPLOS / "trivy.sarif")
        )


def test_errores_de_neo4j_se_convierten():
    with pytest.raises(ErrorGrafo, match="rechazó"):
        crear_ejecucion(DriverSimulado(falla=True), version="v")


def test_finalizar_ejecucion():
    driver = DriverSimulado()
    finalizar_ejecucion(driver, "ej-1", estado="aprobada")
    _, parametros, _ = driver.consultas[0]
    assert parametros["estado"] == "aprobada"

    with pytest.raises(ErrorGrafo):
        finalizar_ejecucion(DriverSimulado(existe=False), "ej-x")


def test_ultima_ejecucion_y_listado():
    assert ultima_ejecucion(DriverSimulado()) == "ej-ultima"
    assert ultima_ejecucion(DriverSimulado(existe=False)) is None
    (fila,) = listar_hallazgos(DriverSimulado(), "ej-1")
    assert fila["severidad"] == "critica"


# --- CLI ----------------------------------------------------------------------------------


def test_cli_registrar_crea_ejecucion_y_resume(monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    monkeypatch.setattr("orchestrator.knowledge.registro.version_conocimiento", lambda: "v1")
    resultado = runner.invoke(app, ["hallazgos", "registrar", str(EJEMPLOS)])

    assert resultado.exit_code == 0, resultado.output
    assert "Hallazgos registrados: 9" in resultado.output
    assert "critica: 1" in resultado.output
    assert driver.cerrado


def test_cli_registrar_en_ejecucion_existente(monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    resultado = runner.invoke(
        app, ["hallazgos", "registrar", str(EJEMPLOS / "gitleaks.sarif"), "--ejecucion", "ej-1"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Ejecución: ej-1" in resultado.output
    assert not any("CREATE (e:Ejecucion" in c[0] for c in driver.consultas)


def test_cli_registrar_ruta_inexistente():
    resultado = runner.invoke(app, ["hallazgos", "registrar", "no_existe"])
    assert resultado.exit_code != 0


def test_cli_listar(monkeypatch):
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: DriverSimulado())
    resultado = runner.invoke(app, ["hallazgos", "listar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Ejecución: ej-ultima (1 hallazgos)" in resultado.output
    assert "[critica] trivy CVE-2026-10001 services/usuarios/package-lock.json:1204" in (
        resultado.output
    )


def test_cli_listar_sin_ejecuciones(monkeypatch):
    monkeypatch.setattr(
        "orchestrator.knowledge.conectar", lambda config: DriverSimulado(existe=False)
    )
    resultado = runner.invoke(app, ["hallazgos", "listar"])
    assert "No hay ejecuciones registradas" in resultado.output


# --- Integración con Neo4j real -------------------------------------------------------------


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_registro_en_neo4j():
    config = obtener_configuracion()
    driver = conectar(config)
    base = config.neo4j_database
    ejecucion_id = crear_ejecucion(driver, documento="prueba-integracion", base_datos=base)
    try:
        hallazgos = leer_carpeta_sarif(EJEMPLOS)
        registrar_hallazgos(driver, ejecucion_id, hallazgos, base_datos=base)
        # Registrar lo mismo otra vez no duplica nodos.
        registrar_hallazgos(driver, ejecucion_id, hallazgos, base_datos=base)

        filas = listar_hallazgos(driver, ejecucion_id, base)
        assert len(filas) == 9
        assert filas[0]["severidad"] == "critica"

        enlaces_cwe = driver.execute_query(
            "MATCH (:Ejecucion {id: $id})-[:REGISTRA]->(:Hallazgo)-[:ES]->(c:CWE) "
            "RETURN collect(DISTINCT c.id) AS cwe",
            {"id": ejecucion_id},
            database_=base,
        ).records[0]["cwe"]
        assert set(enlaces_cwe) == {"CWE-89", "CWE-327", "CWE-916"}
    finally:
        driver.execute_query(
            "MATCH (n) WHERE n.id = $id OR n.ejecucion_id = $id DETACH DELETE n",
            {"id": ejecucion_id},
            database_=base,
        )
        driver.close()
