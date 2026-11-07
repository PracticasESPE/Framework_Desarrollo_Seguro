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

/** Sube el archivo como cuerpo binario; el nombre original va aparte y solo se muestra. */
export async function cargarDocumento(archivo: File): Promise<DocumentoCargado> {
  const respuesta = await fetch(`/documentos?nombre=${encodeURIComponent(archivo.name)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: archivo,
  })
  return leer<DocumentoCargado>(respuesta)
}
