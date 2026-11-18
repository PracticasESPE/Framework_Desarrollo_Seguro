"""Fragmentos de texto de la base de conocimiento, con embeddings e índice vectorial en Neo4j.

Cada fragmento es un nodo (:Fragmento {id, texto, embedding}) enlazado al elemento que describe:
    (:Fragmento)-[:DESCRIBE]->(:CWE | :Control | :RiesgoApi | :Patron | :Directriz)

Es la base de GraphRAG (plan técnico, sección 5.1.2): la búsqueda vectorial encuentra los
fragmentos más parecidos a una pregunta y el grafo aporta lo que está conectado a ellos.
"""

from typing import Any, Literal

import neo4j
from pydantic import BaseModel

from orchestrator.knowledge.base_conocimiento import BaseConocimiento
from orchestrator.knowledge.embeddings import ProveedorEmbeddings
from orchestrator.knowledge.grafo import ErrorGrafo

NOMBRE_INDICE = "fragmento_embedding"
MAX_PALABRAS = 120
SOLAPE_PALABRAS = 20

Origen = Literal["CWE", "Control", "RiesgoApi", "Patron", "Directriz"]


class Fragmento(BaseModel):
    id: str
    texto: str
    origen_id: str
    origen_tipo: Origen


def dividir(
    texto: str, max_palabras: int = MAX_PALABRAS, solape: int = SOLAPE_PALABRAS
) -> list[str]:
    """Parte un texto largo en trozos de hasta `max_palabras`, con solape entre ellos."""
    if max_palabras <= solape:
        raise ValueError("max_palabras debe ser mayor que solape")
    palabras = texto.split()
    if len(palabras) <= max_palabras:
        return [" ".join(palabras)] if palabras else []
    trozos = []
    paso = max_palabras - solape
    for inicio in range(0, len(palabras), paso):
        trozos.append(" ".join(palabras[inicio : inicio + max_palabras]))
        if inicio + max_palabras >= len(palabras):
            break
    return trozos


def generar_fragmentos(base: BaseConocimiento) -> list[Fragmento]:
    """Un texto descriptivo por elemento de la base, dividido si es largo."""
    textos: list[tuple[str, Origen, str]] = []
    for d in base.debilidades:
        textos.append((d.id, "CWE", f"{d.id} {d.nombre}. {d.descripcion}"))
    for c in base.controles:
        textos.append(
            (c.id, "Control", f"Control {c.id} ({c.capitulo}, {c.seccion}): {c.descripcion}")
        )
    for r in base.riesgos_api:
        textos.append((r.id, "RiesgoApi", f"Riesgo {r.id} {r.nombre}: {r.descripcion}"))
    for p in base.patrones:
        textos.append(
            (
                p.id,
                "Patron",
                f"Patrón de microservicios {p.patron}: {p.descripcion}. "
                f"Se implementa con {p.implementacion}.",
            )
        )
    for d in base.directrices:
        practicas = " ".join(f"{practica}." for practica in d.practicas)
        textos.append(
            (d.id, "Directriz", f"Directriz {d.directriz}: {d.descripcion}. Prácticas: {practicas}")
        )

    fragmentos = []
    for origen_id, tipo, texto in textos:
        for numero, trozo in enumerate(dividir(texto), start=1):
            fragmentos.append(
                Fragmento(
                    id=f"frag.{origen_id}.{numero}",
                    texto=trozo,
                    origen_id=origen_id,
                    origen_tipo=tipo,
                )
            )
    return fragmentos


_INDICES_VECTORIALES = """
SHOW VECTOR INDEXES YIELD name, state, options
WHERE name = $nombre
RETURN state, options.indexConfig['vector.dimensions'] AS dimensiones
"""

# Las opciones de un índice no admiten parámetros: la dimensión se inserta como entero.
_CREAR_INDICE = """
CREATE VECTOR INDEX {nombre} IF NOT EXISTS
FOR (f:Fragmento) ON (f.embedding)
OPTIONS {{ indexConfig: {{
    `vector.dimensions`: {dimensiones},
    `vector.similarity_function`: 'cosine'
}} }}
"""

_CARGAR = """
UNWIND $filas AS f
MERGE (n:Fragmento {id: f.id})
SET n.texto = f.texto, n.origen_id = f.origen_id, n.origen_tipo = f.origen_tipo,
    n.modelo = $modelo, n.version = $version, n.embedding = f.embedding
WITH n, f
MATCH (o {id: f.origen_id})
WHERE f.origen_tipo IN labels(o)
MERGE (n)-[r:DESCRIBE]->(o)
"""

_RETIRAR = """
MATCH (n:Fragmento) WHERE coalesce(n.version, '') <> $version
DETACH DELETE n
RETURN count(n) AS total
"""

_CONTAR = """
MATCH (n:Fragmento {version: $version})
OPTIONAL MATCH (n)-[r:DESCRIBE]->()
RETURN count(DISTINCT n) AS fragmentos, count(r) AS enlaces
"""


def asegurar_indice(driver: Any, dimensiones: int, base_datos: str = "neo4j") -> str:
    """Crea el índice vectorial si no existe y devuelve su estado (por ejemplo, ONLINE)."""
    existentes = _ejecutar(driver, _INDICES_VECTORIALES, base_datos, nombre=NOMBRE_INDICE)
    if existentes.records:
        actuales = existentes.records[0]["dimensiones"]
        if actuales != dimensiones:
            raise ErrorGrafo(
                f"El índice {NOMBRE_INDICE} tiene {actuales} dimensiones y el modelo produce "
                f"{dimensiones}. Bórralo en Neo4j Browser con 'DROP INDEX {NOMBRE_INDICE}' "
                "y vuelve a cargar."
            )
    else:
        consulta = _CREAR_INDICE.format(nombre=NOMBRE_INDICE, dimensiones=int(dimensiones))
        _ejecutar(driver, consulta, base_datos)
        existentes = _ejecutar(driver, _INDICES_VECTORIALES, base_datos, nombre=NOMBRE_INDICE)
    return existentes.records[0]["state"] if existentes.records else "desconocido"


def cargar_fragmentos(
    driver: Any,
    base: BaseConocimiento,
    proveedor: ProveedorEmbeddings,
    version_conocimiento: str,
    base_datos: str = "neo4j",
) -> dict[str, Any]:
    """Genera los fragmentos, calcula sus embeddings y los guarda junto al índice vectorial."""
    fragmentos = generar_fragmentos(base)
    vectores = proveedor.embeber([f.texto for f in fragmentos])
    if len(vectores) != len(fragmentos):
        raise ErrorGrafo("El proveedor de embeddings devolvió un número de vectores distinto")
    if any(len(v) != proveedor.dimensiones for v in vectores):
        raise ErrorGrafo(f"Algún vector no tiene {proveedor.dimensiones} dimensiones")

    estado = asegurar_indice(driver, proveedor.dimensiones, base_datos)
    # Si cambia el conocimiento o el modelo, los fragmentos anteriores se reemplazan.
    version = f"{version_conocimiento}:{proveedor.modelo}"
    filas = [{**f.model_dump(), "embedding": v} for f, v in zip(fragmentos, vectores, strict=True)]
    if filas:
        _ejecutar(
            driver, _CARGAR, base_datos, filas=filas, modelo=proveedor.modelo, version=version
        )
    retirados = _ejecutar(driver, _RETIRAR, base_datos, version=version)
    conteo = _ejecutar(driver, _CONTAR, base_datos, version=version)
    fila = conteo.records[0] if conteo.records else {"fragmentos": 0, "enlaces": 0}

    return {
        "modelo": proveedor.modelo,
        "dimensiones": proveedor.dimensiones,
        "indice": NOMBRE_INDICE,
        "estado_indice": estado,
        "fragmentos": fila["fragmentos"],
        "enlaces_describe": fila["enlaces"],
        "fragmentos_retirados": retirados.records[0]["total"] if retirados.records else 0,
    }


def _ejecutar(driver: Any, consulta: str, base_datos: str, **parametros: Any):
    try:
        return driver.execute_query(consulta, parametros, database_=base_datos)
    except neo4j.exceptions.Neo4jError as error:
        raise ErrorGrafo(f"Neo4j rechazó la operación: {error.message}") from error
