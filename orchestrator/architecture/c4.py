"""Diagrama C4 en Mermaid de la arquitectura: fase 2, plan técnico 7.2, paso 5.

Escribe `docs/arquitectura.md` con dos niveles del modelo C4, que GitHub muestra sin herramientas
adicionales:

1. **Contexto.** Quién usa el sistema. Los actores salen de los requisitos de la fase 1.
2. **Contenedores.** Qué piezas lo forman y cómo se comunican:
   - el gateway, la identidad y el bus de eventos, solo cuando la arquitectura los necesita;
   - cada microservicio con su base de datos;
   - las dependencias síncronas (HTTP) y asíncronas (eventos por RabbitMQ).

Además incluye las tablas de servicios y dependencias, los patrones que infirió OPA con enlace a sus
ADR y el resultado de la validación.

Todo sale de `arquitectura.json` aprobada por OPA, sin LLM: el diagrama dibuja exactamente lo que
se validó.

Seguridad:
- Solo se dibuja una arquitectura que OPA aprobó.
- La responsabilidad de cada servicio y el motivo de cada dependencia los escribió el LLM. Dentro
  del diagrama van entre comillas, sin comillas propias ni saltos de línea, así que no pueden
  cerrar la cadena ni añadir instrucciones de Mermaid. Fuera del diagrama se escapan igual que en
  los ADR.
- Si `docs/arquitectura.md` existe y no lo generó el framework, no se pisa.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from orchestrator.architecture.adr import ADR, MARCA, NOMBRE_PATRON, md
from orchestrator.architecture.modelo import Arquitectura
from orchestrator.architecture.validacion import DecisionArquitectura
from orchestrator.ingest.requisito import ModeloRequisitos

# Actores que no son personas: el propio sistema no se dibuja como usuario.
ACTORES_NO_PERSONA = {"sistema", "el sistema", "transversal"}
LARGO_ETIQUETA = 90


class ErrorDiagrama(Exception):
    """No se puede generar el diagrama (arquitectura rechazada o archivo ajeno)."""


def texto_mermaid(texto: str, largo: int = LARGO_ETIQUETA) -> str:
    """Texto no confiable listo para ir entre comillas en Mermaid: una línea, sin comillas.

    También quita `<>` y `#`, que Mermaid interpreta como HTML y como códigos de entidad, `;`,
    que separa sentencias, y `|`, que delimita las etiquetas de las flechas.
    """
    limpio = " ".join(texto.split())
    limpio = limpio.replace('"', "'")
    limpio = re.sub(r"[<>#;|`\\]", "", limpio)
    if len(limpio) > largo:
        limpio = limpio[: largo - 1].rstrip() + "…"
    return limpio


def _alias(prefijo: str, nombre: str) -> str:
    """Identificador seguro para Mermaid: los nombres de servicio ya son [a-z0-9_]."""
    return f"{prefijo}_{re.sub(r'[^a-z0-9_]', '_', nombre.lower())}"


def actores(modelo: ModeloRequisitos) -> list[str]:
    """Actores personas de los requisitos, del más frecuente al menos frecuente."""
    cuentas: dict[str, int] = {}
    for requisito in modelo.requisitos:
        actor = " ".join(requisito.actor.split()).lower()
        if actor and actor not in ACTORES_NO_PERSONA:
            cuentas[actor] = cuentas.get(actor, 0) + 1
    return sorted(cuentas, key=lambda a: (-cuentas[a], a))


def _patrones(decision: DecisionArquitectura) -> set[str]:
    return {p.patron for p in decision.patrones}


def _usa_identidad(arquitectura: Arquitectura) -> bool:
    etiquetas = {e for s in arquitectura.servicios for e in s.etiquetas}
    etiquetas |= set(arquitectura.etiquetas_transversales)
    return bool(etiquetas & {"autenticacion", "autorizacion"})


def _hay_eventos(arquitectura: Arquitectura) -> bool:
    return any(d.tipo == "asincrona" for s in arquitectura.servicios for d in s.depende_de)


def nombre_sistema(arquitectura: Arquitectura, nombre: str | None = None) -> str:
    """El nombre indicado o, si no hay, uno a partir del documento de requisitos."""
    return nombre or f"Sistema del documento «{arquitectura.documento.nombre}»"


# --- Diagramas -----------------------------------------------------------------------------------


def diagrama_contexto(
    arquitectura: Arquitectura, modelo: ModeloRequisitos, nombre: str | None = None
) -> str:
    sistema = texto_mermaid(nombre_sistema(arquitectura, nombre))
    servicios = ", ".join(s.nombre for s in arquitectura.servicios)
    lineas = [
        "C4Context",
        f"    title Contexto: {sistema}",
    ]
    for actor in actores(modelo):
        cantidad = sum(1 for r in modelo.requisitos if r.actor.strip().lower() == actor)
        lineas.append(
            f'    Person({_alias("p", actor)}, "{texto_mermaid(actor.capitalize())}", '
            f'"Aparece en {cantidad} requisito(s)")'
        )
    lineas.append(
        f'    System(sistema, "{sistema}", '
        f'"{texto_mermaid(f"{len(arquitectura.servicios)} microservicios: {servicios}", 140)}")'
    )
    for actor in actores(modelo):
        lineas.append(f'    Rel({_alias("p", actor)}, sistema, "Usa", "HTTPS")')
    return "\n".join(lineas)


def diagrama_contenedores(
    arquitectura: Arquitectura, decision: DecisionArquitectura, nombre: str | None = None
) -> str:
    """Nivel de contenedores con un flowchart de Mermaid y los colores y formas de C4.

    La sintaxis C4 de Mermaid (experimental) coloca las piezas en una rejilla fija y, con una
    base de datos por servicio, las flechas se superponen hasta no poder leerse. El flowchart
    ordena las piezas para evitar los cruces y dibuja lo mismo: personas, contenedores con su
    tecnología, bases de datos, el bus de eventos y las relaciones con su protocolo.
    """
    patrones = _patrones(decision)
    gateway = "api_gateway" in patrones
    identidad = _usa_identidad(arquitectura)
    eventos = _hay_eventos(arquitectura)
    sistema = texto_mermaid(nombre_sistema(arquitectura, nombre))

    def caja(alias: str, titulo: str, tecnologia: str, descripcion: str = "") -> str:
        partes = [f"<b>{texto_mermaid(titulo, 40)}</b>", f"[{tecnologia}]"]
        if descripcion:
            partes.append(texto_mermaid(descripcion, 60))
        return f'{alias}["{"<br/>".join(partes)}"]'

    lineas = [
        "flowchart TB",
        '    usuarios["<b>Usuarios</b><br/>[Persona]<br/>Actores de los requisitos"]',
        f'    subgraph sistema["{sistema}"]',
    ]
    if gateway:
        lineas.append(
            "        "
            + caja("gateway", "API Gateway", "Traefik", "Entrada única: TLS, tokens y límite")
        )
    if identidad:
        lineas.append(
            "        " + caja("identidad", "Identidad", "Keycloak", "Inicio de sesión y JWT")
        )
    for servicio in arquitectura.servicios:
        lineas.append(
            "        "
            + caja(
                _alias("s", servicio.nombre), servicio.nombre, "NestJS", servicio.responsabilidad
            )
        )
    for servicio in arquitectura.servicios:
        alias = _alias("db", servicio.base_datos)
        lineas.append(
            f'        {alias}[("<b>{texto_mermaid(servicio.base_datos, 40)}</b><br/>[PostgreSQL]")]'
        )
    if eventos:
        lineas.append('        eventos[["<b>Bus de eventos</b><br/>[RabbitMQ]"]]')
    lineas.append("    end")

    if gateway:
        lineas.append('    usuarios -->|"HTTPS"| gateway')
        if identidad:
            lineas.append('    gateway -->|"valida tokens (OIDC)"| identidad')
        for servicio in arquitectura.servicios:
            lineas.append(f'    gateway -->|"HTTP"| {_alias("s", servicio.nombre)}')
    else:
        if identidad:
            lineas.append('    usuarios -->|"inicia sesión (OIDC)"| identidad')
        for servicio in arquitectura.servicios:
            lineas.append(f'    usuarios -->|"HTTPS"| {_alias("s", servicio.nombre)}')

    for servicio in arquitectura.servicios:
        lineas.append(
            f'    {_alias("s", servicio.nombre)} -->|"SQL"| {_alias("db", servicio.base_datos)}'
        )

    publicadores: list[str] = []
    for servicio in arquitectura.servicios:
        origen = _alias("s", servicio.nombre)
        for dependencia in servicio.depende_de:
            motivo = texto_mermaid(dependencia.motivo, 40)
            if dependencia.tipo == "sincrona":
                lineas.append(
                    f'    {origen} -->|"HTTP: {motivo}"| {_alias("s", dependencia.servicio)}'
                )
            else:
                # «A depende de B (asíncrona)»: B publica eventos y A los consume.
                if dependencia.servicio not in publicadores:
                    publicadores.append(dependencia.servicio)
                lineas.append(f'    eventos -.->|"{motivo}"| {origen}')
    for publicador in publicadores:
        lineas.append(f'    {_alias("s", publicador)} -.->|"publica eventos"| eventos')

    clases = {
        "persona": "fill:#08427b,stroke:#052e56,color:#fff",
        "contenedor": "fill:#438dd5,stroke:#2e6295,color:#fff",
        "plataforma": "fill:#85bbf0,stroke:#5d82a8,color:#000",
        "datos": "fill:#438dd5,stroke:#2e6295,color:#fff",
    }
    lineas += [f"    classDef {clase} {estilo}" for clase, estilo in clases.items()]
    lineas.append("    class usuarios persona")
    plataforma = [a for a, hay in (("gateway", gateway), ("identidad", identidad)) if hay]
    if eventos:
        plataforma.append("eventos")
    if plataforma:
        lineas.append(f"    class {','.join(plataforma)} plataforma")
    lineas.append(
        "    class "
        + ",".join(_alias("s", s.nombre) for s in arquitectura.servicios)
        + " contenedor"
    )
    lineas.append(
        "    class "
        + ",".join(_alias("db", s.base_datos) for s in arquitectura.servicios)
        + " datos"
    )
    lineas.append("    style sistema fill:none,stroke:#666,stroke-dasharray:5 5")
    return "\n".join(lineas)


# --- Documento -----------------------------------------------------------------------------------


def documento_arquitectura(
    arquitectura: Arquitectura,
    modelo: ModeloRequisitos,
    decision: DecisionArquitectura,
    fecha: date,
    adrs: dict[str, str] | None = None,
    nombre: str | None = None,
) -> str:
    """Markdown de docs/arquitectura.md. `adrs` asocia cada patrón con el enlace a su ADR."""
    if not decision.aprobado:
        motivos = "; ".join(b.motivo for b in decision.bloqueantes) or "sin motivo"
        raise ErrorDiagrama(f"OPA no aprobó la arquitectura: {motivos}")
    adrs = adrs or {}
    documento = arquitectura.documento
    lineas = [
        MARCA,
        f"# Arquitectura: {md(nombre_sistema(arquitectura, nombre))}",
        "",
        f"Generada el {fecha.isoformat()} por el framework a partir de `arquitectura.json`, "
        f"validada por OPA, para el documento {md(documento.nombre)} "
        f"(SHA-256 `{documento.sha256[:12]}`). Los diagramas siguen el modelo C4 y GitHub los "
        "dibuja a partir del texto Mermaid.",
        "",
        "Para regenerarla:",
        "",
        "```bash",
        "framework arquitectura diagrama <arquitectura.json> --requisitos <modelo_requisitos.json> "
        '--nombre "<nombre del sistema>"',
        "```",
        "",
        "## 1. Contexto",
        "",
        "Quién usa el sistema. Los actores salen de los requisitos del documento.",
        "",
        "```mermaid",
        diagrama_contexto(arquitectura, modelo, nombre),
        "```",
        "",
        "## 2. Contenedores",
        "",
        "Las piezas que forman el sistema y cómo se comunican. Las flechas «HTTP» entre servicios "
        "son llamadas síncronas (el que llama espera la respuesta); las «AMQP» pasan por el bus "
        "de eventos (el que publica no espera a nadie).",
        "",
        "```mermaid",
        diagrama_contenedores(arquitectura, decision, nombre),
        "```",
        "",
        "## 3. Servicios",
        "",
        "| Servicio | Contexto | Responsabilidad | Base de datos | Requisitos "
        "| Etiquetas de seguridad |",
        "|---|---|---|---|---|---|",
    ]
    for s in arquitectura.servicios:
        lineas.append(
            f"| `{s.nombre}` | {md(s.contexto)} | {md(s.responsabilidad)} | `{s.base_datos}` | "
            f"{', '.join(s.requisitos)} | {md(', '.join(s.etiquetas)) or 'ninguna'} |"
        )
    if arquitectura.transversales:
        lineas += [
            "",
            "Requisitos transversales, que aplican a todo el sistema: "
            + ", ".join(arquitectura.transversales)
            + (
                f" (etiquetas: {md(', '.join(arquitectura.etiquetas_transversales))})."
                if arquitectura.etiquetas_transversales
                else "."
            ),
        ]

    lineas += ["", "## 4. Dependencias entre servicios", ""]
    dependencias = [(s, d) for s in arquitectura.servicios for d in s.depende_de]
    if dependencias:
        lineas += ["| Servicio | Depende de | Tipo | Para qué |", "|---|---|---|---|"]
        for s, d in dependencias:
            tipo = "síncrona (HTTP)" if d.tipo == "sincrona" else "asíncrona (eventos)"
            lineas.append(f"| `{s.nombre}` | `{d.servicio}` | {tipo} | {md(d.motivo)} |")
    else:
        lineas.append("Ningún servicio depende de otro.")

    lineas += ["", "## 5. Patrones aplicados", ""]
    if decision.patrones:
        lineas += [
            "| Patrón | Implementación | Por qué lo infiere OPA | ADR |",
            "|---|---|---|---|",
        ]
        for p in decision.patrones:
            enlace = f"[ver ADR]({adrs[p.patron]})" if p.patron in adrs else "—"
            lineas.append(
                f"| {NOMBRE_PATRON.get(p.patron, md(p.patron))} | {md(p.implementacion)} | "
                f"{md(p.motivo)} | {enlace} |"
            )
    else:
        lineas.append("OPA no infirió ningún patrón.")

    lineas += [
        "",
        "## 6. Validación de OPA",
        "",
        md(decision.justificacion),
        "",
        "| Regla | Cumple | Detalle |",
        "|---|---|---|",
        *(
            f"| `{c.regla}` | {'sí' if c.cumple else 'no'} | {md(c.detalle) or ' '} |"
            for c in decision.criterios
        ),
    ]
    if decision.advertencias:
        lineas += ["", "Advertencias:", ""]
        lineas += [f"- `{a.regla}`: {md(a.motivo)}" for a in decision.advertencias]
    return "\n".join(lineas) + "\n"


def enlaces_adr(adrs: list[ADR], carpeta_adr: Path, documento: Path) -> dict[str, str]:
    """Enlace relativo, desde el documento, al ADR de cada patrón que ya está escrito."""
    enlaces = {}
    for adr in adrs:
        if adr.patron and (carpeta_adr / adr.archivo).is_file():
            try:
                relativo = os.path.relpath(carpeta_adr / adr.archivo, documento.parent)
            except ValueError:
                continue  # en Windows, en otra unidad no hay ruta relativa: se omite el enlace
            enlaces[adr.patron] = Path(relativo).as_posix()
    return enlaces


def escribir_documento(contenido: str, destino: Path) -> Path:
    if destino.exists():
        with destino.open(encoding="utf-8") as entrada:
            if entrada.readline().strip() != MARCA:
                raise ErrorDiagrama(
                    f"{destino.as_posix()} existe y no lo generó el framework; no se pisa"
                )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    return destino
