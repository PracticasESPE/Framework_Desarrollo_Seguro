"""Proveedores de embeddings: convierten textos en vectores para la búsqueda por significado.

Igual que con los LLM, el resto del motor depende solo de `ProveedorEmbeddings`, así que el
modelo se puede cambiar por configuración. Por defecto se usa un modelo abierto multilingüe que
corre en el propio equipo (sin coste ni claves), como prevé el plan técnico (sección 6.3).
"""

import os
from pathlib import Path
from typing import Protocol, runtime_checkable

MODELO_POR_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class ErrorEmbeddings(Exception):
    """No se pudo cargar el modelo o calcular los embeddings."""


@runtime_checkable
class ProveedorEmbeddings(Protocol):
    modelo: str
    dimensiones: int

    def embeber(self, textos: list[str]) -> list[list[float]]:
        """Devuelve un vector por texto, en el mismo orden."""
        ...


class EmbeddingsLocales:
    """Modelo abierto ejecutado en local con fastembed (ONNX, sin GPU ni PyTorch).

    La primera vez descarga el modelo a `carpeta_cache`; después funciona sin conexión.
    """

    def __init__(self, modelo: str = MODELO_POR_DEFECTO, carpeta_cache: Path | None = None):
        # En Windows sin modo desarrollador la caché funciona sin enlaces simbólicos; sin aviso.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        try:
            from fastembed import TextEmbedding
        except ImportError as error:  # pragma: no cover - fastembed es dependencia del proyecto
            raise ErrorEmbeddings("Falta la librería fastembed") from error

        soportados = {m["model"]: m["dim"] for m in TextEmbedding.list_supported_models()}
        if modelo not in soportados:
            raise ErrorEmbeddings(f"fastembed no ofrece el modelo {modelo!r}")
        self.modelo = modelo
        self.dimensiones = soportados[modelo]
        try:
            self._modelo = TextEmbedding(
                model_name=modelo, cache_dir=str(carpeta_cache) if carpeta_cache else None
            )
        except Exception as error:
            raise ErrorEmbeddings(f"No se pudo cargar el modelo {modelo}: {error}") from error

    def embeber(self, textos: list[str]) -> list[list[float]]:
        if not textos:
            return []
        try:
            return [vector.tolist() for vector in self._modelo.embed(textos)]
        except Exception as error:
            raise ErrorEmbeddings(f"Falló el cálculo de embeddings: {error}") from error
