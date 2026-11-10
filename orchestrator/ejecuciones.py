"""Ejecuciones del pipeline lanzadas desde la API: estado, progreso y cancelación.

Cada ejecución corre en un hilo aparte y publica eventos que la API envía al dashboard con
Server-Sent Events (`GET /ejecuciones/{id}/eventos`). El estado de una ejecución y el de cada fase
se calculan a partir de esos mismos eventos, así que la API y el dashboard nunca discrepan. Por
ahora el motor ejecuta la fase 1 (adquisición de requisitos); las demás fases se sumarán cuando
existan en el motor.

Los eventos se guardan en memoria con un número correlativo. Si el navegador pierde la conexión,
EventSource se reconecta enviando `Last-Event-ID` y recibe solo lo que le faltaba.

La cancelación es cooperativa: la ejecución comprueba la petición entre pasos (después de extraer,
antes de cada sección que clasifica el LLM y antes de guardar) y corta las esperas por el límite de
uso del LLM. Una llamada al LLM o una extracción con Docling ya empezadas terminan antes de que la
ejecución se detenga.

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
from orchestrator.fases import FASES
from orchestrator.ingest.requisito import ModeloRequisitos, Requisito
from orchestrator.llm import ErrorLLM, ProveedorEnCadena, ProveedorLLM, describir_uso

log = logging.getLogger(__name__)

MAX_GUARDADAS = 20
ID_EJECUCION = r"^[0-9a-f]{32}$"

Estado = Literal["en_curso", "completada", "fallida", "cancelada"]
EstadoFinal = Literal["completada", "fallida", "cancelada"]
EstadoFase = Literal["pendiente", "en_curso", "completada", "fallida", "cancelada"]
TipoEvento = Literal["fase", "avance", "resultado", "fin"]


class ResumenFase1(BaseModel):
    """Resultado de la fase 1 que se muestra en el dashboard."""

    archivo: str = Field(description="Nombre del modelo_requisitos.json guardado")
    funcionales: int
    no_funcionales: int
    descartadas: int = Field(description="Unidades del documento que no son requisitos")
    etiquetas: dict[str, int] = Field(description="Etiquetas de seguridad y cuántas veces salen")
    requisitos: list[Requisito]
    ejecucion_neo4j: str | None = Field(
        default=None,
        description="Ejecución de Neo4j con los nodos Requisito; None si no se registraron",
    )


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
    """Resumen de una ejecución: lo que devuelven la lista y la creación."""

    id: str
    documento: str = Field(description="Id del documento procesado")
    nombre_documento: str = Field(description="Nombre original del documento; solo se muestra")
    estado: Estado
    fase_actual: int | None = Field(description="Última fase que empezó")
    progreso: float | None = Field(description="Avance de la fase actual, de 0 a 1")
    mensaje: str | None = Field(description="Último evento: lo que está haciendo o cómo terminó")
    cancelacion_pedida: bool
    inicio: datetime
    fin: datetime | None = None


class FaseEjecucion(BaseModel):
    numero: int
    nombre: str
    es_gate: bool
    estado: EstadoFase
    mensaje: str | None = None
    progreso: float | None = None


class DetalleEjecucion(EstadoEjecucion):
    """Estado completo: el de cada fase del pipeline y el resultado de la fase 1."""

    fases: list[FaseEjecucion]
    eventos: int = Field(description="Eventos publicados; el flujo SSE los reenvía todos")
    resultado: ResumenFase1 | None = None


class EjecucionEnCurso(Exception):
    def __init__(self, id_ejecucion: str) -> None:
        super().__init__(f"Ya hay una ejecución en curso ({id_ejecucion}); espera a que termine")
        self.id_ejecucion = id_ejecucion


class EjecucionTerminada(Exception):
    """Se pidió cancelar una ejecución que ya había terminado."""


class EjecucionCancelada(Exception):
    """La ejecución se detuvo porque se pidió cancelarla."""


class ErrorFase(Exception):
    """Fallo esperado de una fase. El mensaje se puede mostrar en el dashboard."""


class Ejecucion:
    def __init__(self, documento: str, nombre_documento: str = "") -> None:
        self.id = uuid.uuid4().hex
        self.documento = documento
        self.nombre_documento = nombre_documento or documento
        self.estado: Estado = "en_curso"
        self.inicio = datetime.now(UTC)
        self.fin: datetime | None = None
        self.fase_actual: int | None = None
        self._eventos: list[Evento] = []
        self._candado = threading.Lock()
        self._cancelacion = threading.Event()

    @property
    def terminada(self) -> bool:
        return self.estado != "en_curso"

    @property
    def cancelacion_pedida(self) -> bool:
        return self._cancelacion.is_set()

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

    def pedir_cancelacion(self) -> None:
        if self.terminada:
            raise EjecucionTerminada(f"La ejecución ya terminó ({self.estado})")
        self._cancelacion.set()

    def esperar(self, segundos: float) -> None:
        """Pausa que se interrumpe en cuanto se pide cancelar."""
        if self._cancelacion.wait(timeout=segundos):
            self.comprobar_cancelacion()

    def comprobar_cancelacion(self) -> None:
        """Lo llama el trabajo entre pasos: si se pidió cancelar, se detiene ahí."""
        if self._cancelacion.is_set():
            raise EjecucionCancelada("Ejecución cancelada a petición del usuario")

    def terminar(self, estado: EstadoFinal, mensaje: str) -> None:
        # Primero el evento y después el estado: quien vea la ejecución terminada ya tiene el
        # evento «fin» disponible.
        self.publicar("fin", mensaje, estado=estado)
        self.fin = datetime.now(UTC)
        self.estado = estado

    def resumen(self) -> EstadoEjecucion:
        eventos = self.eventos_desde(0)
        ultimo = eventos[-1] if eventos else None
        progreso = next((e.progreso for e in reversed(eventos) if e.progreso is not None), None)
        return EstadoEjecucion(
            id=self.id,
            documento=self.documento,
            nombre_documento=self.nombre_documento,
            estado=self.estado,
            fase_actual=self.fase_actual,
            progreso=progreso,
            mensaje=ultimo.mensaje if ultimo else None,
            cancelacion_pedida=self.cancelacion_pedida,
            inicio=self.inicio,
            fin=self.fin,
        )

    def detalle(self) -> DetalleEjecucion:
        eventos = self.eventos_desde(0)
        resultado = next((e.resultado for e in reversed(eventos) if e.resultado), None)
        return DetalleEjecucion(
            **self.resumen().model_dump(),
            fases=estado_de_fases(eventos),
            eventos=len(eventos),
            resultado=resultado,
        )


def estado_de_fases(eventos: list[Evento]) -> list[FaseEjecucion]:
    """Las 11 fases con su estado según los eventos; las que no tienen eventos, pendientes.

    Es la misma regla que aplica el dashboard (dashboard/src/progreso.ts).
    """
    estados: dict[int, tuple[EstadoFase, str | None, float | None]] = {}
    for evento in eventos:
        if evento.fase is None:
            continue
        estado, mensaje, progreso = estados.get(evento.fase, ("en_curso", None, None))
        progreso = evento.progreso if evento.progreso is not None else progreso
        if evento.tipo == "fase" and evento.estado is not None:
            # Al empezar o terminar se conserva el último avance; si falla o se cancela, el motivo.
            estado = evento.estado
            if estado in ("fallida", "cancelada") or mensaje is None:
                mensaje = evento.mensaje
        else:
            mensaje = evento.mensaje
        estados[evento.fase] = (estado, mensaje, progreso)

    fases = []
    for fase in FASES:
        estado, mensaje, progreso = estados.get(fase.numero, ("pendiente", None, None))
        fases.append(
            FaseEjecucion(**fase.model_dump(), estado=estado, mensaje=mensaje, progreso=progreso)
        )
    return fases


Trabajo = Callable[[Ejecucion], None]


class RegistroEjecuciones:
    """Ejecuciones en memoria. Se pierden al reiniciar la API; los resultados quedan en disco."""

    def __init__(self, maximo: int = MAX_GUARDADAS) -> None:
        self._maximo = maximo
        self._ejecuciones: dict[str, Ejecucion] = {}
        self._candado = threading.Lock()

    def iniciar(self, documento: str, trabajo: Trabajo, nombre_documento: str = "") -> Ejecucion:
        with self._candado:
            for anterior in self._ejecuciones.values():
                if not anterior.terminada:
                    raise EjecucionEnCurso(anterior.id)
            ejecucion = Ejecucion(documento, nombre_documento)
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

    def listar(self) -> list[Ejecucion]:
        """De la más reciente a la más antigua."""
        with self._candado:
            return list(reversed(self._ejecuciones.values()))

    def _recortar(self) -> None:
        terminadas = [e.id for e in self._ejecuciones.values() if e.terminada]
        while len(self._ejecuciones) > self._maximo and terminadas:
            del self._ejecuciones[terminadas.pop(0)]


def _correr(ejecucion: Ejecucion, trabajo: Trabajo) -> None:
    try:
        trabajo(ejecucion)
    except EjecucionCancelada as aviso:
        _detener(ejecucion, "cancelada", str(aviso))
    except (ErrorDocumento, ErrorLLM, ErrorFase) as error:
        _detener(ejecucion, "fallida", str(error))
    except Exception:
        log.exception("La ejecución %s falló", ejecucion.id)
        _detener(ejecucion, "fallida", "Error interno del motor; revisa el log de la API")
    else:
        ejecucion.terminar("completada", "Ejecución completada")


def _detener(ejecucion: Ejecucion, estado: Literal["fallida", "cancelada"], mensaje: str) -> None:
    if ejecucion.fase_actual is not None:
        ejecucion.publicar("fase", mensaje, fase=ejecucion.fase_actual, estado=estado)
    ejecucion.terminar(estado, mensaje)


# --- Fase 1 --------------------------------------------------------------------------------------


RegistrarEnNeo4j = Callable[["ModeloRequisitos"], str]


def trabajo_fase1(
    documento: DocumentoCargado,
    ruta: Path,
    carpeta_requisitos: Path,
    crear_llm: Callable[[], ProveedorLLM],
    registrar: RegistrarEnNeo4j | None = None,
) -> Trabajo:
    """Fase 1 completa, como `framework requisitos clasificar`: extraer, normalizar y clasificar.

    Guarda el modelo en `carpeta_requisitos/<id del documento>.modelo_requisitos.json` y, si se
    indica `registrar`, guarda los requisitos como nodos Requisito en Neo4j, como `framework
    requisitos registrar`. Neo4j es opcional: si no está disponible, la fase termina igual y lo
    avisa, porque el modelo ya quedó en disco y se puede registrar después con ese comando.
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
        ejecucion.comprobar_cancelacion()

        unidades = segmentar(extraido.markdown)
        # Las tablas no se clasifican solas: van como contexto de su sección.
        por_clasificar = sum(1 for u in unidades if u.bloque != "tabla")
        avance(f"Texto normalizado: {len(unidades)} unidades", 0.15)

        llm = crear_llm()
        if isinstance(llm, ProveedorEnCadena):

            def al_cambiar(de: str, a: str, motivo: str) -> None:
                ejecucion.publicar("avance", f"{motivo}: la sección pasa a {a}", fase=1)

            llm.al_cambiar = al_cambiar
        hechas = 0

        def al_avanzar(titulo: str, total: int) -> None:
            nonlocal hechas
            ejecucion.comprobar_cancelacion()  # antes de gastar otra llamada al LLM
            avance(
                f"Clasificando «{titulo}» ({total} unidades)",
                0.15 + 0.8 * hechas / max(por_clasificar, 1),
            )
            hechas += total

        def dormir(segundos: float) -> None:
            # La clasificación espera así cuando el proveedor rechaza por límite de uso (20 y
            # 60 s). Se avisa al dashboard y la espera se corta si se pide cancelar.
            ejecucion.publicar(
                "avance",
                f"El proveedor del LLM alcanzó su límite de uso: se reintenta en {segundos:.0f} s",
                fase=1,
            )
            ejecucion.esperar(segundos)

        pares = clasificar_unidades(unidades, llm, al_avanzar=al_avanzar, dormir=dormir)
        ejecucion.publicar("avance", f"Uso del LLM: {describir_uso(llm)}", fase=1)
        ejecucion.comprobar_cancelacion()
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
        ejecucion_neo4j = (
            _registrar_en_neo4j(ejecucion, registrar, modelo, archivo) if registrar else None
        )

        tipos = Counter(r.tipo for r in requisitos)
        etiquetas = Counter(e for r in requisitos for e in r.etiquetas)
        resumen = ResumenFase1(
            archivo=archivo.name,
            funcionales=tipos["funcional"],
            no_funcionales=tipos["no_funcional"],
            descartadas=sum(1 for _, c in pares if not c.es_requisito),
            etiquetas=dict(etiquetas.most_common()),
            requisitos=requisitos,
            ejecucion_neo4j=ejecucion_neo4j,
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


def _registrar_en_neo4j(
    ejecucion: Ejecucion, registrar: RegistrarEnNeo4j, modelo: ModeloRequisitos, archivo: Path
) -> str | None:
    """Registra los requisitos en Neo4j sin que un fallo detenga la fase: avisa y sigue."""
    from orchestrator.knowledge import ErrorGrafo

    ejecucion.publicar("avance", "Registrando los requisitos en Neo4j", fase=1)
    pendiente = (
        f"Los requisitos están en {archivo.name}; se pueden registrar después con "
        "«framework requisitos registrar»."
    )
    try:
        ejecucion_neo4j = registrar(modelo)
    except ErrorGrafo as error:
        ejecucion.publicar("avance", f"No se registraron en Neo4j: {error} {pendiente}", fase=1)
        return None
    except Exception:
        # El registro es un extra de la fase: un error inesperado no debe perder la clasificación.
        log.exception("No se pudieron registrar en Neo4j los requisitos de %s", ejecucion.id)
        ejecucion.publicar(
            "avance", f"No se registraron en Neo4j por un error interno. {pendiente}", fase=1
        )
        return None
    ejecucion.publicar(
        "avance",
        f"Requisitos registrados en Neo4j: {len(modelo.requisitos)} (ejecución {ejecucion_neo4j})",
        fase=1,
    )
    return ejecucion_neo4j


def registrar_en_neo4j(modelo: ModeloRequisitos) -> str:
    """Crea una ejecución en Neo4j y guarda en ella los requisitos; devuelve su id.

    Es lo mismo que hace `framework requisitos registrar` sin `--ejecucion`.
    """
    from orchestrator.config import obtener_configuracion
    from orchestrator.knowledge import conectar, crear_ejecucion, registrar_requisitos

    config = obtener_configuracion()
    driver = conectar(config)
    try:
        db = config.neo4j_database
        ejecucion_id = crear_ejecucion(driver, documento=modelo.documento.nombre, base_datos=db)
        registrar_requisitos(driver, ejecucion_id, modelo, base_datos=db)
    finally:
        driver.close()
    return ejecucion_id
