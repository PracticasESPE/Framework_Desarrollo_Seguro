"""Caché en disco de las respuestas del LLM.

Las demostraciones, las pruebas manuales y la evaluación procesan una y otra vez los mismos
documentos. Sin caché, cada repetición gasta la cuota del proveedor (en el plan gratuito de Groq,
unos 20 000 tokens por documento de 200 000 al día) y tarda minutos. Con caché, la misma pregunta
al mismo modelo se responde desde el disco en milisegundos.

La clave es un SHA-256 de todo lo que determina la respuesta: proveedor, modelo, nivel, ajustes que
cambian la salida (como el esfuerzo de razonamiento), instrucciones del sistema, esquema y prompt.
Si cambia cualquiera de ellos, la caché no se usa. Solo se guardan respuestas que ya validaron
contra el esquema.

Los prompts de la clasificación encierran cada unidad en marcas con un código aleatorio por
documento (`<unidad-1a2b3c4d …>`), para que el texto del cliente no pueda cerrarlas. Ese código
cambia en cada ejecución, así que para la clave se sustituye por uno fijo; la respuesta del LLM no
lo contiene.

Seguridad:
- La carpeta está en `.cache/`, que Git ignora. Guarda la salida del LLM (actores, acciones y
  entidades extraídos del documento), pero no el prompt ni el texto del documento.
- Una entrada que no valida contra el esquema (archivo editado o dañado) se ignora y se reemplaza.
- La escritura es atómica (archivo temporal y renombrado): dos ejecuciones a la vez no dejan
  entradas a medias.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from orchestrator.llm.base import Nivel, ProveedorLLM, T, UsoLLM

_MARCA_ALEATORIA = re.compile(r"(</?[a-z_]+-)[0-9a-f]{8}\b")


def normalizar_prompt(prompt: str) -> str:
    """Quita del prompt los códigos aleatorios de las marcas, que no cambian la respuesta."""
    return _MARCA_ALEATORIA.sub(r"\g<1>00000000", prompt)


class ProveedorConCache:
    """Envuelve un proveedor: responde desde el disco si ya hizo esa misma pregunta."""

    def __init__(self, proveedor: ProveedorLLM, carpeta: Path) -> None:
        self.proveedor = proveedor
        self.carpeta = carpeta
        self.nombre: str = getattr(proveedor, "nombre", type(proveedor).__name__)
        self.uso = UsoLLM()

    def generar_estructurado(
        self,
        prompt: str,
        esquema: type[T],
        nivel: Nivel = "rapido",
        sistema: str | None = None,
    ) -> T:
        archivo = self._archivo(prompt, esquema, nivel, sistema)
        guardada = self._leer(archivo, esquema)
        if guardada is not None:
            self.uso.desde_cache += 1
            return guardada

        respuesta = self.proveedor.generar_estructurado(prompt, esquema, nivel, sistema)
        self._escribir(archivo, respuesta.model_dump_json())
        return respuesta

    def uso_total(self) -> UsoLLM:
        """Uso del proveedor envuelto más las respuestas servidas desde la caché."""
        total = UsoLLM()
        total.sumar(getattr(self.proveedor, "uso", UsoLLM()))
        total.sumar(self.uso)
        return total

    def _archivo(self, prompt: str, esquema: type[Any], nivel: Nivel, sistema: str | None) -> Path:
        modelos = getattr(self.proveedor, "modelos", {})
        clave = json.dumps(
            {
                "proveedor": self.nombre,
                "modelo": modelos.get(nivel),
                "nivel": nivel,
                "ajustes": _ajustes(self.proveedor),
                "sistema": sistema,
                "esquema": esquema.model_json_schema(),
                "prompt": normalizar_prompt(prompt),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        resumen = hashlib.sha256(clave.encode("utf-8")).hexdigest()
        return self.carpeta / resumen[:2] / f"{resumen}.json"

    @staticmethod
    def _leer(archivo: Path, esquema: type[T]) -> T | None:
        try:
            return esquema.model_validate_json(archivo.read_bytes())
        except (OSError, ValidationError, ValueError):
            return None

    @staticmethod
    def _escribir(archivo: Path, contenido: str) -> None:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporal = tempfile.mkstemp(dir=archivo.parent, suffix=".tmp")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as salida:
                salida.write(contenido)
            os.replace(temporal, archivo)
        except OSError:
            # Sin caché la ejecución sigue funcionando; solo se pierde el ahorro.
            Path(temporal).unlink(missing_ok=True)


def _ajustes(proveedor: object) -> dict[str, object]:
    """Atributos del adaptador que cambian la respuesta y deben formar parte de la clave."""
    return {
        nombre: getattr(proveedor, nombre)
        for nombre in ("temperatura", "esfuerzo_razonamiento", "usar_fallbacks")
        if hasattr(proveedor, nombre)
    }


def estadisticas(carpeta: Path) -> tuple[int, int]:
    """Número de respuestas guardadas y bytes que ocupan."""
    if not carpeta.is_dir():
        return 0, 0
    archivos = [a for a in carpeta.glob("*/*.json") if a.is_file()]
    return len(archivos), sum(a.stat().st_size for a in archivos)


def vaciar(carpeta: Path) -> int:
    """Borra las respuestas guardadas y devuelve cuántas había. Solo toca archivos de la caché."""
    borradas = 0
    if not carpeta.is_dir():
        return 0
    for archivo in carpeta.glob("*/*.json"):
        if re.fullmatch(r"[0-9a-f]{64}\.json", archivo.name):
            archivo.unlink()
            borradas += 1
    for subcarpeta in carpeta.iterdir():
        if subcarpeta.is_dir() and not any(subcarpeta.iterdir()):
            subcarpeta.rmdir()
    return borradas
