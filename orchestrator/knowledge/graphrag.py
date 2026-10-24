"""Consulta GraphRAG: búsqueda vectorial de fragmentos más el conocimiento conectado en el grafo.

Plan técnico, sección 5.1.2 (listing 5.2): la búsqueda por significado encuentra los fragmentos
más parecidos a una pregunta y, a partir del elemento que describe cada uno, se recorren las
relaciones del grafo para traer las CWE, los patrones, las directrices, los controles ASVS y los
riesgos del API Top 10 relacionados. Ese contexto es el que recibirá el LLM, para que sus
propuestas se apoyen en el conocimiento formal del framework y no en el genérico del modelo.
"""

from typing import Any

import neo4j
from pydantic import BaseModel

from orchestrator.knowledge.embeddings import ProveedorEmbeddings
from orchestrator.knowledge.fragmentos import NOMBRE_INDICE
from orchestrator.knowledge.grafo import ErrorGrafo

# Desde el elemento que describe cada fragmento (o) se siguen las relaciones en su sentido:
#   CWE        <- MITIGA de patrones/directrices, <- CUBRE de controles, <- INCLUYE de riesgos
#   Control    -> SE_IMPLEMENTA_CON patrones/directrices, -> PREVIENE riesgos
#   Patron/Directriz <- SE_IMPLEMENTA_CON de controles
_CONSULTA = """
CALL db.index.vector.queryNodes($indice, $k, $vector) YIELD node AS f, score
WHERE score >= $umbral
MATCH (f)-[:DESCRIBE]->(o)
WITH f, score, o,
     CASE WHEN o:CWE THEN [o] ELSE [(o)-[:MITIGA|CUBRE|INCLUYE]->(c:CWE) | c] END AS cwes
WITH f, score, o, cwes,
     CASE
         WHEN o:Patron OR o:Directriz THEN [o]
         WHEN o:Control THEN [(o)-[:SE_IMPLEMENTA_CON]->(p) | p]
         ELSE []
     END + reduce(acc = [], c IN cwes | acc + [(p)-[:MITIGA]->(c) | p]) AS practicas
WITH f, score, o, cwes, practicas,
     CASE WHEN o:Control THEN [o] ELSE [] END
         + [(ctl:Control)-[:PREVIENE]->(o) | ctl]
         + reduce(acc = [], c IN cwes | acc + [(ctl:Control)-[:CUBRE]->(c) | ctl])
         + reduce(acc = [], p IN practicas | acc + [(ctl:Control)-[:SE_IMPLEMENTA_CON]->(p) | ctl])
         AS controles,
     CASE WHEN o:RiesgoApi THEN [o] ELSE [] END
         + [(o)-[:PREVIENE]->(r:RiesgoApi) | r]
         + reduce(acc = [], c IN cwes | acc + [(r:RiesgoApi)-[:INCLUYE]->(c) | r])
         AS riesgos
RETURN f.id AS fragmento, f.texto AS texto, score,
       o.id AS origen_id, labels(o)[0] AS origen_tipo,
       [x IN cwes | {id: x.id, nombre: x.nombre}] AS cwe,
       [x IN practicas | {id: x.id, nombre: x.nombre, tipo: labels(x)[0]}] AS practicas,
       [x IN controles | {id: x.id, descripcion: x.descripcion}] AS controles,
       [x IN riesgos | {id: x.id, nombre: x.nombre}] AS riesgos
ORDER BY score DESC
"""


class Elemento(BaseModel):
    id: str
    nombre: str


class Coincidencia(BaseModel):
    fragmento: str
    texto: str
    puntuacion: float
    origen_id: str
    origen_tipo: str


class ContextoGraphRAG(BaseModel):
    pregunta: str
    coincidencias: list[Coincidencia]
    cwe: list[Elemento]
    patrones: list[Elemento]
    directrices: list[Elemento]
    controles: list[Elemento]
    riesgos: list[Elemento]

    def a_texto(self) -> str:
        """Contexto listo para incluir en un prompt, separado de la pregunta del usuario."""
        if not self.coincidencias:
            return "No se encontró conocimiento relacionado en la base."
        lineas = ["Conocimiento relacionado de la base del framework:"]
        lineas += [f"- {c.texto}" for c in self.coincidencias]
        secciones = [
            ("Debilidades CWE", self.cwe),
            ("Patrones de microservicios", self.patrones),
            ("Directrices Secure by Design", self.directrices),
            ("Controles OWASP ASVS", self.controles),
            ("Riesgos OWASP API Top 10", self.riesgos),
        ]
        for titulo, elementos in secciones:
            if elementos:
                lineas.append(f"{titulo}: " + "; ".join(f"{e.id} ({e.nombre})" for e in elementos))
        return "\n".join(lineas)


def consultar(
    driver: Any,
    proveedor: ProveedorEmbeddings,
    pregunta: str,
    k: int = 5,
    umbral: float = 0.0,
    base_datos: str = "neo4j",
) -> ContextoGraphRAG:
    """Busca los `k` fragmentos más parecidos a la pregunta y reúne el conocimiento conectado."""
    if not pregunta.strip():
        raise ValueError("La pregunta está vacía")
    if k < 1:
        raise ValueError("k debe ser al menos 1")

    (vector,) = proveedor.embeber([pregunta])
    try:
        resultado = driver.execute_query(
            _CONSULTA,
            {"indice": NOMBRE_INDICE, "k": k, "vector": vector, "umbral": umbral},
            database_=base_datos,
        )
    except neo4j.exceptions.Neo4jError as error:
        raise ErrorGrafo(f"Neo4j rechazó la consulta GraphRAG: {error.message}") from error

    acumulado: dict[str, dict[str, Elemento]] = {
        "cwe": {},
        "patrones": {},
        "directrices": {},
        "controles": {},
        "riesgos": {},
    }
    coincidencias = []
    for fila in resultado.records:
        coincidencias.append(
            Coincidencia(
                fragmento=fila["fragmento"],
                texto=fila["texto"],
                puntuacion=round(fila["score"], 4),
                origen_id=fila["origen_id"],
                origen_tipo=fila["origen_tipo"],
            )
        )
        for item in fila["cwe"]:
            _agregar(acumulado["cwe"], item["id"], item["nombre"])
        for item in fila["practicas"]:
            destino = "patrones" if item["tipo"] == "Patron" else "directrices"
            _agregar(acumulado[destino], item["id"], item["nombre"])
        for item in fila["controles"]:
            _agregar(acumulado["controles"], item["id"], item["descripcion"])
        for item in fila["riesgos"]:
            _agregar(acumulado["riesgos"], item["id"], item["nombre"])

    return ContextoGraphRAG(
        pregunta=pregunta,
        coincidencias=coincidencias,
        **{clave: list(elementos.values()) for clave, elementos in acumulado.items()},
    )


def _agregar(destino: dict[str, Elemento], identificador: str, nombre: str | None) -> None:
    """Conserva el orden de aparición (el de mayor parecido primero) y evita repetidos."""
    if identificador not in destino:
        destino[identificador] = Elemento(id=identificador, nombre=nombre or identificador)
