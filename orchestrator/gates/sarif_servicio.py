"""Prepara los SARIF del Gate 1 de un servicio generado para el motor y para GitHub (#71).

Cada herramienta escribe las rutas a su manera: relativas a la carpeta que analizó, con el prefijo
del montaje del contenedor (/src, /work) o como URI file://. GitHub code scanning las necesita
relativas a la raíz del repositorio para ubicar cada alerta, y el motor para la huella de cada
hallazgo. Además, desde julio de 2025 GitHub rechaza varios SARIF con la misma herramienta y la
misma categoría. La de cada uno sale de `runAutomationDetails.id`
(«gate1/<servicio>/<herramienta>/»), así que todos los servicios se publican en una sola subida
sin pisarse.

Solo usa la biblioteca estándar: scripts/gate1-servicios.sh lo ejecuta como script.

    python orchestrator/gates/sarif_servicio.py <sarif> <carpeta del servicio> <servicio> <publicar>
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

# Prefijos de los montajes de los contenedores de las herramientas (la raíz del repositorio).
_MONTAJES = ("/src/", "/work/", "/repo/", "/servicio/")


def ruta_en_el_repositorio(uri: str, servicio: str) -> str:
    """La ruta de `uri` relativa a la raíz del repositorio.

    `servicio` es la carpeta del servicio relativa a esa raíz (salida/servicios/pedidos). Una
    ruta relativa a la carpeta del servicio recibe ese prefijo; una que ya lo trae no cambia.
    """
    ruta = re.sub(r"^file://", "", uri).replace("\\", "/")
    for montaje in _MONTAJES:
        if ruta.startswith(montaje):
            ruta = ruta[len(montaje) :]
            break
    ruta = ruta.lstrip("/")
    while ruta.startswith("./"):
        ruta = ruta[2:]
    servicio = servicio.strip("/")
    if ruta == servicio or ruta.startswith(f"{servicio}/"):
        return ruta
    # Una ruta absoluta del sistema que contiene la carpeta del servicio (p. ej. una carpeta
    # temporal): se recorta hasta ella.
    marca = f"/{servicio}/"
    if marca in f"/{ruta}":
        return servicio + "/" + f"/{ruta}".split(marca, 1)[1]
    return str(PurePosixPath(servicio) / ruta)


def _ubicaciones(resultado: dict[str, Any]):
    for ubicacion in resultado.get("locations") or []:
        fisica = ubicacion.get("physicalLocation") or {}
        artefacto = fisica.get("artifactLocation")
        if isinstance(artefacto, dict):
            yield artefacto


def preparar(documento: dict[str, Any], servicio_dir: str, servicio: str, herramienta: str) -> int:
    """Corrige las rutas y fija la categoría de cada ejecución; devuelve los resultados."""
    total = 0
    ejecuciones = documento.get("runs") or []
    for indice, ejecucion in enumerate(ejecuciones):
        sufijo = "" if len(ejecuciones) == 1 else f"-{indice + 1}"
        ejecucion["automationDetails"] = {"id": f"gate1/{servicio}/{herramienta}{sufijo}/"}
        # Las bases de rutas de la herramienta ya no aplican: todas quedan relativas a la raíz.
        ejecucion.pop("originalUriBaseIds", None)
        for artefacto in ejecucion.get("artifacts") or []:
            ubicacion = artefacto.get("location")
            if isinstance(ubicacion, dict) and isinstance(ubicacion.get("uri"), str):
                ubicacion["uri"] = ruta_en_el_repositorio(ubicacion["uri"], servicio_dir)
                ubicacion.pop("uriBaseId", None)
        for resultado in ejecucion.get("results") or []:
            total += 1
            for artefacto in _ubicaciones(resultado):
                if isinstance(artefacto.get("uri"), str):
                    artefacto["uri"] = ruta_en_el_repositorio(artefacto["uri"], servicio_dir)
                artefacto.pop("uriBaseId", None)
    return total


def preparar_carpeta(carpeta: Path, servicio_dir: str, servicio: str, publicar: Path) -> list[str]:
    """Prepara cada SARIF de `carpeta` y deja una copia en `publicar` para GitHub.

    La copia es plana (<servicio>-<herramienta>.sarif): una sola subida publica todos los
    servicios. Devuelve una línea de resumen por archivo.
    """
    publicar.mkdir(parents=True, exist_ok=True)
    lineas = []
    for ruta in sorted(carpeta.glob("*.sarif")):
        herramienta = ruta.stem
        documento = json.loads(ruta.read_text(encoding="utf-8"))
        total = preparar(documento, servicio_dir, servicio, herramienta)
        texto = json.dumps(documento, ensure_ascii=False, indent=2) + "\n"
        ruta.write_text(texto, encoding="utf-8")
        shutil.copyfile(ruta, publicar / f"{servicio}-{herramienta}.sarif")
        lineas.append(f"{servicio}: {herramienta}.sarif con {total} resultados")
    return lineas


def main(argumentos: list[str]) -> int:
    if len(argumentos) != 4:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    carpeta, servicio_dir, servicio, publicar = argumentos
    for linea in preparar_carpeta(Path(carpeta), servicio_dir, servicio, Path(publicar)):
        print(linea)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
