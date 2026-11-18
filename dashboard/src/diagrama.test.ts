import { describe, expect, it } from 'vitest'
import type { DependenciaPropuesta, ResumenFase2, ServicioPropuesto } from './api'
import { bloquesMermaid, disenarDiagrama, enlaceMermaidLive, usaIdentidad } from './diagrama'

function servicio(
  nombre: string,
  depende_de: DependenciaPropuesta[] = [],
  etiquetas: string[] = [],
): ServicioPropuesto {
  return {
    nombre,
    contexto: nombre,
    responsabilidad: `Gestiona ${nombre}.`,
    base_datos: `${nombre}_db`,
    requisitos: ['RF-01'],
    depende_de,
    etiquetas,
  }
}

const dependencia = (servicio: string, tipo: 'sincrona' | 'asincrona'): DependenciaPropuesta => ({
  servicio,
  tipo,
  motivo: 'Lo necesita.',
})

function resumen(servicios: ServicioPropuesto[], patrones: string[] = []): ResumenFase2 {
  return {
    aprobada: true,
    justificacion: '',
    intentos: [],
    servicios,
    transversales: [],
    etiquetas_transversales: [],
    decisiones: [],
    patrones: patrones.map((patron) => ({
      patron,
      implementacion: 'x',
      motivo: 'x',
      controles: [],
    })),
    archivo_intentos: 'a.json',
    archivo_arquitectura: null,
    adr: [],
    carpeta_adr: null,
    archivo_diagrama: null,
    diagrama: null,
    ejecucion_neo4j: null,
    decisiones_neo4j: null,
  }
}

describe('disenarDiagrama', () => {
  it('dibuja un contenedor y una base de datos por servicio, dentro del lienzo', () => {
    const diseno = disenarDiagrama(resumen([servicio('usuarios'), servicio('pedidos')]))

    const servicios = diseno.cajas.filter((c) => c.tipo === 'servicio')
    expect(servicios.map((c) => c.titulo)).toEqual(['usuarios', 'pedidos'])
    expect(diseno.cajas.filter((c) => c.tipo === 'datos').map((c) => c.titulo)).toEqual([
      'usuarios_db',
      'pedidos_db',
    ])
    for (const caja of diseno.cajas) {
      expect(caja.x).toBeGreaterThanOrEqual(0)
      expect(caja.x + caja.ancho).toBeLessThanOrEqual(diseno.ancho)
      expect(caja.y + caja.alto).toBeLessThanOrEqual(diseno.alto)
    }
    // Sin gateway ni eventos: ni API Gateway ni bus.
    expect(diseno.cajas.map((c) => c.id)).not.toContain('gateway')
    expect(diseno.cajas.map((c) => c.id)).not.toContain('eventos')
    expect(diseno.flechas.filter((f) => f.tipo === 'sql')).toHaveLength(2)
  })

  it('no solapa los servicios y crece con su número', () => {
    const pocos = disenarDiagrama(resumen([servicio('a'), servicio('b')]))
    const nombres = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'].map((n) => servicio(n))
    const muchos = disenarDiagrama(resumen(nombres))

    expect(muchos.ancho).toBeGreaterThan(pocos.ancho)
    const cajas = muchos.cajas.filter((c) => c.tipo === 'servicio').sort((a, b) => a.x - b.x)
    for (let i = 1; i < cajas.length; i++) {
      const anterior = cajas.at(i - 1)
      expect(cajas.at(i)?.x).toBeGreaterThanOrEqual((anterior?.x ?? 0) + (anterior?.ancho ?? 0))
    }
  })

  it('añade el API Gateway solo si OPA infirió ese patrón', () => {
    const con = disenarDiagrama(resumen([servicio('usuarios')], ['api_gateway']))
    const sin = disenarDiagrama(resumen([servicio('usuarios')], ['circuit_breaker']))

    expect(con.cajas.map((c) => c.id)).toContain('gateway')
    expect(sin.cajas.map((c) => c.id)).not.toContain('gateway')
  })

  it('añade la identidad si algún requisito pide autenticación', () => {
    const base = resumen([servicio('usuarios', [], ['autenticacion'])])
    expect(usaIdentidad(base)).toBe(true)
    expect(disenarDiagrama(base).cajas.map((c) => c.id)).toContain('identidad')

    const transversal = { ...resumen([servicio('usuarios')]), etiquetas_transversales: ['autorizacion'] }
    expect(usaIdentidad(transversal)).toBe(true)

    const ninguna = resumen([servicio('usuarios', [], ['cifrado_transito'])])
    expect(usaIdentidad(ninguna)).toBe(false)
    expect(disenarDiagrama(ninguna).cajas.map((c) => c.id)).not.toContain('identidad')
  })

  it('dibuja las llamadas síncronas como arcos HTTP y las asíncronas por el bus', () => {
    const diseno = disenarDiagrama(
      resumen([
        servicio('usuarios'),
        servicio('pedidos', [dependencia('usuarios', 'sincrona')]),
        servicio('notificaciones', [dependencia('pedidos', 'asincrona')]),
      ]),
    )

    const arcos = diseno.flechas.filter((f) => f.tipo === 'http' && f.etiqueta === 'HTTP' && f.trazado.includes('H'))
    expect(arcos.length).toBeGreaterThanOrEqual(1)
    expect(diseno.cajas.map((c) => c.id)).toContain('eventos')
    // pedidos publica y notificaciones consume: dos carriles hacia o desde el bus.
    expect(diseno.flechas.filter((f) => f.tipo === 'evento')).toHaveLength(2)
    expect(diseno.descripcion).toContain('pedidos llama a usuarios')
    expect(diseno.descripcion).toContain('notificaciones reacciona a los eventos de pedidos')
  })

  it('ignora las dependencias de servicios que no existen', () => {
    const diseno = disenarDiagrama(
      resumen([servicio('pedidos', [dependencia('fantasma', 'sincrona')])]),
    )
    expect(diseno.flechas.every((f) => !f.trazado.includes('NaN'))).toBe(true)
  })

  it('recorta los nombres largos y nunca los trata como HTML', () => {
    const peligroso = `<img src=x onerror=alert(1)>${'x'.repeat(40)}`
    const diseno = disenarDiagrama(resumen([servicio(peligroso)]))
    const titulo = diseno.cajas.find((c) => c.tipo === 'servicio')?.titulo ?? ''

    expect(titulo.length).toBeLessThanOrEqual(22)
    expect(titulo.endsWith('…')).toBe(true)
  })
})

const MARKDOWN = [
  '# Arquitectura',
  '',
  '```bash',
  'framework arquitectura diagrama',
  '```',
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
  '    a["Usuarios ñ ✓"] --> b',
  '```',
  '',
].join('\n')

describe('bloquesMermaid', () => {
  it('extrae solo los bloques mermaid, con el encabezado que los precede', () => {
    expect(bloquesMermaid(MARKDOWN)).toEqual([
      { titulo: '1. Contexto', codigo: 'C4Context\n    title Contexto' },
      { titulo: '2. Contenedores', codigo: 'flowchart TB\n    a["Usuarios ñ ✓"] --> b' },
    ])
  })

  it('sin diagramas devuelve una lista vacía', () => {
    expect(bloquesMermaid('# Nada\n\n```bash\nls\n```')).toEqual([])
  })
})

describe('enlaceMermaidLive', () => {
  function decodificar(enlace: string): { code: string; mermaid: string } {
    const base64 = enlace.split('#base64:')[1] ?? ''
    const normal = base64.replaceAll('-', '+').replaceAll('_', '/')
    const binario = atob(normal.padEnd(Math.ceil(normal.length / 4) * 4, '='))
    const bytes = Uint8Array.from(binario, (c) => c.charCodeAt(0))
    return JSON.parse(new TextDecoder().decode(bytes)) as { code: string; mermaid: string }
  }

  it('lleva el código completo en el fragmento, también con tildes y símbolos', () => {
    const codigo = 'flowchart TB\n    a["Usuarios ñ ✓ <b>x</b>"] -->|"HTTP"| b'
    const enlace = enlaceMermaidLive(codigo)

    expect(enlace.startsWith('https://mermaid.live/edit#base64:')).toBe(true)
    expect(decodificar(enlace).code).toBe(codigo)
  })

  it('usa base64 apto para URL: sin +, / ni =', () => {
    const enlace = enlaceMermaidLive('>>>???~~~\n'.repeat(20))
    expect(enlace.split('#base64:')[1]).toMatch(/^[A-Za-z0-9_-]+$/)
  })
})
