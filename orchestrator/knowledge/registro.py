"""Registro de ejecuciones del pipeline y de sus hallazgos como nodos en Neo4j.

Modelo:
    (:Ejecucion {id, fecha, estado, documento, version_conocimiento})
    (:Ejecucion)-[:REGISTRA]->(:Hallazgo {ejecucion_id, huella, ...})
    (:Hallazgo)-[:ES]->(:CWE {id})
"""

import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import neo4j

from orchestrator.gates.hallazgos import Hallazgo
from orchestrator.knowledge.grafo import ErrorGrafo

RAIZ = Path(__file__).resolve().parents[2]

# Posición de cada severidad para ordenar en Cypher de la más grave a la más leve.
_RANGO_SEVERIDAD = (
    "CASE h.severidad WHEN 'critica' THEN 0 WHEN 'alta' THEN 1 WHEN 'media' THEN 2 "
    "WHEN 'baja' THEN 3 ELSE 4 END"
)

_CREAR_EJECUCION = """
CREATE (e:Ejecucion {
    id: $id,
    fecha: $fecha,
    estado: 'en_curso',
    documento: $documento,
    version_conocimiento: $version_conocimiento
})
"""

# MERGE por (ejecucion_id, huella): registrar el mismo SARIF dos veces no duplica hallazgos.
_REGISTRAR_HALLAZGOS = """
MATCH (e:Ejecucion {id: $ejecucion_id})
UNWIND $hallazgos AS dato
MERGE (h:Hallazgo {ejecucion_id: $ejecucion_id, huella: dato.huella})
SET h.herramienta = dato.herramienta,
    h.regla_id = dato.regla_id,
    h.mensaje = dato.mensaje,
    h.severidad = dato.severidad,
    h.archivo = dato.archivo,
    h.linea_inicio = dato.linea_inicio,
    h.linea_fin = dato.linea_fin,
    h.cwe = dato.cwe,
    h.fase = $fase
MERGE (e)-[:REGISTRA]->(h)
WITH h, dato
UNWIND dato.cwe AS cwe_id
MERGE (c:CWE {id: cwe_id})
  ON CREATE SET c.origen = 'hallazgo'
MERGE (h)-[:ES]->(c)
"""

_LISTAR_HALLAZGOS = f"""
MATCH (:Ejecucion {{id: $ejecucion_id}})-[:REGISTRA]->(h:Hallazgo)
RETURN h.herramienta AS herramienta, h.regla_id AS regla_id, h.severidad AS severidad,
       h.archivo AS archivo, h.linea_inicio AS linea_inicio, h.cwe AS cwe, h.huella AS huella
ORDER BY {_RANGO_SEVERIDAD}, h.herramienta, h.archivo, h.linea_inicio
"""

_ULTIMA_EJECUCION = "MATCH (e:Ejecucion) RETURN e.id AS id ORDER BY e.fecha DESC LIMIT 1"

_FINALIZAR_EJECUCION = """
MATCH (e:Ejecucion {id: $id})
SET e.estado = $estado, e.fin = $fin
RETURN e.id AS id
"""


def nuevo_id_ejecucion(ahora: datetime | None = None) -> str:
    momento = ahora or datetime.now(UTC)
    return f"ej-{momento:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


def version_conocimiento() -> str | None:
    """Commit actual del repositorio: identifica la versión de la base de conocimiento usada."""
    try:
        proceso = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None
    if proceso.returncode != 0:
        return None
    return proceso.stdout.strip() or None


def _ejecutar(driver: Any, consulta: str, base_datos: str, **parametros: Any):
    try:
        return driver.execute_query(consulta, parametros, database_=base_datos)
    except neo4j.exceptions.Neo4jError as error:
        raise ErrorGrafo(f"Neo4j rechazó la operación: {error.message}") from error


def crear_ejecucion(
    driver: Any,
    documento: str | None = None,
    base_datos: str = "neo4j",
    id_ejecucion: str | None = None,
    version: str | None = None,
) -> str:
    """Crea el nodo Ejecucion y devuelve su id."""
    ejecucion_id = id_ejecucion or nuevo_id_ejecucion()
    _ejecutar(
        driver,
        _CREAR_EJECUCION,
        base_datos,
        id=ejecucion_id,
        fecha=datetime.now(UTC),
        documento=documento,
        version_conocimiento=version if version is not None else version_conocimiento(),
    )
    return ejecucion_id


def registrar_hallazgos(
    driver: Any,
    ejecucion_id: str,
    hallazgos: list[Hallazgo],
    fase: int = 4,
    base_datos: str = "neo4j",
) -> int:
    """Registra los hallazgos de una fase y los enlaza a su ejecución y a sus CWE."""
    if not hallazgos:
        return 0
    if not existe_ejecucion(driver, ejecucion_id, base_datos):
        raise ErrorGrafo(f"No existe la ejecución {ejecucion_id}")
    _ejecutar(
        driver,
        _REGISTRAR_HALLAZGOS,
        base_datos,
        ejecucion_id=ejecucion_id,
        fase=fase,
        hallazgos=[h.model_dump(mode="json") for h in hallazgos],
    )
    return len({h.huella for h in hallazgos})


def existe_ejecucion(driver: Any, ejecucion_id: str, base_datos: str = "neo4j") -> bool:
    resultado = _ejecutar(
        driver,
        "MATCH (e:Ejecucion {id: $id}) RETURN count(e) AS total",
        base_datos,
        id=ejecucion_id,
    )
    return bool(resultado.records) and resultado.records[0]["total"] > 0


def finalizar_ejecucion(
    driver: Any, ejecucion_id: str, estado: str = "terminada", base_datos: str = "neo4j"
) -> None:
    resultado = _ejecutar(
        driver,
        _FINALIZAR_EJECUCION,
        base_datos,
        id=ejecucion_id,
        estado=estado,
        fin=datetime.now(UTC),
    )
    if not resultado.records:
        raise ErrorGrafo(f"No existe la ejecución {ejecucion_id}")


def ultima_ejecucion(driver: Any, base_datos: str = "neo4j") -> str | None:
    resultado = _ejecutar(driver, _ULTIMA_EJECUCION, base_datos)
    return resultado.records[0]["id"] if resultado.records else None


def listar_hallazgos(
    driver: Any, ejecucion_id: str, base_datos: str = "neo4j"
) -> list[dict[str, Any]]:
    """Hallazgos de una ejecución, de la severidad más grave a la más leve."""
    resultado = _ejecutar(driver, _LISTAR_HALLAZGOS, base_datos, ejecucion_id=ejecucion_id)
    return [registro.data() for registro in resultado.records]
