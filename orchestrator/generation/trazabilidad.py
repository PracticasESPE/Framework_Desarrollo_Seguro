"""Trazabilidad requisito -> componente -> archivo en Neo4j (plan técnico, listing 5.5).

Por cada servicio generado desde `arquitectura.json`:

    (:Requisito)-[:IMPLEMENTA_EN]->(:Componente)-[:CONTIENE]->(:Archivo)

El componente es el servicio y sus requisitos son los que `arquitectura.json` le asigna. Los
archivos son los del servicio generado (sin `node_modules` ni la caché de dependencias). Todo
cuelga de una ejecución, igual que los requisitos y las decisiones.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orchestrator.generation.parametros import ParametrosServicio
from orchestrator.knowledge.registro import ErrorGrafo, _ejecutar, existe_ejecucion

# Carpetas que no forman parte del servicio entregado: dependencias y salidas de compilación.
EXCLUIDAS = frozenset({"node_modules", ".dependencias", "dist", "coverage", ".git"})


class ErrorTrazabilidad(Exception):
    """El servicio o la ejecución no existen, así que no hay nada que enlazar."""


@dataclass(frozen=True)
class EnlaceServicio:
    """Lo que se enlaza de un servicio: su nombre, sus requisitos y sus archivos."""

    servicio: str
    carpeta: str
    requisitos: tuple[str, ...]
    archivos: tuple[str, ...]


@dataclass
class ResumenTrazabilidad:
    servicios: int = 0
    archivos: int = 0
    requisitos_enlazados: int = 0
    requisitos_sin_nodo: list[str] = field(default_factory=list)


def archivos_del_servicio(carpeta: Path) -> tuple[str, ...]:
    """Rutas relativas (con `/`) de los archivos del servicio, sin las carpetas excluidas."""
    rutas: list[str] = []
    # os.walk no entra en node_modules; rglob lo recorría entero antes de filtrarlo.
    for directorio, subcarpetas, archivos in os.walk(carpeta):
        subcarpetas[:] = [s for s in subcarpetas if s not in EXCLUIDAS]
        for nombre in archivos:
            relativa = (Path(directorio) / nombre).relative_to(carpeta)
            rutas.append(relativa.as_posix())
    return tuple(sorted(rutas))


def enlaces_de_servicios(
    parametros: Iterable[ParametrosServicio], raiz: Path
) -> list[EnlaceServicio]:
    """Un EnlaceServicio por servicio, con los archivos de `raiz/<servicio>`.

    Falla si falta la carpeta de algún servicio: enlazar un servicio a medias daría una
    trazabilidad incompleta sin avisar.
    """
    enlaces: list[EnlaceServicio] = []
    for servicio in parametros:
        carpeta = raiz / servicio.servicio
        if not carpeta.is_dir():
            raise ErrorTrazabilidad(f"no existe la carpeta del servicio: {carpeta}")
        enlaces.append(
            EnlaceServicio(
                servicio=servicio.servicio,
                carpeta=carpeta.as_posix(),
                requisitos=tuple(servicio.requisitos),
                archivos=archivos_del_servicio(carpeta),
            )
        )
    return enlaces


_REQUISITOS_EN_GRAFO = """
MATCH (r:Requisito {ejecucion_id: $ejecucion_id})
RETURN r.id AS id
"""

# Componentes y archivos son por ejecución: volver a correrlo no duplica nada.
_REGISTRAR_TRAZABILIDAD = """
MATCH (e:Ejecucion {id: $ejecucion_id})
UNWIND $servicios AS s
MERGE (c:Componente {ejecucion_id: $ejecucion_id, id: s.servicio})
SET c.carpeta = s.carpeta
MERGE (e)-[:TIENE_COMPONENTE]->(c)
WITH c, s
UNWIND s.archivos AS ruta
MERGE (a:Archivo {ejecucion_id: $ejecucion_id, ruta: s.servicio + '/' + ruta})
MERGE (c)-[:CONTIENE]->(a)
WITH c, s
UNWIND s.requisitos AS rid
MATCH (r:Requisito {ejecucion_id: $ejecucion_id, id: rid})
MERGE (r)-[:IMPLEMENTA_EN]->(c)
"""


def registrar_trazabilidad(
    driver: Any,
    ejecucion_id: str,
    enlaces: list[EnlaceServicio],
    base_datos: str = "neo4j",
) -> ResumenTrazabilidad:
    """Escribe los componentes, archivos y enlaces de cada requisito en la ejecución indicada."""
    if not existe_ejecucion(driver, ejecucion_id, base_datos):
        raise ErrorGrafo(f"No existe la ejecución {ejecucion_id}")

    existentes = {
        registro["id"]
        for registro in _ejecutar(
            driver, _REQUISITOS_EN_GRAFO, base_datos, ejecucion_id=ejecucion_id
        ).records
    }
    referenciados = {rid for enlace in enlaces for rid in enlace.requisitos}

    _ejecutar(
        driver,
        _REGISTRAR_TRAZABILIDAD,
        base_datos,
        ejecucion_id=ejecucion_id,
        servicios=[
            {
                "servicio": e.servicio,
                "carpeta": e.carpeta,
                "requisitos": list(e.requisitos),
                "archivos": list(e.archivos),
            }
            for e in enlaces
        ],
    )

    return ResumenTrazabilidad(
        servicios=len(enlaces),
        archivos=sum(len(e.archivos) for e in enlaces),
        requisitos_enlazados=len(referenciados & existentes),
        requisitos_sin_nodo=sorted(referenciados - existentes),
    )
