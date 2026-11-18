"""Prompt de la lógica de negocio de una entidad (fase 3, plan técnico 7.3).

La plantilla genera todo el servicio y deja, por entidad, un punto de extensión entre las marcas
`// @framework:logica-negocio:inicio <entidad>` y `...:fin <entidad>` con tres métodos:
reglasAlCrear, reglasAlActualizar y reglasAlEliminar. El LLM de razonamiento escribe solo el
cuerpo de esos métodos, a partir de los requisitos del servicio y del contexto de seguridad
(GraphRAG). El generador (#64) los inserta y verifica el resultado con tsc y el resto de controles:
el LLM nunca tiene la última palabra (plan técnico 6.1, condición 3).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from orchestrator.knowledge.graphrag import ContextoGraphRAG
from orchestrator.llm.prompts.comun import AVISO_DATOS, Prompt, bloque, nuevo_codigo

VERSION = "1.0"

CuerpoMetodo = Annotated[str, StringConstraints(max_length=4000)]
IdRequisito = Annotated[str, StringConstraints(pattern=r"^(RF|RNF)-\d{2,3}$")]
Frase = Annotated[str, StringConstraints(max_length=300)]

# Firmas de los métodos del punto de extensión, tal como los deja la plantilla.
METODOS = {
    "reglas_al_crear": "reglasAlCrear(datos: Crear{clase}Dto): Promise<void>",
    "reglas_al_actualizar": (
        "reglasAlActualizar(actual: {clase}, cambios: Actualizar{clase}Dto): Promise<void>"
    ),
    "reglas_al_eliminar": "reglasAlEliminar(actual: {clase}): Promise<void>",
}


class LogicaEntidad(BaseModel):
    """Respuesta del LLM: el cuerpo de cada método y su trazabilidad."""

    model_config = ConfigDict(extra="forbid")

    reglas_al_crear: CuerpoMetodo = Field(description="Cuerpo de reglasAlCrear; vacío si no hay")
    reglas_al_actualizar: CuerpoMetodo = Field(
        description="Cuerpo de reglasAlActualizar; vacío si no hay"
    )
    reglas_al_eliminar: CuerpoMetodo = Field(
        description="Cuerpo de reglasAlEliminar; vacío si no hay"
    )
    requisitos: list[IdRequisito] = Field(
        default_factory=list, max_length=50, description="Requisitos que implementan las reglas"
    )
    controles: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Ids de los controles ASVS del contexto que aplican las reglas",
    )
    pendientes: list[Frase] = Field(
        default_factory=list,
        max_length=20,
        description="Reglas de los requisitos que no se pueden implementar en estos métodos",
    )


SISTEMA = f"""Eres un desarrollador sénior de TypeScript y NestJS. Completas las reglas de negocio
de UNA entidad de un microservicio generado con una plantilla. {AVISO_DATOS}

La plantilla ya hace el acceso a la base de datos, la validación de los DTO (tipos, longitudes,
rangos y campos permitidos), la autenticación con Keycloak y el manejo de errores. Tú escribes
SOLO el cuerpo de tres métodos async que se ejecutan antes de guardar o eliminar:
- reglasAlCrear(datos): datos es el DTO de creación, ya validado;
- reglasAlActualizar(actual, cambios): actual es el registro guardado y cambios el DTO parcial;
- reglasAlEliminar(actual).
Si la operación incumple una regla, lanza BadRequestException, ConflictException o
NotFoundException con un mensaje en español para el usuario. Si no hay reglas para un método,
devuelve su cuerpo vacío.

Reglas obligatorias del código:
- solo el cuerpo de cada método: sin import ni require, sin declarar clases ni funciones fuera de
  él y sin cambiar su firma;
- solo puedes usar los parámetros, this.prisma (los modelos de este servicio, con su API tipada) y
  las tres excepciones; no uses $queryRawUnsafe ni $executeRawUnsafe;
- nada de eval, new Function, process, require, fs, child_process, red ni temporizadores;
- no registres en consola datos personales y no pongas en los mensajes detalles internos (ids de
  otros registros, consultas o trazas);
- usa exactamente los nombres en camelCase y los tipos que recibes para cada propiedad y cada
  modelo de this.prisma: el código se compila con tsc en modo estricto;
- los id y las referencias son uuid (texto): compáralos solo por igualdad, nunca con números ni
  por orden; para un estado usa los valores de su enumeración;
- no repitas la validación que ya hace el DTO: implementa las reglas que dependen de otros
  registros, del estado actual o de varias propiedades a la vez;
- los datos de otros servicios no están en esta base: no los consultes.

Implementa solo lo que piden los requisitos que recibes, apoyándote en el conocimiento de
seguridad del framework. En requisitos indica los ids que implementan las reglas y en controles
los ids de los controles ASVS del contexto que aplican. Si una regla necesita algo que estos
métodos no reciben (p. ej. el usuario autenticado o datos de otro servicio), no la inventes:
descríbela en pendientes."""


def _firmas(clase: str) -> str:
    return "\n".join(f"- {firma.format(clase=clase)}" for firma in METODOS.values())


def clase_de(nombre: str) -> str:
    """Clase en TypeScript, como la calcula la plantilla (linea_pedido → LineaPedido)."""
    return "".join(parte.capitalize() for parte in nombre.split("_"))


def propiedad_de(nombre: str) -> str:
    """Propiedad en TypeScript y Prisma, como la calcula la plantilla (cliente_id → clienteId)."""
    primera, *resto = nombre.split("_")
    return primera + "".join(parte.capitalize() for parte in resto)


def _tipos_ts(campo: Any) -> tuple[str, str]:
    """Tipo en el DTO de entrada y en el registro de Prisma (`actual`), como en la plantilla."""
    if campo.tipo == "enumeracion":
        union = " | ".join(f"'{v}'" for v in campo.valores or [])
        dto, registro = union, union
    else:
        dto = {"entero": "number", "decimal": "number", "booleano": "boolean"}.get(
            campo.tipo, "string"
        )
        registro = {
            "entero": "number",
            "decimal": "Prisma.Decimal (usa .toNumber())",
            "booleano": "boolean",
            "fecha": "Date",
            "fecha_hora": "Date",
        }.get(campo.tipo, "string")
    if campo.tipo in ("fecha", "fecha_hora"):
        dto = "string (ISO 8601)"
    if campo.requerido is False:
        dto, registro = f"{dto} | null | undefined", f"{registro} | null"
    return dto, registro


def _numero(valor: float) -> str:
    """Sin notación científica ni decimales de más: 0, 10, 99999999.99."""
    return str(int(valor)) if valor == int(valor) else repr(valor)


def _describir_campos(entidad: Any) -> str:
    lineas = []
    for campo in entidad.campos:
        dto, registro = _tipos_ts(campo)
        detalles = [campo.tipo]
        if campo.unico:
            detalles.append("único")
        if campo.min is not None:
            detalles.append(f"mínimo {_numero(campo.min)}")
        if campo.max is not None:
            detalles.append(f"máximo {_numero(campo.max)}")
        if campo.entidad:
            detalles.append(f"id (uuid) de un registro de {campo.entidad}")
        descripcion = f"; {campo.descripcion}" if campo.descripcion else ""
        lineas.append(
            f"- {propiedad_de(campo.nombre)} ({', '.join(detalles)}{descripcion}): "
            f"en el DTO {dto}; en actual {registro}"
        )
    return "\n".join(lineas)


def prompt_logica(
    especificacion: Any,
    entidad: str,
    requisitos: list[Any],
    contexto: ContextoGraphRAG,
    codigo: str | None = None,
) -> Prompt[LogicaEntidad]:
    """Prompt para las reglas de negocio de `entidad` de una EspecificacionServicio."""
    datos = next((e for e in especificacion.entidades if e.nombre == entidad), None)
    if datos is None:
        raise ValueError(
            f"La especificación de {especificacion.servicio} no tiene la entidad {entidad}"
        )
    codigo = codigo or nuevo_codigo()
    clase = clase_de(entidad)
    modelos = "\n".join(
        f"- this.prisma.{propiedad_de(e.nombre)}: "
        + ", ".join(propiedad_de(c.nombre) for c in e.campos)
        for e in especificacion.entidades
    )
    partes = [
        bloque(
            "entidad",
            codigo,
            f"Descripción: {datos.descripcion or 'sin descripción'}\n"
            f"Propiedades (además de id, creadoEn y actualizadoEn):\n{_describir_campos(datos)}",
            servicio=especificacion.servicio,
            nombre=entidad,
            clase=clase,
        ),
        f"Métodos que debes completar:\n{_firmas(clase)}",
        "Modelos de this.prisma y sus propiedades (todos tienen id, creadoEn y actualizadoEn; "
        f"usa exactamente estos nombres en camelCase en where, data y select):\n{modelos}",
        "Requisitos del servicio:",
        *(
            bloque("requisito", codigo, r.texto, id=r.id, etiquetas=",".join(r.etiquetas))
            for r in requisitos
        ),
        "Conocimiento de seguridad del framework (GraphRAG):",
        bloque("contexto", codigo, contexto.a_texto()),
    ]
    return Prompt(
        nombre="logica",
        version=VERSION,
        sistema=SISTEMA,
        usuario="\n\n".join(partes),
        esquema=LogicaEntidad,
        nivel="razonamiento",
        codigo=codigo,
    )
