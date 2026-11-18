"""Esquema de arquitectura.json: la propuesta arquitectónica de la fase 2.

Dos niveles, como en la fase 1:

- `PropuestaArquitectura` es lo que devuelve el LLM: servicios con su bounded context, los
  requisitos que cubre cada uno, su base de datos y sus dependencias, los requisitos transversales y
  las decisiones con su justificación.
- `Arquitectura` es lo que guarda el motor en arquitectura.json: la propuesta validada más el
  documento de origen y las etiquetas de seguridad de cada servicio, que el motor calcula a partir
  de sus requisitos (el LLM no las elige).

Quién lo consume: OPA revisa las reglas arquitectónicas (base de datos propia, dependencias sin
ciclos) e infiere patrones; las decisiones se convierten en ADR y nodos Decision, y los servicios y
dependencias en el diagrama C4.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from orchestrator.ingest.requisito import DocumentoOrigen, Etiqueta

VERSION_ESQUEMA = "1.0"

_ESTRICTO = ConfigDict(extra="forbid", str_strip_whitespace=True)

NombreServicio = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
IdRequisito = Annotated[str, StringConstraints(pattern=r"^(RF|RNF)-\d{2,3}$")]
IdDecision = Annotated[str, StringConstraints(pattern=r"^D-\d{2}$")]
Nombre = Annotated[str, StringConstraints(min_length=2, max_length=60)]
Frase = Annotated[str, StringConstraints(min_length=10, max_length=600)]


class Dependencia(BaseModel):
    """Un servicio necesita a otro: por una llamada directa o reaccionando a sus eventos."""

    model_config = _ESTRICTO

    servicio: NombreServicio = Field(description="Servicio del que se depende")
    tipo: Literal["sincrona", "asincrona"] = Field(
        description="sincrona: llamada HTTP directa; asincrona: eventos por RabbitMQ"
    )
    motivo: Frase = Field(description="Para qué lo necesita")


class ServicioPropuesto(BaseModel):
    """Un microservicio de la propuesta, tal como lo describe el LLM."""

    model_config = _ESTRICTO

    nombre: NombreServicio = Field(description="En minúsculas, p. ej. «pedidos»")
    contexto: Nombre = Field(description="Bounded context al que pertenece, p. ej. «Ventas»")
    responsabilidad: Frase = Field(description="Qué hace y qué datos son suyos")
    entidades: list[Nombre] = Field(max_length=20, description="Entidades de las que es dueño")
    requisitos: list[IdRequisito] = Field(
        min_length=1, max_length=100, description="Ids de los requisitos que cubre"
    )
    base_datos: NombreServicio = Field(description="Base de datos que usa, p. ej. «pedidos_db»")
    depende_de: list[Dependencia] = Field(default_factory=list, max_length=15)


class DecisionPropuesta(BaseModel):
    """Una decisión arquitectónica con su justificación: la base de un ADR."""

    model_config = _ESTRICTO

    id: IdDecision
    titulo: Nombre
    decision: Frase = Field(description="Qué se decidió")
    justificacion: Frase = Field(description="Por qué, con referencia a los requisitos")
    requisitos: list[IdRequisito] = Field(min_length=1, max_length=100)


class PropuestaArquitectura(BaseModel):
    """Respuesta del LLM."""

    model_config = _ESTRICTO

    servicios: list[ServicioPropuesto] = Field(min_length=1, max_length=15)
    transversales: list[IdRequisito] = Field(
        default_factory=list,
        max_length=100,
        description="Requisitos que aplican a todo el sistema y no a un servicio",
    )
    decisiones: list[DecisionPropuesta] = Field(min_length=1, max_length=20)


class Servicio(ServicioPropuesto):
    etiquetas: list[Etiqueta] = Field(
        description="Etiquetas de seguridad de sus requisitos (las calcula el motor)"
    )


class Arquitectura(BaseModel):
    """arquitectura.json: la propuesta validada y trazable hasta los requisitos."""

    model_config = _ESTRICTO

    version_esquema: Literal["1.0"] = VERSION_ESQUEMA
    documento: DocumentoOrigen
    servicios: list[Servicio] = Field(min_length=1, max_length=15)
    transversales: list[IdRequisito]
    etiquetas_transversales: list[Etiqueta]
    decisiones: list[DecisionPropuesta] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _nombres_unicos(self) -> Arquitectura:
        nombres = [s.nombre for s in self.servicios]
        if len(set(nombres)) != len(nombres):
            raise ValueError("Hay servicios con el mismo nombre")
        ids = [d.id for d in self.decisiones]
        if len(set(ids)) != len(ids):
            raise ValueError("Hay decisiones con el mismo id")
        return self
