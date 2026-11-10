import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { DocumentoCargado, Ejecucion, ResumenFase1 } from './api'
import { EventSourceSimulado, evento } from './pruebas/eventSourceSimulado'

function json(cuerpo: unknown): Response {
  return new Response(JSON.stringify(cuerpo), { headers: { 'Content-Type': 'application/json' } })
}

function respuestaJson(cuerpo: unknown, status: number): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const FASES = [
  { numero: 1, nombre: 'Adquisición de requisitos', es_gate: false },
  { numero: 4, nombre: 'Security Gate 1: análisis estático', es_gate: true },
]

const DOCUMENTO: DocumentoCargado = {
  id: 'f'.repeat(32),
  nombre: 'tienda.docx',
  formato: 'docx',
  tamano: 40960,
  sha256: 'b'.repeat(64),
  fecha: '2026-11-06T15:00:00Z',
}

const EJECUCION: Ejecucion = {
  id: 'e'.repeat(32),
  documento: DOCUMENTO.id,
  nombre_documento: DOCUMENTO.nombre,
  estado: 'en_curso',
  fase_actual: null,
  progreso: null,
  mensaje: null,
  cancelacion_pedida: false,
  inicio: '2026-11-09T15:00:00Z',
  fin: null,
}

const RESUMEN: ResumenFase1 = {
  archivo: `${DOCUMENTO.id}.modelo_requisitos.json`,
  funcionales: 1,
  no_funcionales: 0,
  descartadas: 2,
  etiquetas: { autenticacion: 1 },
  requisitos: [
    {
      id: 'RF-01',
      tipo: 'funcional',
      texto: 'El cliente se registra con su correo y una contraseña.',
      ubicacion: '3.1',
      actor: 'cliente',
      accion: 'registrarse',
      entidades: ['Cliente'],
      servicio_sugerido: 'usuarios',
      etiquetas: ['autenticacion'],
    },
  ],
  ejecucion_neo4j: 'ej-20261111-000000-abcdef',
}

interface Simulacion {
  /** Respuesta de POST /ejecuciones. */
  alIniciar?: Response
  /** Lo que devuelve GET /ejecuciones?estado=en_curso al cargar la página. */
  enCurso?: Ejecucion[]
  /** Respuesta de POST /ejecuciones/{id}/cancelar. */
  alCancelar?: Response
}

/** Responde las rutas de la API del motor como lo haría orchestrator/api.py. */
function simularApi({ alIniciar, enCurso = [], alCancelar }: Simulacion = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((entrada) => {
    const ruta = typeof entrada === 'string' ? entrada : ''
    if (ruta === '/salud') return Promise.resolve(json({ estado: 'ok', version: '0.1.0' }))
    if (ruta === '/fases') return Promise.resolve(json(FASES))
    if (ruta === '/documentos') return Promise.resolve(json([DOCUMENTO]))
    if (ruta === '/ejecuciones?estado=en_curso') return Promise.resolve(json(enCurso))
    if (ruta === '/ejecuciones' && alIniciar) return Promise.resolve(alIniciar)
    if (ruta.endsWith('/cancelar') && alCancelar) return Promise.resolve(alCancelar)
    return Promise.reject(new Error(`Ruta no simulada: ${ruta}`))
  })
}

beforeEach(() => {
  EventSourceSimulado.instancias = []
  vi.stubGlobal('EventSource', EventSourceSimulado)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('muestra el estado del motor, las fases y los documentos cargados', async () => {
    simularApi()

    render(<App />)

    expect(await screen.findByText('Motor v0.1.0')).toBeInTheDocument()
    const fases = screen.getByRole('list')
    expect(within(fases).getAllByRole('listitem')).toHaveLength(2)
    expect(within(fases).getByText('Security Gate 1: análisis estático')).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'tienda.docx' })).toBeInTheDocument()
  })

  it('procesa un documento y muestra el progreso en tiempo real', async () => {
    const fetchSimulado = simularApi({ alIniciar: respuestaJson(EJECUCION, 201) })
    const usuario = userEvent.setup()
    render(<App />)

    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))

    expect(fetchSimulado).toHaveBeenCalledWith(
      '/ejecuciones',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ documento: DOCUMENTO.id }) }),
    )
    const fuente = EventSourceSimulado.instancias[0]
    expect(fuente?.url).toBe(`/ejecuciones/${EJECUCION.id}/eventos`)
    if (!fuente) return
    fuente.abrir()
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }))
    fuente.emitir(
      evento({ tipo: 'avance', fase: 1, mensaje: 'Clasificando «3. Cuenta» (5 unidades)', progreso: 0.5 }),
    )

    const fases = screen.getByRole('region', { name: 'Fases del pipeline' })
    const fase1 = within(fases).getAllByRole('listitem')[0]
    expect(fase1).toHaveTextContent('En curso')
    expect(fase1).toHaveTextContent('Clasificando «3. Cuenta» (5 unidades)')
    expect(within(fases).getByRole('progressbar', { name: 'Progreso de la fase 1' })).toHaveValue(0.5)
    expect(screen.getByRole('progressbar', { name: 'Progreso de la ejecución' })).toHaveValue(50)
    expect(screen.getByRole('log')).toHaveTextContent('Empieza la fase 1: Adquisición')
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeDisabled()

    fuente.emitir(evento({ tipo: 'resultado', fase: 1, progreso: 1, resultado: RESUMEN }))
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'completada', mensaje: 'Adquisición' }))
    fuente.emitir(evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' }))

    expect(screen.getByRole('heading', { name: 'Requisitos identificados' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: /El cliente se registra/ })).toBeInTheDocument()
    expect(screen.getByText('RF-01')).toBeInTheDocument()
    expect(screen.getByText('ej-20261111-000000-abcdef')).toBeInTheDocument()
    expect(fase1).toHaveTextContent('Completada')
    expect(fuente.readyState).toBe(EventSourceSimulado.CLOSED)
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeEnabled()
  })

  it('muestra el motivo si el motor no puede iniciar la ejecución', async () => {
    simularApi({ alIniciar: respuestaJson({ detail: 'Ya hay una ejecución en curso (abc)' }, 409) })
    const usuario = userEvent.setup()
    render(<App />)

    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Ya hay una ejecución en curso')
    expect(EventSourceSimulado.instancias).toHaveLength(0)
  })

  it('avisa si se pierde la conexión con el motor', async () => {
    simularApi({ alIniciar: respuestaJson(EJECUCION, 201) })
    const usuario = userEvent.setup()
    render(<App />)
    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))
    const fuente = EventSourceSimulado.instancias[0]
    if (!fuente) throw new Error('No se abrió el EventSource')

    fuente.fallar(false)
    expect(screen.getByText('Reconectando…')).toBeInTheDocument()
    fuente.fallar(true)
    expect(screen.getByRole('alert')).toHaveTextContent('Se perdió la conexión con el motor')
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeEnabled()
  })

  it('retoma la ejecución en curso al recargar la página', async () => {
    simularApi({ enCurso: [EJECUCION] })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Progreso de la ejecución' })).toBeInTheDocument()
    const fuente = EventSourceSimulado.instancias[0]
    expect(fuente?.url).toBe(`/ejecuciones/${EJECUCION.id}/eventos`)
    fuente?.emitir(evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }))

    const progreso = screen.getByRole('region', { name: 'Progreso de la ejecución' })
    expect(progreso).toHaveTextContent('tienda.docx')
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeDisabled()
  })

  it('cancela la ejecución en curso', async () => {
    const fetchSimulado = simularApi({
      alIniciar: respuestaJson(EJECUCION, 201),
      alCancelar: respuestaJson({ ...EJECUCION, cancelacion_pedida: true }, 202),
    })
    const usuario = userEvent.setup()
    render(<App />)
    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))
    const fuente = EventSourceSimulado.instancias[0]
    if (!fuente) throw new Error('No se abrió el EventSource')
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }))

    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(fetchSimulado).toHaveBeenCalledWith(`/ejecuciones/${EJECUCION.id}/cancelar`, {
      method: 'POST',
    })
    expect(screen.getByRole('button', { name: 'Cancelando…' })).toBeDisabled()
    expect(screen.getByText(/se detendrá en cuanto termine el paso en curso/)).toBeInTheDocument()

    const motivo = 'Ejecución cancelada a petición del usuario'
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'cancelada', mensaje: motivo }))
    fuente.emitir(evento({ tipo: 'fin', estado: 'cancelada', mensaje: motivo }))

    const progreso = screen.getByRole('region', { name: 'Progreso de la ejecución' })
    expect(within(progreso).getByText('Cancelada')).toBeInTheDocument()
    expect(within(progreso).queryByRole('button')).not.toBeInTheDocument()
    const fases = screen.getByRole('region', { name: 'Fases del pipeline' })
    expect(within(fases).getAllByRole('listitem')[0]).toHaveTextContent(`Cancelada${motivo}`)
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeEnabled()
  })

  it('muestra el motivo si no se puede cancelar', async () => {
    simularApi({
      alIniciar: respuestaJson(EJECUCION, 201),
      alCancelar: respuestaJson({ detail: 'La ejecución ya terminó (completada)' }, 409),
    })
    const usuario = userEvent.setup()
    render(<App />)
    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))

    await usuario.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('La ejecución ya terminó')
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled()
  })

  it('avisa cuando la API del motor no está levantada', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))

    render(<App />)

    expect(await screen.findByText('Motor sin conexión')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('uv run framework api')
  })
})
