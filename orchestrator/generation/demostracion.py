"""Demostración de la fase 3 con un solo comando (`framework servicio demo`).

Encadena lo que el motor ya hace al generar un servicio, sin LLM ni Docker, para ver de una vez
hasta dónde llega la fase 3:

1. Parámetros de cada servicio de la arquitectura (nombre, puerto, base de datos, entidades, rutas).
2. Generación de un servicio con la plantilla Copier, a partir del ejemplo `pedidos.yml`.
3. Validación de la estructura generada.
4. Dependencias npm contra la lista permitida.
5. Control negativo de la estructura: se le quita un control de seguridad a una copia y la
   validación tiene que detectarlo.
6. Control negativo de las dependencias: se le añade un paquete inventado a una copia y la lista
   permitida tiene que rechazarlo.
7. Opcional (`--compilar`): instalar, generar el cliente de Prisma y compilar con `tsc`.

Los pasos 5 y 6 comprueban que las defensas funcionan: si no detectan el problema, la demostración
falla. Todo se escribe en `destino`, que la demostración marca con un archivo propio para no borrar
nunca una carpeta que no creó.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from orchestrator.architecture import Arquitectura
from orchestrator.generation.dependencias import (
    RUTA_LISTA,
    ErrorDependencias,
    cargar_lista,
    verificar_servicio,
)
from orchestrator.generation.estructura import RUTA_PLANTILLA, arbol, validar_estructura
from orchestrator.generation.parametros import ErrorParametros, parametros_de_arquitectura
from orchestrator.generation.plantilla import ErrorPlantilla, generar_servicio, leer_especificacion

RAIZ = Path(__file__).resolve().parents[2]
ARQUITECTURA_POR_DEFECTO = (
    RAIZ / "docs" / "adr" / "entrada" / "01_tienda_en_linea.arquitectura.json"
)
EJEMPLO = RUTA_PLANTILLA / "ejemplos" / "pedidos.yml"
MARCA = ".demostracion-del-framework"

# Lo que la fase 3 todavía no hace en el motor, para que la demostración lo diga con claridad.
PENDIENTE = (
    "Generar de una vez todos los servicios de la arquitectura (hoy se genera uno por uno).",
    "El Security Gate 1 sobre los servicios generados.",
    "La trazabilidad requisito -> servicio -> archivo en Neo4j.",
    "La fase 3 en la API y el dashboard (hoy POST /ejecuciones solo acepta las fases 1 y 2).",
)


class ErrorDemostracion(Exception):
    """La demostración no puede empezar (carpeta ajena, arquitectura ilegible...)."""


@dataclass
class Paso:
    titulo: str = ""
    ok: bool = True
    lineas: list[str] = field(default_factory=list)


@dataclass
class _Contexto:
    arquitectura: Path
    destino: Path
    mostrar_arbol: bool
    especificacion: dict | None = None
    servicio: Path | None = None
    roto: Path | None = None
    malo: Path | None = None


def preparar_destino(destino: Path) -> None:
    """Crea `destino` o lo reutiliza si lo creó una demostración anterior, nunca una ajena."""
    if destino.exists():
        if not destino.is_dir():
            raise ErrorDemostracion(f"{destino.as_posix()} no es una carpeta")
        if not (destino / MARCA).is_file() and any(destino.iterdir()):
            raise ErrorDemostracion(
                f"{destino.as_posix()} ya existe y no lo creó la demostración: usa otra carpeta "
                "con --destino para no borrar nada que no sea suyo"
            )
    destino.mkdir(parents=True, exist_ok=True)
    (destino / MARCA).write_text("Carpeta de `framework servicio demo`: se puede borrar.\n")


def _borrar(carpeta: Path | None) -> None:
    if carpeta is not None and carpeta.exists():
        shutil.rmtree(carpeta, ignore_errors=True)


# --- Pasos ---------------------------------------------------------------------------------------


def _parametros(ctx: _Contexto) -> Paso:
    paso = Paso()
    try:
        arq = Arquitectura.model_validate_json(ctx.arquitectura.read_bytes())
    except Exception as error:  # noqa: BLE001 - OSError o ValidationError: se informa y se sigue
        paso.ok = False
        paso.lineas.append(f"No se pudo leer {ctx.arquitectura.name}: {error}")
        return paso
    try:
        parametros = parametros_de_arquitectura(arq)
    except ErrorParametros as error:
        paso.ok = False
        paso.lineas.append("La arquitectura no se puede parametrizar:")
        paso.lineas += [f"  - {problema}" for problema in error.problemas]
        return paso
    paso.lineas.append(f"{len(parametros.servicios)} servicios en {ctx.arquitectura.name}")
    paso.lineas.append(f"  {'servicio':<12} {'puerto':<7} {'base de datos':<16} entidades")
    for s in parametros.servicios:
        entidades = ", ".join(e.nombre for e in s.entidades) or "(las propondrá el LLM)"
        paso.lineas.append(f"  {s.servicio:<12} {s.puerto:<7} {s.base_datos:<16} {entidades}")
    paso.lineas += [f"Advertencia: {a}" for a in parametros.advertencias]
    return paso


def _generar(ctx: _Contexto) -> Paso:
    paso = Paso()
    try:
        ctx.especificacion = leer_especificacion(EJEMPLO)
        nombre = str(ctx.especificacion["servicio"])
        # Solo se borra lo que la demostración creó antes, dentro de su propia carpeta.
        for sufijo in ("", "-roto", "-malo"):
            _borrar(ctx.destino / f"{nombre}{sufijo}")
        ctx.servicio = generar_servicio(ctx.especificacion, ctx.destino)
    except ErrorPlantilla as error:
        paso.ok = False
        paso.lineas.append(str(error))
        return paso
    nombre = ctx.servicio.name
    ctx.roto, ctx.malo = ctx.destino / f"{nombre}-roto", ctx.destino / f"{nombre}-malo"
    archivos = sum(1 for p in ctx.servicio.rglob("*") if p.is_file())
    paso.lineas.append(f"Servicio {nombre} en {ctx.servicio.as_posix()}: {archivos} archivos")
    puerto = ctx.especificacion["puerto"]
    paso.lineas.append(f"Es el ejemplo fijo de la plantilla (puerto {puerto}); en el flujo real")
    paso.lineas.append(
        "  la especificación sale de los parámetros del paso 1 y del LLM (entidades)."
    )
    paso.lineas.append(
        "Trae de serie: guard de Keycloak, ValidationPipe, Helmet, filtro de errores,"
    )
    paso.lineas.append("  configuración por entorno, Dockerfile distroless y pruebas Jest.")
    return paso


def _validar(ctx: _Contexto) -> Paso:
    paso = Paso()
    assert ctx.servicio is not None
    resultado = validar_estructura(ctx.servicio, ctx.especificacion)
    paso.ok = resultado.valida
    if ctx.mostrar_arbol:
        paso.lineas += arbol(resultado.archivos, ctx.servicio.name).splitlines()
    if resultado.valida:
        paso.lineas.append(f"Estructura válida; rutas: {', '.join(resultado.rutas)}")
    else:
        paso.lineas += [f"  - {problema}" for problema in resultado.problemas]
    return paso


def _dependencias(ctx: _Contexto) -> Paso:
    paso = Paso()
    assert ctx.servicio is not None
    try:
        problemas = verificar_servicio(ctx.servicio, cargar_lista(RUTA_LISTA))
    except ErrorDependencias as error:
        paso.ok = False
        paso.lineas.append(str(error))
        return paso
    paso.ok = not problemas
    paso.lineas += (
        [f"  - {p}" for p in problemas]
        if problemas
        else [
            "package.json y package-lock.json: todas las dependencias están en la lista permitida"
        ]
    )
    return paso


def _control_estructura(ctx: _Contexto) -> Paso:
    paso = Paso()
    assert ctx.servicio is not None and ctx.roto is not None
    shutil.copytree(ctx.servicio, ctx.roto)
    (ctx.roto / "src" / "seguridad" / "jwt-auth.guard.ts").unlink()
    (ctx.roto / "Dockerfile").unlink()
    resultado = validar_estructura(ctx.roto)
    detectado = any("jwt-auth.guard.ts" in p for p in resultado.problemas) and any(
        "Dockerfile" in p for p in resultado.problemas
    )
    paso.ok = detectado
    paso.lineas.append(
        "A una copia se le quitaron src/seguridad/jwt-auth.guard.ts y el Dockerfile."
    )
    paso.lineas += [f"  - {p}" for p in resultado.problemas]
    paso.lineas.append(
        "Detectado: un servicio sin sus controles de seguridad no se daría por válido."
        if detectado
        else "NO se detectó: la validación de la estructura no protege."
    )
    return paso


def _control_dependencias(ctx: _Contexto) -> Paso:
    paso = Paso()
    assert ctx.servicio is not None and ctx.malo is not None
    shutil.copytree(ctx.servicio, ctx.malo)
    ruta = ctx.malo / "package.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["dependencies"]["expres-validator-pro"] = "^1.0.0"
    ruta.write_text(json.dumps(datos, indent=2) + "\n", encoding="utf-8")
    problemas = verificar_servicio(ctx.malo, cargar_lista(RUTA_LISTA))
    rechazado = any("expres-validator-pro" in str(p) for p in problemas)
    paso.ok = rechazado
    paso.lineas.append("A una copia se le añadió «expres-validator-pro» (un paquete inventado).")
    paso.lineas += [f"  - {p}" for p in problemas]
    paso.lineas.append(
        "Rechazado: nunca se llegaría a descargar."
        if rechazado
        else "NO se rechazó: la lista de dependencias permitidas no protege."
    )
    return paso


def _compilar(ctx: _Contexto) -> Paso:
    from orchestrator.generation.logica import ErrorLogica, compilar, preparar

    paso = Paso()
    assert ctx.servicio is not None
    try:
        preparar(ctx.servicio)
        errores = compilar(ctx.servicio)
    except ErrorLogica as error:
        paso.ok = False
        paso.lineas.append(str(error))
        return paso
    paso.ok = not errores
    paso.lineas += (
        [f"  - {e}" for e in errores] if errores else ["El servicio compila sin errores (tsc)."]
    )
    return paso


# --- Ejecución -----------------------------------------------------------------------------------

_PASOS: list[tuple[str, Callable[[_Contexto], Paso]]] = [
    ("Parámetros de cada servicio, calculados desde la arquitectura (sin LLM)", _parametros),
    (f"Generar un servicio con la plantilla Copier ({EJEMPLO.name})", _generar),
    ("Validar la estructura generada contra la especificación", _validar),
    ("Dependencias npm contra la lista permitida (slopsquatting)", _dependencias),
    ("Control: quitar un control de seguridad tiene que detectarse", _control_estructura),
    ("Control: un paquete npm inventado tiene que rechazarse", _control_dependencias),
]
_PASO_COMPILAR = (
    "Instalar, generar el cliente de Prisma y compilar con tsc (tarda unos minutos)",
    _compilar,
)


def demostrar(
    arquitectura: Path,
    destino: Path,
    compilar: bool = False,
    mostrar_arbol: bool = False,
    al_empezar: Callable[[int, int, str], None] | None = None,
    al_terminar: Callable[[Paso], None] | None = None,
) -> list[Paso]:
    """Ejecuta los pasos en orden y devuelve sus resultados.

    Si falla la generación, el resto de pasos depende de ella y se omiten. Las copias de los
    controles negativos se borran siempre al terminar.
    """
    preparar_destino(destino)
    ctx = _Contexto(arquitectura, destino, mostrar_arbol)
    pasos = [*_PASOS, _PASO_COMPILAR] if compilar else list(_PASOS)
    resultados: list[Paso] = []
    try:
        for numero, (titulo, ejecutar) in enumerate(pasos, start=1):
            if ctx.servicio is None and ejecutar not in (_parametros, _generar):
                break  # sin servicio generado, los demás pasos no tienen sobre qué trabajar
            if al_empezar:
                al_empezar(numero, len(pasos), titulo)
            paso = ejecutar(ctx)
            paso.titulo = titulo
            resultados.append(paso)
            if al_terminar:
                al_terminar(paso)
    finally:
        _borrar(ctx.roto)
        _borrar(ctx.malo)
    return resultados
