"""Fase 4 del motor: normaliza los resultados del Security Gate 1.

Las herramientas del Gate 1 (scripts/gate1.sh) dejan sus resultados SARIF en
salida/security/sarif. Esta fase los convierte al modelo común de hallazgos, guarda el
resumen en salida/hallazgos/fase4.json y, si Neo4j está configurado, los registra.
La decisión de aprobar o rechazar el gate la tomará OPA (política gates.gate1).
"""

import json
import os
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

from orchestrator.config import Configuracion
from orchestrator.gates.hallazgos import Hallazgo, contar_por_severidad
from orchestrator.gates.sarif import ErrorSarif, leer_carpeta_sarif

FASE = 4


class ErrorFase(Exception):
    """La fase no pudo completarse."""


class ResultadoFase4(BaseModel):
    carpeta_sarif: str
    archivos_sarif: list[str]
    total: int
    por_severidad: dict[str, int]
    por_herramienta: dict[str, int]
    ejecucion_id: str | None = None
    registrado_en_grafo: bool = False
    motivo_sin_grafo: str | None = None
    hallazgos: list[Hallazgo]


def carpeta_sarif_por_defecto(config: Configuracion) -> Path:
    return config.directorio_salida / "security" / "sarif"


def ejecutar_fase4(
    config: Configuracion,
    carpeta_sarif: Path | None = None,
    usar_grafo: bool | None = None,
    ejecucion_id: str | None = None,
    documento: str | None = None,
) -> ResultadoFase4:
    """Lee los SARIF del Gate 1 y devuelve los hallazgos normalizados.

    usar_grafo: True obliga a registrar en Neo4j, False lo omite y None lo hace solo si
    NEO4J_PASSWORD está configurada.
    """
    carpeta = carpeta_sarif or carpeta_sarif_por_defecto(config)
    archivos = sorted(carpeta.glob("*.sarif")) if carpeta.is_dir() else []
    if not archivos:
        raise ErrorFase(
            f"No hay archivos .sarif en {carpeta}. ¿Se ejecutó el Gate 1 (scripts/gate1.sh)?"
        )
    try:
        hallazgos = leer_carpeta_sarif(carpeta)
    except ErrorSarif as error:
        raise ErrorFase(str(error)) from error

    resultado = ResultadoFase4(
        carpeta_sarif=carpeta.as_posix(),
        archivos_sarif=[a.name for a in archivos],
        total=len(hallazgos),
        por_severidad=contar_por_severidad(hallazgos),
        por_herramienta=dict(sorted(Counter(h.herramienta for h in hallazgos).items())),
        hallazgos=hallazgos,
    )

    if usar_grafo is None:
        usar_grafo = config.neo4j_password is not None
        if not usar_grafo:
            resultado.motivo_sin_grafo = "NEO4J_PASSWORD no está configurada"
    elif not usar_grafo:
        resultado.motivo_sin_grafo = "omitido con --sin-grafo"

    if usar_grafo:
        _registrar(config, resultado, ejecucion_id, documento)
    return resultado


def _registrar(
    config: Configuracion,
    resultado: ResultadoFase4,
    ejecucion_id: str | None,
    documento: str | None,
) -> None:
    from orchestrator.knowledge import ErrorGrafo, conectar, crear_ejecucion, registrar_hallazgos

    try:
        driver = conectar(config)
        try:
            resultado.ejecucion_id = ejecucion_id or crear_ejecucion(
                driver, documento=documento, base_datos=config.neo4j_database
            )
            registrar_hallazgos(
                driver,
                resultado.ejecucion_id,
                resultado.hallazgos,
                fase=FASE,
                base_datos=config.neo4j_database,
            )
        finally:
            driver.close()
    except ErrorGrafo as error:
        raise ErrorFase(f"No se pudieron registrar los hallazgos en Neo4j: {error}") from error
    resultado.registrado_en_grafo = True


def guardar_resultado(resultado: ResultadoFase4, config: Configuracion) -> Path:
    destino = config.directorio_salida / "hallazgos" / "fase4.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resultado.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destino


def resumen_markdown(resultado: ResultadoFase4) -> str:
    """Resumen para el registro del paso en GitHub Actions."""
    lineas = [
        "### Fase 4 en el motor: hallazgos normalizados",
        "",
        f"Archivos SARIF leídos: {', '.join(resultado.archivos_sarif)}",
        "",
    ]
    if resultado.total == 0:
        lineas += ["Sin hallazgos: ninguna herramienta del Gate 1 encontró problemas.", ""]
    else:
        lineas += [
            "| Severidad | Hallazgos |",
            "|---|---|",
            *(f"| {s} | {n} |" for s, n in resultado.por_severidad.items()),
            f"| **total** | **{resultado.total}** |",
            "",
            "| Herramienta | Hallazgos |",
            "|---|---|",
            *(f"| {h} | {n} |" for h, n in resultado.por_herramienta.items()),
            "",
        ]
    if resultado.registrado_en_grafo:
        lineas.append(f"Registrados en Neo4j en la ejecución `{resultado.ejecucion_id}`.")
    else:
        lineas.append(f"No registrados en Neo4j: {resultado.motivo_sin_grafo}.")
    return "\n".join(lineas) + "\n"


def publicar_resumen_en_actions(texto: str) -> bool:
    """Añade el resumen a la página de la ejecución si corre dentro de GitHub Actions."""
    ruta = os.environ.get("GITHUB_STEP_SUMMARY")
    if not ruta:
        return False
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(texto)
    return True
