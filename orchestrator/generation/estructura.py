"""Validación de la estructura de un servicio generado con la plantilla (fase 3, #69).

Después de Copier, y antes de que el LLM, el pipeline o una persona toquen el servicio, se
comprueba que lo generado es lo que pedía su especificación:

- **El árbol de archivos** es exactamente el de la plantilla para esas entidades: ni falta ni
  sobra nada. La lista sale de la propia plantilla (cada archivo de `plantilla/`, y los de
  `{% yield %}` una vez por entidad), así que no se desincroniza; además, los archivos de los
  controles de seguridad deben estar siempre, aunque alguien los quite de la plantilla.
- **Nada quedó sin renderizar** (`{{` o `{%`) y no hay enlaces simbólicos.
- **El contenido clave coincide con los parámetros**: el nombre del paquete, las rutas de cada
  controlador (`/api/<servicio>/<entidad>`), los controladores y servicios del módulo con sus
  controles globales (guard, ValidationPipe y filtro de errores), un modelo Prisma por entidad con
  su tabla, las marcas del punto de extensión del LLM, y el puerto, la audiencia y la base de datos
  del Dockerfile, de main.ts y de .env.example.

Lo que crean después la instalación, la compilación, las pruebas y el generador de lógica
(node_modules, dist, coverage, el cliente de Prisma, openapi/ y logica/) no cuenta como sobrante.

Solo usa la biblioteca estándar y PyYAML, así que el CI lo ejecuta como script, sin el motor:

    python orchestrator/generation/estructura.py salida/servicios/pedidos
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RUTA_PLANTILLA = Path(__file__).resolve().parents[2] / "templates" / "microservicio_nestjs"

# Carpetas y archivos que crean la instalación, la compilación, las pruebas y el generador de
# lógica de negocio: no los genera la plantilla.
_PRODUCIDOS_DESPUES = (
    "node_modules/",
    "dist/",
    "coverage/",
    "src/generated/",
    "openapi/",
    "logica/",
)
_ARCHIVOS_DESPUES = {".env"}

# Los controles de seguridad del servicio: deben estar aunque alguien los quite de la plantilla.
ARCHIVOS_DE_SEGURIDAD = (
    ".npmrc",
    ".dockerignore",
    ".gitignore",
    "Dockerfile",
    "package-lock.json",
    "src/configuracion/entorno.ts",
    "src/seguridad/filtro-errores.ts",
    "src/seguridad/http.ts",
    "src/seguridad/jwt-auth.guard.ts",
    "src/seguridad/validacion-global.ts",
)

_YIELD = re.compile(r"\{%\s*yield\s+entidad\s+from\s+modelo\s*%\}(.*?)\{%\s*endyield\s*%\}")


def clase_de(identificador: str) -> str:
    """El nombre de la clase, como `servicio_clase` y `clase` de copier.yml."""
    return "".join(parte.capitalize() for parte in identificador.split("_"))


def archivo_de(identificador: str) -> str:
    """El nombre de archivo y de ruta, como `servicio_archivo` y `archivo` de copier.yml."""
    return identificador.replace("_", "-")


@dataclass
class ResultadoEstructura:
    """El árbol generado, las rutas que expone y los problemas encontrados."""

    archivos: list[str]
    rutas: list[str] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return not self.problemas


def _nombres(especificacion: dict[str, Any]) -> tuple[str, list[str]]:
    servicio = especificacion["servicio"]
    entidades = [e["nombre"] for e in especificacion["entidades"]]
    return servicio, entidades


def archivos_esperados(
    especificacion: dict[str, Any], plantilla: Path = RUTA_PLANTILLA
) -> set[str]:
    """Los archivos que debe generar la plantilla para `especificacion`, relativos al servicio."""
    servicio, entidades = _nombres(especificacion)
    raiz = plantilla / "plantilla"
    esperados: set[str] = set()
    for ruta in raiz.rglob("*"):
        if not ruta.is_file():
            continue
        relativa = ruta.relative_to(raiz).as_posix()
        if relativa.endswith(".jinja"):
            relativa = relativa[: -len(".jinja")]
        relativa = relativa.replace("{{_copier_conf.answers_file}}", ".copier-answers.yml")
        relativa = relativa.replace("{{servicio_archivo}}", archivo_de(servicio))
        if por_entidad := _YIELD.search(relativa):
            for entidad in entidades:
                nombre = por_entidad.group(1).replace("{{ entidad.archivo }}", archivo_de(entidad))
                esperados.add(
                    relativa[: por_entidad.start()] + nombre + relativa[por_entidad.end() :]
                )
        else:
            esperados.add(relativa)
    return esperados


def _generados(carpeta: Path, problemas: list[str]) -> list[str]:
    archivos = []
    for ruta in sorted(carpeta.rglob("*")):
        relativa = ruta.relative_to(carpeta).as_posix()
        if relativa.startswith(_PRODUCIDOS_DESPUES) or relativa in _ARCHIVOS_DESPUES:
            continue
        if ruta.is_symlink():
            problemas.append(f"{relativa} es un enlace simbólico")
        elif ruta.is_file():
            archivos.append(relativa)
    return archivos


def _leer(carpeta: Path, relativa: str) -> str:
    try:
        return (carpeta / relativa).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _contenido(carpeta: Path, especificacion: dict[str, Any], problemas: list[str]) -> list[str]:
    """Comprueba el contenido clave y devuelve las rutas que declaran los controladores."""
    servicio, entidades = _nombres(especificacion)
    puerto = especificacion.get("puerto", 3000)
    base_datos = especificacion.get("base_datos", f"{servicio}_db")
    svc = archivo_de(servicio)

    def exigir(relativa: str, fragmento: str, motivo: str) -> None:
        if fragmento not in _leer(carpeta, relativa):
            problemas.append(f"{relativa}: {motivo} (falta «{fragmento}»)")

    exigir("package.json", f'"name": "{servicio}"', "el paquete no lleva el nombre del servicio")
    exigir("Dockerfile", f"EXPOSE {puerto}", "la imagen no expone el puerto del servicio")
    exigir("Dockerfile", "USER 65532:65532", "la imagen no corre con el usuario sin privilegios")
    exigir(
        "src/main.ts",
        f"leerEntorno(process.env, {puerto})",
        "main.ts no usa el puerto del servicio",
    )
    exigir(".env.example", f"PORT={puerto}", "el puerto de ejemplo no es el del servicio")
    exigir(
        ".env.example", f"KEYCLOAK_AUDIENCE={servicio}-api", "la audiencia no es la del servicio"
    )
    exigir(".env.example", f"/{base_datos}\n", "la base de datos no es la del servicio")

    modulo = f"src/{svc}.module.ts"
    for control in (
        "{ provide: APP_GUARD, useClass: JwtAuthGuard }",
        "{ provide: APP_PIPE, useFactory: crearValidacionGlobal }",
        "{ provide: APP_FILTER, useClass: FiltroErrores }",
    ):
        exigir(modulo, control, "el módulo no registra un control global")
    texto_modulo = _leer(carpeta, modulo)
    controladores = re.search(r"controllers: \[([^\]]*)\]", texto_modulo)
    declarados = sorted(
        c.strip() for c in (controladores.group(1) if controladores else "").split(",") if c.strip()
    )
    esperados = sorted(f"{clase_de(e)}Controller" for e in entidades)
    if declarados != esperados:
        problemas.append(f"{modulo}: los controladores son {declarados}, no {esperados}")

    esquema = _leer(carpeta, "prisma/schema.prisma")
    modelos = sorted(re.findall(r"^model (\w+) \{", esquema, flags=re.M))
    if modelos != sorted(clase_de(e) for e in entidades):
        problemas.append(
            f"prisma/schema.prisma: los modelos son {modelos}, no los de las entidades"
        )

    rutas = []
    for entidad in entidades:
        archivo = archivo_de(entidad)
        exigir(modulo, f"    {clase_de(entidad)}Service,\n", "el módulo no registra un servicio")
        exigir("prisma/schema.prisma", f'@@map("{entidad}")', "una entidad no tiene su tabla")
        controlador = _leer(carpeta, f"src/{archivo}.controller.ts")
        declaradas = re.findall(r"@Controller\('([^']*)'\)", controlador)
        if declaradas != [f"{svc}/{archivo}"]:
            problemas.append(
                f"src/{archivo}.controller.ts: declara {declaradas}, no ['{svc}/{archivo}']"
            )
        rutas += [f"/api/{r}" for r in declaradas]
        servicio_ts = _leer(carpeta, f"src/{archivo}.service.ts")
        for lado in ("inicio", "fin"):
            marca = f"// @framework:logica-negocio:{lado} {entidad}"
            if servicio_ts.count(marca) != 1:
                problemas.append(f"src/{archivo}.service.ts: la marca «{marca}» no aparece una vez")
    return rutas


def validar_estructura(
    carpeta: Path,
    especificacion: dict[str, Any] | None = None,
    plantilla: Path = RUTA_PLANTILLA,
) -> ResultadoEstructura:
    """Valida el servicio de `carpeta` contra su especificación.

    Sin `especificacion`, usa las respuestas que guardó Copier en `.copier-answers.yml`.
    """
    problemas: list[str] = []
    if especificacion is None:
        try:
            especificacion = yaml.safe_load(_leer(carpeta, ".copier-answers.yml")) or {}
        except yaml.YAMLError:
            especificacion = {}
    if not isinstance(especificacion.get("servicio"), str) or not isinstance(
        especificacion.get("entidades"), list
    ):
        return ResultadoEstructura(
            archivos=[],
            problemas=[
                "No hay especificación: falta .copier-answers.yml o no tiene servicio y entidades"
            ],
        )

    generados = _generados(carpeta, problemas)
    esperados = archivos_esperados(especificacion, plantilla) | set(ARCHIVOS_DE_SEGURIDAD)
    for falta in sorted(esperados - set(generados)):
        problemas.append(f"Falta {falta}")
    for sobra in sorted(set(generados) - esperados):
        problemas.append(f"Archivo inesperado: {sobra}")
    for relativa in generados:
        texto = _leer(carpeta, relativa)
        if "{{" in texto or "{%" in texto:
            problemas.append(f"{relativa} quedó sin renderizar")

    rutas = _contenido(carpeta, especificacion, problemas)
    return ResultadoEstructura(archivos=generados, rutas=rutas, problemas=problemas)


def arbol(archivos: list[str], raiz: str) -> str:
    """El árbol de archivos en texto, como `tree --charset=ascii` (también en la consola de
    Windows): carpetas primero y en orden alfabético."""
    nodos: dict[str, Any] = {}
    for archivo in archivos:
        actual = nodos
        for parte in archivo.split("/"):
            actual = actual.setdefault(parte, {})

    lineas = [f"{raiz}/"]

    def pintar(nodo: dict[str, Any], sangria: str) -> None:
        hijos = sorted(nodo.items(), key=lambda kv: (not kv[1], kv[0]))
        for indice, (nombre, contenido) in enumerate(hijos):
            ultimo = indice == len(hijos) - 1
            lineas.append(
                f"{sangria}{'`-- ' if ultimo else '|-- '}{nombre}{'/' if contenido else ''}"
            )
            if contenido:
                pintar(contenido, sangria + ("    " if ultimo else "|   "))

    pintar(nodos, "")
    carpetas = len(
        {"/".join(a.split("/")[:n]) for a in archivos for n in range(1, a.count("/") + 1)}
    )
    lineas.append(f"\n{carpetas} carpetas, {len(archivos)} archivos")
    return "\n".join(lineas)


def main(argumentos: list[str]) -> int:
    if len(argumentos) != 1:
        print("Uso: python orchestrator/generation/estructura.py <carpeta del servicio>")
        return 2
    carpeta = Path(argumentos[0])
    resultado = validar_estructura(carpeta)
    if resultado.archivos:
        print(arbol(resultado.archivos, carpeta.resolve().name))
    if resultado.rutas:
        print(f"Rutas: {', '.join(resultado.rutas)}")
    if not resultado.valida:
        print(f"Estructura inválida ({len(resultado.problemas)} problemas):")
        for problema in resultado.problemas:
            print(f"  - {problema}")
        return 1
    print("Estructura válida: coincide con la especificación del servicio.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
