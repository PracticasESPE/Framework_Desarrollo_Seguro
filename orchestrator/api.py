"""API del motor del framework. También sirve el dashboard compilado (dashboard/dist)."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles

from orchestrator import __version__
from orchestrator.config import obtener_configuracion
from orchestrator.documentos import (
    TAMANO_MAXIMO,
    DocumentoCargado,
    DocumentoDemasiadoGrande,
    ErrorDocumento,
    FormatoNoPermitido,
    detectar_formato,
    guardar_documento,
    listar_documentos,
)
from orchestrator.fases import FASES, Fase

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


def montar_dashboard(aplicacion: FastAPI, carpeta: Path = DASHBOARD) -> bool:
    """Sirve el dashboard compilado en la raíz, si existe. Se monta después de las rutas de la API,
    que tienen prioridad."""
    if not (carpeta / "index.html").is_file():
        return False
    aplicacion.mount("/", StaticFiles(directory=carpeta, html=True), name="dashboard")
    return True


montar_dashboard(app)
