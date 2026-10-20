"""Lectura y validación de la base de conocimiento en YAML (knowledge_base/).

El conocimiento se escribe y versiona en Git y después se carga a Neo4j. Antes de cargarlo se
valida aquí, para que un archivo mal escrito se detecte en las pruebas y no a mitad del pipeline.
"""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

RAIZ_POR_DEFECTO = Path(__file__).resolve().parents[2] / "knowledge_base"


Componente = Literal["servicio", "gateway", "base_datos", "contenedor", "identidad", "pipeline"]


class _Elemento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    descripcion: str = Field(min_length=1)
    controles_asociados: list[str] = Field(min_length=1)
    cwe_mitigadas: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _formatos(self):
        for control in self.controles_asociados:
            if not _coincide(r"ASVS-V\d+\.\d+\.\d+", control):
                raise ValueError(f"control con formato inválido: {control!r}")
        for cwe in self.cwe_mitigadas:
            if not _coincide(r"CWE-\d+", cwe):
                raise ValueError(f"CWE con formato inválido: {cwe!r}")
        return self


class Condicion(BaseModel):
    """Condición que usa OPA para inferir un patrón: una etiqueta o un mínimo de servicios."""

    model_config = ConfigDict(extra="forbid")

    etiqueta: str | None = None
    numero_servicios_minimo: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _una_sola(self):
        if (self.etiqueta is None) == (self.numero_servicios_minimo is None):
            raise ValueError(
                "cada condición lleva 'etiqueta' o 'numero_servicios_minimo', no ambas"
            )
        return self


class Patron(_Elemento):
    patron: str
    aplica_cuando: list[Condicion] = Field(min_length=1)
    implementacion: str

    @model_validator(mode="after")
    def _id(self):
        if not _coincide(r"arq\.[a-z_]+\.\d{3}", self.id):
            raise ValueError(f"id de patrón inválido: {self.id!r} (formato arq.<tema>.<NNN>)")
        return self


class Directriz(_Elemento):
    directriz: str
    aplica_a: list[Componente] = Field(min_length=1)
    practicas: list[str] = Field(min_length=1)
    verificacion: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _id(self):
        if not _coincide(r"sbd\.[a-z_]+\.\d{3}", self.id):
            raise ValueError(f"id de directriz inválido: {self.id!r} (formato sbd.<tema>.<NNN>)")
        return self


class BaseConocimiento(BaseModel):
    patrones: list[Patron] = []
    directrices: list[Directriz] = []

    def resumen(self) -> dict[str, int]:
        return {
            "patrones": len(self.patrones),
            "directrices": len(self.directrices),
            "controles_distintos": len(self._todos("controles_asociados")),
            "cwe_distintas": len(self._todos("cwe_mitigadas")),
        }

    def _todos(self, campo: str) -> set[str]:
        return {v for e in (*self.patrones, *self.directrices) for v in getattr(e, campo)}


class ErrorBaseConocimiento(Exception):
    """La base de conocimiento tiene uno o más archivos inválidos."""

    def __init__(self, errores: list[str]):
        self.errores = errores
        super().__init__(f"{len(errores)} error(es) en la base de conocimiento")


# Carpeta -> (modelo, campo que debe coincidir con el nombre del archivo)
_TIPOS: dict[str, tuple[type[_Elemento], str]] = {
    "patrones": (Patron, "patron"),
    "directrices": (Directriz, "directriz"),
}


def cargar_base_conocimiento(raiz: str | Path = RAIZ_POR_DEFECTO) -> BaseConocimiento:
    """Lee y valida todos los YAML; reúne todos los errores antes de fallar."""
    raiz = Path(raiz)
    errores: list[str] = []
    leidos: dict[str, list] = {carpeta: [] for carpeta in _TIPOS}
    ids: dict[str, Path] = {}

    for carpeta, (modelo, campo_nombre) in _TIPOS.items():
        for ruta in sorted((raiz / carpeta).glob("*.yaml")):
            nombre = f"{carpeta}/{ruta.name}"
            try:
                datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
                elemento = modelo.model_validate(datos)
            except yaml.YAMLError as error:
                errores.append(f"{nombre}: YAML mal formado: {error}")
                continue
            except ValidationError as error:
                detalle = "; ".join(_describir(e) for e in error.errors())
                errores.append(f"{nombre}: {detalle}")
                continue

            if getattr(elemento, campo_nombre) != ruta.stem:
                errores.append(
                    f"{nombre}: el campo '{campo_nombre}' debe ser {ruta.stem!r}, "
                    f"no {getattr(elemento, campo_nombre)!r}"
                )
            if elemento.id in ids:
                errores.append(
                    f"{nombre}: id repetido {elemento.id!r} (ya está en {ids[elemento.id]})"
                )
            ids[elemento.id] = nombre
            leidos[carpeta].append(elemento)

    if errores:
        raise ErrorBaseConocimiento(errores)
    return BaseConocimiento(**leidos)


def _describir(error: dict) -> str:
    ubicacion = ".".join(str(parte) for parte in error.get("loc", ())) or "archivo"
    mensaje = str(error.get("msg", "")).removeprefix("Value error, ")
    return f"{ubicacion}: {mensaje}"


def _coincide(patron: str, valor: str) -> bool:
    return re.fullmatch(patron, valor) is not None
