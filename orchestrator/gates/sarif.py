"""Lector de archivos SARIF 2.1.0: los convierte al modelo común de hallazgos."""

import json
import re
from pathlib import Path
from typing import Any

from orchestrator.gates.hallazgos import Hallazgo, Severidad, calcular_huella

VERSION_SOPORTADA = "2.1.0"

_CWE = re.compile(r"CWE-(\d+)", re.IGNORECASE)

# Gitleaks publica datos del commit como huellas parciales; no identifican un hallazgo.
_METADATOS_DE_COMMIT = frozenset({"commitSha", "email", "author", "date", "commitMessage"})

# Nivel SARIF -> severidad, cuando la herramienta no publica una puntuación.
_SEVERIDAD_POR_NIVEL = {
    "error": Severidad.ALTA,
    "warning": Severidad.MEDIA,
    "note": Severidad.BAJA,
    "none": Severidad.INFO,
}


class ErrorSarif(Exception):
    """El archivo no es un SARIF válido o no es de la versión soportada."""


def leer_sarif(ruta: str | Path) -> list[Hallazgo]:
    """Lee un archivo SARIF y devuelve sus hallazgos; omite los resultados suprimidos."""
    ruta = Path(ruta)
    try:
        documento = json.loads(ruta.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise ErrorSarif(f"No se pudo leer {ruta}: {error}") from error
    except json.JSONDecodeError as error:
        raise ErrorSarif(f"{ruta} no contiene JSON válido: {error}") from error
    try:
        return convertir_sarif(documento)
    except ErrorSarif as error:
        raise ErrorSarif(f"{ruta}: {error}") from error


def leer_carpeta_sarif(carpeta: str | Path) -> list[Hallazgo]:
    """Lee todos los .sarif de una carpeta, en orden alfabético."""
    hallazgos: list[Hallazgo] = []
    for ruta in sorted(Path(carpeta).glob("*.sarif")):
        hallazgos.extend(leer_sarif(ruta))
    return hallazgos


def convertir_sarif(documento: Any) -> list[Hallazgo]:
    if not isinstance(documento, dict) or not isinstance(documento.get("runs"), list):
        raise ErrorSarif("falta la lista 'runs'")
    version = documento.get("version")
    if version != VERSION_SOPORTADA:
        raise ErrorSarif(f"versión SARIF no soportada: {version!r}")

    hallazgos: list[Hallazgo] = []
    for ejecucion in documento["runs"]:
        controlador = (ejecucion.get("tool") or {}).get("driver") or {}
        herramienta = str(controlador.get("name") or "desconocida").lower()
        reglas = controlador.get("rules") or []
        reglas_por_id = {r.get("id"): r for r in reglas if isinstance(r, dict)}

        for resultado in ejecucion.get("results") or []:
            if resultado.get("suppressions"):
                continue
            regla = _regla_del_resultado(resultado, reglas, reglas_por_id)
            hallazgos.append(_convertir_resultado(herramienta, resultado, regla))
    return hallazgos


def _regla_del_resultado(resultado: dict, reglas: list, reglas_por_id: dict) -> dict:
    regla_id = resultado.get("ruleId") or (resultado.get("rule") or {}).get("id")
    if regla_id in reglas_por_id:
        return reglas_por_id[regla_id]
    indice = resultado.get("ruleIndex", (resultado.get("rule") or {}).get("index"))
    if isinstance(indice, int) and 0 <= indice < len(reglas):
        return reglas[indice]
    return {}


def _convertir_resultado(herramienta: str, resultado: dict, regla: dict) -> Hallazgo:
    regla_id = str(
        resultado.get("ruleId")
        or (resultado.get("rule") or {}).get("id")
        or regla.get("id")
        or "sin-regla"
    )
    mensaje = _texto(resultado.get("message")) or _texto(regla.get("shortDescription")) or regla_id
    archivo, linea_inicio, linea_fin, fragmento = _ubicacion(resultado)

    return Hallazgo(
        herramienta=herramienta,
        regla_id=regla_id,
        mensaje=mensaje,
        severidad=_severidad(resultado, regla),
        archivo=archivo,
        linea_inicio=linea_inicio,
        linea_fin=linea_fin,
        cwe=_cwe(resultado, regla),
        huella=_huella(herramienta, regla_id, archivo, resultado, fragmento, linea_inicio),
    )


def _texto(mensaje: Any) -> str:
    if isinstance(mensaje, dict):
        return str(mensaje.get("text") or mensaje.get("markdown") or "").strip()
    return ""


def _ubicacion(resultado: dict) -> tuple[str | None, int | None, int | None, str]:
    ubicaciones = resultado.get("locations") or []
    if not ubicaciones:
        return None, None, None, ""
    fisica = ubicaciones[0].get("physicalLocation") or {}
    uri = (fisica.get("artifactLocation") or {}).get("uri")
    region = fisica.get("region") or {}
    inicio = region.get("startLine")
    inicio = inicio if isinstance(inicio, int) and inicio >= 1 else None
    fin = region.get("endLine")
    fin = fin if isinstance(fin, int) and fin >= 1 else inicio
    fragmento = str((region.get("snippet") or {}).get("text") or "")
    return _normalizar_ruta(uri), inicio, fin, fragmento


def _normalizar_ruta(uri: Any) -> str | None:
    if not isinstance(uri, str) or not uri:
        return None
    ruta = uri.replace("\\", "/")
    ruta = re.sub(r"^file:/+", "/", ruta)
    return ruta.removeprefix("./")


def _severidad(resultado: dict, regla: dict) -> Severidad:
    for propiedades in (resultado.get("properties"), regla.get("properties")):
        puntuacion = (propiedades or {}).get("security-severity")
        try:
            valor = float(puntuacion)
        except (TypeError, ValueError):
            continue
        if valor >= 9.0:
            return Severidad.CRITICA
        if valor >= 7.0:
            return Severidad.ALTA
        if valor >= 4.0:
            return Severidad.MEDIA
        if valor > 0.0:
            return Severidad.BAJA
        return Severidad.INFO

    # Según la especificación: nivel del resultado, si no el de la regla, si no "warning".
    nivel = (
        resultado.get("level")
        or (regla.get("defaultConfiguration") or {}).get("level")
        or "warning"
    )
    return _SEVERIDAD_POR_NIVEL.get(str(nivel).lower(), Severidad.MEDIA)


def _cwe(resultado: dict, regla: dict) -> list[str]:
    fuentes: list[str] = []
    for propiedades in (regla.get("properties") or {}, resultado.get("properties") or {}):
        for clave in ("tags", "cwe"):
            valor = propiedades.get(clave)
            fuentes.extend(valor if isinstance(valor, list) else [valor])
    for relacion in regla.get("relationships") or []:
        fuentes.append((relacion.get("target") or {}).get("id"))

    encontrados: list[str] = []
    for fuente in fuentes:
        for numero in _CWE.findall(str(fuente or "")):
            identificador = f"CWE-{int(numero)}"
            if identificador not in encontrados:
                encontrados.append(identificador)
    return encontrados


def _huella(
    herramienta: str,
    regla_id: str,
    archivo: str | None,
    resultado: dict,
    fragmento: str,
    linea: int | None,
) -> str:
    for clave in ("fingerprints", "partialFingerprints"):
        huellas = resultado.get(clave)
        if not isinstance(huellas, dict):
            continue
        utiles = {k: v for k, v in huellas.items() if v and k not in _METADATOS_DE_COMMIT}
        if utiles:
            primera = sorted(utiles)[0]
            return f"{herramienta}:{primera}:{utiles[primera]}"
    # Sin huella publicada: el fragmento de código resiste mejor que la línea a los
    # desplazamientos entre iteraciones, salvo que la herramienta lo oculte.
    contexto = fragmento if fragmento and fragmento != "REDACTED" else str(linea or "")
    return calcular_huella(herramienta, regla_id, archivo, contexto)
