import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { DocumentoCargado, Ejecucion, ResumenFase1, ResumenFase2 } from './api'
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
  { numero: 2, nombre: 'Análisis y propuesta arquitectónica', es_gate: false },
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

const EJECUCION_FASE2: Ejecucion = {
  ...EJECUCION,
  id: 'd'.repeat(32),
  fase_actual: 2,
  inicio: '2026-11-09T15:10:00Z',
}

const ARQUITECTURA: ResumenFase2 = {
  aprobada: true,
  justificacion: 'Arquitectura aprobada: cumple las 4 reglas',
  intentos: [
    {
      numero: 1,
      origen: 'llm',
      aprobado: false,
      justificacion: 'Arquitectura rechazada',
      bloqueantes: ['Los servicios pedidos, usuarios comparten la base de datos usuarios_db'],
      advertencias: [],
    },
    {
      numero: 2,
      origen: 'llm',
      aprobado: true,
      justificacion: 'Arquitectura aprobada: cumple las 4 reglas',
      bloqueantes: [],
      advertencias: [],
    },
  ],
  servicios: [
    {
      nombre: 'usuarios',
      contexto: 'Identidad',
      responsabilidad: 'Registra a los clientes y guarda sus credenciales.',
      base_datos: 'usuarios_db',
      requisitos: ['RF-01'],
      depende_de: [],
      etiquetas: ['autenticacion'],
    },
    {
      nombre: 'pedidos',
      contexto: 'Ventas',
      responsabilidad: 'Gestiona los pedidos del cliente.',
      base_datos: 'pedidos_db',
      requisitos: ['RF-02'],
      depende_de: [
        { servicio: 'usuarios', tipo: 'sincrona', motivo: 'Valida al cliente que hace el pedido.' },
      ],
      etiquetas: [],
    },
  ],
  transversales: ['RNF-01'],
  etiquetas_transversales: ['cifrado_transito'],
  decisiones: [
    {
      id: 'D-01',
      titulo: 'Usuarios y pedidos separados',
      decision: 'Separar el registro de clientes de la gestión de pedidos.',
      justificacion: 'Cada uno cambia por motivos distintos',
      requisitos: ['RF-01', 'RF-02'],
    },
  ],
  patrones: [
    {
      patron: 'api_gateway',
      implementacion: 'traefik',
      motivo: 'Hay requisitos de autenticación y varios servicios',
      controles: ['ASVS-V4.1.1'],
    },
  ],
  archivo_intentos: `${DOCUMENTO.id}.intentos.json`,
  archivo_arquitectura: `${DOCUMENTO.id}.arquitectura.json`,
  adr: [
    {
      archivo: '0001-usuarios-y-pedidos-separados.md',
      titulo: 'Usuarios y pedidos separados',
      redactado_por: 'plantilla del motor',
    },
  ],
  carpeta_adr: `${DOCUMENTO.id}.adr`,
  archivo_diagrama: `${DOCUMENTO.id}.arquitectura.md`,
  diagrama: [
    '# Arquitectura',
    '',
    '## 1. Contexto',
    '',
    '```mermaid',
    'C4Context',
    '    title Contexto',
    '```',
    '',
    '## 2. Contenedores',
    '',
    '```mermaid',
    'flowchart TB',
    '    usuarios["Usuarios"]',
    '```',
    '',
  ].join('\n'),
  ejecucion_neo4j: 'ej-20261111-000000-abcdef',
  decisiones_neo4j: 1,
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
  /** Respuesta de POST /ejecuciones con la fase 1. */
  alIniciar?: Response
  /** Respuesta de POST /ejecuciones con `fase: 2`. */
  alIniciarFase2?: Response
  /** Lo que devuelve GET /ejecuciones al cargar la página, de la más reciente a la más antigua. */
  ejecuciones?: Ejecucion[]
  /** Respuesta de POST /ejecuciones/{id}/cancelar. */
  alCancelar?: Response
}

/** La petición de POST /ejecuciones que lanza la fase 2. */
function esFase2(init: RequestInit | undefined): boolean {
  return typeof init?.body === 'string' && init.body.includes('"fase":2')
}

/** El EventSource se abre en un efecto de React: se espera a que existan antes de usarlos. */
async function esperarFuentes(cantidad: number) {
  await waitFor(() => expect(EventSourceSimulado.instancias).toHaveLength(cantidad))
}

/** Responde las rutas de la API del motor como lo haría orchestrator/api.py. */
function simularApi({ alIniciar, alIniciarFase2, ejecuciones = [], alCancelar }: Simulacion = {}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((entrada, init) => {
    const ruta = typeof entrada === 'string' ? entrada : ''
    if (ruta === '/salud') return Promise.resolve(json({ estado: 'ok', version: '0.1.0' }))
    if (ruta === '/fases') return Promise.resolve(json(FASES))
    if (ruta === '/documentos') return Promise.resolve(json([DOCUMENTO]))
    if (ruta === '/ejecuciones' && init?.method !== 'POST') return Promise.resolve(json(ejecuciones))
    if (ruta === '/ejecuciones' && esFase2(init) && alIniciarFase2) {
      return Promise.resolve(alIniciarFase2)
    }
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
    expect(within(fases).getAllByRole('listitem')).toHaveLength(3)
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
    simularApi({ ejecuciones: [EJECUCION] })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Progreso de la ejecución' })).toBeInTheDocument()
    await esperarFuentes(1)
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
    expect(screen.getByRole('alert')).toHaveTextContent('uv run python -m orchestrator.cli api')
  })
})

describe('App: fase 2', () => {
  async function terminarLaFase1(usuario: ReturnType<typeof userEvent.setup>) {
    await usuario.click(await screen.findByRole('button', { name: 'Procesar tienda.docx' }))
    const fuente = EventSourceSimulado.instancias[0]
    if (!fuente) throw new Error('No se abrió el EventSource de la fase 1')
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }))
    return {
      fuente,
      terminar() {
        fuente.emitir(evento({ tipo: 'resultado', fase: 1, progreso: 1, resultado: RESUMEN }))
        fuente.emitir(
          evento({ tipo: 'fase', fase: 1, estado: 'completada', mensaje: 'Adquisición' }),
        )
        fuente.emitir(
          evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' }),
        )
      },
    }
  }

  function llamadasDeFase2(fetchSimulado: ReturnType<typeof simularApi>) {
    return fetchSimulado.mock.calls.filter(([, init]) => esFase2(init))
  }

  it('espera a que se pulse el botón antes de lanzar la fase 2', async () => {
    const fetchSimulado = simularApi({ alIniciar: respuestaJson(EJECUCION, 201) })
    const usuario = userEvent.setup()
    render(<App />)
    const fase1 = await terminarLaFase1(usuario)

    // Mientras la fase 1 está en marcha no se ofrece la fase 2.
    expect(screen.queryByRole('button', { name: 'Continuar a la fase 2' })).not.toBeInTheDocument()
    fase1.terminar()

    const paso = screen.getByRole('region', { name: 'Siguiente paso: fase 2' })
    expect(paso).toHaveTextContent('Revisa los 1 requisitos de tienda.docx')
    expect(paso).toHaveTextContent('gasta llamadas al LLM')
    expect(within(paso).getByRole('button', { name: 'Continuar a la fase 2' })).toBeEnabled()
    // Con la fase 1 terminada y revisada, el motor no recibió ninguna petición de la fase 2.
    expect(llamadasDeFase2(fetchSimulado)).toHaveLength(0)
    expect(EventSourceSimulado.instancias).toHaveLength(1)
  })

  it('lanza la fase 2 al pulsar el botón y muestra su progreso y la arquitectura', async () => {
    const fetchSimulado = simularApi({
      alIniciar: respuestaJson(EJECUCION, 201),
      alIniciarFase2: respuestaJson(EJECUCION_FASE2, 201),
    })
    const usuario = userEvent.setup()
    render(<App />)
    const fase1 = await terminarLaFase1(usuario)
    fase1.terminar()

    await usuario.click(screen.getByRole('button', { name: 'Continuar a la fase 2' }))

    expect(fetchSimulado).toHaveBeenCalledWith(
      '/ejecuciones',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ documento: DOCUMENTO.id, fase: 2 }),
      }),
    )
    const fuente2 = EventSourceSimulado.instancias[1]
    expect(fuente2?.url).toBe(`/ejecuciones/${EJECUCION_FASE2.id}/eventos`)
    if (!fuente2) return
    // El botón desaparece y los requisitos de la fase 1 siguen a la vista.
    expect(screen.queryByRole('button', { name: 'Continuar a la fase 2' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Requisitos identificados' })).toBeInTheDocument()

    fuente2.abrir()
    fuente2.emitir(
      evento({ tipo: 'fase', fase: 2, estado: 'en_curso', mensaje: 'Análisis', progreso: 0 }),
    )
    fuente2.emitir(
      evento({
        tipo: 'avance',
        fase: 2,
        mensaje: 'Pidiendo al LLM la arquitectura (intento 1 de 3)',
        progreso: 0.25,
      }),
    )

    const fases = screen.getByRole('region', { name: 'Fases del pipeline' })
    const [primera, segunda] = within(fases).getAllByRole('listitem')
    expect(primera).toHaveTextContent('Completada')
    expect(segunda).toHaveTextContent('En curso')
    expect(segunda).toHaveTextContent('Pidiendo al LLM la arquitectura (intento 1 de 3)')
    const progreso = screen.getByRole('region', { name: 'Progreso de la fase 2' })
    expect(within(progreso).getByRole('progressbar')).toHaveValue(25)
    expect(progreso).toHaveTextContent('tienda.docx')
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeDisabled()

    fuente2.emitir(evento({ tipo: 'resultado', fase: 2, progreso: 1, arquitectura: ARQUITECTURA }))
    fuente2.emitir(evento({ tipo: 'fase', fase: 2, estado: 'completada', mensaje: 'Análisis' }))
    fuente2.emitir(evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' }))

    const arquitectura = screen.getByRole('region', { name: 'Arquitectura propuesta' })
    expect(arquitectura).toHaveTextContent('Aprobada por OPA')
    expect(arquitectura).toHaveTextContent('usuarios (sincrona)')
    expect(arquitectura).toHaveTextContent('Intento 1: OPA rechaza')
    expect(arquitectura).toHaveTextContent('comparten la base de datos usuarios_db')
    expect(arquitectura).toHaveTextContent('Intento 2: OPA aprueba')
    expect(arquitectura).toHaveTextContent('D-01 · Usuarios y pedidos separados')
    expect(arquitectura).toHaveTextContent('api gateway · traefik')
    expect(arquitectura).toHaveTextContent('0001-usuarios-y-pedidos-separados.md')
    expect(
      within(arquitectura).getByRole('img', { name: /Diagrama de contenedores/ }),
    ).toBeInTheDocument()
    expect(arquitectura).toHaveTextContent('pedidos llama a usuarios')
    expect(arquitectura).toHaveTextContent('Código Mermaid del documento C4')
    const enlaces = within(arquitectura).getAllByRole('link', { name: 'Abrir en Mermaid Live' })
    expect(enlaces).toHaveLength(2)
    expect(enlaces[0]).toHaveAttribute(
      'href',
      expect.stringMatching(/^https:\/\/mermaid\.live\/edit#base64:/),
    )
    expect(enlaces[0]).toHaveAttribute('rel', 'noopener noreferrer')
    expect(arquitectura).toHaveTextContent('1 decisiones registradas en Neo4j')
    expect(within(fases).getAllByRole('listitem')[1]).toHaveTextContent('Completada')
    expect(fuente2.readyState).toBe(EventSourceSimulado.CLOSED)
    // Con la fase 2 completada ya no se ofrece lanzarla otra vez.
    expect(screen.queryByRole('button', { name: /fase 2/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeEnabled()
  })

  it('no ofrece la fase 2 si la fase 1 falló', async () => {
    simularApi({ alIniciar: respuestaJson(EJECUCION, 201) })
    const usuario = userEvent.setup()
    render(<App />)
    const { fuente } = await terminarLaFase1(usuario)

    const motivo = 'Groq rechazó la clave'
    fuente.emitir(evento({ tipo: 'fase', fase: 1, estado: 'fallida', mensaje: motivo }))
    fuente.emitir(evento({ tipo: 'fin', estado: 'fallida', mensaje: motivo }))

    expect(screen.queryByRole('region', { name: 'Siguiente paso: fase 2' })).not.toBeInTheDocument()
  })

  it('muestra el motivo si el motor no puede lanzar la fase 2 y permite reintentar', async () => {
    simularApi({
      alIniciar: respuestaJson(EJECUCION, 201),
      alIniciarFase2: respuestaJson({ detail: 'Ya hay una ejecución en curso (abc)' }, 409),
    })
    const usuario = userEvent.setup()
    render(<App />)
    const fase1 = await terminarLaFase1(usuario)
    fase1.terminar()

    await usuario.click(screen.getByRole('button', { name: 'Continuar a la fase 2' }))

    const paso = screen.getByRole('region', { name: 'Siguiente paso: fase 2' })
    expect(await within(paso).findByRole('alert')).toHaveTextContent(
      'Ya hay una ejecución en curso',
    )
    expect(within(paso).getByRole('button', { name: 'Continuar a la fase 2' })).toBeEnabled()
    expect(EventSourceSimulado.instancias).toHaveLength(1)
  })

  it('si OPA rechaza todas las propuestas, muestra los motivos y deja reintentar', async () => {
    simularApi({
      alIniciar: respuestaJson(EJECUCION, 201),
      alIniciarFase2: respuestaJson(EJECUCION_FASE2, 201),
    })
    const usuario = userEvent.setup()
    render(<App />)
    const fase1 = await terminarLaFase1(usuario)
    fase1.terminar()
    await usuario.click(screen.getByRole('button', { name: 'Continuar a la fase 2' }))
    const fuente2 = EventSourceSimulado.instancias[1]
    if (!fuente2) throw new Error('No se abrió el EventSource de la fase 2')

    const rechazada: ResumenFase2 = {
      ...ARQUITECTURA,
      aprobada: false,
      intentos: ARQUITECTURA.intentos.slice(0, 1),
      adr: [],
      archivo_arquitectura: null,
      carpeta_adr: null,
      archivo_diagrama: null,
      diagrama: null,
    }
    const motivo = 'OPA no aprobó ninguna propuesta en 1 intentos: queda para revisión humana'
    fuente2.emitir(evento({ tipo: 'fase', fase: 2, estado: 'en_curso', mensaje: 'Análisis' }))
    fuente2.emitir(evento({ tipo: 'resultado', fase: 2, arquitectura: rechazada }))
    fuente2.emitir(evento({ tipo: 'fase', fase: 2, estado: 'fallida', mensaje: motivo }))
    fuente2.emitir(evento({ tipo: 'fin', estado: 'fallida', mensaje: motivo }))

    const arquitectura = screen.getByRole('region', { name: 'Arquitectura propuesta' })
    expect(arquitectura).toHaveTextContent('Rechazada por OPA')
    expect(arquitectura).toHaveTextContent('queda para revisión humana')
    expect(arquitectura).toHaveTextContent('comparten la base de datos usuarios_db')
    expect(within(arquitectura).queryByRole('img')).not.toBeInTheDocument()
    expect(within(arquitectura).queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Volver a intentar la fase 2' })).toBeEnabled()
  })

  it('retoma una fase 2 en curso al recargar la página', async () => {
    simularApi({ ejecuciones: [EJECUCION_FASE2] })
    render(<App />)

    expect(await screen.findByRole('region', { name: 'Progreso de la fase 2' })).toBeInTheDocument()
    await esperarFuentes(1)
    expect(EventSourceSimulado.instancias[0]?.url).toBe(
      `/ejecuciones/${EJECUCION_FASE2.id}/eventos`,
    )
    expect(
      screen.queryByRole('region', { name: 'Progreso de la ejecución' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeDisabled()
  })

  describe('al recargar la página', () => {
    const FASE1_TERMINADA: Ejecucion = {
      ...EJECUCION,
      estado: 'completada',
      fase_actual: 1,
      progreso: 1,
      fin: '2026-11-09T15:05:00Z',
    }
    const FASE2_TERMINADA: Ejecucion = {
      ...EJECUCION_FASE2,
      estado: 'completada',
      progreso: 1,
      fin: '2026-11-09T15:12:00Z',
    }

    function emitirFase1Terminada(fuente: EventSourceSimulado | undefined) {
      fuente?.emitir(evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }))
      fuente?.emitir(evento({ tipo: 'resultado', fase: 1, progreso: 1, resultado: RESUMEN }))
      fuente?.emitir(evento({ tipo: 'fase', fase: 1, estado: 'completada', mensaje: 'Adquisición' }))
      fuente?.emitir(evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' }))
    }

    it('recuerda la fase 1 terminada: reaparecen los requisitos y el botón de la fase 2', async () => {
      const fetchSimulado = simularApi({ ejecuciones: [FASE1_TERMINADA] })
      render(<App />)

      await screen.findByRole('region', { name: 'Progreso de la ejecución' })
      await esperarFuentes(1)
      expect(EventSourceSimulado.instancias).toHaveLength(1)
      emitirFase1Terminada(EventSourceSimulado.instancias[0])

      expect(screen.getByRole('heading', { name: 'Requisitos identificados' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Continuar a la fase 2' })).toBeEnabled()
      // Recordarla no lanza nada: solo se leyó la lista de ejecuciones.
      expect(fetchSimulado.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0)
    })

    it('recuerda también la fase 2 terminada y no vuelve a ofrecerla', async () => {
      simularApi({ ejecuciones: [FASE2_TERMINADA, FASE1_TERMINADA] })
      render(<App />)

      await screen.findByRole('region', { name: 'Progreso de la fase 2' })
      await esperarFuentes(2)
      expect(EventSourceSimulado.instancias.map((f) => f.url)).toEqual([
        `/ejecuciones/${FASE1_TERMINADA.id}/eventos`,
        `/ejecuciones/${FASE2_TERMINADA.id}/eventos`,
      ])
      emitirFase1Terminada(EventSourceSimulado.instancias[0])
      const fuente2 = EventSourceSimulado.instancias[1]
      fuente2?.emitir(evento({ tipo: 'fase', fase: 2, estado: 'en_curso', mensaje: 'Análisis' }))
      fuente2?.emitir(evento({ tipo: 'resultado', fase: 2, arquitectura: ARQUITECTURA }))
      fuente2?.emitir(evento({ tipo: 'fase', fase: 2, estado: 'completada', mensaje: 'Análisis' }))
      fuente2?.emitir(evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' }))

      expect(screen.getByRole('region', { name: 'Arquitectura propuesta' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /fase 2/ })).not.toBeInTheDocument()
      const fases = screen.getByRole('region', { name: 'Fases del pipeline' })
      expect(within(fases).getAllByRole('listitem')[1]).toHaveTextContent('Completada')
    })

    it('si la fase 2 está en curso, también recupera los requisitos de la fase 1', async () => {
      simularApi({ ejecuciones: [EJECUCION_FASE2, FASE1_TERMINADA] })
      render(<App />)

      await screen.findByRole('region', { name: 'Progreso de la fase 2' })
      await esperarFuentes(2)
      emitirFase1Terminada(EventSourceSimulado.instancias[0])
      EventSourceSimulado.instancias[1]?.emitir(
        evento({ tipo: 'fase', fase: 2, estado: 'en_curso', mensaje: 'Análisis' }),
      )

      expect(screen.getByRole('heading', { name: 'Requisitos identificados' })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /fase 2/ })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Procesar tienda.docx' })).toBeDisabled()
    })

    it('ignora una fase 2 vieja si el documento se volvió a procesar después', async () => {
      const fase1Nueva: Ejecucion = {
        ...FASE1_TERMINADA,
        id: 'c'.repeat(32),
        inicio: '2026-11-09T16:00:00Z',
      }
      simularApi({ ejecuciones: [fase1Nueva, FASE2_TERMINADA, FASE1_TERMINADA] })
      render(<App />)

      await screen.findByRole('region', { name: 'Progreso de la ejecución' })
      await esperarFuentes(1)
      expect(EventSourceSimulado.instancias.map((f) => f.url)).toEqual([
        `/ejecuciones/${fase1Nueva.id}/eventos`,
      ])
      expect(screen.queryByRole('region', { name: 'Progreso de la fase 2' })).not.toBeInTheDocument()
    })

    it('sin ejecuciones recordadas no muestra nada', async () => {
      simularApi({ ejecuciones: [] })
      render(<App />)

      expect(await screen.findByText('Motor v0.1.0')).toBeInTheDocument()
      expect(EventSourceSimulado.instancias).toHaveLength(0)
      expect(screen.queryByRole('region', { name: /Progreso/ })).not.toBeInTheDocument()
    })
  })
})
