"""API del motor del framework. También sirve el dashboard compilado (dashboard/dist).

La documentación interactiva está en `/docs` (Swagger UI) y `/redoc`. La API escucha solo en
127.0.0.1 porque todavía no tiene autenticación.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi import Path as ParametroRuta
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    DetalleEjecucion,
    Ejecucion,
    EjecucionEnCurso,
    EjecucionTerminada,
    Estado,
    EstadoEjecucion,
    Evento,
    RegistrarEnNeo4j,
    RegistroEjecuciones,
    registrar_en_neo4j,
    trabajo_fase1,
)
from orchestrator.fases import FASES, Fase
from orchestrator.ingest.requisito import ModeloRequisitos
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

DESCRIPCION = """
API del motor del framework de desarrollo seguro guiado por conocimiento.

Flujo de la fase 1 desde el dashboard o desde cualquier cliente:

1. `POST /documentos` carga el documento de requisitos y devuelve su `id`.
2. `POST /ejecuciones` con ese `id` lanza la fase 1 en segundo plano.
3. `GET /ejecuciones/{id}/eventos` sigue el progreso en tiempo real (Server-Sent Events), o
   `GET /ejecuciones/{id}` consulta el estado en un momento dado.
4. `GET /documentos/{id}/requisitos` devuelve el `modelo_requisitos.json` generado.

La API escucha solo en `127.0.0.1` porque todavía no tiene autenticación.
"""

ETIQUETAS = [
    {"name": "motor", "description": "Estado y configuración del motor."},
    {
        "name": "documentos",
        "description": "Carga del documento de requisitos (PDF, DOCX, TXT o Markdown) y el "
        "modelo de requisitos generado a partir de él.",
    },
    {
        "name": "ejecuciones",
        "description": "Ejecución del pipeline: lanzarla, consultar su estado, seguir su "
        "progreso en tiempo real y cancelarla. Hoy ejecuta la fase 1.",
    },
]

app = FastAPI(
    title="Framework de desarrollo seguro",
    description=DESCRIPCION,
    version=__version__,
    openapi_tags=ETIQUETAS,
)


class Error(BaseModel):
    """Cuerpo de las respuestas de error."""

    detail: str


def _error(descripcion: str) -> dict[str, object]:
    return {"model": Error, "description": descripcion}


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


# --- Motor -----------------------------------------------------------------------------------


@app.get("/salud", tags=["motor"], summary="Comprobar que el motor responde")
def salud() -> dict[str, str]:
    return {"estado": "ok", "version": __version__}


@app.get("/fases", tags=["motor"], summary="Las 11 fases del pipeline")
def listar_fases() -> list[Fase]:
    return list(FASES)


@app.get("/configuracion", tags=["motor"], summary="Configuración activa, sin secretos")
def ver_configuracion() -> dict[str, object]:
    return obtener_configuracion().resumen()


# --- Documentos ------------------------------------------------------------------------------


def carpeta_documentos() -> Path:
    return obtener_configuracion().directorio_salida / "documentos"


def carpeta_requisitos() -> Path:
    return obtener_configuracion().directorio_salida / "requisitos"


Carpeta = Annotated[Path, Depends(carpeta_documentos)]
CarpetaRequisitos = Annotated[Path, Depends(carpeta_requisitos)]
IdDocumento = Annotated[
    str, ParametroRuta(pattern=ID_DOCUMENTO, description="Id que devolvió la carga")
]


@app.post(
    "/documentos",
    tags=["documentos"],
    status_code=201,
    summary="Cargar el documento de requisitos",
    responses={
        400: _error("El contenido no corresponde al formato"),
        413: _error("El documento supera el tamaño máximo"),
        415: _error("Formato no permitido"),
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


@app.get(
    "/documentos",
    tags=["documentos"],
    summary="Documentos cargados, del más reciente al más antiguo",
)
def ver_documentos(carpeta: Carpeta) -> list[DocumentoCargado]:
    return listar_documentos(carpeta)


@app.get(
    "/documentos/{id_documento}/requisitos",
    tags=["documentos"],
    summary="Modelo de requisitos generado por la fase 1",
    responses={404: _error("El documento no existe o todavía no se ha procesado")},
)
def ver_requisitos(
    id_documento: IdDocumento, carpeta: Carpeta, destino: CarpetaRequisitos
) -> ModeloRequisitos:
    """Devuelve el `modelo_requisitos.json` de la última ejecución completada con ese documento.

    Se lee del disco, así que sigue disponible después de reiniciar la API.
    """
    try:
        obtener_documento(carpeta, id_documento)
    except DocumentoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    archivo = destino / f"{id_documento}.modelo_requisitos.json"
    try:
        return ModeloRequisitos.model_validate_json(archivo.read_bytes())
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404, detail="El documento todavía no se ha procesado"
        ) from error
    except ValidationError as error:
        # Lo escribe el propio motor; si no valida, es que se editó a mano o cambió el esquema.
        raise HTTPException(
            status_code=500, detail="El modelo de requisitos guardado no es válido"
        ) from error


# --- Ejecuciones -----------------------------------------------------------------------------

REGISTRO = RegistroEjecuciones()
# Cada cuánto se revisan los eventos nuevos de una ejecución mientras hay un navegador conectado.
INTERVALO_EVENTOS_S = 0.25


def registro_ejecuciones() -> RegistroEjecuciones:
    return REGISTRO


def fabrica_llm() -> Callable[[], ProveedorLLM]:
    return crear_proveedor


def registrador_neo4j() -> RegistrarEnNeo4j | None:
    """Al terminar la fase 1, los requisitos se guardan como nodos Requisito en Neo4j."""
    return registrar_en_neo4j


Registro = Annotated[RegistroEjecuciones, Depends(registro_ejecuciones)]


class SolicitudEjecucion(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"documento": "0123456789abcdef0123456789abcdef"}]},
    )

    documento: str = Field(pattern=ID_DOCUMENTO, description="Id de un documento cargado")


@app.post(
    "/ejecuciones",
    tags=["ejecuciones"],
    status_code=201,
    summary="Lanzar la fase 1 con un documento cargado",
    responses={
        404: _error("No existe el documento"),
        409: _error("Ya hay una ejecución en curso: el motor procesa un documento a la vez"),
    },
)
def iniciar_ejecucion(
    solicitud: SolicitudEjecucion,
    respuesta: Response,
    carpeta: Carpeta,
    destino: CarpetaRequisitos,
    registro: Registro,
    crear_llm: Annotated[Callable[[], ProveedorLLM], Depends(fabrica_llm)],
    registrar: Annotated[RegistrarEnNeo4j | None, Depends(registrador_neo4j)],
) -> EstadoEjecucion:
    """Lanza la ejecución en segundo plano y responde enseguida.

    El progreso se sigue en `/ejecuciones/{id}/eventos` y el estado se consulta en
    `/ejecuciones/{id}`, que es lo que indica la cabecera `Location`.
    """
    try:
        documento, ruta = obtener_documento(carpeta, solicitud.documento)
    except DocumentoNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        ejecucion = registro.iniciar(
            documento.id,
            trabajo_fase1(documento, ruta, destino, crear_llm, registrar),
            nombre_documento=documento.nombre,
        )
    except EjecucionEnCurso as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    respuesta.headers["Location"] = f"/ejecuciones/{ejecucion.id}"
    return ejecucion.resumen()


@app.get(
    "/ejecuciones",
    tags=["ejecuciones"],
    summary="Ejecuciones recientes, de la más reciente a la más antigua",
)
def listar_ejecuciones(
    registro: Registro,
    estado: Annotated[
        Estado | None, Query(description="Solo las ejecuciones en este estado")
    ] = None,
) -> list[EstadoEjecucion]:
    """Ejecuciones que recuerda el motor desde que arrancó: hasta 20, en memoria.

    Con `estado=en_curso`, el dashboard retoma la ejecución en marcha al recargar la página.
    """
    return [e.resumen() for e in registro.listar() if estado is None or e.estado == estado]


def ejecucion_existente(
    id_ejecucion: Annotated[
        str, ParametroRuta(pattern=ID_EJECUCION, description="Id que devolvió la creación")
    ],
    registro: Registro,
) -> Ejecucion:
    # Se comprueba en una dependencia porque, una vez abierto el flujo de eventos, ya no se
    # puede responder con un 404.
    ejecucion = registro.obtener(id_ejecucion)
    if ejecucion is None:
        raise HTTPException(status_code=404, detail="No existe la ejecución")
    return ejecucion


EjecucionExistente = Annotated[Ejecucion, Depends(ejecucion_existente)]


@app.get(
    "/ejecuciones/{id_ejecucion}",
    tags=["ejecuciones"],
    summary="Estado de una ejecución y de cada fase",
    responses={404: _error("No existe la ejecución")},
)
def ver_ejecucion(ejecucion: EjecucionExistente) -> DetalleEjecucion:
    """Estado en este momento: el de la ejecución, el de cada una de las 11 fases y, cuando
    termina la fase 1, su resultado. Para seguir el progreso sin consultar a cada rato, usa
    `/ejecuciones/{id}/eventos`."""
    return ejecucion.detalle()


@app.post(
    "/ejecuciones/{id_ejecucion}/cancelar",
    tags=["ejecuciones"],
    status_code=202,
    summary="Pedir que se cancele una ejecución",
    responses={
        404: _error("No existe la ejecución"),
        409: _error("La ejecución ya terminó"),
    },
)
def cancelar_ejecucion(ejecucion: EjecucionExistente) -> EstadoEjecucion:
    """La ejecución se detiene en el siguiente paso: tras la extracción o antes de la siguiente
    sección que clasifica el LLM. Por eso responde 202: el evento «fin» con estado `cancelada`
    llega por `/ejecuciones/{id}/eventos`."""
    try:
        ejecucion.pedir_cancelacion()
    except EjecucionTerminada as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ejecucion.resumen()


@app.get(
    "/ejecuciones/{id_ejecucion}/eventos",
    tags=["ejecuciones"],
    response_class=EventSourceResponse,
    summary="Progreso de una ejecución en tiempo real (Server-Sent Events)",
    responses={404: _error("No existe la ejecución")},
)
async def eventos_de_ejecucion(
    ejecucion: EjecucionExistente,
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
