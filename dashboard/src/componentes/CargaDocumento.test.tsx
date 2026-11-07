import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { DocumentoCargado } from '../api'
import { CargaDocumento } from './CargaDocumento'

const DOCUMENTO: DocumentoCargado = {
  id: '0123456789abcdef0123456789abcdef',
  nombre: 'requisitos.pdf',
  formato: 'pdf',
  tamano: 8,
  sha256: 'a'.repeat(64),
  fecha: '2026-11-06T15:00:00Z',
}

function respuesta(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function preparar() {
  const onCargado = vi.fn()
  render(<CargaDocumento onCargado={onCargado} />)
  const entrada = screen.getByLabelText(/arrastra el documento/i)
  // applyAccept: false para comprobar que el componente también rechaza lo que el navegador deja pasar.
  const usuario = userEvent.setup({ applyAccept: false })
  return { onCargado, entrada, usuario }
}

describe('CargaDocumento', () => {
  it('sube el documento y muestra lo que devolvió la API', async () => {
    const fetchSimulado = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(respuesta(DOCUMENTO, 201))
    const { onCargado, entrada, usuario } = preparar()
    const archivo = new File(['%PDF-1.7'], 'requisitos.pdf', { type: 'application/pdf' })

    await usuario.upload(entrada, archivo)

    expect(await screen.findByText('Documento recibido')).toBeInTheDocument()
    expect(fetchSimulado).toHaveBeenCalledWith(
      '/documentos?nombre=requisitos.pdf',
      expect.objectContaining({ method: 'POST', body: archivo }),
    )
    expect(onCargado).toHaveBeenCalledWith(DOCUMENTO)
    expect(screen.getByText(DOCUMENTO.id)).toBeInTheDocument()
  })

  it('codifica el nombre original en la consulta', async () => {
    const fetchSimulado = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(respuesta(DOCUMENTO, 201))
    const { entrada, usuario } = preparar()

    await usuario.upload(entrada, new File(['x'], 'mis requisitos&v=2.txt'))

    expect(fetchSimulado.mock.calls[0]?.[0]).toBe('/documentos?nombre=mis%20requisitos%26v%3D2.txt')
  })

  it('rechaza un formato no permitido sin llamar a la API', async () => {
    const fetchSimulado = vi.spyOn(globalThis, 'fetch')
    const { onCargado, entrada, usuario } = preparar()

    await usuario.upload(entrada, new File(['MZ'], 'malicioso.exe'))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Formato no permitido/)
    expect(fetchSimulado).not.toHaveBeenCalled()
    expect(onCargado).not.toHaveBeenCalled()
  })

  it('muestra el motivo cuando la API rechaza el documento', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      respuesta({ detail: 'El archivo no es un PDF válido' }, 400),
    )
    const { onCargado, entrada, usuario } = preparar()

    await usuario.upload(entrada, new File(['<html>'], 'falso.pdf'))

    expect(await screen.findByRole('alert')).toHaveTextContent('El archivo no es un PDF válido')
    expect(onCargado).not.toHaveBeenCalled()
  })

  it('avisa si la API no responde', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    const { entrada, usuario } = preparar()

    await usuario.upload(entrada, new File(['hola'], 'requisitos.txt'))

    expect(await screen.findByRole('alert')).toHaveTextContent('Failed to fetch')
  })
})
