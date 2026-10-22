"""Carga de la base de conocimiento (YAML) a Neo4j como nodos y relaciones.

Modelo (plan técnico, sección 5.1.2 y figura 5.1):
    (:Patron)    -[:MITIGA]->            (:CWE)
    (:Directriz) -[:MITIGA]->            (:CWE)
    (:Control)   -[:SE_IMPLEMENTA_CON]-> (:Patron) y (:Directriz)
    (:Control)   -[:CUBRE]->             (:CWE)
    (:Control)   -[:PREVIENE]->          (:RiesgoApi)
    (:RiesgoApi) -[:INCLUYE]->           (:CWE)

La carga es idempotente (MERGE por id) y lleva la versión del conocimiento: lo que ya no está en
los YAML se retira del grafo. Los nodos CWE se conservan siempre, porque los hallazgos de las
ejecuciones también apuntan a ellos; solo se retiran sus relaciones de conocimiento antiguas.
"""

import hashlib
from pathlib import Path
from typing import Any

import neo4j

from orchestrator.knowledge.base_conocimiento import RAIZ_POR_DEFECTO, BaseConocimiento
from orchestrator.knowledge.grafo import ErrorGrafo

ETIQUETAS_CONOCIMIENTO = ("Patron", "Directriz", "Control", "RiesgoApi")
RELACIONES_CONOCIMIENTO = ("MITIGA", "SE_IMPLEMENTA_CON", "CUBRE", "PREVIENE", "INCLUYE")

_CWE = """
UNWIND $filas AS f
MERGE (n:CWE {id: f.id})
SET n.nombre = f.nombre, n.descripcion = f.descripcion, n.origen = 'conocimiento',
    n.version = $version
"""

_PATRONES = """
UNWIND $filas AS f
MERGE (n:Patron {id: f.id})
SET n.nombre = f.patron, n.descripcion = f.descripcion, n.implementacion = f.implementacion,
    n.aplica_cuando = f.aplica_cuando, n.version = $version
WITH n, f
UNWIND f.cwe_mitigadas AS cwe
MATCH (c:CWE {id: cwe})
MERGE (n)-[r:MITIGA]->(c) SET r.version = $version
"""

_DIRECTRICES = """
UNWIND $filas AS f
MERGE (n:Directriz {id: f.id})
SET n.nombre = f.directriz, n.descripcion = f.descripcion, n.aplica_a = f.aplica_a,
    n.practicas = f.practicas, n.verificacion = f.verificacion, n.version = $version
WITH n, f
UNWIND f.cwe_mitigadas AS cwe
MATCH (c:CWE {id: cwe})
MERGE (n)-[r:MITIGA]->(c) SET r.version = $version
"""

_CONTROLES = """
UNWIND $filas AS f
MERGE (n:Control {id: f.id})
SET n.capitulo = f.capitulo, n.seccion = f.seccion, n.descripcion = f.descripcion,
    n.niveles = f.niveles, n.version = $version
WITH n, f
UNWIND f.cwe AS cwe
MATCH (c:CWE {id: cwe})
MERGE (n)-[r:CUBRE]->(c) SET r.version = $version
"""

# Un control "se implementa con" el patrón o la directriz que lo cita.
_IMPLEMENTA = """
UNWIND $filas AS f
MATCH (p {id: f.id}) WHERE p:Patron OR p:Directriz
UNWIND f.controles_asociados AS control
MATCH (c:Control {id: control})
MERGE (c)-[r:SE_IMPLEMENTA_CON]->(p) SET r.version = $version
"""

_RIESGOS = """
UNWIND $filas AS f
MERGE (n:RiesgoApi {id: f.id})
SET n.nombre = f.nombre, n.descripcion = f.descripcion, n.version = $version
WITH n, f
CALL (n, f) {
    UNWIND f.cwe AS cwe
    MATCH (c:CWE {id: cwe})
    MERGE (n)-[r:INCLUYE]->(c) SET r.version = $version
}
WITH n, f
UNWIND f.controles AS control
MATCH (c:Control {id: control})
MERGE (c)-[r:PREVIENE]->(n) SET r.version = $version
"""

_RETIRAR_RELACIONES = """
MATCH ()-[r]->()
WHERE type(r) IN $tipos AND coalesce(r.version, '') <> $version
DELETE r
RETURN count(r) AS total
"""

_RETIRAR_NODOS = """
MATCH (n)
WHERE any(etiqueta IN labels(n) WHERE etiqueta IN $etiquetas)
  AND coalesce(n.version, '') <> $version
DETACH DELETE n
RETURN count(n) AS total
"""

_CONTAR = """
UNWIND $etiquetas AS etiqueta
CALL (etiqueta) {
    MATCH (n) WHERE etiqueta IN labels(n) AND n.version = $version RETURN count(n) AS total
}
RETURN etiqueta, total
"""

_CONTAR_RELACIONES = """
MATCH ()-[r]->() WHERE type(r) IN $tipos AND r.version = $version
RETURN type(r) AS tipo, count(r) AS total
"""


def calcular_version(raiz: str | Path = RAIZ_POR_DEFECTO) -> str:
    """Huella del contenido de todos los YAML: cambia si cambia cualquier conocimiento."""
    resumen = hashlib.sha256()
    raiz = Path(raiz)
    for ruta in sorted(raiz.rglob("*.yaml")):
        resumen.update(ruta.relative_to(raiz).as_posix().encode("utf-8"))
        resumen.update(ruta.read_bytes().replace(b"\r\n", b"\n"))
    return resumen.hexdigest()[:12]


def _condicion(condicion: Any) -> str:
    if condicion.etiqueta is not None:
        return f"etiqueta:{condicion.etiqueta}"
    return f"numero_servicios_minimo:{condicion.numero_servicios_minimo}"


def cargar_en_grafo(
    driver: Any, base: BaseConocimiento, version: str, base_datos: str = "neo4j"
) -> dict[str, Any]:
    """Carga la base validada; devuelve los nodos y relaciones cargados y los retirados."""
    patrones = [
        {**p.model_dump(), "aplica_cuando": [_condicion(c) for c in p.aplica_cuando]}
        for p in base.patrones
    ]
    directrices = [d.model_dump() for d in base.directrices]

    # Los CWE van primero: los demás nodos se enlazan a ellos.
    pasos = [
        (_CWE, [d.model_dump() for d in base.debilidades]),
        (_PATRONES, patrones),
        (_DIRECTRICES, directrices),
        (_CONTROLES, [c.model_dump() for c in base.controles]),
        (_IMPLEMENTA, patrones + directrices),
        (_RIESGOS, [r.model_dump() for r in base.riesgos_api]),
    ]
    for consulta, filas in pasos:
        if filas:
            _ejecutar(driver, consulta, base_datos, filas=filas, version=version)

    retiradas = _ejecutar(
        driver,
        _RETIRAR_RELACIONES,
        base_datos,
        tipos=list(RELACIONES_CONOCIMIENTO),
        version=version,
    )
    retirados = _ejecutar(
        driver, _RETIRAR_NODOS, base_datos, etiquetas=list(ETIQUETAS_CONOCIMIENTO), version=version
    )
    nodos = _ejecutar(
        driver, _CONTAR, base_datos, etiquetas=[*ETIQUETAS_CONOCIMIENTO, "CWE"], version=version
    )
    relaciones = _ejecutar(
        driver, _CONTAR_RELACIONES, base_datos, tipos=list(RELACIONES_CONOCIMIENTO), version=version
    )

    return {
        "version": version,
        "nodos": {r["etiqueta"]: r["total"] for r in nodos.records},
        "relaciones": {r["tipo"]: r["total"] for r in relaciones.records},
        "nodos_retirados": _total(retirados),
        "relaciones_retiradas": _total(retiradas),
    }


def _total(resultado: Any) -> int:
    return resultado.records[0]["total"] if resultado.records else 0


def _ejecutar(driver: Any, consulta: str, base_datos: str, **parametros: Any):
    try:
        return driver.execute_query(consulta, parametros, database_=base_datos)
    except neo4j.exceptions.Neo4jError as error:
        raise ErrorGrafo(f"Neo4j rechazó la operación: {error.message}") from error
