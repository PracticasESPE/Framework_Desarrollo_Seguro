"""Prompt de la especificación de un microservicio para la plantilla Copier (fase 3).

El LLM de razonamiento propone las entidades y los campos de un servicio de arquitectura.json a
partir de sus requisitos y del contexto de seguridad (GraphRAG). El motor completa lo que no debe
decidir el LLM (nombre, descripción, base de datos y puerto, que ya fijó la arquitectura) y la
especificación resultante es la entrada de `servicio generar` (templates/microservicio_nestjs).

El esquema repite las reglas de templates/microservicio_nestjs/copier.yml: una especificación que
Pydantic acepta, Copier también. Así un error del LLM se detecta y se reintenta aquí, antes de
generar nada.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from orchestrator.knowledge.graphrag import ContextoGraphRAG
from orchestrator.llm.prompts.comun import AVISO_DATOS, Prompt, bloque, nuevo_codigo

VERSION = "1.0"

Identificador = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
ValorEnumeracion = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
Descripcion = Annotated[
    str, StringConstraints(max_length=300, pattern=r"^[^\x00-\x1f\x7f]*$", strip_whitespace=True)
]
TipoCampo = Literal[
    "texto",
    "correo",
    "entero",
    "decimal",
    "booleano",
    "fecha",
    "fecha_hora",
    "uuid",
    "enumeracion",
    "referencia",
]

# Los añade la plantilla en todas las entidades, o chocarían con sus clases.
CAMPOS_RESERVADOS = {"id", "creado_en", "actualizado_en"}
ENTIDADES_RESERVADAS = {
    "prisma",
    "prisma_client",
    "paginacion",
    "error_respuesta",
    "error_validacion",
    "app",
    "main",
}
_ENTERO_MIN, _ENTERO_MAX = -2147483648, 2147483647


class Campo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Identificador
    tipo: TipoCampo
    descripcion: Descripcion | None = None
    requerido: bool | None = None
    unico: bool | None = None
    min: float | None = None
    max: float | None = None
    escala: int | None = None
    valores: list[ValorEnumeracion] | None = None
    entidad: Identificador | None = None

    @model_validator(mode="after")
    def _reglas_del_tipo(self) -> Campo:
        if self.nombre in CAMPOS_RESERVADOS:
            raise ValueError(f"«{self.nombre}» lo añade la plantilla en todas las entidades")
        limites = self.min is not None or self.max is not None
        if limites and self.tipo not in ("texto", "entero", "decimal"):
            raise ValueError("min y max solo valen para texto, entero y decimal")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min no puede ser mayor que max")
        if self.tipo == "texto":
            if self.min is not None and (self.min < 0 or self.min != int(self.min)):
                raise ValueError("en un texto, min es una longitud entera")
            if self.max is not None and (self.max != int(self.max) or not 1 <= self.max <= 10000):
                raise ValueError("en un texto, max es una longitud entera de 1 a 10000")
        if self.tipo == "entero":
            for limite in (self.min, self.max):
                if limite is not None and (
                    limite != int(limite) or not _ENTERO_MIN <= limite <= _ENTERO_MAX
                ):
                    raise ValueError("un entero va de -2147483648 a 2147483647")
        if self.escala is not None and (self.tipo != "decimal" or not 0 <= self.escala <= 6):
            raise ValueError("escala solo vale para decimal, de 0 a 6")
        if self.tipo == "enumeracion":
            if (
                not self.valores
                or len(self.valores) > 30
                or len(set(self.valores)) != len(self.valores)
            ):
                raise ValueError("una enumeración necesita de 1 a 30 valores distintos")
        elif self.valores is not None:
            raise ValueError("valores solo vale para enumeracion")
        if self.tipo == "referencia":
            if self.entidad is None or not self.nombre.endswith("_id"):
                raise ValueError("una referencia se llama «<algo>_id» e indica su «entidad»")
        elif self.entidad is not None:
            raise ValueError("entidad solo vale para referencia")
        return self

    def para_plantilla(self) -> dict[str, Any]:
        """Sin las claves vacías y con los límites enteros como enteros (Copier los distingue)."""
        datos = self.model_dump(exclude_none=True)
        for clave in ("min", "max"):
            if clave in datos and self.tipo in ("texto", "entero"):
                datos[clave] = int(datos[clave])
        return datos


class Entidad(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Identificador
    descripcion: Descripcion | None = None
    campos: list[Campo] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def _nombres(self) -> Entidad:
        if self.nombre in ENTIDADES_RESERVADAS:
            raise ValueError(f"la entidad «{self.nombre}» tiene un nombre reservado")
        nombres = [c.nombre for c in self.campos]
        if len(set(nombres)) != len(nombres):
            raise ValueError(f"la entidad {self.nombre} tiene campos con el mismo nombre")
        return self


class EntidadesPropuestas(BaseModel):
    """Respuesta del LLM: solo las entidades; el resto de la especificación lo pone el motor."""

    model_config = ConfigDict(extra="forbid")

    entidades: list[Entidad] = Field(min_length=1, max_length=20)
    requisitos_cubiertos: list[str] = Field(
        default_factory=list, description="Ids de los requisitos que reflejan estas entidades"
    )

    @model_validator(mode="after")
    def _referencias(self) -> EntidadesPropuestas:
        nombres = [e.nombre for e in self.entidades]
        if len(set(nombres)) != len(nombres):
            raise ValueError("hay entidades con el mismo nombre")
        for entidad in self.entidades:
            for campo in entidad.campos:
                if campo.tipo == "referencia" and campo.entidad not in nombres:
                    raise ValueError(
                        f"{entidad.nombre}.{campo.nombre} referencia a «{campo.entidad}», que no "
                        "es una entidad de este servicio: usa un campo uuid con descripción"
                    )
        return self


class EspecificacionServicio(BaseModel):
    """La especificación completa que recibe la plantilla Copier."""

    model_config = ConfigDict(extra="forbid")

    servicio: Identificador
    descripcion: Descripcion = ""
    base_datos: Identificador
    puerto: int = Field(ge=1024, le=65535)
    entidades: list[Entidad] = Field(min_length=1, max_length=20)

    def para_plantilla(self) -> dict[str, Any]:
        datos = self.model_dump(exclude={"entidades"})
        datos["entidades"] = [
            {
                **e.model_dump(exclude_none=True, exclude={"campos"}),
                "campos": [c.para_plantilla() for c in e.campos],
            }
            for e in self.entidades
        ]
        return datos


SISTEMA = f"""Eres un arquitecto de software que diseña el modelo de datos de UN microservicio
NestJS con Prisma y PostgreSQL. Recibes el servicio tal como lo definió la arquitectura, sus
requisitos y el conocimiento de seguridad del framework. {AVISO_DATOS}

Devuelve las entidades de las que es dueño el servicio, con sus campos:
- nombres en snake_case (a-z, 0-9, _), de 2 a 40 caracteres; no declares id, creado_en ni
  actualizado_en: los añade la plantilla en todas las entidades;
- tipo de cada campo: texto, correo, entero, decimal, booleano, fecha, fecha_hora, uuid,
  enumeracion o referencia;
- referencia solo entre entidades de ESTE servicio, con un campo llamado «<algo>_id» e indicando su
  «entidad». Un dato de otro servicio (p. ej. el cliente del servicio de usuarios) es un campo uuid
  con una descripción que diga de qué servicio viene: cada servicio tiene su propia base de datos;
- enumeracion para estados y listas cerradas, con sus «valores» en snake_case;
- min y max (solo en texto, entero y decimal) con los límites que piden los requisitos o, si no
  dicen nada, con límites razonables: nunca dejes un texto sin max;
- requerido false solo para lo que de verdad es opcional, y unico para lo que no puede repetirse.

Seguridad, según el conocimiento que recibes:
- no guardes contraseñas, tokens ni números de tarjeta: la identidad la gestiona Keycloak y los
  pagos la pasarela; guarda solo identificadores de esos sistemas;
- guarda los datos personales mínimos que piden los requisitos;
- los importes y los totales son decimal con min 0; las cantidades, entero con min y max.

En requisitos_cubiertos indica los ids de los requisitos que reflejan las entidades."""


def prompt_especificacion(
    servicio: Any,
    requisitos: list[Any],
    contexto: ContextoGraphRAG,
    codigo: str | None = None,
) -> Prompt[EntidadesPropuestas]:
    """Prompt para las entidades de `servicio` (un Servicio de arquitectura.json).

    `requisitos` son los Requisito del modelo de la fase 1 que cubre el servicio.
    """
    codigo = codigo or nuevo_codigo()
    entidades = ", ".join(servicio.entidades) or "ninguna"
    etiquetas = ", ".join(servicio.etiquetas) or "ninguna"
    partes = [
        bloque(
            "servicio",
            codigo,
            f"Responsabilidad: {servicio.responsabilidad}\n"
            f"Entidades que le asignó la arquitectura: {entidades}\n"
            f"Etiquetas de seguridad de sus requisitos: {etiquetas}",
            nombre=servicio.nombre,
            contexto=servicio.contexto,
        ),
        "Requisitos del servicio:",
        *(
            bloque(
                "requisito",
                codigo,
                r.texto,
                id=r.id,
                tipo=r.tipo,
                etiquetas=",".join(r.etiquetas),
            )
            for r in requisitos
        ),
        "Conocimiento de seguridad del framework (GraphRAG):",
        bloque("contexto", codigo, contexto.a_texto()),
    ]
    return Prompt(
        nombre="especificacion",
        version=VERSION,
        sistema=SISTEMA,
        usuario="\n\n".join(partes),
        esquema=EntidadesPropuestas,
        nivel="razonamiento",
        codigo=codigo,
    )


def construir_especificacion(
    servicio: Any, propuesta: EntidadesPropuestas, puerto: int
) -> EspecificacionServicio:
    """La especificación para la plantilla: lo que fijó la arquitectura y las entidades del LLM."""
    return EspecificacionServicio(
        servicio=servicio.nombre,
        descripcion=servicio.responsabilidad[:300].replace("\n", " "),
        base_datos=servicio.base_datos,
        puerto=puerto,
        entidades=propuesta.entidades,
    )
