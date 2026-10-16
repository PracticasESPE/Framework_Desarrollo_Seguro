"""Conexión a Neo4j y aplicación del esquema definido en los scripts Cypher de graph/."""

from pathlib import Path
from typing import Any

import neo4j
from neo4j import GraphDatabase

from orchestrator.config import Configuracion, obtener_configuracion

CARPETA_ESQUEMA = Path(__file__).resolve().parents[2] / "graph"


class ErrorGrafo(Exception):
    """No se pudo conectar con Neo4j o aplicar el esquema."""


def leer_sentencias(ruta: str | Path) -> list[str]:
    """Separa un script Cypher en sentencias, sin comentarios de línea."""
    lineas = [
        linea
        for linea in Path(ruta).read_text(encoding="utf-8").splitlines()
        if not linea.strip().startswith("//")
    ]
    return [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]


def scripts_esquema(carpeta: str | Path = CARPETA_ESQUEMA) -> list[Path]:
    """Scripts .cypher en el orden en que se aplican (por nombre: 01_, 02_, ...)."""
    return sorted(Path(carpeta).glob("*.cypher"))


def conectar(configuracion: Configuracion | None = None) -> neo4j.Driver:
    config = configuracion or obtener_configuracion()
    if config.neo4j_password is None:
        raise ErrorGrafo("Falta la variable NEO4J_PASSWORD en el entorno o en .env")

    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password.get_secret_value()),
    )
    try:
        driver.verify_connectivity()
    except neo4j.exceptions.AuthError as error:
        driver.close()
        raise ErrorGrafo("Neo4j rechazó el usuario o la contraseña") from error
    except (neo4j.exceptions.ServiceUnavailable, OSError) as error:
        driver.close()
        raise ErrorGrafo(
            f"No se pudo conectar con Neo4j en {config.neo4j_uri}. "
            "¿Está levantado con 'docker compose -f docker-compose.dev.yml up -d neo4j'?"
        ) from error
    return driver


def aplicar_esquema(
    driver: Any, base_datos: str = "neo4j", carpeta: str | Path = CARPETA_ESQUEMA
) -> int:
    """Ejecuta todas las sentencias de los scripts y devuelve cuántas se aplicaron."""
    scripts = scripts_esquema(carpeta)
    if not scripts:
        raise ErrorGrafo(f"No hay scripts .cypher en {carpeta}")

    aplicadas = 0
    for script in scripts:
        for sentencia in leer_sentencias(script):
            try:
                driver.execute_query(sentencia, database_=base_datos)
            except neo4j.exceptions.Neo4jError as error:
                raise ErrorGrafo(
                    f"Falló una sentencia de {script.name}: {error.message}"
                ) from error
            aplicadas += 1
    return aplicadas


def estado_esquema(driver: Any, base_datos: str = "neo4j") -> dict[str, list[dict[str, Any]]]:
    """Restricciones e índices presentes en la base, como los muestra Neo4j Browser."""
    restricciones = driver.execute_query(
        "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties "
        "RETURN name, type, labelsOrTypes, properties ORDER BY name",
        database_=base_datos,
    ).records
    indices = driver.execute_query(
        "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state, owningConstraint "
        "RETURN name, type, labelsOrTypes, properties, state, owningConstraint ORDER BY name",
        database_=base_datos,
    ).records
    return {
        "restricciones": [registro.data() for registro in restricciones],
        "indices": [registro.data() for registro in indices],
    }


def resumen_grafo(driver: Any, base_datos: str = "neo4j") -> dict[str, dict[str, int]]:
    """Cuántos nodos hay por etiqueta y cuántas relaciones por tipo."""
    nodos = driver.execute_query(
        "MATCH (n) UNWIND labels(n) AS etiqueta "
        "RETURN etiqueta, count(*) AS total ORDER BY etiqueta",
        database_=base_datos,
    ).records
    relaciones = driver.execute_query(
        "MATCH ()-[r]->() RETURN type(r) AS relacion, count(*) AS total ORDER BY relacion",
        database_=base_datos,
    ).records
    return {
        "nodos": {r["etiqueta"]: r["total"] for r in nodos},
        "relaciones": {r["relacion"]: r["total"] for r in relaciones},
    }
