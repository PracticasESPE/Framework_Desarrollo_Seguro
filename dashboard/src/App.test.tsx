import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'

function json(cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { headers: { 'Content-Type': 'application/json' } })
}

const FASES = [
  { numero: 1, nombre: 'Adquisición de requisitos', es_gate: false },
  { numero: 4, nombre: 'Security Gate 1: análisis estático', es_gate: true },
]

describe('App', () => {
  it('muestra el estado del motor, las fases y los documentos cargados', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((entrada) => {
      const ruta = typeof entrada === 'string' ? entrada : ''
      if (ruta === '/salud') return Promise.resolve(json({ estado: 'ok', version: '0.1.0' }))
      if (ruta === '/fases') return Promise.resolve(json(FASES))
      return Promise.resolve(
        json([
          {
            id: 'f'.repeat(32),
            nombre: 'tienda.docx',
            formato: 'docx',
            tamano: 40960,
            sha256: 'b'.repeat(64),
            fecha: '2026-11-06T15:00:00Z',
          },
        ]),
      )
    })

    render(<App />)

    expect(await screen.findByText('Motor v0.1.0')).toBeInTheDocument()
    const fases = screen.getByRole('list')
    expect(within(fases).getAllByRole('listitem')).toHaveLength(2)
    expect(within(fases).getByText('Security Gate 1: análisis estático')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'tienda.docx' })).toBeInTheDocument()
  })

  it('avisa cuando la API del motor no está levantada', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    render(<App />)

    expect(await screen.findByText('Motor sin conexión')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('uv run framework api')
  })
})
