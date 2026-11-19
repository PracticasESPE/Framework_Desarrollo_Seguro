"""Verificación de las dependencias npm de un servicio contra la lista permitida (#66).

Plan técnico 6.5: los paquetes npm alucinados («slopsquatting») son un riesgo especialmente alto,
así que toda dependencia se valida contra knowledge_base/dependencias_permitidas.yaml antes de
instalarla, se instala con --ignore-scripts y pasa por SCA (Trivy).

Qué se comprueba:

- package.json: cada paquete de dependencies, devDependencies y overrides está en su sección de la
  lista, con el mismo rango o con una versión exacta dentro de él; nada de URLs de git o http,
  archivos locales, alias npm:, «latest» ni «*»; no hay optionalDependencies, peerDependencies ni
  bundleDependencies; y ningún script se ejecuta al instalar (preinstall, install, postinstall,
  prepare).
- package-lock.json, si existe: todo se descarga del registro de la lista y con su huella sha512,
  nada se enlaza desde el disco, y las versiones resueltas de las dependencias directas están en
  el rango permitido. Las indirectas las revisa Trivy.

El módulo solo usa la biblioteca estándar, Pydantic y PyYAML, para que el CI pueda ejecutarlo como
script sin instalar el motor completo:

    python orchestrator/generation/dependencias.py salida/servicios/pedidos
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RUTA_LISTA = Path(__file__).resolve().parents[2] / "knowledge_base" / "dependencias_permitidas.yaml"

_NOMBRE_NPM = re.compile(r"^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_COMPARADOR = re.compile(r"^(\^|~|>=|<=|>|<|=)?(.+)$")
# Formas de declarar una versión que no pasan por el registro o no fijan nada.
_FORMAS_PROHIBIDAS = re.compile(
    r"^(git|git\+|github:|gitlab:|bitbucket:|https?:|file:|link:|npm:|workspace:|portal:)|^[*x]?$|^latest$|/",
    re.IGNORECASE,
)
SCRIPTS_DE_INSTALACION = {
    "preinstall",
    "install",
    "postinstall",
    "prepare",
    "preprepare",
    "postprepare",
    "prepublish",
}
SECCIONES = {
    "dependencies": "dependencias",
    "devDependencies": "desarrollo",
    "overrides": "overrides",
}
SECCIONES_PROHIBIDAS = ("optionalDependencies", "peerDependencies", "bundleDependencies")


class ErrorDependencias(Exception):
    """La lista permitida o el package.json no se pudieron leer."""


# --- Versiones (subconjunto de semver de npm) --------------------------------------------------


def _clave(version: str) -> tuple[int, int, int, int, str] | None:
    """Clave de orden de una versión exacta; una preliminar va antes que la final."""
    coincidencia = _VERSION.match(version.strip())
    if not coincidencia:
        return None
    mayor, menor, parche, previa = coincidencia.groups()
    return int(mayor), int(menor), int(parche), 0 if previa else 1, previa or ""


def es_version_exacta(texto: str) -> bool:
    return _clave(texto) is not None


def _limites(comparador: str) -> list[tuple[str, tuple]] | None:
    """Condiciones (operador, clave) de un comparador de npm, o None si no se entiende."""
    coincidencia = _COMPARADOR.match(comparador.strip())
    if not coincidencia:
        return None
    operador, texto = coincidencia.groups()
    clave = _clave(texto)
    if clave is None:
        return None
    mayor, menor, parche = clave[:3]
    if operador == "^":
        if mayor > 0:
            tope = (mayor + 1, 0, 0, 0, "")
        elif menor > 0:
            tope = (0, menor + 1, 0, 0, "")
        else:
            tope = (0, 0, parche + 1, 0, "")
        return [(">=", clave), ("<", tope)]
    if operador == "~":
        return [(">=", clave), ("<", (mayor, menor + 1, 0, 0, ""))]
    return [(operador or "=", clave)]


def rango_valido(rango: str) -> bool:
    alternativas = [a.split() for a in rango.split("||")]
    return all(a and all(_limites(c) is not None for c in a) for a in alternativas)


def satisface(version: str, rango: str) -> bool:
    """Si una versión exacta cumple un rango de npm (^, ~, exactas, >=, <=, >, <, ||)."""
    clave = _clave(version)
    if clave is None or not rango_valido(rango):
        return False
    operaciones = {
        "=": lambda a, b: a == b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
    }
    for alternativa in rango.split("||"):
        condiciones = [c for comparador in alternativa.split() for c in _limites(comparador) or []]
        if not all(operaciones[op](clave, limite) for op, limite in condiciones):
            continue
        # Como npm: una versión preliminar solo vale si el rango la nombra en esa misma versión.
        if clave[3] == 0 and not any(
            lim[:3] == clave[:3] and lim[3] == 0 for _, lim in condiciones
        ):
            continue
        return True
    return False


# --- Lista permitida ---------------------------------------------------------------------------


class Paquete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paquete: str
    version: str
    motivo: str = Field(min_length=5)

    @field_validator("paquete")
    @classmethod
    def _nombre(cls, valor: str) -> str:
        if not _NOMBRE_NPM.match(valor):
            raise ValueError(f"«{valor}» no es un nombre de paquete npm válido")
        return valor

    @field_validator("version")
    @classmethod
    def _rango(cls, valor: str) -> str:
        if _FORMAS_PROHIBIDAS.search(valor) or not rango_valido(valor):
            raise ValueError(f"«{valor}» no es un rango de versiones de npm admitido")
        return valor


class ListaPermitida(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    ecosistema: Literal["npm"]
    registro: str = Field(pattern=r"^https://")
    dependencias: list[Paquete]
    desarrollo: list[Paquete]
    overrides: list[Paquete] = Field(default_factory=list)

    @model_validator(mode="after")
    def _sin_repetidos(self) -> ListaPermitida:
        for seccion in ("dependencias", "desarrollo", "overrides"):
            nombres = [p.paquete for p in getattr(self, seccion)]
            if repetidos := sorted({n for n in nombres if nombres.count(n) > 1}):
                raise ValueError(f"paquetes repetidos en {seccion}: {repetidos}")
        return self

    def rangos(self, seccion: str) -> dict[str, str]:
        return {p.paquete: p.version for p in getattr(self, seccion)}


def cargar_lista(ruta: Path = RUTA_LISTA) -> ListaPermitida:
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        return ListaPermitida.model_validate(datos)
    except (OSError, yaml.YAMLError, ValueError) as error:
        raise ErrorDependencias(
            f"No se pudo leer la lista permitida {ruta.name}: {error}"
        ) from error


# --- Verificación ------------------------------------------------------------------------------


class Problema(BaseModel):
    archivo: str
    seccion: str
    paquete: str | None = None
    motivo: str

    def __str__(self) -> str:
        quien = f" {self.paquete}" if self.paquete else ""
        return f"{self.archivo} [{self.seccion}]{quien}: {self.motivo}"


def verificar_package_json(datos: dict, lista: ListaPermitida) -> list[Problema]:
    problemas: list[Problema] = []

    def problema(seccion: str, paquete: str | None, motivo: str) -> None:
        problemas.append(
            Problema(archivo="package.json", seccion=seccion, paquete=paquete, motivo=motivo)
        )

    for seccion_npm, seccion_lista in SECCIONES.items():
        declarados = datos.get(seccion_npm) or {}
        if not isinstance(declarados, dict):
            problema(seccion_npm, None, "debe ser un objeto «paquete: versión»")
            continue
        permitidos = lista.rangos(seccion_lista)
        for nombre, version in declarados.items():
            if not isinstance(version, str):
                problema(seccion_npm, nombre, "la versión debe ser un texto (sin objetos anidados)")
            elif nombre not in permitidos:
                otras = [
                    s
                    for s in SECCIONES.values()
                    if s != seccion_lista and nombre in lista.rangos(s)
                ]
                donde = f"; solo está permitido en {otras[0]}" if otras else ""
                problema(
                    seccion_npm, nombre, f"no está en la lista de dependencias permitidas{donde}"
                )
            elif _FORMAS_PROHIBIDAS.search(version.strip()):
                problema(
                    seccion_npm,
                    nombre,
                    f"«{version}» no se descarga del registro o no fija la versión",
                )
            elif version != permitidos[nombre] and not (
                es_version_exacta(version) and satisface(version, permitidos[nombre])
            ):
                problema(
                    seccion_npm,
                    nombre,
                    f"la versión «{version}» no es la permitida («{permitidos[nombre]}»)",
                )
    for seccion in SECCIONES_PROHIBIDAS:
        if datos.get(seccion):
            problema(
                seccion,
                None,
                "no se permite: cada dependencia se declara en su sección de la lista",
            )
    scripts = datos.get("scripts") or {}
    for nombre in sorted(set(scripts) & SCRIPTS_DE_INSTALACION):
        problema(
            "scripts", nombre, "se ejecutaría al instalar: no se permiten scripts de instalación"
        )
    return problemas


def verificar_lock(datos: dict, lista: ListaPermitida) -> list[Problema]:
    """package-lock.json (versión 2 o 3): origen, integridad y versiones de las directas."""
    problemas: list[Problema] = []

    def problema(paquete: str | None, motivo: str) -> None:
        problemas.append(
            Problema(
                archivo="package-lock.json", seccion="packages", paquete=paquete, motivo=motivo
            )
        )

    paquetes = datos.get("packages")
    if datos.get("lockfileVersion", 0) < 2 or not isinstance(paquetes, dict):
        return [
            Problema(
                archivo="package-lock.json",
                seccion="lockfileVersion",
                motivo="se necesita lockfileVersion 2 o 3",
            )
        ]
    raiz = paquetes.get("", {})
    directas = {
        **{n: "dependencias" for n in raiz.get("dependencies", {})},
        **{n: "desarrollo" for n in raiz.get("devDependencies", {})},
    }
    for ruta, info in paquetes.items():
        if not ruta:
            continue
        nombre = ruta.rsplit("node_modules/", 1)[-1]
        if info.get("link"):
            problema(nombre, "se enlaza desde el disco en lugar de descargarse del registro")
            continue
        resuelto = info.get("resolved")
        if resuelto and not resuelto.startswith(lista.registro):
            origen = resuelto.split("/")[2] if "//" in resuelto else resuelto
            problema(nombre, f"se descarga de fuera del registro permitido ({origen})")
        if resuelto and not str(info.get("integrity", "")).startswith("sha512-"):
            problema(nombre, "no tiene huella de integridad sha512")
        if ruta == f"node_modules/{nombre}" and nombre in directas:
            rango = lista.rangos(directas[nombre]).get(nombre)
            version = info.get("version", "")
            if rango and not satisface(version, rango):
                problema(
                    nombre,
                    f"la versión instalada {version} no está en el rango permitido «{rango}»",
                )
    return problemas


def verificar_servicio(carpeta: Path, lista: ListaPermitida | None = None) -> list[Problema]:
    """Verifica package.json y, si existe, package-lock.json de la carpeta de un servicio."""
    lista = lista or cargar_lista()
    try:
        package = json.loads((carpeta / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ErrorDependencias(f"No se pudo leer {carpeta.name}/package.json: {error}") from error
    problemas = verificar_package_json(package, lista)
    lock = carpeta / "package-lock.json"
    if lock.is_file():
        try:
            problemas += verificar_lock(json.loads(lock.read_text(encoding="utf-8")), lista)
        except ValueError as error:
            raise ErrorDependencias(f"No se pudo leer package-lock.json: {error}") from error
    return problemas


def main(argumentos: list[str]) -> int:
    if len(argumentos) != 1:
        print(
            "Uso: python orchestrator/generation/dependencias.py <carpeta del servicio>",
            file=sys.stderr,
        )
        return 2
    carpeta = Path(argumentos[0])
    try:
        problemas = verificar_servicio(carpeta)
    except ErrorDependencias as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    if problemas:
        print(f"{carpeta.as_posix()}: {len(problemas)} problemas con la lista permitida")
        for p in problemas:
            print(f"  - {p}")
        return 1
    archivos = (
        "package.json y package-lock.json cumplen"
        if (carpeta / "package-lock.json").is_file()
        else "package.json cumple"
    )
    print(f"{carpeta.as_posix()}: {archivos} la lista de dependencias permitidas")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
