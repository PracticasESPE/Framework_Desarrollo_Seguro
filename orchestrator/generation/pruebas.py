"""Generador de las pruebas Jest de la lógica de negocio con el LLM (fase 3, plan técnico 6.2).

Por cada entidad con reglas de negocio aceptadas (orchestrator/generation/logica.py):

1. Pide al LLM de razonamiento los casos de prueba con el prompt `pruebas`: el código de las
   reglas, los requisitos que implementan y los nombres y tipos de la entidad.
2. Analiza el cuerpo de cada caso como el de la lógica (sin import, require, process, red...), y
   además sin jest.mock ni describe/it/test anidados.
3. Arma `src/<entidad>.reglas.spec.ts`: los imports, el doble de Prisma y el acceso a los métodos
   los escribe el motor; el LLM solo aporta el cuerpo de cada `it`.
4. Lo ejecuta con Jest. Si el archivo no compila o algún caso falla, vuelve a pedirlo con los
   errores (hasta 3 intentos).
5. Si tras el último intento siguen fallando casos, los quita, comprueba que el resto pasa y los
   deja registrados como descartados: una prueba que falla puede ser una prueba mal escrita o un
   error real de la lógica, y lo decide una persona, no el LLM.

La verificación es la ejecución con Jest (plan técnico, tabla 6.1): solo se queda en el servicio lo
que pasa.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from orchestrator.generation.logica import ErrorLogica, _ejecutar, problemas_del_codigo, solo_codigo
from orchestrator.llm.base import Nivel, ProveedorLLM
from orchestrator.llm.prompts import LogicaEntidad, clase_de, prompt_pruebas
from orchestrator.llm.prompts.logica import propiedad_de
from orchestrator.llm.prompts.pruebas import METODOS_PRISMA, CasoPrueba, PruebasEntidad

INTENTOS = 3
_PROHIBIDO_EN_PRUEBAS: list[tuple[str, str]] = [
    (
        r"\bjest\s*\.\s*(mock|unmock|doMock|requireActual|requireMock|isolateModules)\b",
        "sustituir módulos (jest.mock)",
    ),
    (r"\b(describe|it|test)\s*(\.\w+)?\s*\(", "describe, it o test anidados"),
]


class CasoEjecutado(BaseModel):
    numero: int
    nombre: str
    requisito: str | None
    estado: str
    error: str | None = None


class IntentoPruebas(BaseModel):
    numero: int
    fecha: datetime
    problemas: list[str]
    error_de_compilacion: str | None
    casos: list[CasoEjecutado]


class ResultadoPruebas(BaseModel):
    """Registro de las pruebas de una entidad: se guarda en pruebas/<entidad>.json."""

    servicio: str
    entidad: str
    archivo: str
    aceptadas: int
    descartadas: list[CasoEjecutado]
    huella_prompt: str
    intentos: list[IntentoPruebas]
    pruebas: PruebasEntidad | None


class ResultadoJest(BaseModel):
    error_de_compilacion: str | None
    estados: dict[int, tuple[str, str | None]]  # número del caso -> (estado, error)


Ejecutor = Callable[[Path, str], ResultadoJest]


# --- Análisis y armado del archivo -------------------------------------------------------------


def problemas_del_caso(caso: CasoPrueba) -> list[str]:
    codigo = solo_codigo(caso.cuerpo)
    problemas = problemas_del_codigo(caso.cuerpo)
    problemas += [
        f"no se permite {motivo}"
        for patron, motivo in _PROHIBIDO_EN_PRUEBAS
        if re.search(patron, codigo)
    ]
    return problemas


def problemas_de_las_pruebas(pruebas: PruebasEntidad, requisitos: set[str]) -> list[str]:
    problemas = []
    for numero, caso in enumerate(pruebas.casos, 1):
        problemas += [f"caso {numero} («{caso.nombre}»): {p}" for p in problemas_del_caso(caso)]
        if caso.requisito and caso.requisito not in requisitos:
            problemas.append(
                f"caso {numero} («{caso.nombre}»): el código no implementa {caso.requisito}"
            )
    return problemas


def _cadena_ts(texto: str) -> str:
    """Literal de TypeScript entre comillas simples, sin saltos de línea."""
    limpio = re.sub(r"[\x00-\x1f\x7f  ]+", " ", texto)
    return "'" + limpio.replace("\\", "\\\\").replace("'", "\\'") + "'"


def titulo(numero: int, caso: CasoPrueba) -> str:
    """El número al principio identifica cada caso en el informe de Jest."""
    requisito = f" ({caso.requisito})" if caso.requisito else ""
    return f"{numero:02d}. {caso.nombre}{requisito}"


def archivo_de_pruebas(
    especificacion: Any, entidad: str, casos: list[tuple[int, CasoPrueba]]
) -> str:
    clase = clase_de(entidad)
    archivo = entidad.replace("_", "-")
    modelos = "\n".join(
        f"  {propiedad_de(e.nombre)}: {{ "
        + ", ".join(f"{m}: jest.fn()" for m in METODOS_PRISMA)
        + " },"
        for e in especificacion.entidades
    )
    casos_ts = "\n\n".join(
        f"  it({_cadena_ts(titulo(numero, caso))}, async () => {{\n"
        + "\n".join(f"    {linea}".rstrip() for linea in caso.cuerpo.strip().splitlines())
        + "\n  });"
        for numero, caso in casos
    )
    return f"""/* eslint-disable @typescript-eslint/no-unused-vars */
// Pruebas de las reglas de negocio de {clase}, generadas por el LLM (fase 3) y verificadas con
// Jest. El motor escribe este encabezado; el LLM, el cuerpo de cada caso. Se regeneran con
// «framework servicio pruebas»: no editar a mano.
import {{
  BadRequestException,
  ConflictException,
  NotFoundException,
}} from '@nestjs/common';
import {{ Test }} from '@nestjs/testing';
import type {{ Actualizar{clase}Dto }} from './dto/actualizar-{archivo}.dto';
import type {{ Crear{clase}Dto }} from './dto/crear-{archivo}.dto';
import type {{ {clase} }} from './generated/prisma/client';
import {{ PrismaService }} from './prisma.service';
import {{ {clase}Service }} from './{archivo}.service';

// Prisma devuelve los decimales como objetos Decimal; las reglas usan toNumber().
const decimal = (valor: number) => ({{ toNumber: () => valor, valueOf: () => valor }});

const prisma = {{
  $transaction: jest.fn(),
{modelos}
}};

type Reglas = {{
  reglasAlCrear(datos: Crear{clase}Dto): Promise<void>;
  reglasAlActualizar(actual: {clase}, cambios: Actualizar{clase}Dto): Promise<void>;
  reglasAlEliminar(actual: {clase}): Promise<void>;
}};

describe('Reglas de negocio de {clase} (generadas)', () => {{
  let reglas: Reglas;

  beforeEach(async () => {{
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({{
      providers: [{clase}Service, {{ provide: PrismaService, useValue: prisma }}],
    }}).compile();
    reglas = modulo.get({clase}Service) as unknown as Reglas;
  }});

{casos_ts}
}});
"""


# --- Ejecución con Jest ------------------------------------------------------------------------


def ejecutar_jest(carpeta: Path, archivo: str) -> ResultadoJest:
    """Ejecuta un archivo de pruebas con Jest y lee su informe JSON."""
    with tempfile.TemporaryDirectory() as temporal:
        informe = Path(temporal) / "jest.json"
        _ejecutar(
            ["npx", "jest", archivo, "--ci", "--runInBand", "--json", f"--outputFile={informe}"],
            carpeta,
            600,
        )
        try:
            datos = json.loads(informe.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise ErrorLogica(f"Jest no generó su informe: {error}") from error
    return leer_informe(datos)


def leer_informe(datos: dict) -> ResultadoJest:
    """Estados de los casos («01. ...») y el error del archivo si no llegó a ejecutarse."""
    resultados = datos.get("testResults") or [{}]
    suite = resultados[0]
    estados: dict[int, tuple[str, str | None]] = {}
    for caso in suite.get("assertionResults", []):
        coincidencia = re.match(r"^(\d+)\.", caso.get("title", ""))
        if coincidencia:
            error = "\n".join(caso.get("failureMessages") or []) or None
            estados[int(coincidencia.group(1))] = (caso.get("status", "failed"), error)
    error_suite = None
    if not estados and (suite.get("message") or suite.get("status") == "failed"):
        error_suite = suite.get("message") or "el archivo de pruebas no se pudo ejecutar"
    return ResultadoJest(error_de_compilacion=error_suite, estados=estados)


def _resumen_error(texto: str | None, maximo: int = 600) -> str:
    """Las primeras líneas útiles de un error de Jest, sin códigos de color."""
    limpio = re.sub(r"\x1b\[[0-9;]*m", "", texto or "")
    lineas = [
        linea.rstrip() for linea in limpio.splitlines() if linea.strip() and " at " not in linea
    ]
    return "\n".join(lineas)[:maximo]


# --- Generador ---------------------------------------------------------------------------------


def generar_pruebas(
    carpeta: Path,
    especificacion: Any,
    entidad: str,
    logica: LogicaEntidad,
    requisitos: list[Any],
    llm: ProveedorLLM,
    intentos: int = INTENTOS,
    ejecutor: Ejecutor = ejecutar_jest,
    al_intento: Callable[[IntentoPruebas], None] | None = None,
    nivel: Nivel = "razonamiento",
) -> ResultadoPruebas:
    """Genera y verifica src/<entidad>.reglas.spec.ts. Si nada pasa, no deja el archivo."""
    relativo = f"src/{entidad.replace('_', '-')}.reglas.spec.ts"
    destino = carpeta / relativo
    ids = {r.id for r in requisitos}
    historial: list[IntentoPruebas] = []
    motivos: list[str] = []
    pruebas: PruebasEntidad | None = None
    huella = ""
    ultimo = ResultadoJest(error_de_compilacion=None, estados={})

    def registrar(problemas: list[str], resultado: ResultadoJest, casos) -> IntentoPruebas:
        intento = IntentoPruebas(
            numero=len(historial) + 1,
            fecha=datetime.now(UTC),
            problemas=problemas,
            error_de_compilacion=_resumen_error(resultado.error_de_compilacion) or None,
            casos=[
                CasoEjecutado(
                    numero=n,
                    nombre=c.nombre,
                    requisito=c.requisito,
                    estado=resultado.estados.get(n, ("sin ejecutar", None))[0],
                    error=_resumen_error(resultado.estados.get(n, ("", None))[1]) or None,
                )
                for n, c in casos
            ],
        )
        historial.append(intento)
        if al_intento is not None:
            al_intento(intento)
        return intento

    for _ in range(intentos):
        prompt = prompt_pruebas(
            especificacion,
            entidad,
            logica,
            requisitos,
            retroalimentacion=motivos or None,
            nivel=nivel,
        )
        huella = prompt.huella
        pruebas = prompt.enviar(llm)
        casos = list(enumerate(pruebas.casos, 1))
        problemas = problemas_de_las_pruebas(pruebas, ids)
        ultimo = ResultadoJest(error_de_compilacion=None, estados={})
        if not problemas:
            destino.write_text(archivo_de_pruebas(especificacion, entidad, casos), encoding="utf-8")
            ultimo = ejecutor(carpeta, relativo)
        intento = registrar(problemas, ultimo, casos)
        fallidos = [c for c in intento.casos if c.estado != "passed"]
        if not problemas and not ultimo.error_de_compilacion and not fallidos:
            return ResultadoPruebas(
                servicio=especificacion.servicio,
                entidad=entidad,
                archivo=relativo,
                aceptadas=len(casos),
                descartadas=[],
                huella_prompt=huella,
                intentos=historial,
                pruebas=pruebas,
            )
        motivos = problemas[:]
        if ultimo.error_de_compilacion:
            error = _resumen_error(ultimo.error_de_compilacion, 1200)
            motivos.append(f"el archivo no compila o no se ejecuta: {error}")
        motivos += [f"falla el caso «{c.nombre}»: {c.error or c.estado}" for c in fallidos][:10]

    # Último recurso: quedarse con los casos que pasan, si el archivo compiló.
    if pruebas is not None and not ultimo.error_de_compilacion and ultimo.estados:
        casos = list(enumerate(pruebas.casos, 1))
        pasan = [(n, c) for n, c in casos if ultimo.estados.get(n, ("",))[0] == "passed"]
        descartados = [c for c in historial[-1].casos if c.estado != "passed"]
        if pasan:
            destino.write_text(archivo_de_pruebas(especificacion, entidad, pasan), encoding="utf-8")
            confirmacion = ejecutor(carpeta, relativo)
            intento = registrar([], confirmacion, pasan)
            if not confirmacion.error_de_compilacion and all(
                c.estado == "passed" for c in intento.casos
            ):
                return ResultadoPruebas(
                    servicio=especificacion.servicio,
                    entidad=entidad,
                    archivo=relativo,
                    aceptadas=len(pasan),
                    descartadas=descartados,
                    huella_prompt=huella,
                    intentos=historial,
                    pruebas=pruebas,
                )
    destino.unlink(missing_ok=True)
    return ResultadoPruebas(
        servicio=especificacion.servicio,
        entidad=entidad,
        archivo=relativo,
        aceptadas=0,
        descartadas=historial[-1].casos if historial else [],
        huella_prompt=huella,
        intentos=historial,
        pruebas=pruebas,
    )
