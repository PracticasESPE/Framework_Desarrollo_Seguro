"""Ejecuciones del pipeline lanzadas desde la API: estado, progreso y cancelación.

Cada ejecución corre en un hilo aparte y publica eventos que la API envía al dashboard con
Server-Sent Events (`GET /ejecuciones/{id}/eventos`). El estado de una ejecución y el de cada fase
se calculan a partir de esos mismos eventos, así que la API y el dashboard nunca discrepan. Por
ahora el motor ejecuta la fase 1 (adquisición de requisitos), la fase 2 (propuesta arquitectónica)
y la fase 3 (generación de los microservicios); las demás fases se sumarán cuando existan en el
motor. Las fases 2 y 3 no arrancan solas: el usuario revisa el resultado de la anterior y las
lanza con una petición aparte, porque gastan llamadas al LLM.

Los eventos se guardan en memoria con un número correlativo. Si el navegador pierde la conexión,
EventSource se reconecta enviando `Last-Event-ID` y recibe solo lo que le faltaba.

La cancelación es cooperativa: la ejecución comprueba la petición entre pasos (después de extraer,
antes de cada sección que clasifica el LLM y antes de guardar) y corta las esperas por el límite de
uso del LLM. Una llamada al LLM o una extracción con Docling ya empezadas terminan antes de que la
ejecución se detenga.

Seguridad:
- Una sola ejecución a la vez (CWE-400): la fase 1 ocupa Docling y la cuota del LLM, la fase 2
  la cuota del LLM, y la fase 3 la cuota del LLM, npm, tsc y Jest.
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
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from orchestrator.architecture.ciclo import INTENTOS, ResultadoCiclo
from orchestrator.architecture.modelo import Arquitectura
from orchestrator.architecture.validacion import DecisionArquitectura, validar_arquitectura
from orchestrator.documentos import DocumentoCargado, ErrorDocumento
from orchestrator.fases import FASES
from orchestrator.generation.sistema import ResultadoSistema
from orchestrator.generation.sistema import mensaje_breve as motivo_breve
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


class IntentoResumen(BaseModel):
    """Un intento del ciclo LLM ↔ OPA: lo que propuso el LLM y lo que decidió OPA."""

    numero: int
    origen: str = Field(description="«llm» si lo propuso el LLM, «inicial» si ya existía")
    aprobado: bool
    justificacion: str
    bloqueantes: list[str] = Field(description="Motivos por los que OPA rechazó la propuesta")
    advertencias: list[str]


class DependenciaResumen(BaseModel):
    servicio: str = Field(description="Servicio del que se depende")
    tipo: Literal["sincrona", "asincrona"]
    motivo: str


class ServicioResumen(BaseModel):
    nombre: str
    contexto: str
    responsabilidad: str
    base_datos: str
    requisitos: list[str]
    depende_de: list[DependenciaResumen]
    etiquetas: list[str]


class DecisionResumen(BaseModel):
    id: str
    titulo: str
    decision: str
    justificacion: str
    requisitos: list[str]


class PatronResumen(BaseModel):
    patron: str
    implementacion: str
    motivo: str
    controles: list[str]


class AdrResumen(BaseModel):
    archivo: str
    titulo: str
    redactado_por: str


class ResumenFase2(BaseModel):
    """Resultado de la fase 2 que se muestra en el dashboard.

    Si OPA no aprobó ninguna propuesta, `aprobada` es False y los servicios y decisiones son los del
    último intento, para que una persona los revise; no hay ADR ni diagrama.
    """

    aprobada: bool
    justificacion: str = Field(description="Decisión final de OPA")
    intentos: list[IntentoResumen]
    servicios: list[ServicioResumen]
    transversales: list[str]
    etiquetas_transversales: list[str] = Field(
        description="Etiquetas de seguridad de los requisitos transversales"
    )
    decisiones: list[DecisionResumen]
    patrones: list[PatronResumen]
    archivo_intentos: str = Field(description="Registro de intentos del ciclo, en salida/")
    archivo_arquitectura: str | None = Field(default=None, description="arquitectura.json aprobada")
    adr: list[AdrResumen] = Field(default_factory=list)
    carpeta_adr: str | None = None
    archivo_diagrama: str | None = Field(default=None, description="Documento con el diagrama C4")
    diagrama: str | None = Field(default=None, description="Markdown del documento, con Mermaid")
    ejecucion_neo4j: str | None = Field(
        default=None, description="Ejecución de Neo4j con las decisiones; None si no se guardaron"
    )
    decisiones_neo4j: int | None = None


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
    arquitectura: ResumenFase2 | None = None
    servicios: ResultadoSistema | None = None


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
    """Estado completo: el de cada fase del pipeline y el resultado de la fase 1, la 2 o la 3."""

    fases: list[FaseEjecucion]
    eventos: int = Field(description="Eventos publicados; el flujo SSE los reenvía todos")
    resultado: ResumenFase1 | None = None
    arquitectura: ResumenFase2 | None = None
    servicios: ResultadoSistema | None = None


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
        arquitectura = next((e.arquitectura for e in reversed(eventos) if e.arquitectura), None)
        servicios = next((e.servicios for e in reversed(eventos) if e.servicios), None)
        return DetalleEjecucion(
            **self.resumen().model_dump(),
            fases=estado_de_fases(eventos),
            eventos=len(eventos),
            resultado=resultado,
            arquitectura=arquitectura,
            servicios=servicios,
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


# --- Fase 2 --------------------------------------------------------------------------------------

RegistrarDecisiones = Callable[[ModeloRequisitos, ResultadoCiclo], tuple[str, int]]

NOMBRE_FASE2 = "Análisis y propuesta arquitectónica"
# Reparto del avance de la fase 2: ciclo LLM ↔ OPA, guardado, ADR y diagrama.
_INICIO_CICLO = 0.05
_FIN_CICLO = 0.5
_FIN_ADR = 0.92


def nombre_modelo_requisitos(id_documento: str) -> str:
    return f"{id_documento}.modelo_requisitos.json"


def trabajo_fase2(
    documento: DocumentoCargado,
    carpeta_requisitos: Path,
    carpeta_arquitectura: Path,
    crear_llm: Callable[[], ProveedorLLM],
    registrar: RegistrarDecisiones | None = None,
    intentos: int = INTENTOS,
    validar: Callable[[Arquitectura], DecisionArquitectura] = validar_arquitectura,
) -> Trabajo:
    """Fase 2 completa, como `framework arquitectura proponer`, `adr` y `diagrama` en secuencia.

    Parte del `modelo_requisitos.json` que dejó la fase 1 en disco, así que no depende de que la
    ejecución de la fase 1 siga en memoria. El LLM propone la arquitectura y OPA la valida (hasta
    `intentos` veces, con `validar`); si la aprueba, se guardan `arquitectura.json`, los ADR y el
    diagrama C4 en `carpeta_arquitectura`. Las decisiones se registran en Neo4j si se indica
    `registrar`; si no está disponible, la fase termina igual y lo avisa.

    Si OPA no aprueba ninguna propuesta, la fase falla con un resumen del ciclo: la arquitectura
    queda para revisión humana.
    """

    def trabajo(ejecucion: Ejecucion) -> None:
        from orchestrator.architecture import ciclo_llm_opa, proponer_arquitectura
        from orchestrator.architecture.adr import (
            ErrorADR,
            construir_adrs,
            escribir_adrs,
            redactar,
        )
        from orchestrator.architecture.c4 import (
            ErrorDiagrama,
            documento_arquitectura,
            enlaces_adr,
            escribir_documento,
        )
        from orchestrator.opa import ErrorOPA

        def avance(mensaje: str, progreso: float | None = None) -> None:
            campos = {} if progreso is None else {"progreso": round(progreso, 3)}
            ejecucion.publicar("avance", mensaje, fase=2, **campos)

        def dormir(segundos: float) -> None:
            # El proveedor rechazó por límite de uso: se avisa y la espera se corta al cancelar.
            avance(
                f"El proveedor del LLM alcanzó su límite de uso: se reintenta en {segundos:.0f} s"
            )
            ejecucion.esperar(segundos)

        def progreso_del_ciclo(intento: int) -> float:
            return _INICIO_CICLO + (_FIN_CICLO - _INICIO_CICLO) * intento / intentos

        ejecucion.publicar("fase", NOMBRE_FASE2, fase=2, estado="en_curso", progreso=0.0)
        modelo = _leer_modelo_requisitos(carpeta_requisitos, documento.id)
        avance(f"Requisitos cargados: {len(modelo.requisitos)} de {modelo.documento.nombre}", 0.03)

        llm = crear_llm()
        if isinstance(llm, ProveedorEnCadena):

            def al_cambiar(de: str, a: str, motivo: str) -> None:
                avance(f"{motivo_breve(motivo)}: se pasa a {a}")

            llm.al_cambiar = al_cambiar

        llamadas = 0

        def proponer(modelo_, llm_, nivel="razonamiento", retroalimentacion=None):  # noqa: ANN001, ANN202
            nonlocal llamadas
            ejecucion.comprobar_cancelacion()  # antes de gastar otra llamada al LLM
            llamadas += 1
            con_motivos = " con los motivos de OPA" if retroalimentacion else ""
            avance(
                f"Pidiendo al LLM la arquitectura (intento {llamadas} de {intentos}){con_motivos}",
                progreso_del_ciclo(llamadas - 1),
            )

            def reintento(numero: int, problemas: list[str]) -> None:
                avance(
                    f"La propuesta {numero} no pasó las comprobaciones del motor: "
                    + "; ".join(problemas)
                )

            return proponer_arquitectura(
                modelo_,
                llm_,
                nivel=nivel,
                retroalimentacion=retroalimentacion,
                dormir=dormir,
                al_reintentar=reintento,
            )

        def al_intento(intento) -> None:  # noqa: ANN001
            veredicto = "OPA aprueba" if intento.decision.aprobado else "OPA rechaza"
            avance(
                f"Intento {intento.numero}: {veredicto}. {intento.decision.justificacion}",
                progreso_del_ciclo(intento.numero),
            )
            for bloqueante in intento.decision.bloqueantes:
                avance(f"OPA rechaza: {bloqueante.motivo}")

        try:
            resultado = ciclo_llm_opa(
                modelo,
                llm,
                intentos=intentos,
                al_intento=al_intento,
                validar=validar,
                proponer=proponer,
            )
        except ErrorOPA as error:
            raise ErrorFase(str(error)) from error
        avance(f"Uso del LLM: {describir_uso(llm)}")
        ejecucion.comprobar_cancelacion()

        carpeta_arquitectura.mkdir(parents=True, exist_ok=True)
        archivo_intentos = carpeta_arquitectura / f"{documento.id}.intentos.json"
        archivo_intentos.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")
        final = resultado.final
        resumen = _resumen_fase2(resultado, archivo_intentos.name)

        if resultado.aprobada:
            archivo = carpeta_arquitectura / f"{documento.id}.arquitectura.json"
            archivo.write_text(final.arquitectura.model_dump_json(indent=2), encoding="utf-8")
            resumen.archivo_arquitectura = archivo.name
            avance(
                f"Arquitectura aprobada por OPA: {len(final.arquitectura.servicios)} servicios, "
                f"{len(final.arquitectura.decisiones)} decisiones",
                _FIN_CICLO + 0.02,
            )

        if registrar is not None:
            registro = _registrar_decisiones(ejecucion, registrar, modelo, resultado)
            if registro is not None:
                resumen.ejecucion_neo4j, resumen.decisiones_neo4j = registro

        if not resultado.aprobada:
            _publicar_resultado_fase2(ejecucion, resumen)
            raise ErrorFase(
                f"OPA no aprobó ninguna propuesta en {len(resultado.intentos)} intentos: "
                "la arquitectura queda para revisión humana"
            )

        ejecucion.comprobar_cancelacion()
        try:
            adrs = construir_adrs(final.arquitectura, final.decision, modelo)
            avance(f"Redactando {len(adrs)} ADR", 0.55)
            hechos = 0

            def al_redactar(adr, por: str) -> None:  # noqa: ANN001
                nonlocal hechos
                hechos += 1
                avance(
                    f"ADR-{adr.numero:04d} «{adr.titulo}»: {por}",
                    0.55 + (_FIN_ADR - 0.55) * hechos / len(adrs),
                )
                ejecucion.comprobar_cancelacion()  # antes de la siguiente llamada al LLM

            redactar(adrs, llm, al_redactar=al_redactar, dormir=dormir)
            carpeta_adr = carpeta_arquitectura / f"{documento.id}.adr"
            escribir_adrs(adrs, final.arquitectura, final.decision, carpeta_adr)
            avance(f"ADR escritos en {carpeta_adr.name}", _FIN_ADR)

            destino = carpeta_arquitectura / f"{documento.id}.arquitectura.md"
            contenido = documento_arquitectura(
                final.arquitectura,
                modelo,
                final.decision,
                date.today(),
                enlaces_adr(adrs, carpeta_adr, destino),
            )
            escribir_documento(contenido, destino)
        except (ErrorADR, ErrorDiagrama) as error:
            raise ErrorFase(str(error)) from error
        avance(f"Diagrama C4 escrito en {destino.name}", 0.98)

        resumen.adr = [
            AdrResumen(archivo=a.archivo, titulo=a.titulo, redactado_por=a.redactado_por)
            for a in adrs
        ]
        resumen.carpeta_adr = carpeta_adr.name
        resumen.archivo_diagrama = destino.name
        resumen.diagrama = contenido
        _publicar_resultado_fase2(ejecucion, resumen)
        ejecucion.publicar("fase", NOMBRE_FASE2, fase=2, estado="completada", progreso=1.0)

    return trabajo


def _leer_modelo_requisitos(carpeta: Path, id_documento: str) -> ModeloRequisitos:
    from pydantic import ValidationError

    archivo = carpeta / nombre_modelo_requisitos(id_documento)
    try:
        return ModeloRequisitos.model_validate_json(archivo.read_bytes())
    except FileNotFoundError as error:
        raise ErrorFase(
            "Falta la fase 1: procesa el documento antes de proponer la arquitectura"
        ) from error
    except ValidationError as error:
        log.exception("El modelo de requisitos %s no es válido", archivo.name)
        raise ErrorFase(
            "El modelo de requisitos guardado no es válido; vuelve a procesar el documento"
        ) from error


def _publicar_resultado_fase2(ejecucion: Ejecucion, resumen: ResumenFase2) -> None:
    if resumen.aprobada:
        mensaje = (
            f"Arquitectura aprobada: {len(resumen.servicios)} servicios, "
            f"{len(resumen.decisiones)} decisiones, {len(resumen.adr)} ADR"
        )
    else:
        mensaje = f"OPA no aprobó la arquitectura tras {len(resumen.intentos)} intentos"
    ejecucion.publicar(
        "resultado",
        mensaje,
        fase=2,
        progreso=1.0 if resumen.aprobada else None,
        arquitectura=resumen,
    )


def _resumen_fase2(resultado: ResultadoCiclo, archivo_intentos: str) -> ResumenFase2:
    final = resultado.final
    arquitectura = final.arquitectura
    return ResumenFase2(
        aprobada=resultado.aprobada,
        justificacion=final.decision.justificacion,
        intentos=[
            IntentoResumen(
                numero=i.numero,
                origen=i.origen,
                aprobado=i.decision.aprobado,
                justificacion=i.decision.justificacion,
                bloqueantes=[b.motivo for b in i.decision.bloqueantes],
                advertencias=[a.motivo for a in i.decision.advertencias],
            )
            for i in resultado.intentos
        ],
        servicios=[
            ServicioResumen(
                nombre=s.nombre,
                contexto=s.contexto,
                responsabilidad=s.responsabilidad,
                base_datos=s.base_datos,
                requisitos=list(s.requisitos),
                depende_de=[
                    DependenciaResumen(servicio=d.servicio, tipo=d.tipo, motivo=d.motivo)
                    for d in s.depende_de
                ],
                etiquetas=list(s.etiquetas),
            )
            for s in arquitectura.servicios
        ],
        transversales=list(arquitectura.transversales),
        etiquetas_transversales=list(arquitectura.etiquetas_transversales),
        decisiones=[
            DecisionResumen(
                id=d.id,
                titulo=d.titulo,
                decision=d.decision,
                justificacion=d.justificacion,
                requisitos=list(d.requisitos),
            )
            for d in arquitectura.decisiones
        ],
        patrones=[
            PatronResumen(
                patron=p.patron,
                implementacion=p.implementacion,
                motivo=p.motivo,
                controles=list(p.controles),
            )
            for p in final.decision.patrones
        ],
        archivo_intentos=archivo_intentos,
    )


def _registrar_decisiones(
    ejecucion: Ejecucion,
    registrar: RegistrarDecisiones,
    modelo: ModeloRequisitos,
    resultado: ResultadoCiclo,
) -> tuple[str, int] | None:
    """Guarda las decisiones en Neo4j sin que un fallo detenga la fase: avisa y sigue."""
    from orchestrator.knowledge import ErrorGrafo

    ejecucion.publicar("avance", "Registrando las decisiones en Neo4j", fase=2)
    try:
        ejecucion_neo4j, registradas = registrar(modelo, resultado)
    except ErrorGrafo as error:
        ejecucion.publicar("avance", f"No se registraron en Neo4j: {error}", fase=2)
        return None
    except Exception:
        # El registro es un extra: un error inesperado no debe perder la arquitectura.
        log.exception("No se pudieron registrar en Neo4j las decisiones de %s", ejecucion.id)
        ejecucion.publicar("avance", "No se registraron en Neo4j por un error interno", fase=2)
        return None
    ejecucion.publicar(
        "avance",
        f"Decisiones registradas en Neo4j: {registradas} (ejecución {ejecucion_neo4j})",
        fase=2,
    )
    return ejecucion_neo4j, registradas


def registrar_decisiones_en_neo4j(
    modelo: ModeloRequisitos, resultado: ResultadoCiclo
) -> tuple[str, int]:
    """Guarda las decisiones del ciclo en la ejecución con los requisitos del documento.

    Si no hay ninguna, crea una y registra los requisitos, para que las decisiones queden
    enlazadas a ellos. Es lo mismo que hace `framework arquitectura proponer`.
    """
    from orchestrator.config import obtener_configuracion
    from orchestrator.knowledge import conectar, crear_ejecucion, registrar_requisitos
    from orchestrator.knowledge.registro import ejecucion_de_documento, registrar_decisiones

    config = obtener_configuracion()
    driver = conectar(config)
    try:
        db = config.neo4j_database
        ejecucion_id = ejecucion_de_documento(driver, modelo.documento.sha256, db)
        if ejecucion_id is None:
            ejecucion_id = crear_ejecucion(driver, documento=modelo.documento.nombre, base_datos=db)
            registrar_requisitos(driver, ejecucion_id, modelo, base_datos=db)
        registradas = registrar_decisiones(driver, ejecucion_id, resultado, base_datos=db)
    finally:
        driver.close()
    return ejecucion_id, registradas


# --- Fase 3 --------------------------------------------------------------------------------------


NOMBRE_FASE3 = "Generación de la estructura interna"

# Función servicio -> contexto GraphRAG y la que cierra la conexión con Neo4j.
CrearContexto = Callable[[], tuple[Callable[[object], object], Callable[[], None]]]


def nombre_arquitectura(id_documento: str) -> str:
    return f"{id_documento}.arquitectura.json"


def trabajo_fase3(
    documento: DocumentoCargado,
    carpeta_requisitos: Path,
    carpeta_arquitectura: Path,
    carpeta_servicios: Path,
    crear_llm: Callable[[], ProveedorLLM],
    crear_contexto: CrearContexto | None = None,
    compilar: bool = True,
) -> Trabajo:
    """Fase 3 completa, como `framework servicio sistema`: un microservicio por servicio.

    Parte de `arquitectura.json` (fase 2) y del modelo de requisitos (fase 1) guardados en disco.
    Cada ejecución escribe en una carpeta nueva, `carpeta_servicios/<documento>-<fecha>`, para no
    tocar nunca lo generado antes. Las dependencias se instalan una sola vez en
    `carpeta_servicios/.dependencias` y las comparten todos los servicios y todas las ejecuciones
    con el mismo package-lock.json. Con `crear_contexto`, cada servicio recibe el contexto de
    seguridad de GraphRAG; si Neo4j no responde, la fase sigue sin él y lo avisa.
    """

    def trabajo(ejecucion: Ejecucion) -> None:
        from orchestrator.generation.sistema import (
            CARPETA_DEPENDENCIAS,
            ErrorSistema,
            generar_sistema,
        )

        def avance(mensaje: str, progreso: float | None = None) -> None:
            campos = {} if progreso is None else {"progreso": round(min(progreso, 1.0), 3)}
            ejecucion.publicar("avance", mensaje, fase=3, **campos)

        ejecucion.publicar("fase", NOMBRE_FASE3, fase=3, estado="en_curso", progreso=0.0)
        modelo = _leer_modelo_requisitos(carpeta_requisitos, documento.id)
        arquitectura = _leer_arquitectura(carpeta_arquitectura, documento.id)
        avance(
            f"Arquitectura cargada: {len(arquitectura.servicios)} servicios y "
            f"{len(modelo.requisitos)} requisitos",
            0.0,
        )

        llm = crear_llm()
        if isinstance(llm, ProveedorEnCadena):

            def al_cambiar(de: str, a: str, motivo: str) -> None:
                avance(f"{motivo_breve(motivo)}: se pasa a {a}")

            llm.al_cambiar = al_cambiar

        contexto_de, cerrar = None, None
        if crear_contexto is not None:
            try:
                contexto_de, cerrar = crear_contexto()
                avance("Contexto de seguridad: GraphRAG sobre Neo4j")
            except Exception as error:  # Neo4j o los embeddings no están disponibles
                log.warning("Fase 3 sin contexto GraphRAG: %s", error)
                avance("Sin contexto GraphRAG (Neo4j no responde): los prompts van sin él")

        fecha = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        destino = carpeta_servicios / f"{documento.id}-{fecha}"
        try:
            resultado = generar_sistema(
                arquitectura,
                modelo,
                destino,
                llm,
                documento=documento.nombre,
                contexto_de=contexto_de,
                compilar_servicios=compilar,
                dependencias=carpeta_servicios / CARPETA_DEPENDENCIAS,
                avance=avance,
                comprobar_cancelacion=ejecucion.comprobar_cancelacion,
                esperar=ejecucion.esperar,
            )
        except ErrorSistema as error:
            raise ErrorFase(str(error)) from error
        finally:
            if cerrar is not None:
                cerrar()
        avance(f"Uso del LLM: {describir_uso(llm)}")

        # La carpeta solo se muestra: relativa a la de servicios, sin la ruta de la máquina.
        resultado.carpeta = destino.name
        total = len(resultado.servicios)
        mensaje = f"{resultado.completos} de {total} servicios generados y verificados"
        ejecucion.publicar("resultado", mensaje, fase=3, progreso=1.0, servicios=resultado)
        if resultado.completos == 0:
            raise ErrorFase(
                f"Ningún servicio se completó: {mensaje}; revisa el detalle de cada uno"
            )
        ejecucion.publicar("fase", NOMBRE_FASE3, fase=3, estado="completada", progreso=1.0)

    return trabajo


def _leer_arquitectura(carpeta: Path, id_documento: str) -> Arquitectura:
    from pydantic import ValidationError

    archivo = carpeta / nombre_arquitectura(id_documento)
    try:
        return Arquitectura.model_validate_json(archivo.read_bytes())
    except FileNotFoundError as error:
        raise ErrorFase(
            "Falta la fase 2: propón y aprueba la arquitectura antes de generar los servicios"
        ) from error
    except ValidationError as error:
        log.exception("La arquitectura %s no es válida", archivo.name)
        raise ErrorFase(
            "La arquitectura guardada no es válida; vuelve a ejecutar la fase 2"
        ) from error


def contexto_graphrag_en_neo4j(k: int = 3):  # noqa: ANN201
    """Contexto de seguridad de cada servicio con GraphRAG, y la función que cierra Neo4j.

    Lo mismo que usa `framework servicio prompt`: las preguntas fijas de las etiquetas de seguridad
    del servicio, respondidas con Neo4j y los embeddings locales.
    """
    from orchestrator.config import obtener_configuracion
    from orchestrator.knowledge import conectar
    from orchestrator.knowledge.embeddings import EmbeddingsLocales
    from orchestrator.knowledge.graphrag import consultar
    from orchestrator.llm.prompts import contexto_de_seguridad

    config = obtener_configuracion()
    if config.neo4j_password is None:
        raise RuntimeError("NEO4J_PASSWORD no está configurada")
    proveedor = EmbeddingsLocales(config.embeddings_modelo, config.embeddings_cache)
    driver = conectar(config)

    def consultor(pregunta: str):  # noqa: ANN202
        return consultar(driver, proveedor, pregunta, k=k, base_datos=config.neo4j_database)

    def contexto_de(servicio):  # noqa: ANN001, ANN202
        return contexto_de_seguridad(servicio.etiquetas, consultor)

    return contexto_de, driver.close
