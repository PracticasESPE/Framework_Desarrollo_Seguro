"""Esquema del modelo de requisitos de la fase 1 (plan técnico, 7.1 y listing 7.1).

Hay dos modelos con responsabilidades distintas:

- `ClasificacionRequisito` es lo único que se le pide al LLM para cada unidad del documento: si es
  un requisito y, si lo es, su tipo, actor, acción, entidades, servicio sugerido y etiquetas de
  seguridad. El LLM no devuelve ni el texto ni el id.
- `Requisito` lo arma el motor: une la unidad (texto literal y ubicación, del documento) con la
  clasificación (del LLM) y le asigna el id. Así el LLM no puede reescribir un requisito ni
  inventar uno que no está en el documento, y cada requisito se traza hasta su frase original.

Pydantic rechaza las salidas incompletas o fuera de lista (principio P1: el LLM propone, las reglas
validan): una etiqueta inventada, un requisito sin actor o un id que no corresponde a su tipo.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from orchestrator.ingest.normalizacion import UnidadTexto

VERSION_ESQUEMA = "1.0"

TipoRequisito = Literal["funcional", "no_funcional"]
# Las mismas de evaluation/datasets/vocabulario.yaml (lo comprueba tests/test_requisito.py).
Etiqueta = Literal[
    "autenticacion",
    "autorizacion",
    "control_acceso_recursos",
    "validacion_entrada",
    "hash_password",
    "cifrado_transito",
    "punto_unico_acceso",
    "limite_peticiones",
    "auditoria",
]
PREFIJO_POR_TIPO: dict[str, str] = {"funcional": "RF", "no_funcional": "RNF"}

Corto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Accion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Servicio = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]{1,39}$")
]
_ESTRICTO = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _sin_repetidos(valores: list) -> list:
    """Quita repetidos conservando el orden; comparar sin mayúsculas evita «Pedido» y «pedido»."""
    vistos: set[str] = set()
    resultado = []
    for valor in valores:
        clave = valor.casefold() if isinstance(valor, str) else valor
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(valor)
    return resultado


class _Semantica(BaseModel):
    """Campos que vienen del análisis semántico, comunes a la clasificación y al requisito."""

    model_config = _ESTRICTO

    actor: Corto = Field(description="Quién realiza o necesita la acción, p. ej. «cliente»")
    accion: Accion = Field(description="Qué hace o qué debe cumplirse, en pocas palabras")
    entidades: list[Corto] = Field(
        max_length=15, description="Entidades de negocio en singular, p. ej. «Pedido»"
    )
    servicio_sugerido: Servicio = Field(
        description="Microservicio en minúsculas, p. ej. «pedidos»; «transversal» si es de todos"
    )
    etiquetas: list[Etiqueta] = Field(
        max_length=9, description="Etiquetas de seguridad de la lista; vacía si no aplica"
    )

    @model_validator(mode="after")
    def _limpiar_listas(self) -> Self:
        self.entidades = _sin_repetidos(self.entidades)
        self.etiquetas = _sin_repetidos(self.etiquetas)
        return self


class ClasificacionRequisito(BaseModel):
    """Respuesta del LLM para una unidad del documento."""

    model_config = _ESTRICTO

    es_requisito: bool = Field(
        description="Falso para contexto, perfiles o frases fuera del alcance del sistema"
    )
    tipo: TipoRequisito | None = None
    actor: Corto | None = None
    accion: Accion | None = None
    entidades: list[Corto] = Field(default_factory=list, max_length=15)
    servicio_sugerido: Servicio | None = None
    etiquetas: list[Etiqueta] = Field(default_factory=list, max_length=9)

    @model_validator(mode="after")
    def _completa_si_es_requisito(self) -> Self:
        if not self.es_requisito:
            return self
        faltan = [
            campo
            for campo in ("tipo", "actor", "accion", "servicio_sugerido")
            if not getattr(self, campo)
        ]
        if faltan:
            raise ValueError(f"Un requisito necesita {', '.join(faltan)}")
        return self


class Requisito(_Semantica):
    """Un requisito del modelo estructurado, trazable hasta su frase en el documento."""

    id: Annotated[str, StringConstraints(pattern=r"^(RF|RNF)-\d{2,3}$")]
    tipo: TipoRequisito
    texto: Annotated[str, StringConstraints(min_length=10, max_length=2000)] = Field(
        description="Frase literal del documento, tal como quedó tras la normalización"
    )
    ubicacion: Annotated[str, StringConstraints(min_length=1, max_length=60)]

    @model_validator(mode="after")
    def _id_segun_tipo(self) -> Self:
        prefijo = self.id.split("-")[0]
        if prefijo != PREFIJO_POR_TIPO[self.tipo]:
            raise ValueError(f"El id {self.id} no corresponde a un requisito {self.tipo}")
        return self


class DocumentoOrigen(BaseModel):
    model_config = _ESTRICTO

    nombre: str
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    herramienta: str


class ModeloRequisitos(BaseModel):
    """Contenido de modelo_requisitos.json, la salida de la fase 1."""

    model_config = _ESTRICTO

    version_esquema: Literal["1.0"] = VERSION_ESQUEMA
    documento: DocumentoOrigen
    requisitos: list[Requisito] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unicos(self) -> Self:
        cuentas = Counter(r.id for r in self.requisitos)
        repetidos = sorted(id_ for id_, veces in cuentas.items() if veces > 1)
        if repetidos:
            raise ValueError(f"Ids repetidos: {', '.join(repetidos)}")
        return self


def construir_requisitos(
    pares: list[tuple[UnidadTexto, ClasificacionRequisito]],
) -> list[Requisito]:
    """Une cada unidad con su clasificación y numera los requisitos por tipo, en orden de aparición.

    Las unidades que el LLM marca como no requisito se descartan. Las tablas solo dan contexto a
    los requisitos que las citan y no se convierten en requisitos por sí mismas.
    """
    contadores = {"funcional": 0, "no_funcional": 0}
    requisitos = []
    for unidad, clasificacion in pares:
        if not clasificacion.es_requisito or unidad.bloque == "tabla":
            continue
        assert clasificacion.tipo is not None  # garantizado por la validación
        contadores[clasificacion.tipo] += 1
        prefijo = PREFIJO_POR_TIPO[clasificacion.tipo]
        requisitos.append(
            Requisito(
                id=f"{prefijo}-{contadores[clasificacion.tipo]:02d}",
                tipo=clasificacion.tipo,
                texto=unidad.texto,
                ubicacion=unidad.ubicacion,
                actor=clasificacion.actor,
                accion=clasificacion.accion,
                entidades=clasificacion.entidades,
                servicio_sugerido=clasificacion.servicio_sugerido,
                etiquetas=clasificacion.etiquetas,
            )
        )
    return requisitos
