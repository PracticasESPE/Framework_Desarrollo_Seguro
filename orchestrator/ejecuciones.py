"""Ejecuciones del pipeline lanzadas desde la API y sus eventos de progreso.

Cada ejecución corre en un hilo aparte y publica eventos que la API envía al dashboard con
Server-Sent Events (`GET /ejecuciones/{id}/eventos`). Por ahora el motor ejecuta la fase 1
(adquisición de requisitos); las demás fases se sumarán cuando existan en el motor.

Los eventos se guardan en memoria con un número correlativo. Si el navegador pierde la conexión,
EventSource se reconecta enviando `Last-Event-ID` y recibe solo lo que le faltaba.

Seguridad:
- Una sola ejecución a la vez (CWE-400): la fase 1 ocupa Docling y la cuota del LLM.
- El registro guarda como mucho MAX_GUARDADAS ejecuciones y descarta las terminadas más antiguas,
  para que la memoria no crezca sin límite.
- El documento se busca por el id que generó el servidor, nunca por una ruta (CWE-22).
- Los errores esperados (documento no válido, fallo del LLM) llegan al dashboard con su mensaje.
  Los inesperados se registran en el log y al dashboard solo llega un aviso genérico (CWE-209).
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.documentos import DocumentoCargado, ErrorDocumento
from orchestrator.ingest.requisito import Requisito
from orchestrator.llm import ErrorLLM, ProveedorLLM

log = logging.getLogger(__name__)

MAX_GUARDADAS = 20
ID_EJECUCION = r"^[0-9a-f]{32}$"

Estado = Literal["en_curso", "completada", "fallida"]
TipoEvento = Literal["fase", "avance", "resultado", "fin"]


class ResumenFase1(BaseModel):
    """Resultado de la fase 1 que se muestra en el dashboard."""

    archivo: str = Field(description="Nombre del modelo_requisitos.json guardado")
    funcionales: int
    no_funcionales: int
    descartadas: int = Field(description="Unidades del documento que no son requisitos")
    etiquetas: dict[str, int] = Field(description="Etiquetas de seguridad y cuántas veces salen")
    requisitos: list[Requisito]


class Evento(BaseModel):
    """Un evento de progreso. `id` es correlativo dentro de la ejecución y empieza en 1."""

    id: int
    tipo: TipoEvento
    fecha: datetime
    mensaje: str
    fase: int | None = None
    estado: Estado | None = Field(
        default=None, description="Estado de la fase (eventos «fase») o de la ejecución («fin»)"
    )
    progreso: float | None = Field(default=None, ge=0, le=1)
    resultado: ResumenFase1 | None = None


class EstadoEjecucion(BaseModel):
    """Lo que la API devuelve de una ejecución."""

    id: str
    documento: str
    estado: Estado
    inicio: datetime
    fin: datetime | None = None


class EjecucionEnCurso(Exception):
    def __init__(self, id_ejecucion: str) -> None:
        super().__init__(f"Ya hay una ejecución en curso ({id_ejecucion}); espera a que termine")
        self.id_ejecucion = id_ejecucion


class ErrorFase(Exception):
    """Fallo esperado de una fase. El mensaje se puede mostrar en el dashboard."""


class Ejecucion:
    def __init__(self, documento: str) -> None:
        self.id = uuid.uuid4().hex
        self.documento = documento
        self.estado: Estado = "en_curso"
        self.inicio = datetime.now(UTC)
        self.fin: datetime | None = None
        self.fase_actual: int | None = None
        self._eventos: list[Evento] = []
        self._candado = threading.Lock()

    @property
    def terminada(self) -> bool:
        return self.estado != "en_curso"

    def publicar(self, tipo: TipoEvento, mensaje: str, **campos: object) -> Evento:
        with self._candado:
            evento = Evento.model_validate(
                {
                    "id": len(self._eventos) + 1,
                    "tipo": tipo,
                    "fecha": datetime.now(UTC),
                    "mensaje": mensaje,
                    **campos,
                }
            )
            self._eventos.append(evento)
        if tipo == "fase" and evento.estado == "en_curso":
            self.fase_actual = evento.fase
        return evento

    def eventos_desde(self, ultimo: int) -> list[Evento]:
        """Eventos con id mayor que `ultimo` (0 para todos)."""
        with self._candado:
            return self._eventos[max(ultimo, 0) :]

    def terminar(self, estado: Literal["completada", "fallida"], mensaje: str) -> None:
        # Primero el evento y después el estado: quien vea la ejecución terminada ya tiene el
        # evento «fin» disponible.
        self.publicar("fin", mensaje, estado=estado)
        self.fin = datetime.now(UTC)
        self.estado = estado

    def resumen(self) -> EstadoEjecucion:
        return EstadoEjecucion(
            id=self.id,
            documento=self.documento,
            estado=self.estado,
            inicio=self.inicio,
            fin=self.fin,
        )


Trabajo = Callable[[Ejecucion], None]


class RegistroEjecuciones:
    """Ejecuciones en memoria. Se pierden al reiniciar la API; los resultados quedan en disco."""

    def __init__(self, maximo: int = MAX_GUARDADAS) -> None:
        self._maximo = maximo
        self._ejecuciones: dict[str, Ejecucion] = {}
        self._candado = threading.Lock()

    def iniciar(self, documento: str, trabajo: Trabajo) -> Ejecucion:
        with self._candado:
            for anterior in self._ejecuciones.values():
                if not anterior.terminada:
                    raise EjecucionEnCurso(anterior.id)
            ejecucion = Ejecucion(documento)
            self._ejecuciones[ejecucion.id] = ejecucion
            self._recortar()
        hilo = threading.Thread(
            target=_correr, args=(ejecucion, trabajo), name=f"ejecucion-{ejecucion.id[:8]}"
        )
        hilo.daemon = True
        hilo.start()
        return ejecucion

    def obtener(self, id_ejecucion: str) -> Ejecucion | None:
        with self._candado:
            return self._ejecuciones.get(id_ejecucion)

    def _recortar(self) -> None:
        terminadas = [e.id for e in self._ejecuciones.values() if e.terminada]
        while len(self._ejecuciones) > self._maximo and terminadas:
            del self._ejecuciones[terminadas.pop(0)]


def _correr(ejecucion: Ejecucion, trabajo: Trabajo) -> None:
    try:
        trabajo(ejecucion)
    except (ErrorDocumento, ErrorLLM, ErrorFase) as error:
        _fallar(ejecucion, str(error))
    except Exception:
        log.exception("La ejecución %s falló", ejecucion.id)
        _fallar(ejecucion, "Error interno del motor; revisa el log de la API")
    else:
        ejecucion.terminar("completada", "Ejecución completada")


def _fallar(ejecucion: Ejecucion, mensaje: str) -> None:
    if ejecucion.fase_actual is not None:
        ejecucion.publicar("fase", mensaje, fase=ejecucion.fase_actual, estado="fallida")
    ejecucion.terminar("fallida", mensaje)


# --- Fase 1 --------------------------------------------------------------------------------------


def trabajo_fase1(
    documento: DocumentoCargado,
    ruta: Path,
    carpeta_requisitos: Path,
    crear_llm: Callable[[], ProveedorLLM],
) -> Trabajo:
    """Fase 1 completa, como `framework requisitos clasificar`: extraer, normalizar y clasificar.

    Guarda el modelo en `carpeta_requisitos/<id del documento>.modelo_requisitos.json`.
    """

    def trabajo(ejecucion: Ejecucion) -> None:
        from orchestrator.ingest import (
            DocumentoOrigen,
            ModeloRequisitos,
            construir_requisitos,
            extraer_markdown,
            segmentar,
        )
        from orchestrator.ingest.clasificacion import clasificar_unidades

        def avance(mensaje: str, progreso: float) -> None:
            ejecucion.publicar("avance", mensaje, fase=1, progreso=round(progreso, 3))

        ejecucion.publicar(
            "fase", "Adquisición de requisitos", fase=1, estado="en_curso", progreso=0.0
        )
        avance(f"Extrayendo el texto de {documento.nombre}", 0.02)
        extraido = extraer_markdown(ruta, documento.nombre)
        avance(f"Texto extraído con {extraido.herramienta}: {extraido.caracteres} caracteres", 0.1)

        unidades = segmentar(extraido.markdown)
        # Las tablas no se clasifican solas: van como contexto de su sección.
        por_clasificar = sum(1 for u in unidades if u.bloque != "tabla")
        avance(f"Texto normalizado: {len(unidades)} unidades", 0.15)

        llm = crear_llm()
        hechas = 0

        def al_avanzar(titulo: str, total: int) -> None:
            nonlocal hechas
            avance(
                f"Clasificando «{titulo}» ({total} unidades)",
                0.15 + 0.8 * hechas / max(por_clasificar, 1),
            )
            hechas += total

        pares = clasificar_unidades(unidades, llm, al_avanzar=al_avanzar)
        requisitos = construir_requisitos(pares)
        if not requisitos:
            raise ErrorFase("El LLM no encontró ningún requisito en el documento")
        modelo = ModeloRequisitos(
            documento=DocumentoOrigen(
                nombre=extraido.nombre, sha256=extraido.sha256, herramienta=extraido.herramienta
            ),
            requisitos=requisitos,
        )
        carpeta_requisitos.mkdir(parents=True, exist_ok=True)
        archivo = carpeta_requisitos / f"{documento.id}.modelo_requisitos.json"
        archivo.write_text(modelo.model_dump_json(indent=2), encoding="utf-8")

        tipos = Counter(r.tipo for r in requisitos)
        etiquetas = Counter(e for r in requisitos for e in r.etiquetas)
        resumen = ResumenFase1(
            archivo=archivo.name,
            funcionales=tipos["funcional"],
            no_funcionales=tipos["no_funcional"],
            descartadas=sum(1 for _, c in pares if not c.es_requisito),
            etiquetas=dict(etiquetas.most_common()),
            requisitos=requisitos,
        )
        ejecucion.publicar(
            "resultado",
            f"{len(requisitos)} requisitos identificados ({resumen.funcionales} funcionales, "
            f"{resumen.no_funcionales} no funcionales)",
            fase=1,
            progreso=1.0,
            resultado=resumen,
        )
        ejecucion.publicar(
            "fase", "Adquisición de requisitos", fase=1, estado="completada", progreso=1.0
        )

    return trabajo
