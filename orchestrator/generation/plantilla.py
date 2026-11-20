"""Generación de un microservicio NestJS con la plantilla Copier (fase 3, plan técnico 7.3).

La plantilla (`templates/microservicio_nestjs`) produce el esqueleto determinista del servicio:
módulo, entidades Prisma y DTO con class-validator. El LLM no escribe esa parte; solo completará la
lógica de negocio en los puntos que marque la plantilla (#64).

Los datos de la especificación vendrán del LLM, así que se tratan como no confiables:

- Copier los valida con `copier.yml` antes de escribir nada: cada nombre que acaba como
  identificador en TypeScript o en Prisma debe cumplir una expresión regular, y el tipo de cada
  campo sale de una lista cerrada.
- La plantilla no declara tareas, migraciones ni extensiones, y se ejecuta con `unsafe=False`: si
  alguien las añadiera, Copier se negaría a ejecutarlas.
- Nunca se escribe sobre un servicio que ya existe.
- Lo generado se valida contra la especificación (estructura.py): el árbol de archivos, las rutas,
  el módulo, el esquema Prisma y las marcas del LLM. Si no coincide, el servicio se borra: nunca
  queda a medias en el destino.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from orchestrator.generation.estructura import RUTA_PLANTILLA, validar_estructura


class ErrorPlantilla(Exception):
    """La especificación no es válida o el servicio no se pudo generar."""


def leer_especificacion(ruta: Path) -> dict[str, Any]:
    """Lee la especificación del servicio (YAML o JSON) que recibe la plantilla."""
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise ErrorPlantilla(f"No se pudo leer {ruta.name}: {error}") from error
    if not isinstance(datos, dict):
        raise ErrorPlantilla(f"{ruta.name} debe ser un objeto con servicio y entidades")
    return datos


def _ruta_de_la_plantilla(plantilla: Path) -> str:
    """Ruta relativa al directorio actual cuando se puede.

    Copier la guarda en `.copier-answers.yml` del servicio generado: así no queda en él la ruta
    absoluta de la máquina de quien lo generó.
    """
    try:
        return Path(os.path.relpath(plantilla)).as_posix()
    except ValueError:  # Otra unidad en Windows: no hay ruta relativa.
        return plantilla.as_posix()


def generar_servicio(
    especificacion: dict[str, Any], destino: Path, plantilla: Path = RUTA_PLANTILLA
) -> Path:
    """Genera el servicio en `destino/<servicio>` y devuelve esa carpeta.

    Lanza ErrorPlantilla si la especificación no pasa las validaciones de la plantilla, si la
    carpeta del servicio ya existe y no está vacía, o si lo generado no tiene la estructura que
    corresponde a la especificación.
    """
    import copier
    from copier.errors import CopierError

    servicio = especificacion.get("servicio")
    if not isinstance(servicio, str) or not servicio or Path(servicio).name != servicio:
        raise ErrorPlantilla("La especificación debe indicar el nombre del servicio («servicio»)")
    carpeta = destino / servicio
    if carpeta.exists() and any(carpeta.iterdir()):
        raise ErrorPlantilla(
            f"{carpeta.as_posix()} ya existe y no está vacía: bórrala o elige otro destino"
        )

    try:
        copier.run_copy(
            _ruta_de_la_plantilla(plantilla),
            carpeta,
            data=especificacion,
            defaults=True,
            overwrite=False,
            unsafe=False,
            quiet=True,
        )
    except ValueError as error:
        # Copier valida antes de escribir: «Validation error for question 'x': motivo».
        raise ErrorPlantilla(str(error)) from error
    except CopierError as error:
        raise ErrorPlantilla(f"Copier no pudo generar el servicio: {error}") from error

    resultado = validar_estructura(carpeta, especificacion, plantilla)
    if not resultado.valida:
        shutil.rmtree(carpeta, ignore_errors=True)
        detalle = "\n- ".join(resultado.problemas)
        raise ErrorPlantilla(f"El servicio generado no tiene la estructura esperada:\n- {detalle}")
    return carpeta
