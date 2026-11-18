"""Pruebas del cargador de la base de conocimiento a Neo4j.

Las pruebas de integración necesitan Neo4j levantado con docker compose y se activan con la
variable NEO4J_INTEGRACION=1; las demás usan un driver simulado.
"""

import os
from types import SimpleNamespace

import neo4j
import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.knowledge import ErrorGrafo, conectar
from orchestrator.knowledge.base_conocimiento import cargar_base_conocimiento
from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo

runner = CliRunner()


class DriverSimulado:
    """Guarda cada consulta y responde a las de conteo con valores fijos."""

    def __init__(self, falla=False):
        self.consultas: list[tuple[str, dict]] = []
        self.falla = falla
        self.cerrado = False

    def execute_query(self, consulta, parametros=None, database_="neo4j"):
        self.consultas.append((consulta, parametros or {}))
        if self.falla:
            raise neo4j.exceptions.ClientError("sin conexión")
        if "DETACH DELETE" in consulta:
            filas = [{"total": 1}]
        elif "DELETE r" in consulta:
            filas = [{"total": 2}]
        elif "RETURN etiqueta, total" in consulta:
            filas = [{"etiqueta": e, "total": 3} for e in parametros["etiquetas"]]
        elif "RETURN type(r) AS tipo" in consulta:
            filas = [{"tipo": "MITIGA", "total": 5}]
        else:
            filas = []
        return SimpleNamespace(records=filas)

    def close(self):
        self.cerrado = True

    def primera(self, fragmento: str) -> dict:
        return next(p for c, p in self.consultas if fragmento in c)


def test_carga_en_orden_y_con_la_version():
    base = cargar_base_conocimiento()
    driver = DriverSimulado()

    resultado = cargar_en_grafo(driver, base, "v-prueba")

    consultas = [c for c, _ in driver.consultas]
    # Primero los CWE, porque el resto de nodos se enlaza a ellos.
    assert "MERGE (n:CWE" in consultas[0]
    assert all(p["version"] == "v-prueba" for _, p in driver.consultas)
    assert resultado["version"] == "v-prueba"
    assert resultado["nodos_retirados"] == 1
    assert resultado["relaciones_retiradas"] == 2
    assert resultado["relaciones"] == {"MITIGA": 5}
    assert set(resultado["nodos"]) == {"Patron", "Directriz", "Control", "RiesgoApi", "CWE"}


def test_envia_todos_los_elementos():
    base = cargar_base_conocimiento()
    driver = DriverSimulado()
    cargar_en_grafo(driver, base, "v")

    assert len(driver.primera("MERGE (n:CWE")["filas"]) == len(base.debilidades)
    assert len(driver.primera("MERGE (n:Control")["filas"]) == len(base.controles)
    assert len(driver.primera("MERGE (n:RiesgoApi")["filas"]) == 10
    implementa = driver.primera("SE_IMPLEMENTA_CON")["filas"]
    assert len(implementa) == len(base.patrones) + len(base.directrices)


def test_las_condiciones_de_los_patrones_se_guardan_como_texto():
    base = cargar_base_conocimiento()
    driver = DriverSimulado()
    cargar_en_grafo(driver, base, "v")

    patrones = {p["id"]: p for p in driver.primera("MERGE (n:Patron")["filas"]}
    assert patrones["arq.gateway.001"]["aplica_cuando"] == [
        "etiqueta:punto_unico_acceso",
        "etiqueta:autenticacion_centralizada",
        "numero_servicios_minimo:2",
    ]


def test_base_vacia_solo_limpia_y_cuenta():
    driver = DriverSimulado()
    cargar_en_grafo(driver, _vacia(), "v")

    assert not any("MERGE" in c for c, _ in driver.consultas)


def _vacia():
    from orchestrator.knowledge.base_conocimiento import BaseConocimiento

    return BaseConocimiento()


def test_error_de_neo4j():
    with pytest.raises(ErrorGrafo, match="Neo4j rechazó la operación"):
        cargar_en_grafo(DriverSimulado(falla=True), cargar_base_conocimiento(), "v")


def test_la_version_depende_del_contenido(tmp_path):
    (tmp_path / "directrices").mkdir()
    archivo = tmp_path / "directrices" / "a.yaml"
    archivo.write_text("id: x\n", encoding="utf-8")
    primera = calcular_version(tmp_path)

    assert calcular_version(tmp_path) == primera
    archivo.write_text("id: y\n", encoding="utf-8")
    assert calcular_version(tmp_path) != primera


def test_la_version_no_cambia_por_saltos_de_linea_de_windows(tmp_path):
    (tmp_path / "a.yaml").write_bytes(b"id: x\nnombre: y\n")
    unix = calcular_version(tmp_path)
    (tmp_path / "a.yaml").write_bytes(b"id: x\r\nnombre: y\r\n")
    assert calcular_version(tmp_path) == unix


def test_comando_cargar(monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    monkeypatch.setattr("orchestrator.knowledge.aplicar_esquema", lambda d, base: 22)

    resultado = runner.invoke(app, ["conocimiento", "cargar"])

    assert resultado.exit_code == 0, resultado.output
    assert "Conocimiento cargado en Neo4j" in resultado.output
    assert "MITIGA: 5" in resultado.output
    assert driver.cerrado


def test_comando_cargar_sin_neo4j(monkeypatch):
    def sin_conexion(config):
        raise ErrorGrafo("No se pudo conectar con Neo4j")

    monkeypatch.setattr("orchestrator.knowledge.conectar", sin_conexion)
    resultado = runner.invoke(app, ["conocimiento", "cargar"])

    assert resultado.exit_code == 1
    assert "No se pudo conectar" in resultado.output


def test_comando_cargar_no_toca_neo4j_si_la_base_es_invalida(tmp_path, monkeypatch):
    (tmp_path / "directrices").mkdir()
    (tmp_path / "directrices" / "x.yaml").write_text("id: [roto\n", encoding="utf-8")
    llamado = []
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: llamado.append(1))

    resultado = runner.invoke(app, ["conocimiento", "cargar", "--raiz", str(tmp_path)])

    assert resultado.exit_code == 1
    assert "inválida" in resultado.output
    assert llamado == []


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_carga_en_neo4j():
    config = obtener_configuracion()
    driver = conectar(config)
    db = config.neo4j_database
    base = cargar_base_conocimiento()
    try:
        primera = cargar_en_grafo(driver, base, "integracion-1", base_datos=db)
        # Cargar lo mismo otra vez no duplica nada.
        segunda = cargar_en_grafo(driver, base, "integracion-1", base_datos=db)
        assert segunda["nodos"] == primera["nodos"]
        assert segunda["relaciones"] == primera["relaciones"]
        assert primera["nodos"]["Directriz"] == len(base.directrices)
        assert primera["nodos"]["RiesgoApi"] == 10
        assert primera["relaciones"]["SE_IMPLEMENTA_CON"] > 0

        # Una versión sin una directriz la retira del grafo, pero conserva los CWE.
        reducida = base.model_copy(update={"directrices": base.directrices[1:]})
        tercera = cargar_en_grafo(driver, reducida, "integracion-2", base_datos=db)
        assert tercera["nodos"]["Directriz"] == len(base.directrices) - 1
        assert tercera["nodos_retirados"] >= 1
        assert tercera["nodos"]["CWE"] == primera["nodos"]["CWE"]
    finally:
        cargar_en_grafo(driver, base, calcular_version(), base_datos=db)
        driver.close()
