// Cliente de la API del motor (orchestrator/api.py). Rutas relativas: el dashboard se sirve desde
// la misma API y en desarrollo Vite las reenvía (vite.config.ts).

export interface Salud {
  estado: string
  version: string
}

export interface Fase {
  numero: number
  nombre: string
  es_gate: boolean
}

export type Formato = 'pdf' | 'docx' | 'txt' | 'md'

export interface DocumentoCargado {
  id: string
  nombre: string
  formato: Formato
  tamano: number
  sha256: string
  fecha: string
}

export class ErrorApi extends Error {}

async function leer<T>(respuesta: Response): Promise<T> {
  if (!respuesta.ok) {
    throw new ErrorApi(await motivo(respuesta))
  }
  return (await respuesta.json()) as T
}

async function motivo(respuesta: Response): Promise<string> {
  try {
    const cuerpo = (await respuesta.json()) as { detail?: unknown }
    if (typeof cuerpo.detail === 'string') return cuerpo.detail
  } catch {
    // La respuesta no es JSON: se usa el mensaje genérico.
  }
  return `La API respondió con el código ${respuesta.status}`
}

export async function obtenerSalud(): Promise<Salud> {
  return leer<Salud>(await fetch('/salud'))
}

export async function obtenerFases(): Promise<Fase[]> {
  return leer<Fase[]>(await fetch('/fases'))
}

export async function listarDocumentos(): Promise<DocumentoCargado[]> {
  return leer<DocumentoCargado[]>(await fetch('/documentos'))
}

export type EstadoEjecucion = 'en_curso' | 'completada' | 'fallida' | 'cancelada'

export interface Ejecucion {
  id: string
  documento: string
  nombre_documento: string
  estado: EstadoEjecucion
  fase_actual: number | null
  progreso: number | null
  mensaje: string | null
  cancelacion_pedida: boolean
  inicio: string
  fin: string | null
}

export interface Requisito {
  id: string
  tipo: 'funcional' | 'no_funcional'
  texto: string
  ubicacion: string
  actor: string
  accion: string
  entidades: string[]
  servicio_sugerido: string
  etiquetas: string[]
}

export interface ResumenFase1 {
  archivo: string
  funcionales: number
  no_funcionales: number
  descartadas: number
  etiquetas: Record<string, number>
  requisitos: Requisito[]
  /** Ejecución de Neo4j con los nodos Requisito; null si no se registraron. */
  ejecucion_neo4j: string | null
}

export interface IntentoArquitectura {
  numero: number
  /** «llm» si lo propuso el LLM, «inicial» si ya existía. */
  origen: string
  aprobado: boolean
  justificacion: string
  /** Motivos por los que OPA rechazó la propuesta. */
  bloqueantes: string[]
  advertencias: string[]
}

export interface DependenciaPropuesta {
  servicio: string
  tipo: 'sincrona' | 'asincrona'
  motivo: string
}

export interface ServicioPropuesto {
  nombre: string
  contexto: string
  responsabilidad: string
  base_datos: string
  requisitos: string[]
  depende_de: DependenciaPropuesta[]
  etiquetas: string[]
}

export interface DecisionArquitectonica {
  id: string
  titulo: string
  decision: string
  justificacion: string
  requisitos: string[]
}

export interface PatronInferido {
  patron: string
  implementacion: string
  motivo: string
  controles: string[]
}

export interface AdrGenerado {
  archivo: string
  titulo: string
  redactado_por: string
}

/** Resultado de la fase 2 (ResumenFase2 en orchestrator/ejecuciones.py). */
export interface ResumenFase2 {
  aprobada: boolean
  justificacion: string
  intentos: IntentoArquitectura[]
  servicios: ServicioPropuesto[]
  transversales: string[]
  /** Etiquetas de seguridad de los requisitos transversales. */
  etiquetas_transversales: string[]
  decisiones: DecisionArquitectonica[]
  patrones: PatronInferido[]
  archivo_intentos: string
  archivo_arquitectura: string | null
  adr: AdrGenerado[]
  carpeta_adr: string | null
  archivo_diagrama: string | null
  /** Markdown del documento de arquitectura, con los diagramas C4 en Mermaid. */
  diagrama: string | null
  ejecucion_neo4j: string | null
  decisiones_neo4j: number | null
}

/**
 * Qué pasó con la lógica de negocio de una entidad: «aceptada» si el LLM la escribió y pasó el
 * análisis y tsc; «sin_logica» si ningún intento pasó (queda para revisión); «error» si no se
 * pudo pedir; «omitida» si no se llegó a generar.
 */
export type EstadoLogica = 'aceptada' | 'sin_logica' | 'error' | 'omitida'

export interface EntidadGenerada {
  nombre: string
  ruta: string
  logica: EstadoLogica
  requisitos: string[]
  /** Lo que el LLM no pudo implementar en las reglas. */
  pendientes: string[]
  intentos_logica: number
  pruebas_aceptadas: number
  pruebas_descartadas: number
  detalle: string | null
}

export interface ServicioGenerado {
  servicio: string
  carpeta: string
  puerto: number
  base_datos: string
  prefijo: string
  entidades: EntidadGenerada[]
  archivos: number
  estructura_valida: boolean
  problemas_estructura: string[]
  /** null si no se llegó a comprobar. */
  dependencias_permitidas: boolean | null
  problemas_dependencias: string[]
  dependencias_compartidas: boolean
  /** null si no se compiló. */
  compila: boolean | null
  errores_tsc: string[]
  error: string | null
  completo: boolean
}

/** Resultado de la fase 3 (ResultadoSistema en orchestrator/generation/sistema.py). */
export interface ResumenFase3 {
  documento: string
  /** Carpeta de los servicios dentro de salida/servicios. */
  carpeta: string
  compilado: boolean
  servicios: ServicioGenerado[]
  advertencias: string[]
  completos: number
}

/** Lo que llega en cada evento de /ejecuciones/{id}/eventos (orchestrator/ejecuciones.py). */
export interface EventoEjecucion {
  id: number
  tipo: 'fase' | 'avance' | 'resultado' | 'fin'
  fecha: string
  mensaje: string
  fase: number | null
  estado: EstadoEjecucion | null
  progreso: number | null
  resultado: ResumenFase1 | null
  arquitectura: ResumenFase2 | null
  servicios: ResumenFase3 | null
}

/** Lanza la fase 1 con un documento cargado; el progreso se sigue con `rutaEventos`. */
export async function iniciarEjecucion(documento: string): Promise<Ejecucion> {
  const respuesta = await fetch('/ejecuciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ documento }),
  })
  return leer<Ejecucion>(respuesta)
}

/**
 * Lanza la fase 2 (propuesta arquitectónica) con un documento que ya pasó por la fase 1. Gasta
 * llamadas al LLM, así que solo se llama cuando la persona lo pide después de revisar los
 * requisitos.
 */
export async function iniciarFase2(documento: string): Promise<Ejecucion> {
  const respuesta = await fetch('/ejecuciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ documento, fase: 2 }),
  })
  return leer<Ejecucion>(respuesta)
}

/**
 * Lanza la fase 3 (un microservicio por servicio de la arquitectura aprobada). Gasta llamadas al
 * LLM, así que solo se llama cuando la persona lo pide después de revisar la arquitectura.
 */
export async function iniciarFase3(documento: string): Promise<Ejecucion> {
  const respuesta = await fetch('/ejecuciones', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ documento, fase: 3 }),
  })
  return leer<Ejecucion>(respuesta)
}

export async function listarEjecuciones(estado?: EstadoEjecucion): Promise<Ejecucion[]> {
  const consulta = estado ? `?estado=${estado}` : ''
  return leer<Ejecucion[]>(await fetch(`/ejecuciones${consulta}`))
}

/** La ejecución se detiene en su siguiente paso; el evento «fin» llega por `rutaEventos`. */
export async function cancelarEjecucion(idEjecucion: string): Promise<Ejecucion> {
  const respuesta = await fetch(`/ejecuciones/${encodeURIComponent(idEjecucion)}/cancelar`, {
    method: 'POST',
  })
  return leer<Ejecucion>(respuesta)
}

export function rutaEventos(idEjecucion: string): string {
  return `/ejecuciones/${encodeURIComponent(idEjecucion)}/eventos`
}

/** Sube el archivo como cuerpo binario; el nombre original va aparte y solo se muestra. */
export async function cargarDocumento(archivo: File): Promise<DocumentoCargado> {
  const respuesta = await fetch(`/documentos?nombre=${encodeURIComponent(archivo.name)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: archivo,
  })
  return leer<DocumentoCargado>(respuesta)
}
