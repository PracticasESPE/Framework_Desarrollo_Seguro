"""Requisitos de la fase 1 como nodos Requisito en Neo4j.

Las pruebas unitarias usan el driver simulado de test_registro.py. La de integración necesita
Neo4j levantado con docker compose y NEO4J_INTEGRACION=1.
"""

import json
import os

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.ingest import DocumentoOrigen, ModeloRequisitos, Requisito
from orchestrator.knowledge import (
    ErrorGrafo,
    conectar,
    crear_ejecucion,
    listar_requisitos,
    registrar_requisitos,
)
from tests.test_registro import DriverSimulado, Registro

runner = CliRunner()


def _modelo() -> ModeloRequisitos:
    comun = {"actor": "cliente", "accion": "registrarse", "servicio_sugerido": "usuarios"}
    return ModeloRequisitos(
        documento=DocumentoOrigen(
            nombre="requisitos.pdf", sha256="a" * 64, herramienta="docling 2.148.0"
        ),
        requisitos=[
            Requisito(
                id="RF-01",
                tipo="funcional",
                texto="El cliente se registra con su correo y una contraseña.",
                ubicacion="3.1",
                entidades=["Cliente"],
                etiquetas=["autenticacion"],
                **comun,
            ),
            Requisito(
                id="RNF-01",
                tipo="no_funcional",
                texto="Las contraseñas nunca se guardan tal como se escriben.",
                ubicacion="3.5",
                entidades=["Contraseña"],
                etiquetas=["hash_password", "cifrado_transito"],
                **comun,
            ),
            Requisito(
                id="RF-02",
                tipo="funcional",
                texto="El cliente busca productos por nombre o categoría.",
                ubicacion="4.1",
                entidades=["Producto"],
                etiquetas=[],
                **comun,
            ),
        ],
    )


class DriverConRequisitos(DriverSimulado):
    """Además responde a la consulta del listado de requisitos."""

    def execute_query(self, consulta, parametros=None, database_="neo4j"):
        if "RETURN DISTINCT e.id AS id" in consulta:
            self.consultas.append((consulta, parametros or {}, database_))
            filas = [Registro(id="ej-con-requisitos")] if self.existe else []
            return type("Resultado", (), {"records": filas})()
        if "RETURN r.id AS id" in consulta:
            self.consultas.append((consulta, parametros or {}, database_))
            filas = [
                Registro(
                    id="RF-01",
                    tipo="funcional",
                    texto="El cliente se registra con su correo y una contraseña.",
                    ubicacion="3.1",
                    actor="cliente",
                    servicio_sugerido="usuarios",
                    etiquetas=["autenticacion"],
                )
            ]
            return type("Resultado", (), {"records": filas})()
        return super().execute_query(consulta, parametros, database_)


# --- Registro -------------------------------------------------------------------------------


def test_registrar_requisitos_en_una_consulta():
    driver = DriverSimulado()
    assert registrar_requisitos(driver, "ej-1", _modelo(), base_datos="b") == 3

    consulta, parametros, base = driver.consulta_con("UNWIND $requisitos")
    assert "MERGE (r:Requisito {ejecucion_id: $ejecucion_id, id: dato.id})" in consulta
    assert "MERGE (e)-[:TIENE_REQUISITO]->(r)" in consulta
    assert base == "b"
    assert parametros["ejecucion_id"] == "ej-1"
    assert parametros["documento"] == {
        "nombre": "requisitos.pdf",
        "sha256": "a" * 64,
        "herramienta": "docling 2.148.0",
    }
    requisitos = parametros["requisitos"]
    assert [r["id"] for r in requisitos] == ["RF-01", "RNF-01", "RF-02"]
    assert [r["orden"] for r in requisitos] == [0, 1, 2]
    assert requisitos[1]["etiquetas"] == ["hash_password", "cifrado_transito"]
    assert requisitos[0]["texto"] == "El cliente se registra con su correo y una contraseña."


def test_volver_a_registrar_quita_los_requisitos_que_ya_no_estan():
    driver = DriverSimulado()
    registrar_requisitos(driver, "ej-1", _modelo())
    consulta, _, _ = driver.consulta_con("UNWIND $requisitos")
    assert "WHERE NOT viejo.id IN [r IN $requisitos | r.id]" in consulta
    assert "DETACH DELETE viejo" in consulta


def test_registrar_en_ejecucion_inexistente():
    with pytest.raises(ErrorGrafo, match="No existe la ejecución"):
        registrar_requisitos(DriverSimulado(existe=False), "ej-x", _modelo())


def test_errores_de_neo4j_se_convierten():
    with pytest.raises(ErrorGrafo, match="rechazó"):
        registrar_requisitos(DriverSimulado(falla=True), "ej-1", _modelo())


def test_listar_requisitos_en_el_orden_del_documento():
    driver = DriverConRequisitos()
    (fila,) = listar_requisitos(driver, "ej-1")
    assert fila["id"] == "RF-01"
    consulta, parametros, _ = driver.consulta_con("RETURN r.id AS id")
    assert "ORDER BY r.orden" in consulta
    assert parametros == {"ejecucion_id": "ej-1"}


# --- CLI ------------------------------------------------------------------------------------


@pytest.fixture
def archivo_modelo(tmp_path):
    archivo = tmp_path / "requisitos-pdf.modelo_requisitos.json"
    archivo.write_text(_modelo().model_dump_json(), encoding="utf-8")
    return archivo


def test_cli_registrar_crea_la_ejecucion_y_la_deja_para_el_pipeline(
    archivo_modelo, tmp_path, monkeypatch
):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path / "salida"))
    monkeypatch.setattr("orchestrator.knowledge.registro.version_conocimiento", lambda: "v1")
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)

    resultado = runner.invoke(app, ["requisitos", "registrar", str(archivo_modelo)])

    assert resultado.exit_code == 0, resultado.output
    assert "Requisitos registrados: 3 (funcionales: 2, no funcionales: 1)" in resultado.output
    _, parametros, _ = driver.consulta_con("CREATE (e:Ejecucion")
    assert parametros["documento"] == "requisitos.pdf"
    pipeline = json.loads((tmp_path / "salida" / "gates" / "ejecucion.json").read_text("utf-8"))
    assert pipeline["ejecucion_id"] == parametros["id"]
    assert f"Ejecución: {parametros['id']}" in resultado.output
    assert driver.cerrado


def test_cli_registrar_en_ejecucion_existente(archivo_modelo, tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path / "salida"))
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)

    resultado = runner.invoke(
        app, ["requisitos", "registrar", str(archivo_modelo), "--ejecucion", "ej-1"]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Ejecución: ej-1" in resultado.output
    assert not any("CREATE (e:Ejecucion" in c[0] for c in driver.consultas)


def test_cli_registrar_rechaza_un_json_que_no_es_un_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "orchestrator.knowledge.conectar", lambda config: pytest.fail("no debe conectar")
    )
    archivo = tmp_path / "otro.json"
    archivo.write_text('{"documento": {}, "requisitos": []}', encoding="utf-8")

    resultado = runner.invoke(app, ["requisitos", "registrar", str(archivo)])

    assert resultado.exit_code == 1
    assert "no es un modelo de requisitos válido" in resultado.output


def test_cli_registrar_archivo_inexistente():
    resultado = runner.invoke(app, ["requisitos", "registrar", "no_existe.json"])
    assert resultado.exit_code != 0


def test_cli_registrar_informa_si_neo4j_falla(archivo_modelo, tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path / "salida"))
    monkeypatch.setattr(
        "orchestrator.knowledge.conectar", lambda config: DriverSimulado(falla=True)
    )
    resultado = runner.invoke(
        app, ["requisitos", "registrar", str(archivo_modelo), "--ejecucion", "ej-1"]
    )
    assert resultado.exit_code == 1
    assert "rechazó" in resultado.output
    assert not (tmp_path / "salida" / "gates" / "ejecucion.json").exists()


def test_cli_listar(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: DriverConRequisitos())

    resultado = runner.invoke(app, ["requisitos", "listar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Ejecución: ej-con-requisitos (1 requisitos)" in resultado.output
    assert "RF-01   [3.1] usuarios | autenticacion" in resultado.output


def test_cli_listar_sin_ejecuciones(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    monkeypatch.setattr(
        "orchestrator.knowledge.conectar", lambda config: DriverConRequisitos(existe=False)
    )
    resultado = runner.invoke(app, ["requisitos", "listar"])
    assert "No hay requisitos registrados" in resultado.output


def test_cli_listar_una_ejecucion_concreta(tmp_path, monkeypatch):
    driver = DriverConRequisitos()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    resultado = runner.invoke(app, ["requisitos", "listar", "--ejecucion", "ej-7"])
    assert "Ejecución: ej-7 (1 requisitos)" in resultado.output
    assert not any("RETURN DISTINCT e.id" in c[0] for c in driver.consultas)


# --- Integración con Neo4j real -------------------------------------------------------------


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_requisitos_en_neo4j():
    config = obtener_configuracion()
    driver = conectar(config)
    base = config.neo4j_database
    ejecucion_id = crear_ejecucion(driver, documento="prueba-integracion", base_datos=base)
    try:
        modelo = _modelo()
        registrar_requisitos(driver, ejecucion_id, modelo, base_datos=base)
        # Registrar otra vez no duplica nodos.
        registrar_requisitos(driver, ejecucion_id, modelo, base_datos=base)
        filas = listar_requisitos(driver, ejecucion_id, base)
        assert [f["id"] for f in filas] == ["RF-01", "RNF-01", "RF-02"]
        assert filas[1]["etiquetas"] == ["hash_password", "cifrado_transito"]

        # Un modelo nuevo con menos requisitos deja solo los que tiene.
        reducido = modelo.model_copy(update={"requisitos": modelo.requisitos[:1]})
        registrar_requisitos(driver, ejecucion_id, reducido, base_datos=base)
        assert [f["id"] for f in listar_requisitos(driver, ejecucion_id, base)] == ["RF-01"]

        documento = driver.execute_query(
            "MATCH (e:Ejecucion {id: $id}) RETURN e.documento AS nombre, "
            "e.documento_sha256 AS sha256",
            {"id": ejecucion_id},
            database_=base,
        ).records[0]
        assert (documento["nombre"], documento["sha256"]) == ("requisitos.pdf", "a" * 64)
    finally:
        driver.execute_query(
            "MATCH (n) WHERE n.id = $id OR n.ejecucion_id = $id DETACH DELETE n",
            {"id": ejecucion_id},
            database_=base,
        )
        driver.close()
