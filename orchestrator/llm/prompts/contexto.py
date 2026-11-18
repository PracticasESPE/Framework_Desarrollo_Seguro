"""Contexto de seguridad para los prompts de generación, recuperado con GraphRAG.

Plan técnico 6.1, condición 2: el prompt incluye los controles y fragmentos OWASP/CWE relevantes
recuperados desde Neo4j, no el conocimiento genérico del modelo.

Las preguntas no las escribe el LLM ni el cliente: salen de las etiquetas de seguridad de los
requisitos del servicio, con un texto fijo por etiqueta. Así la recuperación es reproducible y el
documento del cliente no puede dirigir qué conocimiento recibe el LLM. A todas se suma una pregunta
base (validación de entrada y errores), que aplica a cualquier servicio con API.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from orchestrator.knowledge.graphrag import Coincidencia, ContextoGraphRAG, Elemento

PREGUNTA_BASE = (
    "Validación de los datos de entrada en el servidor y manejo de errores sin exponer detalles "
    "internos en una API REST"
)

PREGUNTAS_POR_ETIQUETA: dict[str, str] = {
    "autenticacion": "Autenticación con tokens JWT validados en cada petición, sesiones con "
    "caducidad y bloqueo tras intentos fallidos",
    "autorizacion": "Control de acceso por roles: cada operación comprueba que el rol del usuario "
    "la permite y se deniega por defecto",
    "control_acceso_recursos": "Autorización a nivel de objeto: cada usuario solo puede leer o "
    "cambiar sus propios recursos aunque cambie el identificador",
    "validacion_entrada": "Validación estricta de tipos, rangos, longitudes y listas permitidas, "
    "y valores calculados en el servidor en lugar de aceptarlos del cliente",
    "hash_password": "Almacenamiento seguro de contraseñas con un algoritmo de hash lento y sal",
    "cifrado_transito": "Cifrado de todas las comunicaciones con TLS",
    "punto_unico_acceso": "API gateway como único punto de entrada a los microservicios",
    "limite_peticiones": "Límite de peticiones por usuario y protección contra fuerza bruta y "
    "consumo excesivo de recursos",
    "auditoria": "Registro de auditoría de las acciones sensibles, que no se puede modificar y no "
    "guarda datos sensibles",
}

# Fragmentos que llegan al prompt: más allá de esto el contexto crece sin aportar.
MAXIMO_COINCIDENCIAS = 12

Consultor = Callable[[str], ContextoGraphRAG]


def preguntas_de_seguridad(etiquetas: Iterable[str]) -> list[str]:
    """La pregunta base y una por cada etiqueta conocida, sin repetir y en orden estable."""
    vistas = dict.fromkeys(e for e in etiquetas if e in PREGUNTAS_POR_ETIQUETA)
    return [PREGUNTA_BASE, *(PREGUNTAS_POR_ETIQUETA[e] for e in sorted(vistas))]


def combinar(contextos: list[ContextoGraphRAG], pregunta: str) -> ContextoGraphRAG:
    """Une varios contextos: cada fragmento y elemento una vez, los más parecidos antes."""
    mejores: dict[str, Coincidencia] = {}
    for contexto in contextos:
        for c in contexto.coincidencias:
            if c.fragmento not in mejores or c.puntuacion > mejores[c.fragmento].puntuacion:
                mejores[c.fragmento] = c
    coincidencias = sorted(mejores.values(), key=lambda c: (-c.puntuacion, c.fragmento))

    def unir(campo: str) -> list[Elemento]:
        vistos: dict[str, Elemento] = {}
        for contexto in contextos:
            for elemento in getattr(contexto, campo):
                vistos.setdefault(elemento.id, elemento)
        return list(vistos.values())

    return ContextoGraphRAG(
        pregunta=pregunta,
        coincidencias=coincidencias[:MAXIMO_COINCIDENCIAS],
        cwe=unir("cwe"),
        patrones=unir("patrones"),
        directrices=unir("directrices"),
        controles=unir("controles"),
        riesgos=unir("riesgos"),
    )


def contexto_de_seguridad(etiquetas: Iterable[str], consultar: Consultor) -> ContextoGraphRAG:
    """Consulta GraphRAG con las preguntas de las etiquetas y combina las respuestas."""
    preguntas = preguntas_de_seguridad(etiquetas)
    return combinar([consultar(p) for p in preguntas], " / ".join(preguntas))


def contexto_vacio() -> ContextoGraphRAG:
    """Sin Neo4j o sin embeddings cargados: el prompt lo dice en lugar de inventar contexto."""
    return ContextoGraphRAG(
        pregunta="", coincidencias=[], cwe=[], patrones=[], directrices=[], controles=[], riesgos=[]
    )
