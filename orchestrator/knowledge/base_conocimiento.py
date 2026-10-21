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


class _Catalogado(BaseModel):
    """Elemento de un catálogo externo (ASVS, CWE, OWASP API Top 10)."""

    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def _comprobar(valores: list[str], patron: str, que: str) -> None:
        for valor in valores:
            if not _coincide(patron, valor):
                raise ValueError(f"{que} con formato inválido: {valor!r}")


class Control(_Catalogado):
    """Requisito de OWASP ASVS 4.0.3."""

    id: str
    capitulo: str
    seccion: str
    descripcion: str = Field(min_length=1)
    niveles: list[Literal[1, 2, 3]] = Field(min_length=1)
    cwe: list[str] = []

    @model_validator(mode="after")
    def _formatos(self):
        self._comprobar([self.id], r"ASVS-V\d+\.\d+\.\d+", "control")
        self._comprobar(self.cwe, r"CWE-\d+", "CWE")
        return self


class Debilidad(_Catalogado):
    """Entrada del catálogo CWE de MITRE."""

    id: str
    nombre: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)

    @model_validator(mode="after")
    def _formatos(self):
        self._comprobar([self.id], r"CWE-\d+", "CWE")
        return self


class RiesgoApi(_Catalogado):
    """Riesgo del OWASP API Security Top 10 (edición 2023)."""

    id: str
    nombre: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    cwe: list[str] = []
    controles: list[str] = []

    @model_validator(mode="after")
    def _formatos(self):
        self._comprobar([self.id], r"API(10|[1-9]):2023", "riesgo")
        self._comprobar(self.cwe, r"CWE-\d+", "CWE")
        self._comprobar(self.controles, r"ASVS-V\d+\.\d+\.\d+", "control")
        return self


class BaseConocimiento(BaseModel):
    patrones: list[Patron] = []
    directrices: list[Directriz] = []
    controles: list[Control] = []
    debilidades: list[Debilidad] = []
    riesgos_api: list[RiesgoApi] = []

    def resumen(self) -> dict[str, int]:
        return {
            "patrones": len(self.patrones),
            "directrices": len(self.directrices),
            "controles_asvs": len(self.controles),
            "debilidades_cwe": len(self.debilidades),
            "riesgos_api_top10": len(self.riesgos_api),
            "controles_referenciados": len(self.controles_referenciados()),
            "cwe_referenciadas": len(self.cwe_referenciadas()),
        }

    def controles_referenciados(self) -> set[str]:
        return {
            *(c for e in (*self.patrones, *self.directrices) for c in e.controles_asociados),
            *(c for r in self.riesgos_api for c in r.controles),
        }

    def cwe_referenciadas(self) -> set[str]:
        return {
            *(c for e in (*self.patrones, *self.directrices) for c in e.cwe_mitigadas),
            *(c for e in (*self.controles, *self.riesgos_api) for c in e.cwe),
        }

    def referencias_rotas(self) -> list[str]:
        """Controles y CWE citados que no están en sus catálogos (solo si el catálogo existe)."""
        errores: list[str] = []
        if self.controles:
            conocidos = {c.id for c in self.controles}
            errores += [
                f"el control {c} no está en controles/asvs.yaml"
                for c in sorted(self.controles_referenciados() - conocidos)
            ]
        if self.debilidades:
            conocidas = {d.id for d in self.debilidades}
            errores += [
                f"la {c} no está en vulnerabilidades/cwe.yaml"
                for c in sorted(self.cwe_referenciadas() - conocidas, key=_numero)
            ]
        return errores


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

    catalogos: dict[str, list] = {}
    for campo, (archivo, clave, modelo) in _CATALOGOS.items():
        catalogos[campo] = _leer_catalogo(raiz / archivo, archivo, clave, modelo, ids, errores)

    if errores:
        raise ErrorBaseConocimiento(errores)
    base = BaseConocimiento(**leidos, **catalogos)
    rotas = base.referencias_rotas()
    if rotas:
        raise ErrorBaseConocimiento(rotas)
    return base


# Campo de BaseConocimiento -> (archivo, lista dentro del archivo, modelo)
_CATALOGOS: dict[str, tuple[str, str, type[_Catalogado]]] = {
    "controles": ("controles/asvs.yaml", "controles", Control),
    "debilidades": ("vulnerabilidades/cwe.yaml", "debilidades", Debilidad),
    "riesgos_api": ("vulnerabilidades/owasp_api_top10.yaml", "riesgos", RiesgoApi),
}


def _leer_catalogo(
    ruta: Path, nombre: str, clave: str, modelo: type, ids: dict, errores: list[str]
) -> list:
    if not ruta.is_file():
        return []
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        errores.append(f"{nombre}: YAML mal formado: {error}")
        return []
    entradas = datos.get(clave) if isinstance(datos, dict) else None
    if not isinstance(entradas, list) or not datos.get("fuente"):
        errores.append(f"{nombre}: debe tener 'fuente' y la lista '{clave}'")
        return []

    elementos = []
    for posicion, entrada in enumerate(entradas, start=1):
        try:
            elemento = modelo.model_validate(entrada)
        except ValidationError as error:
            detalle = "; ".join(_describir(e) for e in error.errors())
            errores.append(f"{nombre}, entrada {posicion}: {detalle}")
            continue
        if elemento.id in ids:
            errores.append(f"{nombre}: id repetido {elemento.id!r} (ya está en {ids[elemento.id]})")
        ids[elemento.id] = nombre
        elementos.append(elemento)
    return elementos


def _numero(identificador: str) -> int:
    return int(identificador.split("-")[1])


def _describir(error: dict) -> str:
    ubicacion = ".".join(str(parte) for parte in error.get("loc", ())) or "archivo"
    mensaje = str(error.get("msg", "")).removeprefix("Value error, ")
    return f"{ubicacion}: {mensaje}"


def _coincide(patron: str, valor: str) -> bool:
    return re.fullmatch(patron, valor) is not None
