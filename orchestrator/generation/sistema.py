"""Fase 3 completa: los N microservicios de arquitectura.json (plan técnico 7.3).

Encadena las piezas de la fase 3, servicio por servicio:

1. Parámetros de la plantilla de cada servicio desde la arquitectura (parametros.py): nombre,
   base de datos, puerto, entidades y rutas. Se validan todos antes de generar nada.
2. Especificación con el LLM (prompt `especificacion`): solo los campos de cada entidad; el esquema
   de la respuesta exige exactamente las entidades de la arquitectura.
3. Servicio con la plantilla Copier, con su estructura validada (plantilla.py, estructura.py).
4. Dependencias contra la lista permitida, antes de instalar nada (dependencias.py).
5. Instalación y compilación (`tsc --noEmit`). Todos los servicios comparten el mismo
   package-lock.json salvo el nombre, así que las dependencias se instalan una sola vez en
   `.dependencias/<huella del lock>/` y cada servicio enlaza ahí su node_modules: la instalación es
   lo más lento de la fase (unos 750 paquetes por servicio).
6. Lógica de negocio con el LLM, verificada con tsc (logica.py), y sus pruebas Jest, verificadas
   ejecutándolas (pruebas.py). Lo que no pasa no se queda en el servicio.
7. La estructura se valida otra vez al final: el LLM solo pudo escribir entre las marcas.

Un fallo en un servicio no detiene los demás: queda en su resumen. La cancelación sí detiene la
fase (entre pasos, nunca a mitad de escribir un archivo).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, computed_field

from orchestrator.generation.dependencias import ErrorDependencias, verificar_servicio
from orchestrator.generation.estructura import validar_estructura
from orchestrator.generation.logica import (
    ErrorLogica,
    _ejecutar,
    compilar,
    generar_logica,
    preparar,
)
from orchestrator.generation.parametros import (
    ErrorParametros,
    ParametrosServicio,
    especificacion,
    parametros_de_arquitectura,
)
from orchestrator.generation.plantilla import ErrorPlantilla, generar_servicio
from orchestrator.generation.pruebas import generar_pruebas
from orchestrator.knowledge.graphrag import ContextoGraphRAG
from orchestrator.llm import ErrorLLM
from orchestrator.llm.base import ErrorLimiteLLM, ErrorProveedorLLM, ProveedorLLM
from orchestrator.llm.prompts import contexto_vacio, prompt_especificacion

CARPETA_DEPENDENCIAS = ".dependencias"
ARCHIVO_RESUMEN = "sistema.json"
# Esperas ante el límite de uso del LLM, como en la fase 2: los planes gratuitos limitan las
# peticiones y los tokens por minuto, y la fase 3 hace muchas llamadas seguidas.
ESPERAS_LIMITE_S = (30.0, 60.0, 120.0)
ESPERA_MAXIMA_S = 120.0

EstadoLogica = Literal["aceptada", "sin_logica", "error", "omitida"]


def mensaje_breve(error: object, maximo: int = 300) -> str:
    """El mensaje de un error para el resumen y el dashboard: una línea y sin el cuerpo de la
    respuesta del proveedor del LLM, que incluye identificadores de la cuenta (p. ej. la
    organización de Groq). «groq: error 413 de la API: Error code: 413 - {...}» queda en
    «groq: error 413 de la API».
    """
    linea = (str(error).splitlines() or [""])[0]
    breve = re.split(r":\s*(?:Error code|\{)", linea, maxsplit=1)[0]
    return breve[:maximo].rstrip(" :")


class ErrorSistema(Exception):
    """La fase 3 no puede empezar: arquitectura sin parámetros válidos o destino ocupado."""


class EntidadGenerada(BaseModel):
    nombre: str
    ruta: str
    logica: EstadoLogica = Field(
        description="aceptada: reglas del LLM verificadas con tsc; sin_logica: ningún intento pasó "
        "y el archivo quedó como lo generó la plantilla; error: no se pudo pedir; omitida: no se "
        "generó (sin compilación o el servicio falló antes)"
    )
    requisitos: list[str] = Field(default_factory=list, description="Requisitos que implementa")
    pendientes: list[str] = Field(
        default_factory=list, description="Lo que el LLM no pudo implementar en esos métodos"
    )
    intentos_logica: int = 0
    pruebas_aceptadas: int = 0
    pruebas_descartadas: int = 0
    detalle: str | None = None


class ServicioGenerado(BaseModel):
    servicio: str
    carpeta: str = Field(description="Carpeta del servicio, relativa a la del sistema")
    puerto: int
    base_datos: str
    prefijo: str
    entidades: list[EntidadGenerada] = Field(default_factory=list)
    archivos: int = 0
    estructura_valida: bool = False
    problemas_estructura: list[str] = Field(default_factory=list)
    dependencias_permitidas: bool | None = None
    problemas_dependencias: list[str] = Field(default_factory=list)
    dependencias_compartidas: bool = False
    compila: bool | None = Field(default=None, description="None si no se compiló")
    errores_tsc: list[str] = Field(default_factory=list)
    error: str | None = Field(default=None, description="Por qué el servicio no se completó")

    @computed_field
    @property
    def completo(self) -> bool:
        """Generado, con la estructura de la plantilla, compilando (si se compiló) y sin entidades
        cuya lógica no se pudo pedir. Una entidad «sin_logica» sí cuenta: ningún intento pasó y
        queda, sin reglas, para revisión."""
        return (
            self.error is None
            and self.estructura_valida
            and self.compila is not False
            and all(e.logica != "error" for e in self.entidades)
        )


class ResultadoSistema(BaseModel):
    """Resumen de la fase 3: se guarda en <destino>/sistema.json y se muestra en el dashboard."""

    documento: str
    carpeta: str = Field(description="Carpeta con los servicios generados")
    compilado: bool = Field(description="Se instalaron las dependencias y se compiló con tsc")
    servicios: list[ServicioGenerado]
    advertencias: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def completos(self) -> int:
        return sum(s.completo for s in self.servicios)


Avance = Callable[[str, float | None], None]
ContextoDe = Callable[[Any], ContextoGraphRAG]
Instalador = Callable[[Path], None]


def _sin_aviso(mensaje: str, progreso: float | None = None) -> None:
    del mensaje, progreso


def _nada() -> None:
    return None


class LLMConEsperas:
    """El proveedor del LLM, pero esperando y reintentando cuando ninguno está disponible.

    La cadena de proveedores aparta durante un tiempo al que alcanzó su límite; si los aparta a
    todos, aquí se espera lo que pide el proveedor (como mucho ESPERA_MAXIMA_S) y se reintenta. La
    cuota diaria no se espera. Si una llamada agota todas las esperas, las siguientes fallan sin
    esperar: el LLM no se va a recuperar a tiempo y la fase no debe quedarse horas parada.
    """

    def __init__(
        self,
        llm: ProveedorLLM,
        esperar: Callable[[float], None] = time.sleep,
        avisar: Callable[[str], None] | None = None,
        comprobar_cancelacion: Callable[[], None] = lambda: None,
        esperas_s: tuple[float, ...] = ESPERAS_LIMITE_S,
    ) -> None:
        self._llm = llm
        self._esperar = esperar
        self._avisar = avisar or (lambda mensaje: None)
        self._comprobar = comprobar_cancelacion
        self._esperas = esperas_s
        self.agotado = False

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):  # noqa: ANN001, ANN201
        if self.agotado:
            raise ErrorProveedorLLM(
                "El LLM no está disponible: se agotaron las esperas en un servicio anterior"
            )
        for numero in range(len(self._esperas) + 1):
            try:
                return self._llm.generar_estructurado(prompt, esquema, nivel, sistema)
            except ErrorProveedorLLM as error:
                diario = isinstance(error, ErrorLimiteLLM) and error.diario
                if diario or numero == len(self._esperas):
                    self.agotado = True
                    raise
                pedida = error.espera_s if isinstance(error, ErrorLimiteLLM) else None
                espera = min(max(pedida or self._esperas[numero], 5.0), ESPERA_MAXIMA_S)
                self._avisar(f"{mensaje_breve(error)}: se reintenta en {espera:.0f} s")
                self._esperar(espera)
                self._comprobar()  # una cancelación durante la espera no gasta otra llamada
        raise AssertionError("inalcanzable")

    def __getattr__(self, nombre: str):  # noqa: ANN204
        return getattr(self._llm, nombre)


# --- Dependencias compartidas ----------------------------------------------------------------


def huella_del_lock(carpeta: Path) -> str:
    """Huella del package-lock.json sin el nombre del servicio: igual en todos los generados."""
    lock = json.loads((carpeta / "package-lock.json").read_text(encoding="utf-8"))
    lock["name"] = ""
    lock.get("packages", {}).get("", {})["name"] = ""
    texto = json.dumps(lock, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def enlazar_directorio(enlace: Path, destino: Path) -> None:
    """`enlace` apunta a `destino`: unión de directorios en Windows (no pide permisos), enlace
    simbólico en los demás sistemas."""
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(destino.resolve()), str(enlace))
    else:
        enlace.symlink_to(destino.resolve(), target_is_directory=True)


def instalar_compartidas(carpeta: Path, raiz: Path) -> Path:
    """Instala (una vez) las dependencias del lock de `carpeta` en `raiz/<huella>/node_modules`.

    La instalación se hace con `npm ci --ignore-scripts` sobre el package.json y el lock del
    servicio, ya comprobados contra la lista permitida. Si otra ejecución ya las instaló con el
    mismo lock, se reutilizan.
    """
    huella = huella_del_lock(carpeta)
    compartida = raiz / huella
    modulos = compartida / "node_modules"
    lista = compartida / ".instalado"
    if lista.is_file() and modulos.is_dir():
        return modulos
    shutil.rmtree(compartida, ignore_errors=True)
    compartida.mkdir(parents=True)
    for archivo in ("package.json", "package-lock.json", ".npmrc"):
        shutil.copyfile(carpeta / archivo, compartida / archivo)
    proceso = _ejecutar(
        ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], compartida, 900
    )
    if proceso.returncode != 0:
        raise ErrorLogica(f"npm ci falló: {proceso.stderr.strip()[-500:]}")
    lista.write_text(huella, encoding="utf-8")
    return modulos


# --- Fase 3 ------------------------------------------------------------------------------------


def _requisitos_de(servicio: Any, modelo: Any) -> list[Any]:
    ids = set(servicio.requisitos)
    return [r for r in modelo.requisitos if r.id in ids]


def _resumen_inicial(parametros: ParametrosServicio) -> ServicioGenerado:
    return ServicioGenerado(
        servicio=parametros.servicio,
        carpeta=parametros.servicio,
        puerto=parametros.puerto,
        base_datos=parametros.base_datos,
        prefijo=parametros.prefijo,
        entidades=[
            EntidadGenerada(nombre=e.nombre, ruta=e.ruta, logica="omitida")
            for e in parametros.entidades
        ],
    )


def generar_sistema(
    arquitectura: Any,
    modelo: Any,
    destino: Path,
    llm: ProveedorLLM,
    *,
    documento: str = "",
    contexto_de: ContextoDe | None = None,
    compilar_servicios: bool = True,
    con_logica: bool = True,
    con_pruebas: bool = True,
    dependencias: Path | None = None,
    avance: Avance = _sin_aviso,
    comprobar_cancelacion: Callable[[], None] = _nada,
    esperar: Callable[[float], None] = time.sleep,
) -> ResultadoSistema:
    """Genera en `destino` un microservicio por cada servicio de `arquitectura` (un Arquitectura).

    `modelo` es el ModeloRequisitos de la fase 1. `contexto_de(servicio)` da el contexto GraphRAG
    de un servicio (por defecto, vacío). Sin `compilar_servicios` no se instala nada, no se compila
    y no hay pruebas: la lógica solo pasa el análisis del código. `dependencias` es la carpeta de
    las dependencias compartidas (por defecto, `destino/.dependencias`). `esperar` hace las
    esperas por el límite de uso del LLM (la API pasa una que se corta al cancelar).
    """
    try:
        parametros = parametros_de_arquitectura(arquitectura)
    except ErrorParametros as error:
        raise ErrorSistema(
            "La arquitectura no se puede convertir en parámetros de la plantilla: "
            + "; ".join(error.problemas)
        ) from error
    if destino.exists() and any(destino.iterdir()):
        raise ErrorSistema(f"{destino.as_posix()} ya existe y no está vacía")
    destino.mkdir(parents=True, exist_ok=True)
    especificaciones = destino / "especificaciones"
    especificaciones.mkdir()
    raiz_dependencias = dependencias or destino / CARPETA_DEPENDENCIAS
    contexto_de = contexto_de or (lambda servicio: contexto_vacio())
    llm = LLMConEsperas(
        llm,
        esperar=esperar,
        avisar=lambda mensaje: avance(mensaje, None),
        comprobar_cancelacion=comprobar_cancelacion,
    )

    resultado = ResultadoSistema(
        documento=documento,
        carpeta=destino.as_posix(),
        compilado=compilar_servicios,
        servicios=[_resumen_inicial(p) for p in parametros.servicios],
        advertencias=list(parametros.advertencias),
    )
    total = len(parametros.servicios)
    por_nombre = {s.nombre: s for s in arquitectura.servicios}

    for indice, (params, resumen) in enumerate(
        zip(parametros.servicios, resultado.servicios, strict=True)
    ):
        servicio = por_nombre[params.servicio]
        requisitos = _requisitos_de(servicio, modelo)

        def paso(
            mensaje: str, fraccion: float, indice: int = indice, nombre: str = params.servicio
        ) -> None:
            avance(f"{nombre} ({indice + 1}/{total}): {mensaje}", (indice + fraccion) / total)

        try:
            _generar_un_servicio(
                params,
                servicio,
                requisitos,
                resumen,
                destino,
                especificaciones,
                llm,
                contexto_de,
                compilar_servicios=compilar_servicios,
                con_logica=con_logica,
                con_pruebas=con_pruebas,
                raiz_dependencias=raiz_dependencias,
                paso=paso,
                comprobar_cancelacion=comprobar_cancelacion,
            )
        except (ErrorLLM, ErrorLogica, ErrorPlantilla, ErrorDependencias, ValidationError) as error:
            resumen.error = mensaje_breve(error, 500)
            paso(f"no se completó: {resumen.error}", 1.0)
        _guardar(resultado, destino)

    return resultado


def _guardar(resultado: ResultadoSistema, destino: Path) -> None:
    (destino / ARCHIVO_RESUMEN).write_text(resultado.model_dump_json(indent=2), encoding="utf-8")


def _generar_un_servicio(
    params: ParametrosServicio,
    servicio: Any,
    requisitos: list[Any],
    resumen: ServicioGenerado,
    destino: Path,
    especificaciones: Path,
    llm: ProveedorLLM,
    contexto_de: ContextoDe,
    *,
    compilar_servicios: bool,
    con_logica: bool,
    con_pruebas: bool,
    raiz_dependencias: Path,
    paso: Callable[[str, float], None],
    comprobar_cancelacion: Callable[[], None],
) -> None:
    comprobar_cancelacion()
    contexto = contexto_de(servicio)
    paso(f"el LLM propone los campos de {len(params.entidades)} entidades", 0.02)
    prompt = prompt_especificacion(servicio, requisitos, contexto)
    respuesta = prompt.enviar(llm)
    spec = especificacion(params, respuesta)
    datos = spec.para_plantilla()
    (especificaciones / f"{params.servicio}.yml").write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    comprobar_cancelacion()
    carpeta = generar_servicio(datos, destino)
    estructura = validar_estructura(carpeta, datos)
    resumen.archivos = len(estructura.archivos)
    resumen.estructura_valida = estructura.valida
    paso(f"generado con la plantilla: {resumen.archivos} archivos, estructura validada", 0.15)

    problemas = verificar_servicio(carpeta)
    resumen.problemas_dependencias = [str(p) for p in problemas]
    resumen.dependencias_permitidas = not problemas
    if problemas:
        raise ErrorDependencias(f"Dependencias no permitidas: {resumen.problemas_dependencias[0]}")

    if compilar_servicios:
        comprobar_cancelacion()
        paso("instalando dependencias y generando el cliente de Prisma", 0.2)
        modulos = instalar_compartidas(carpeta, raiz_dependencias)
        enlazar_directorio(carpeta / "node_modules", modulos)
        resumen.dependencias_compartidas = True
        preparar(carpeta)
        resumen.errores_tsc = compilar(carpeta)
        resumen.compila = not resumen.errores_tsc
        paso("compila con tsc" if resumen.compila else "no compila con tsc", 0.3)
        if not resumen.compila:
            raise ErrorLogica(f"El servicio generado no compila: {resumen.errores_tsc[0]}")

    if con_logica:
        _logica_y_pruebas(
            carpeta,
            spec,
            requisitos,
            contexto,
            llm,
            resumen,
            compilar_servicios=compilar_servicios,
            con_pruebas=con_pruebas,
            paso=paso,
            comprobar_cancelacion=comprobar_cancelacion,
        )
        if compilar_servicios:
            paso("comprobando con tsc la lógica y las pruebas", 0.98)
            _compilar_al_final(carpeta, resumen)

    final = validar_estructura(carpeta, datos)
    resumen.estructura_valida = final.valida
    resumen.problemas_estructura = final.problemas
    paso("listo" if resumen.completo else "terminado con problemas", 1.0)


def _compilar_al_final(carpeta: Path, resumen: ServicioGenerado) -> None:
    """tsc sobre el servicio terminado, como el Gate 1.

    Las pruebas del LLM se verifican con Jest, y ts-jest no comprueba los tipos
    (isolatedModules): pasan en Jest pero no en `tsc --noEmit`, y el Gate 1 rechazaría el servicio.
    El archivo de pruebas de una entidad que no compila se descarta, con el motivo; si después
    sigue sin compilar, el servicio queda como «no compila».
    """
    errores = compilar(carpeta)
    for entidad in resumen.entidades:
        relativo = f"src/{entidad.nombre.replace('_', '-')}.reglas.spec.ts"
        propios = [e for e in errores if Path(e.split("(", 1)[0]).as_posix().endswith(relativo)]
        if not propios or not (carpeta / relativo).is_file():
            continue
        (carpeta / relativo).unlink()
        entidad.pruebas_descartadas += entidad.pruebas_aceptadas
        entidad.pruebas_aceptadas = 0
        entidad.detalle = (
            f"Pruebas descartadas: no compilan con tsc ({mensaje_breve(propios[0], 200)})"
        )
    if any(e.detalle and e.detalle.startswith("Pruebas descartadas") for e in resumen.entidades):
        errores = compilar(carpeta)
    resumen.errores_tsc = errores
    resumen.compila = not errores


def _logica_y_pruebas(
    carpeta: Path,
    spec: Any,
    requisitos: list[Any],
    contexto: ContextoGraphRAG,
    llm: ProveedorLLM,
    resumen: ServicioGenerado,
    *,
    compilar_servicios: bool,
    con_pruebas: bool,
    paso: Callable[[str, float], None],
    comprobar_cancelacion: Callable[[], None],
) -> None:
    registro_logica = carpeta / "logica"
    registro_pruebas = carpeta / "pruebas"
    registro_logica.mkdir(exist_ok=True)
    cantidad = len(resumen.entidades)
    for numero, entidad in enumerate(resumen.entidades):
        comprobar_cancelacion()
        fraccion = 0.3 + 0.7 * numero / max(cantidad, 1)
        paso(f"lógica de negocio de {entidad.nombre}", fraccion)
        try:
            logica = generar_logica(
                carpeta,
                spec,
                entidad.nombre,
                requisitos,
                contexto,
                llm,
                compilador=compilar if compilar_servicios else None,
            )
        except (ErrorLLM, ErrorLogica) as error:
            entidad.logica = "error"
            entidad.detalle = mensaje_breve(error)
            continue
        (registro_logica / f"{entidad.nombre}.json").write_text(
            logica.model_dump_json(indent=2), encoding="utf-8"
        )
        entidad.intentos_logica = len(logica.intentos)
        if not (logica.aprobada and logica.logica):
            entidad.logica = "sin_logica"
            entidad.detalle = "Ningún intento pasó el análisis y tsc: queda para revisión"
            continue
        entidad.logica = "aceptada"
        entidad.requisitos = list(logica.logica.requisitos)
        entidad.pendientes = list(logica.logica.pendientes)

        if not (compilar_servicios and con_pruebas):
            continue
        comprobar_cancelacion()
        paso(f"pruebas Jest de las reglas de {entidad.nombre}", fraccion + 0.35 / max(cantidad, 1))
        try:
            pruebas = generar_pruebas(carpeta, spec, entidad.nombre, logica.logica, requisitos, llm)
        except (ErrorLLM, ErrorLogica) as error:
            entidad.detalle = f"Pruebas: {mensaje_breve(error, 280)}"
            continue
        registro_pruebas.mkdir(exist_ok=True)
        (registro_pruebas / f"{entidad.nombre}.json").write_text(
            pruebas.model_dump_json(indent=2), encoding="utf-8"
        )
        entidad.pruebas_aceptadas = pruebas.aceptadas
        entidad.pruebas_descartadas = len(pruebas.descartadas)
