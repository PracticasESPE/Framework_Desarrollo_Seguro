"""API del motor del framework. También sirve el dashboard compilado (dashboard/dist)."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi import Path as ParametroRuta
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from orchestrator import __version__
from orchestrator.config import obtener_configuracion
from orchestrator.documentos import (
    ID_DOCUMENTO,
    TAMANO_MAXIMO,
    DocumentoCargado,
    DocumentoDemasiadoGrande,
    DocumentoNoEncontrado,
    ErrorDocumento,
    FormatoNoPermitido,
    detectar_formato,
    guardar_documento,
    listar_documentos,
    obtener_documento,
)
from orchestrator.ejecuciones import (
    ID_EJECUCION,
    Ejecucion,
    EjecucionEnCurso,
    EstadoEjecucion,
    Evento,
    RegistroEjecuciones,
    trabajo_fase1,
)
from orchestrator.fases import FASES, Fase
from orchestrator.llm import ProveedorLLM, crear_proveedor

DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

# El dashboard solo carga recursos propios y llama a esta misma API, así que no necesita CORS.
POLITICA_DE_CONTENIDO = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)
CABECERAS_DE_SEGURIDAD = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
# La documentación interactiva de FastAPI carga Swagger UI y ReDoc desde una CDN.
RUTAS_DE_DOCUMENTACION = {"/docs", "/docs/oauth2-redirect", "/redoc"}

app = FastAPI(
    title="Framework de desarrollo seguro",
    description="API del motor del framework de desarrollo seguro guiado por conocimiento.",
    version=__version__,
)


@app.middleware("http")
async def cabeceras_de_seguridad(
    request: Request, siguiente: Callable[[Request], Awaitable[Response]]
) -> Response:
    respuesta = await siguiente(request)
    for cabecera, valor in CABECERAS_DE_SEGURIDAD.items():
        respuesta.headers.setdefault(cabecera, valor)
    if request.url.path not in RUTAS_DE_DOCUMENTACION:
        respuesta.headers.setdefault("Content-Security-Policy", POLITICA_DE_CONTENIDO)
    return respuesta


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok", "version": __version__}


@app.get("/fases")
def listar_fases() -> list[Fase]:
    return list(FASES)


@app.get("/configuracion")
def ver_configuracion() -> dict[str, object]:
    return obtener_configuracion().resumen()


def carpeta_documentos() -> Path:
    return obtener_configuracion().directorio_salida / "documentos"


Carpeta = Annotated[Path, Depends(carpeta_documentos)]


@app.post(
    "/documentos",
    status_code=201,
    summary="Cargar el documento de requisitos",
    responses={
        400: {"description": "El contenido no corresponde al formato"},
        413: {"description": "El documento supera el tamaño máximo"},
        415: {"description": "Formato no permitido"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def cargar_documento(
    request: Request,
    carpeta: Carpeta,
    nombre: Annotated[
        str,
        Query(
            min_length=1,
            max_length=255,
            description="Nombre original del archivo: solo se muestra y da el formato.",
        ),
    ],
) -> DocumentoCargado:
    """Recibe el archivo como cuerpo binario y lo guarda con un nombre generado por el servidor.

    El cuerpo se lee por partes y se corta al superar el máximo, sin esperar a recibirlo entero.
    """
    try:
        detectar_formato(nombre)
    except FormatoNoPermitido as error:
        raise HTTPException(status_code=415, detail=str(error)) from error

    demasiado_grande = HTTPException(
        status_code=413,
        detail=f"El documento supera el máximo de {TAMANO_MAXIMO // (1024 * 1024)} MB",
    )
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > TAMANO_MAXIMO:
        raise demasiado_grande
    datos = bytearray()
    async for trozo in request.stream():
        datos.extend(trozo)
        if len(datos) > TAMANO_MAXIMO:
            raise demasiado_grande

    try:
        return guardar_documento(bytes(datos), nombre, carpeta)
    except DocumentoDemasiadoGrande as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except ErrorDocumento as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/documentos", summary="Documentos cargados, del más reciente al más antiguo")
def ver_documentos(carpeta: Carpeta) -> list[DocumentoCargado]:
    return listar_documentos(carpeta)


# --- Ejecuciones y progreso (Server-Sent Events) ---------------------------------------------

REGISTRO = RegistroEjecuciones()
# Cada cuánto se revisan los eventos nuevos de una ejecución mientras hay un navegador conectado.
INTERVALO_EVENTOS_S = 0.25


def registro_ejecuciones() -> RegistroEjecuciones:
    return REGISTRO


def carpeta_requisitos() -> Path:
    return obtener_configuracion().directorio_salida / "requisitos"


def fabrica_llm() -> Callable[[], ProveedorLLM]:
    return crear_proveedor


class SolicitudEjecucion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documento: str = Field(pattern=ID_DOCUMENTO, description="Id de un documento cargado")


@app.post(
    "/ejecuciones",
    status_code=201,
    summary="Ejecutar la fase 1 con un documento cargado",
    responses={
        404: {"description": "No existe el documento"},
        409: {"description": "Ya hay una ejecución en curso"},
    },
)
def iniciar_ejecucion(
    solicitud: SolicitudEjecucion,
    carpeta: Carpeta,
    destino: Annotated[Path, Depends(carpeta_requisitos)],
    registro: Annotated[RegistroEjecuciones, Depends(registro_ejecuciones)],
    crear_llm: Annotated[Callable[[], ProveedorLLM], Depends(fabrica_llm)],
) -> EstadoEjecucion:
    """Lanza la ejecución en segundo plano. El progreso se sigue en `/ejecuciones/{id}/eventos`."""
    try:
        documento, ruta = obtener_documento(carpeta, solicitud.documento)
    except DocumentoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        ejecucion = registro.iniciar(
            documento.id, trabajo_fase1(documento, ruta, destino, crear_llm)
        )
    except EjecucionEnCurso as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ejecucion.resumen()


def ejecucion_existente(
    id_ejecucion: Annotated[str, ParametroRuta(pattern=ID_EJECUCION)],
    registro: Annotated[RegistroEjecuciones, Depends(registro_ejecuciones)],
) -> Ejecucion:
    # Se comprueba en una dependencia porque, una vez abierto el flujo de eventos, ya no se
    # puede responder con un 404.
    ejecucion = registro.obtener(id_ejecucion)
    if ejecucion is None:
        raise HTTPException(status_code=404, detail="No existe la ejecución")
    return ejecucion


@app.get(
    "/ejecuciones/{id_ejecucion}/eventos",
    response_class=EventSourceResponse,
    summary="Progreso de una ejecución en tiempo real (Server-Sent Events)",
    responses={404: {"description": "No existe la ejecución"}},
)
async def eventos_de_ejecucion(
    ejecucion: Annotated[Ejecucion, Depends(ejecucion_existente)],
    last_event_id: Annotated[
        int | None,
        Header(ge=0, description="Último evento recibido; lo envía EventSource al reconectar"),
    ] = None,
) -> AsyncIterator[ServerSentEvent]:
    """Envía los eventos de la ejecución (`data` es un `Evento` en JSON) hasta el evento «fin».

    Quien se conecta tarde recibe primero todo lo ocurrido; quien se reconecta, solo lo que le
    faltaba. FastAPI añade un comentario `: ping` cada 15 s para que la conexión no caduque.
    """
    enviados = last_event_id or 0
    while True:
        for evento in ejecucion.eventos_desde(enviados):
            yield _evento_sse(evento)
            enviados = evento.id
            if evento.tipo == "fin":
                return
        if ejecucion.terminada and not ejecucion.eventos_desde(enviados):
            return  # el navegador ya tenía el evento «fin»
        await asyncio.sleep(INTERVALO_EVENTOS_S)


def _evento_sse(evento: Evento) -> ServerSentEvent:
    return ServerSentEvent(data=evento.model_dump(mode="json"), id=str(evento.id))


def montar_dashboard(aplicacion: FastAPI, carpeta: Path = DASHBOARD) -> bool:
    """Sirve el dashboard compilado en la raíz, si existe. Se monta después de las rutas de la API,
    que tienen prioridad."""
    if not (carpeta / "index.html").is_file():
        return False
    aplicacion.mount("/", StaticFiles(directory=carpeta, html=True), name="dashboard")
    return True


montar_dashboard(app)
