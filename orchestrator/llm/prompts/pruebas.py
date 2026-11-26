"""Prompt de las pruebas Jest de la lógica de negocio de una entidad (fase 3, plan técnico 6.2).

La plantilla ya prueba lo que genera ella (src/<entidad>.service.spec.ts) y sustituye las reglas
de negocio por dobles. Este prompt pide al LLM de razonamiento las pruebas de esas reglas: el
bloque que escribió el LLM en el punto de extensión (prompt `logica`). El LLM solo escribe el cuerpo
de cada caso; el motor arma el archivo (imports, doble de Prisma, acceso a los métodos) y lo
verifica ejecutándolo con Jest (orchestrator/generation/pruebas.py).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from orchestrator.llm.base import Nivel
from orchestrator.llm.prompts.comun import AVISO_DATOS, Prompt, bloque, nuevo_codigo
from orchestrator.llm.prompts.logica import (
    LogicaEntidad,
    _describir_campos,
    clase_de,
    propiedad_de,
)

VERSION = "1.0"

# Métodos de cada modelo que el doble de Prisma ofrece como jest.fn().
METODOS_PRISMA = (
    "findUnique",
    "findFirst",
    "findMany",
    "count",
    "aggregate",
    "create",
    "update",
    "updateMany",
    "upsert",
    "delete",
    "deleteMany",
)

IdRequisito = Annotated[str, StringConstraints(pattern=r"^(RF|RNF)-\d{2,3}$")]
Frase = Annotated[str, StringConstraints(max_length=300)]
Nombre = Annotated[
    str, StringConstraints(min_length=5, max_length=120, pattern=r"^[^\x00-\x1f\x7f]*$")
]


class CasoPrueba(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: Nombre = Field(description="Qué comprueba, en una frase: «rechaza un total ...»")
    metodo: Literal["reglasAlCrear", "reglasAlActualizar", "reglasAlEliminar"]
    requisito: IdRequisito | None = Field(default=None, description="Requisito que comprueba")
    cuerpo: Annotated[str, StringConstraints(min_length=10, max_length=3000)] = Field(
        description="Cuerpo de la función async del caso, sin it(...) alrededor"
    )


class PruebasEntidad(BaseModel):
    """Respuesta del LLM: los casos y lo que no se puede probar en estos métodos."""

    model_config = ConfigDict(extra="forbid")

    casos: list[CasoPrueba] = Field(min_length=1, max_length=20)
    sin_probar: list[Frase] = Field(
        default_factory=list,
        max_length=20,
        description="Reglas del código que no se pueden probar con un doble de Prisma",
    )


SISTEMA = f"""Eres un desarrollador sénior de TypeScript que escribe pruebas unitarias con Jest
para las reglas de negocio de UNA entidad de un microservicio NestJS. {AVISO_DATOS}

El archivo ya está preparado; tú escribes SOLO el cuerpo de cada caso (lo que va dentro de
`it('...', async () => {{ ... }})`). En cada caso tienes disponibles, y nada más:
- reglas: el servicio con los tres métodos a probar, ya accesibles:
  reglas.reglasAlCrear(datos), reglas.reglasAlActualizar(actual, cambios),
  reglas.reglasAlEliminar(actual);
- prisma: el doble de la base de datos; cada modelo tiene sus métodos como jest.fn() (p. ej.
  prisma.pedido.findFirst.mockResolvedValue(...)); jest.resetAllMocks() ya se ejecutó antes;
- decimal(n): un valor como el Decimal de Prisma (usa .toNumber());
- BadRequestException, ConflictException y NotFoundException; expect y jest.

Cómo escribir cada caso:
- prepara lo que devuelve la base con mockResolvedValue y los datos con objetos literales
  convertidos al tipo: `{{ ... }} as CrearXDto`, `{{ ... }} as ActualizarXDto` y, para un registro
  guardado, `{{ ... }} as unknown as X` (X es la clase de la entidad);
- llama al método con await y comprueba el resultado: `await expect(...).rejects.toBeInstanceOf(
  BadRequestException)` si la regla rechaza, o `await expect(...).resolves.toBeUndefined()` si la
  operación sigue; si hace falta, comprueba las llamadas a prisma con toHaveBeenCalledWith;
- por cada regla del código, un caso en que se cumple y otro en que se incumple;
- usa exactamente los nombres en camelCase y los tipos que recibes; las propiedades de los modelos
  de prisma son las del código que pruebas.

Reglas obligatorias: sin import ni require, sin jest.mock, sin describe, it ni test anidados, sin
console, process, temporizadores ni red. Prueba solo lo que hace el código que recibes; lo que el
código no puede hacer (pendientes) no se prueba. En requisito indica el id que comprueba cada caso
y en sin_probar lo que no se pueda probar con un doble de Prisma."""


def _metodos_del_codigo(logica: LogicaEntidad) -> str:
    partes = []
    for campo, firma in (
        ("reglas_al_crear", "reglasAlCrear(datos)"),
        ("reglas_al_actualizar", "reglasAlActualizar(actual, cambios)"),
        ("reglas_al_eliminar", "reglasAlEliminar(actual)"),
    ):
        cuerpo = getattr(logica, campo).strip() or "// sin reglas: no hay nada que probar"
        partes.append(f"async {firma} {{\n{cuerpo}\n}}")
    return "\n\n".join(partes)


def prompt_pruebas(
    especificacion: Any,
    entidad: str,
    logica: LogicaEntidad,
    requisitos: list[Any],
    codigo: str | None = None,
    retroalimentacion: list[str] | None = None,
    nivel: Nivel = "razonamiento",
) -> Prompt[PruebasEntidad]:
    """Prompt para las pruebas de las reglas de negocio de `entidad`."""
    datos = next((e for e in especificacion.entidades if e.nombre == entidad), None)
    if datos is None:
        raise ValueError(
            f"La especificación de {especificacion.servicio} no tiene la entidad {entidad}"
        )
    codigo = codigo or nuevo_codigo()
    clase = clase_de(entidad)
    modelos = "\n".join(
        f"- prisma.{propiedad_de(e.nombre)}: " + ", ".join(propiedad_de(c.nombre) for c in e.campos)
        for e in especificacion.entidades
    )
    partes = [
        bloque(
            "entidad",
            codigo,
            f"Propiedades (además de id, creadoEn y actualizadoEn):\n{_describir_campos(datos)}",
            servicio=especificacion.servicio,
            nombre=entidad,
            clase=clase,
        ),
        f"Tipos disponibles: Crear{clase}Dto, Actualizar{clase}Dto y {clase}.",
        "Modelos del doble de prisma (cada uno con "
        f"{', '.join(METODOS_PRISMA)}) y sus propiedades:\n{modelos}",
        "Código que debes probar (las reglas de negocio de la entidad):",
        bloque("codigo", codigo, _metodos_del_codigo(logica)),
        "Requisitos que implementa el código:",
        *(bloque("requisito", codigo, r.texto, id=r.id) for r in requisitos),
    ]
    if logica.pendientes:
        partes.append(
            "Lo que el código NO hace (no lo pruebes):\n"
            + bloque("pendientes", codigo, "\n".join(f"- {p}" for p in logica.pendientes))
        )
    if retroalimentacion:
        partes.append(
            "Tus pruebas anteriores se rechazaron por estos motivos. Corrígelos y devuelve todos "
            "los casos:\n"
            + bloque("rechazo", codigo, "\n".join(f"- {m}" for m in retroalimentacion))
        )
    return Prompt(
        nombre="pruebas",
        version=VERSION,
        sistema=SISTEMA,
        usuario="\n\n".join(partes),
        esquema=PruebasEntidad,
        nivel=nivel,
        codigo=codigo,
    )
