// Mismos límites que orchestrator/documentos.py (lo comprueba tests/test_documentos.py).
// Aquí solo sirven para avisar antes de subir: quien decide es siempre la API.
export const TAMANO_MAXIMO = 10 * 1024 * 1024
export const EXTENSIONES = ['.pdf', '.docx', '.txt', '.md']

export function extension(nombre: string): string {
  const punto = nombre.lastIndexOf('.')
  return punto > 0 ? nombre.slice(punto).toLowerCase() : ''
}

/** Devuelve el motivo por el que no se puede subir el archivo, o null si se puede. */
export function validarArchivo(archivo: File): string | null {
  if (!EXTENSIONES.includes(extension(archivo.name))) {
    return 'Formato no permitido: el documento debe ser PDF, DOCX, TXT o MD'
  }
  if (archivo.size === 0) {
    return 'El archivo está vacío'
  }
  if (archivo.size > TAMANO_MAXIMO) {
    return `El documento supera el máximo de ${TAMANO_MAXIMO / (1024 * 1024)} MB`
  }
  return null
}

export function formatearTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
