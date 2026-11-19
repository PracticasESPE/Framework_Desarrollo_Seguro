"""Generador de la lógica de negocio: rellena los puntos de extensión con el LLM (fase 3, #64).

La plantilla deja en `src/<entidad>.service.ts` un punto de extensión por entidad, entre las
marcas `// @framework:logica-negocio:inicio <entidad>` y `...:fin <entidad>`, con tres métodos:
reglasAlCrear, reglasAlActualizar y reglasAlEliminar. Por cada entidad, el generador:

1. Pide al LLM de razonamiento el cuerpo de los tres métodos con el prompt `logica`
   (orchestrator/llm/prompts), que lleva los requisitos del servicio y el contexto GraphRAG.
2. Analiza el código antes de escribirlo: sin import, require, eval, process, consultas en crudo,
   red, temporizadores ni consola; solo `this.prisma` de la clase; y las llaves equilibradas, para
   que el cuerpo no pueda cerrar el método y escribir fuera de él.
3. Comprueba que los requisitos y los controles ASVS que cita existen.
4. Lo inserta entre las marcas y compila el servicio con `tsc --noEmit`.
5. Si algo falla, vuelve a pedirlo con los motivos (hasta 3 intentos). Si no lo consigue, deja el
   archivo como lo generó la plantilla: el servicio compila, sin reglas, y queda para revisión.

El LLM nunca tiene la última palabra (plan técnico 6.1): lo que no pasa el análisis y tsc no se
queda en el servicio. Semgrep, ESLint y las pruebas lo revisan después en el Gate 1.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from orchestrator.knowledge.graphrag import ContextoGraphRAG
from orchestrator.llm.base import ProveedorLLM
from orchestrator.llm.prompts import LogicaEntidad, clase_de, prompt_logica

INTENTOS = 3
_MARCA = "// @framework:logica-negocio:{lado} {entidad}"

# Lo que no puede aparecer en el código del LLM (fuera de cadenas y comentarios).
_PROHIBIDO: list[tuple[str, str]] = [
    (r"\bimport\b", "import"),
    (r"\brequire\s*\(", "require"),
    (r"\beval\s*\(", "eval"),
    (r"\bFunction\s*\(|\bnew\s+Function\b", "construir funciones desde texto (Function)"),
    (r"\bprocess\b", "process"),
    (r"\bglobalThis\b|\bglobal\b\.|\bwindow\b", "el objeto global"),
    (r"\bchild_process\b|\bfs\b\s*\.", "acceso al sistema (fs, child_process)"),
    (r"\$(query|execute)Raw", "consultas SQL en crudo ($queryRaw, $executeRaw)"),
    (r"\bset(Timeout|Interval|Immediate)\b", "temporizadores"),
    (r"\bfetch\s*\(|\bXMLHttpRequest\b|\bWebSocket\b|\bhttps?\s*\.", "llamadas de red"),
    (r"\bconsole\s*\.", "console (puede registrar datos personales)"),
    (r"__proto__|\bprototype\b|\bconstructor\b", "prototipos o constructores"),
    (r"\b(class|export|function)\b", "declarar clases, funciones o exportaciones"),
    (r"\bthis\s*\.\s*(?!prisma\b)\w+", "miembros de la clase distintos de this.prisma"),
]
# Cadenas, plantillas de texto y comentarios, para analizar solo el código.
_NO_CODIGO = re.compile(
    r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`",
    re.DOTALL,
)
_ERROR_TSC = re.compile(
    r"^(?P<archivo>.+?)\((?P<linea>\d+),(?P<columna>\d+)\): error (?P<texto>.+)$"
)


class ErrorLogica(Exception):
    """El servicio no tiene el punto de extensión o no se pudo preparar para compilar."""


class IntentoLogica(BaseModel):
    numero: int
    fecha: datetime
    problemas: list[str]
    errores_tsc: list[str]


class ResultadoLogica(BaseModel):
    """Registro de la generación de una entidad: se guarda en logica/<entidad>.json."""

    servicio: str
    entidad: str
    archivo: str
    aprobada: bool
    huella_prompt: str
    intentos: list[IntentoLogica]
    logica: LogicaEntidad | None


# --- Análisis del código -----------------------------------------------------------------------


def solo_codigo(cuerpo: str) -> str:
    """El cuerpo sin cadenas, plantillas de texto ni comentarios."""
    return _NO_CODIGO.sub(" ", cuerpo)


def problemas_del_codigo(cuerpo: str) -> list[str]:
    """Lo que impide aceptar el cuerpo de un método; vacío si se puede insertar."""
    codigo = solo_codigo(cuerpo)
    # Las marcas se buscan en todo el texto: en un comentario también acabarían en el archivo y
    # partirían el punto de extensión la próxima vez que se regenere.
    marcas = ["no se permiten las marcas del punto de extensión"] if "@framework:" in cuerpo else []
    problemas = marcas + [
        f"no se permite {motivo}" for patron, motivo in _PROHIBIDO if re.search(patron, codigo)
    ]
    profundidad = 0
    for caracter in codigo:
        profundidad += {"{": 1, "}": -1}.get(caracter, 0)
        if profundidad < 0:
            problemas.append("cierra más llaves de las que abre: saldría del método")
            break
    else:
        if profundidad:
            problemas.append("deja llaves sin cerrar")
    return problemas


def problemas_de_la_respuesta(
    logica: LogicaEntidad, requisitos: set[str], controles: set[str]
) -> list[str]:
    """El código de los tres métodos y la trazabilidad que declara el LLM."""
    problemas = []
    for metodo in ("reglas_al_crear", "reglas_al_actualizar", "reglas_al_eliminar"):
        problemas += [f"{metodo}: {p}" for p in problemas_del_codigo(getattr(logica, metodo))]
    if inventados := sorted(set(logica.requisitos) - requisitos):
        problemas.append(f"cita requisitos que no son de este servicio: {inventados}")
    if inventados := sorted(set(logica.controles) - controles):
        problemas.append(f"cita controles que no están en el contexto: {inventados}")
    return problemas


# --- Inserción en el punto de extensión --------------------------------------------------------


def _comentario(texto: str) -> str:
    """Una línea de comentario segura: sin saltos de línea ni marcas del punto de extensión."""
    limpio = re.sub(r"[\x00-\x1f\x7f  ]+", " ", texto).replace("@framework:", "")
    return limpio.strip()[:300]


def _metodo(firma: str, cuerpo: str, parametros: list[str]) -> str:
    if cuerpo.strip():
        lineas = "\n".join(f"    {linea}".rstrip() for linea in cuerpo.strip().splitlines())
        return f"  protected async {firma} {{\n{lineas}\n  }}"
    # Sin reglas: el mismo método que deja la plantilla.
    sin_uso = "\n".join(f"    void {p};" for p in parametros)
    return f"  protected {firma} {{\n{sin_uso}\n    return Promise.resolve();\n  }}"


def bloque_logica(entidad: str, logica: LogicaEntidad) -> str:
    """El punto de extensión completo, marcas incluidas, con los métodos del LLM."""
    clase = clase_de(entidad)
    cabecera = [
        _MARCA.format(lado="inicio", entidad=entidad),
        f"// Reglas de negocio de {clase} generadas por el LLM (fase 3) y verificadas con tsc.",
        "// Se regeneran con «framework servicio logica»: no editar a mano.",
    ]
    if logica.requisitos:
        cabecera.append(_comentario(f"// Requisitos: {', '.join(logica.requisitos)}"))
    if logica.controles:
        cabecera.append(_comentario(f"// Controles ASVS: {', '.join(logica.controles)}"))
    cabecera += [_comentario(f"// Pendiente: {p}") for p in logica.pendientes]
    metodos = [
        _metodo(
            f"reglasAlCrear(datos: Crear{clase}Dto): Promise<void>",
            logica.reglas_al_crear,
            ["datos"],
        ),
        _metodo(
            f"reglasAlActualizar(actual: {clase}, cambios: Actualizar{clase}Dto): Promise<void>",
            logica.reglas_al_actualizar,
            ["actual", "cambios"],
        ),
        _metodo(
            f"reglasAlEliminar(actual: {clase}): Promise<void>",
            logica.reglas_al_eliminar,
            ["actual"],
        ),
    ]
    lineas = [f"  {c}" if c.startswith("//") else f"  // {c}" for c in cabecera]
    return (
        "\n".join(lineas)
        + "\n\n"
        + "\n\n".join(metodos)
        + "\n  "
        + _MARCA.format(lado="fin", entidad=entidad)
    )


def insertar_logica(contenido: str, entidad: str, logica: LogicaEntidad) -> str:
    """Reemplaza el punto de extensión de `entidad` en el contenido de su service.ts."""
    inicio = re.escape(_MARCA.format(lado="inicio", entidad=entidad))
    fin = re.escape(_MARCA.format(lado="fin", entidad=entidad))
    patron = re.compile(rf"^[ \t]*{inicio}\n.*?^[ \t]*{fin}[ \t]*$", re.MULTILINE | re.DOTALL)
    if len(patron.findall(contenido)) != 1:
        raise ErrorLogica(f"El archivo no tiene un único punto de extensión de {entidad}")
    return patron.sub(lambda _: bloque_logica(entidad, logica), contenido)


# --- Compilación -------------------------------------------------------------------------------

Compilador = Callable[[Path], list[str]]


def _ejecutar(argumentos: list[str], carpeta: Path, tiempo_s: int) -> subprocess.CompletedProcess:
    ejecutable = shutil.which(argumentos[0])
    if ejecutable is None:
        raise ErrorLogica(f"No se encontró {argumentos[0]}: instala Node.js para compilar")
    entorno = {
        **os.environ,
        "DATABASE_URL": "postgresql://compilar:compilar@localhost:5432/compilar",
    }
    try:
        return subprocess.run(
            [ejecutable, *argumentos[1:]],
            cwd=carpeta,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=tiempo_s,
            env=entorno,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ErrorLogica(f"No se pudo ejecutar {' '.join(argumentos)}: {error}") from error


def _comprobar_dependencias(carpeta: Path, momento: str) -> None:
    """Para con error si alguna dependencia no está en la lista permitida (#66)."""
    from orchestrator.generation.dependencias import ErrorDependencias, verificar_servicio

    try:
        problemas = verificar_servicio(carpeta)
    except ErrorDependencias as error:
        raise ErrorLogica(str(error)) from error
    if problemas:
        detalle = "; ".join(str(p) for p in problemas[:10])
        raise ErrorLogica(f"Dependencias no permitidas {momento}: {detalle}")


def preparar(carpeta: Path) -> None:
    """Instala las dependencias (sin scripts) y genera el cliente de Prisma, si hace falta.

    Antes de instalar comprueba package.json contra la lista permitida, para no descargar nunca
    un paquete que no esté aprobado; después comprueba el package-lock.json resultante.
    """
    if not (carpeta / "node_modules").is_dir():
        _comprobar_dependencias(carpeta, "antes de instalar")
        # Con package-lock.json, npm ci instala exactamente las versiones recién verificadas.
        orden = "ci" if (carpeta / "package-lock.json").is_file() else "install"
        proceso = _ejecutar(
            ["npm", orden, "--ignore-scripts", "--no-audit", "--no-fund"], carpeta, 900
        )
        if proceso.returncode != 0:
            raise ErrorLogica(f"npm {orden} falló: {proceso.stderr.strip()[-500:]}")
        _comprobar_dependencias(carpeta, "en el package-lock.json")
    if not (carpeta / "src" / "generated" / "prisma").is_dir():
        proceso = _ejecutar(["npx", "prisma", "generate"], carpeta, 300)
        if proceso.returncode != 0:
            raise ErrorLogica(f"prisma generate falló: {proceso.stderr.strip()[-500:]}")


def compilar(carpeta: Path) -> list[str]:
    """Errores de `tsc --noEmit`, uno por línea: «src/archivo.ts(12,5): error TS2339: ...»."""
    proceso = _ejecutar(["npx", "tsc", "--noEmit", "--pretty", "false"], carpeta, 300)
    salida = (proceso.stdout + proceso.stderr).splitlines()
    return [linea.strip() for linea in salida if _ERROR_TSC.match(linea.strip())]


def errores_del_archivo(errores: list[str], archivo: str) -> list[str]:
    """Los errores de tsc de un archivo, con la línea y la columna pero sin la ruta."""
    propios = []
    for error in errores:
        coincidencia = _ERROR_TSC.match(error)
        if coincidencia and Path(coincidencia["archivo"]).as_posix().endswith(archivo):
            propios.append(
                f"línea {coincidencia['linea']}, columna {coincidencia['columna']}: "
                f"{coincidencia['texto']}"
            )
    return propios


# --- Generador ---------------------------------------------------------------------------------


def generar_logica(
    carpeta: Path,
    especificacion: Any,
    entidad: str,
    requisitos: list[Any],
    contexto: ContextoGraphRAG,
    llm: ProveedorLLM,
    intentos: int = INTENTOS,
    compilador: Compilador | None = compilar,
    al_intento: Callable[[IntentoLogica], None] | None = None,
) -> ResultadoLogica:
    """Rellena el punto de extensión de `entidad` en el servicio generado en `carpeta`.

    Con `compilador=None` no compila (solo el análisis del código). Si ningún intento pasa, el
    archivo queda como estaba.
    """
    archivo_relativo = f"src/{entidad.replace('_', '-')}.service.ts"
    archivo = carpeta / archivo_relativo
    try:
        original = archivo.read_text(encoding="utf-8")
    except OSError as error:
        raise ErrorLogica(f"No se encontró {archivo_relativo} en {carpeta}") from error
    insertar_logica(
        original,
        entidad,
        LogicaEntidad(reglas_al_crear="", reglas_al_actualizar="", reglas_al_eliminar=""),
    )  # Comprueba el punto de extensión antes de gastar una llamada al LLM.

    ids_requisitos = {r.id for r in requisitos}
    ids_controles = {c.id for c in contexto.controles}
    historial: list[IntentoLogica] = []
    motivos: list[str] = []
    logica: LogicaEntidad | None = None
    huella = ""
    for numero in range(1, intentos + 1):
        prompt = prompt_logica(
            especificacion, entidad, requisitos, contexto, retroalimentacion=motivos or None
        )
        huella = prompt.huella
        logica = prompt.enviar(llm)
        problemas = problemas_de_la_respuesta(logica, ids_requisitos, ids_controles)
        errores: list[str] = []
        if not problemas:
            archivo.write_text(insertar_logica(original, entidad, logica), encoding="utf-8")
            if compilador is not None:
                errores = errores_del_archivo(compilador(carpeta), archivo_relativo)
        intento = IntentoLogica(
            numero=numero, fecha=datetime.now(UTC), problemas=problemas, errores_tsc=errores
        )
        historial.append(intento)
        if al_intento is not None:
            al_intento(intento)
        if not problemas and not errores:
            return ResultadoLogica(
                servicio=especificacion.servicio,
                entidad=entidad,
                archivo=archivo_relativo,
                aprobada=True,
                huella_prompt=huella,
                intentos=historial,
                logica=logica,
            )
        archivo.write_text(original, encoding="utf-8")
        motivos = problemas + [f"tsc: {e}" for e in errores[:15]]

    return ResultadoLogica(
        servicio=especificacion.servicio,
        entidad=entidad,
        archivo=archivo_relativo,
        aprobada=False,
        huella_prompt=huella,
        intentos=historial,
        logica=logica,
    )
