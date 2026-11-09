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

export type EstadoEjecucion = 'en_curso' | 'completada' | 'fallida'

export interface Ejecucion {
  id: string
  documento: string
  estado: EstadoEjecucion
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
