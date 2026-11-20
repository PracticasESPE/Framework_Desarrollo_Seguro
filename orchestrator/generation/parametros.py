"""Parámetros de la plantilla por servicio, a partir de arquitectura.json (fase 3, #69).

La arquitectura aprobada (fase 2) ya fija de cada servicio lo que el LLM no debe decidir al
generarlo: su nombre, su descripción, su base de datos, las entidades de las que es dueño y, a
partir de ellos, su puerto y sus rutas. Este módulo los calcula para los N servicios de una vez y
valida el conjunto antes de generar nada:

- cada entidad se convierte al identificador de la plantilla («LineaPedido» → «linea_pedido») y
  debe ser válido, no estar reservado y no repetirse dentro del servicio;
- cada servicio tiene un puerto y un prefijo de rutas propios (`/api/<servicio>`), sin choques;
- un servicio sin entidades no se puede generar (la plantilla necesita al menos una), salvo que
  las proponga el LLM: queda como advertencia;
- una entidad que aparece en varios servicios es una advertencia, no un error: cada servicio
  tiene su propia base (Database per Service), así que son tablas independientes, normalmente una
  proyección de lectura. Sin una dependencia declarada entre esos servicios, la copia no tiene de
  dónde actualizarse, y la advertencia lo dice.

El LLM solo aporta los campos de cada entidad (prompt `especificacion`), y el esquema de su
respuesta exige exactamente las entidades de estos parámetros. `especificacion()` junta las dos
partes en la entrada de la plantilla.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict

from orchestrator.generation.estructura import archivo_de, clase_de
from orchestrator.llm.prompts.especificacion import (
    ENTIDADES_RESERVADAS,
    EntidadesPropuestas,
    EspecificacionServicio,
    descripcion_de,
    esquema_de_entidades,
    identificador_de_entidad,
)

# 3000 es el puerto del servicio de referencia (services/usuarios); los generados van a continuación
# en el orden de la arquitectura, así que el puerto de cada servicio es estable entre ejecuciones.
PUERTO_BASE = 3001

_IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9_]{1,39}$")


class ErrorParametros(Exception):
    """La arquitectura no se puede convertir en parámetros válidos de la plantilla."""

    def __init__(self, problemas: list[str]) -> None:
        self.problemas = problemas
        super().__init__("; ".join(problemas))


class EntidadDelServicio(BaseModel):
    """Una entidad tal como la nombró la arquitectura y como la nombra la plantilla."""

    model_config = ConfigDict(frozen=True)

    original: str
    nombre: str
    archivo: str
    clase: str
    ruta: str


class ParametrosServicio(BaseModel):
    """Lo que la arquitectura fija de un servicio para la plantilla."""

    model_config = ConfigDict(frozen=True)

    servicio: str
    descripcion: str
    base_datos: str
    puerto: int
    prefijo: str
    audiencia: str
    entidades: tuple[EntidadDelServicio, ...]
    requisitos: tuple[str, ...]

    @property
    def nombres_de_entidades(self) -> list[str]:
        return [e.nombre for e in self.entidades]

    @property
    def rutas(self) -> list[str]:
        return [e.ruta for e in self.entidades]

    def esquema_de_la_respuesta(self) -> type[EntidadesPropuestas]:
        """El esquema que debe cumplir la respuesta del LLM para este servicio."""
        return esquema_de_entidades(self.nombres_de_entidades)


class ParametrosArquitectura(BaseModel):
    """Los parámetros de todos los servicios y las advertencias que no impiden generarlos."""

    model_config = ConfigDict(frozen=True)

    servicios: tuple[ParametrosServicio, ...]
    advertencias: tuple[str, ...]

    def de(self, servicio: str) -> ParametrosServicio:
        for parametros in self.servicios:
            if parametros.servicio == servicio:
                return parametros
        nombres = ", ".join(p.servicio for p in self.servicios)
        raise KeyError(f"«{servicio}» no está en la arquitectura; usa: {nombres}")


def _entidades(servicio: Any, problemas: list[str]) -> list[EntidadDelServicio]:
    entidades: list[EntidadDelServicio] = []
    vistos: dict[str, str] = {}
    prefijo = f"/api/{archivo_de(servicio.nombre)}"
    for original in servicio.entidades:
        nombre = identificador_de_entidad(original)
        donde = f"{servicio.nombre}: la entidad «{original}»"
        if not _IDENTIFICADOR.fullmatch(nombre):
            problemas.append(
                f"{donde} no da un identificador válido («{nombre}»): debe empezar por una letra "
                "y tener de 2 a 40 caracteres"
            )
        elif nombre in ENTIDADES_RESERVADAS:
            problemas.append(f"{donde} («{nombre}») tiene un nombre reservado por la plantilla")
        elif nombre in vistos:
            problemas.append(f"{donde} y «{vistos[nombre]}» dan el mismo identificador «{nombre}»")
        else:
            vistos[nombre] = original
            entidades.append(
                EntidadDelServicio(
                    original=original,
                    nombre=nombre,
                    archivo=archivo_de(nombre),
                    clase=clase_de(nombre),
                    ruta=f"{prefijo}/{archivo_de(nombre)}",
                )
            )
    return entidades


def _advertencias_de_entidades_compartidas(
    arquitectura: Any, servicios: list[ParametrosServicio]
) -> list[str]:
    duenos: dict[str, list[str]] = {}
    for parametros in servicios:
        for entidad in parametros.entidades:
            duenos.setdefault(entidad.nombre, []).append(parametros.servicio)
    dependencias = {s.nombre: {d.servicio for d in s.depende_de} for s in arquitectura.servicios}
    advertencias = []
    for entidad, nombres in sorted(duenos.items()):
        if len(nombres) < 2:
            continue
        conectados = all(
            any(
                b in dependencias.get(a, set()) or a in dependencias.get(b, set())
                for b in nombres
                if b != a
            )
            for a in nombres
        )
        mensaje = (
            f"La entidad «{entidad}» está en {', '.join(nombres)}: cada servicio tendrá su propia "
            "tabla en su base (Database per Service)"
        )
        if not conectados:
            mensaje += ", y no hay una dependencia declarada entre ellos para mantener la copia"
        advertencias.append(mensaje)
    return advertencias


def parametros_de_arquitectura(arquitectura: Any) -> ParametrosArquitectura:
    """Los parámetros de la plantilla de cada servicio de `arquitectura` (un Arquitectura).

    Valida todos los servicios y reúne todos los problemas en un ErrorParametros.
    """
    problemas: list[str] = []
    advertencias: list[str] = []
    servicios: list[ParametrosServicio] = []
    for indice, servicio in enumerate(arquitectura.servicios):
        entidades = _entidades(servicio, problemas)
        if not servicio.entidades:
            advertencias.append(
                f"{servicio.nombre}: la arquitectura no le asigna entidades; las propondrá el LLM "
                "y no se podrán contrastar con ella"
            )
        servicios.append(
            ParametrosServicio(
                servicio=servicio.nombre,
                descripcion=descripcion_de(servicio),
                base_datos=servicio.base_datos,
                puerto=PUERTO_BASE + indice,
                prefijo=f"/api/{archivo_de(servicio.nombre)}",
                audiencia=f"{servicio.nombre}-api",
                entidades=tuple(entidades),
                requisitos=tuple(servicio.requisitos),
            )
        )

    # Los nombres de servicio ya son únicos (lo valida Arquitectura); sus bases, puertos y rutas
    # se comprueban igualmente, porque una colisión haría que dos servicios se pisaran.
    for campo, descripcion in (("base_datos", "la base de datos"), ("prefijo", "el prefijo")):
        usados: dict[str, str] = {}
        for parametros in servicios:
            valor = getattr(parametros, campo)
            if valor in usados:
                problemas.append(
                    f"{usados[valor]} y {parametros.servicio} comparten {descripcion} «{valor}»"
                )
            usados.setdefault(valor, parametros.servicio)

    if problemas:
        raise ErrorParametros(problemas)
    advertencias += _advertencias_de_entidades_compartidas(arquitectura, servicios)
    return ParametrosArquitectura(servicios=tuple(servicios), advertencias=tuple(advertencias))


def especificacion(
    parametros: ParametrosServicio, propuesta: EntidadesPropuestas
) -> EspecificacionServicio:
    """La entrada de la plantilla: los parámetros de la arquitectura y los campos del LLM.

    Vuelve a comprobar que las entidades son las de la arquitectura, aunque la respuesta no haya
    pasado por el esquema estricto (p. ej. una especificación editada a mano).
    """
    propuesta = parametros.esquema_de_la_respuesta().model_validate(propuesta.model_dump())
    return EspecificacionServicio(
        servicio=parametros.servicio,
        descripcion=parametros.descripcion,
        base_datos=parametros.base_datos,
        puerto=parametros.puerto,
        entidades=propuesta.entidades,
    )
