import { describe, expect, it } from 'vitest'
import { TAMANO_MAXIMO, extension, formatearTamano, validarArchivo } from './validacion'

function archivo(nombre: string, tamano: number): File {
  return new File([new Uint8Array(tamano)], nombre)
}

describe('validarArchivo', () => {
  it.each(['requisitos.pdf', 'REQUISITOS.DOCX', 'requisitos.txt', 'historias.md'])(
    'acepta %s',
    (nombre) => {
      expect(validarArchivo(archivo(nombre, 10))).toBeNull()
    },
  )

  it.each(['malicioso.exe', 'requisitos.pdf.exe', 'pagina.html', 'sin-extension', '.pdf'])(
    'rechaza %s',
    (nombre) => {
      expect(validarArchivo(archivo(nombre, 10))).toMatch(/Formato no permitido/)
    },
  )

  it('rechaza un archivo vacío', () => {
    expect(validarArchivo(archivo('requisitos.pdf', 0))).toMatch(/vacío/)
  })

  it('rechaza un archivo mayor que el máximo', () => {
    expect(validarArchivo(archivo('requisitos.pdf', TAMANO_MAXIMO + 1))).toMatch(/10 MB/)
    expect(validarArchivo(archivo('requisitos.pdf', TAMANO_MAXIMO))).toBeNull()
  })
})

describe('utilidades', () => {
  it('extrae la extensión en minúsculas', () => {
    expect(extension('Requisitos.PDF')).toBe('.pdf')
    expect(extension('.bashrc')).toBe('')
  })

  it('formatea tamaños', () => {
    expect(formatearTamano(512)).toBe('512 B')
    expect(formatearTamano(2048)).toBe('2.0 KB')
    expect(formatearTamano(3 * 1024 * 1024)).toBe('3.0 MB')
  })
})
