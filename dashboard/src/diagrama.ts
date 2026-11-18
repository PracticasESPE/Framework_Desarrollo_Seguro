// Diagrama de contenedores de la arquitectura propuesta, dibujado con SVG propio.
//
// Mismo contenido que el flowchart de Mermaid que genera el motor (orchestrator/architecture/c4.py):
// usuarios, API Gateway, identidad, un contenedor por servicio con su base de datos, el bus de
// eventos y las llamadas entre servicios. Se calcula aquí, a partir del resumen de la fase 2, para
// no cargar ninguna librería ni relajar la política de contenido: el SVG solo usa atributos y
// clases del CSS del dashboard (la CSP bloquea los estilos en línea).

import type { ResumenFase2 } from './api'

export type TipoCaja = 'persona' | 'plataforma' | 'servicio' | 'datos' | 'bus'
export type TipoFlecha = 'https' | 'http' | 'sql' | 'evento'

export interface Caja {
  id: string
  tipo: TipoCaja
  titulo: string
  detalle: string
  x: number
  y: number
  ancho: number
  alto: number
}

export interface Flecha {
  tipo: TipoFlecha
  /** Trazado SVG (`d` de un path). */
  trazado: string
  /** Si termina en punta de flecha. Por defecto sí; los rieles que solo reparten, no. */
  sinPunta?: boolean
  etiqueta?: string
  /** Posición de la etiqueta. */
  x?: number
  y?: number
}

export interface Diseno {
  ancho: number
  alto: number
  cajas: Caja[]
  flechas: Flecha[]
  /** Donde empieza el marco punteado del sistema (todo lo que no son los usuarios). */
  marcoY: number
  /** Frase para lectores de pantalla: qué servicios hay y cómo se llaman entre sí. */
  descripcion: string
}

const ANCHO_SERVICIO = 168
const ALTO_SERVICIO = 64
const ANCHO_BD = 140
const ALTO_BD = 46
const PASO = 210
const MARGEN = 30
const Y_PERSONA = 14
const Y_PLATAFORMA = 104
const Y_MARCO = 88
const Y_RIEL = 190
const Y_SERVICIOS = 262
const Y_BD = 392
const Y_BUS = 480
const ALTO_BUS = 34

function recortar(texto: string, largo: number): string {
  return texto.length > largo ? `${texto.slice(0, largo - 1)}…` : texto
}

/** Se dibuja una pieza de identidad si algún requisito pide autenticación o autorización. */
export function usaIdentidad(resumen: ResumenFase2): boolean {
  const etiquetas = new Set([
    ...resumen.servicios.flatMap((servicio) => servicio.etiquetas),
    ...resumen.etiquetas_transversales,
  ])
  return etiquetas.has('autenticacion') || etiquetas.has('autorizacion')
}

export function disenarDiagrama(resumen: ResumenFase2): Diseno {
  const servicios = resumen.servicios
  const hayGateway = resumen.patrones.some((patron) => patron.patron === 'api_gateway')
  const hayIdentidad = usaIdentidad(resumen)
  const hayEventos = servicios.some((s) => s.depende_de.some((d) => d.tipo === 'asincrona'))

  const ancho = Math.max(MARGEN * 2 + servicios.length * PASO, 640)
  const inicio = (ancho - servicios.length * PASO) / 2
  const centro = new Map(servicios.map((s, i) => [s.nombre, inicio + PASO * i + PASO / 2]))
  const xCentro = ancho / 2

  const cajas: Caja[] = []
  const flechas: Flecha[] = []
  const caja = (c: Caja) => cajas.push(c)

  caja({
    id: 'usuarios',
    tipo: 'persona',
    titulo: 'Usuarios',
    detalle: '[Persona]',
    x: xCentro - 90,
    y: Y_PERSONA,
    ancho: 180,
    alto: 52,
  })

  // Entrada: con gateway, todo el tráfico pasa por él; sin gateway, los usuarios llegan a cada servicio.
  const origenRiel = { x: xCentro, y: Y_PERSONA + 52 }
  let salidaRiel = origenRiel
  if (hayGateway) {
    const xGateway = hayIdentidad ? xCentro - 110 : xCentro - 90
    caja({
      id: 'gateway',
      tipo: 'plataforma',
      titulo: 'API Gateway',
      detalle: '[Traefik]',
      x: xGateway,
      y: Y_PLATAFORMA,
      ancho: 180,
      alto: 52,
    })
    flechas.push({
      tipo: 'https',
      trazado: `M ${xGateway + 90} ${Y_PERSONA + 52} V ${Y_PLATAFORMA}`,
      etiqueta: 'HTTPS',
      x: xGateway + 98,
      y: (Y_PERSONA + 52 + Y_PLATAFORMA) / 2 + 4,
    })
    salidaRiel = { x: xGateway + 90, y: Y_PLATAFORMA + 52 }
    if (hayIdentidad) {
      caja({
        id: 'identidad',
        tipo: 'plataforma',
        titulo: 'Identidad',
        detalle: '[Keycloak]',
        x: xGateway + 230,
        y: Y_PLATAFORMA,
        ancho: 180,
        alto: 52,
      })
      flechas.push({
        tipo: 'http',
        trazado: `M ${xGateway + 180} ${Y_PLATAFORMA + 26} H ${xGateway + 230}`,
        etiqueta: 'OIDC',
        x: xGateway + 192,
        y: Y_PLATAFORMA + 18,
      })
    }
  } else if (hayIdentidad) {
    caja({
      id: 'identidad',
      tipo: 'plataforma',
      titulo: 'Identidad',
      detalle: '[Keycloak]',
      x: xCentro + 130,
      y: Y_PLATAFORMA,
      ancho: 180,
      alto: 52,
    })
    flechas.push({
      tipo: 'https',
      trazado: `M ${xCentro + 90} ${Y_PERSONA + 52} V ${Y_PLATAFORMA - 20} H ${xCentro + 220} V ${Y_PLATAFORMA}`,
      etiqueta: 'OIDC',
      x: xCentro + 150,
      y: Y_PLATAFORMA - 26,
    })
  }

  // Riel horizontal que reparte la entrada a cada servicio.
  const xs = [...centro.values()]
  if (xs.length > 0) {
    const [minimo, maximo] = [Math.min(...xs), Math.max(...xs)]
    flechas.push({
      tipo: hayGateway ? 'http' : 'https',
      sinPunta: true,
      trazado: `M ${salidaRiel.x} ${salidaRiel.y} V ${Y_RIEL} M ${Math.min(minimo, salidaRiel.x)} ${Y_RIEL} H ${Math.max(maximo, salidaRiel.x)}`,
      etiqueta: hayGateway ? 'HTTP' : 'HTTPS',
      x: salidaRiel.x + 8,
      y: Y_RIEL - 8,
    })
    for (const x of xs) {
      flechas.push({ tipo: hayGateway ? 'http' : 'https', trazado: `M ${x} ${Y_RIEL} V ${Y_SERVICIOS}` })
    }
  }

  for (const servicio of servicios) {
    const x = centro.get(servicio.nombre) ?? 0
    caja({
      id: `servicio-${servicio.nombre}`,
      tipo: 'servicio',
      titulo: recortar(servicio.nombre, 22),
      detalle: '[NestJS]',
      x: x - ANCHO_SERVICIO / 2,
      y: Y_SERVICIOS,
      ancho: ANCHO_SERVICIO,
      alto: ALTO_SERVICIO,
    })
    caja({
      id: `bd-${servicio.nombre}`,
      tipo: 'datos',
      titulo: recortar(servicio.base_datos, 20),
      detalle: '[PostgreSQL]',
      x: x - ANCHO_BD / 2,
      y: Y_BD,
      ancho: ANCHO_BD,
      alto: ALTO_BD,
    })
    flechas.push({
      tipo: 'sql',
      trazado: `M ${x - 30} ${Y_SERVICIOS + ALTO_SERVICIO} V ${Y_BD}`,
      etiqueta: 'SQL',
      x: x - 24,
      y: (Y_SERVICIOS + ALTO_SERVICIO + Y_BD) / 2 + 4,
    })
  }

  // Llamadas síncronas: arcos por encima de los servicios, cada uno a una altura distinta.
  let niveles = 0
  // Cada llamada sale y llega a una distancia distinta del centro, para que no se monten.
  const salidas = new Map<string, number>()
  const llegadas = new Map<string, number>()
  for (const servicio of servicios) {
    for (const dependencia of servicio.depende_de) {
      if (dependencia.tipo !== 'sincrona') continue
      const desde = centro.get(servicio.nombre)
      const hasta = centro.get(dependencia.servicio)
      if (desde === undefined || hasta === undefined || desde === hasta) continue
      const sentido = hasta > desde ? 1 : -1
      const k = salidas.get(servicio.nombre) ?? 0
      const j = llegadas.get(dependencia.servicio) ?? 0
      salidas.set(servicio.nombre, k + 1)
      llegadas.set(dependencia.servicio, j + 1)
      const salida = desde + sentido * (30 + k * 16)
      const llegada = hasta - sentido * (30 + j * 16)
      const altura = Y_SERVICIOS - 20 - (niveles % 3) * 16
      niveles += 1
      flechas.push({
        tipo: 'http',
        trazado: `M ${salida} ${Y_SERVICIOS} V ${altura} H ${llegada} V ${Y_SERVICIOS}`,
        etiqueta: 'HTTP',
        // Junto a la salida, lejos de las líneas verticales que bajan a los servicios del medio.
        x: salida + (sentido === 1 ? 6 : -30),
        y: altura - 4,
      })
    }
  }

  // Eventos: «A depende de B (asíncrona)» significa que B publica y A consume del bus.
  if (hayEventos) {
    caja({
      id: 'eventos',
      tipo: 'bus',
      titulo: 'Bus de eventos',
      detalle: '[RabbitMQ]',
      x: 14,
      y: Y_BUS,
      ancho: ancho - 28,
      alto: ALTO_BUS,
    })
    const publicadores = new Set<string>()
    for (const servicio of servicios) {
      for (const dependencia of servicio.depende_de) {
        if (dependencia.tipo === 'asincrona') publicadores.add(dependencia.servicio)
      }
    }
    const carril = (x: number, desdeServicio: boolean, hacia: 'bus' | 'servicio') => {
      const xCarril = x + (desdeServicio ? 96 : 114)
      const salidaX = x + (desdeServicio ? 56 : 66)
      const arriba = `${salidaX} ${Y_SERVICIOS + ALTO_SERVICIO}`
      const codo = Y_SERVICIOS + ALTO_SERVICIO + (desdeServicio ? 16 : 24)
      flechas.push({
        tipo: 'evento',
        trazado:
          hacia === 'bus'
            ? `M ${arriba} V ${codo} H ${xCarril} V ${Y_BUS}`
            : `M ${xCarril} ${Y_BUS} V ${codo} H ${salidaX} V ${Y_SERVICIOS + ALTO_SERVICIO}`,
      })
    }
    for (const nombre of publicadores) {
      const x = centro.get(nombre)
      if (x !== undefined) carril(x, true, 'bus')
    }
    for (const servicio of servicios) {
      if (!servicio.depende_de.some((d) => d.tipo === 'asincrona')) continue
      const x = centro.get(servicio.nombre)
      if (x !== undefined) carril(x, false, 'servicio')
    }
  }

  const alto = (hayEventos ? Y_BUS + ALTO_BUS : Y_BD + ALTO_BD) + 20
  return { ancho, alto, cajas, flechas, marcoY: Y_MARCO, descripcion: describir(resumen, hayGateway, hayEventos) }
}

function describir(resumen: ResumenFase2, hayGateway: boolean, hayEventos: boolean): string {
  const partes = [
    `${resumen.servicios.length} servicios, cada uno con su base de datos` +
      (hayGateway ? ', detrás de un API Gateway' : '') +
      (hayEventos ? ' y con un bus de eventos' : '') +
      '.',
  ]
  for (const servicio of resumen.servicios) {
    for (const dependencia of servicio.depende_de) {
      const como = dependencia.tipo === 'sincrona' ? 'llama a' : 'reacciona a los eventos de'
      partes.push(`${servicio.nombre} ${como} ${dependencia.servicio}.`)
    }
  }
  return partes.join(' ')
}

// --- Código Mermaid ----------------------------------------------------------------------------

export interface BloqueMermaid {
  titulo: string
  codigo: string
}

/**
 * Los diagramas Mermaid del documento de arquitectura. El título es el encabezado `## ` que los
 * precede (p. ej. «1. Contexto»).
 */
export function bloquesMermaid(markdown: string): BloqueMermaid[] {
  const bloques: BloqueMermaid[] = []
  let titulo = 'Diagrama'
  let dentro: string[] | null = null
  for (const linea of markdown.split('\n')) {
    if (dentro === null) {
      if (linea.startsWith('## ')) titulo = linea.slice(3).trim()
      else if (linea.trim() === '```mermaid') dentro = []
    } else if (linea.trim() === '```') {
      bloques.push({ titulo, codigo: dentro.join('\n') })
      dentro = null
    } else {
      dentro.push(linea)
    }
  }
  return bloques
}

const MERMAID_LIVE = 'https://mermaid.live/edit#base64:'

/**
 * Enlace al editor Mermaid Live con el diagrama cargado. El código viaja en el fragmento (después
 * del #), que el navegador no envía al servidor al abrir la página.
 */
export function enlaceMermaidLive(codigo: string): string {
  const estado = JSON.stringify({
    code: codigo,
    mermaid: JSON.stringify({ theme: 'default' }),
    autoSync: true,
    updateDiagram: true,
  })
  const bytes = new TextEncoder().encode(estado)
  let binario = ''
  for (const byte of bytes) binario += String.fromCharCode(byte)
  const base64 = btoa(binario).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
  return `${MERMAID_LIVE}${base64}`
}
