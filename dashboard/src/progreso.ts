import { useEffect, useState } from 'react'
import {
  rutaEventos,
  type Ejecucion,
  type EstadoEjecucion,
  type EventoEjecucion,
  type ResumenFase1,
  type ResumenFase2,
} from './api'

export interface EstadoFase {
  estado: EstadoEjecucion
  mensaje: string
  progreso: number | null
}

/** Estado de cada fase según los eventos recibidos. Las fases sin eventos están pendientes. */
export function estadoDeFases(eventos: EventoEjecucion[]): Map<number, EstadoFase> {
  const fases = new Map<number, EstadoFase>()
  for (const evento of eventos) {
    if (evento.fase === null) continue
    const anterior = fases.get(evento.fase)
    const progreso = evento.progreso ?? anterior?.progreso ?? null
    if (evento.tipo === 'fase' && evento.estado !== null) {
      // Al empezar o terminar se conserva el último avance; si falla o se cancela, el motivo.
      // Es la misma regla que estado_de_fases en orchestrator/ejecuciones.py.
      const detenida = evento.estado === 'fallida' || evento.estado === 'cancelada'
      const mensaje = detenida ? evento.mensaje : (anterior?.mensaje ?? evento.mensaje)
      fases.set(evento.fase, { estado: evento.estado, mensaje, progreso })
    } else {
      fases.set(evento.fase, {
        estado: anterior?.estado ?? 'en_curso',
        mensaje: evento.mensaje,
        progreso,
      })
    }
  }
  return fases
}

export function resultadoDe(eventos: EventoEjecucion[]): ResumenFase1 | null {
  return eventos.findLast((evento) => evento.resultado !== null)?.resultado ?? null
}

export function arquitecturaDe(eventos: EventoEjecucion[]): ResumenFase2 | null {
  return eventos.findLast((evento) => evento.arquitectura !== null)?.arquitectura ?? null
}

export function finDe(eventos: EventoEjecucion[]): EventoEjecucion | null {
  return eventos.find((evento) => evento.tipo === 'fin') ?? null
}

export interface EjecucionRecordada {
  id: string
  documento: string
  nombreDocumento: string
}

function recordar(ejecucion: Ejecucion | null): EjecucionRecordada | null {
  return ejecucion && {
    id: ejecucion.id,
    documento: ejecucion.documento,
    nombreDocumento: ejecucion.nombre_documento,
  }
}

/**
 * Qué ejecuciones vuelve a mostrar el dashboard al recargar la página. Parte de la que está en
 * marcha o, si no hay, de la más reciente (el motor las lista de la más reciente a la más antigua)
 * y recupera las dos fases de ese documento: el flujo de eventos reenvía todo lo ocurrido, así que
 * los requisitos, el botón de la fase 2 y la arquitectura reaparecen tal como estaban.
 */
export function recuperarSesion(ejecuciones: Ejecucion[]): {
  fase1: EjecucionRecordada | null
  fase2: EjecucionRecordada | null
} {
  const referencia = ejecuciones.find((e) => e.estado === 'en_curso') ?? ejecuciones[0]
  if (!referencia) return { fase1: null, fase2: null }
  const delDocumento = ejecuciones.filter((e) => e.documento === referencia.documento)
  const fase1 = delDocumento.find((e) => e.fase_actual !== 2) ?? null
  // Una fase 2 anterior a la última fase 1 es de un procesamiento viejo del documento.
  const fase2 =
    delDocumento.find((e) => e.fase_actual === 2 && (fase1 === null || e.inicio > fase1.inicio)) ??
    null
  return { fase1: recordar(fase1), fase2: recordar(fase2) }
}

export type ConexionEventos = 'conectando' | 'abierta' | 'reconectando' | 'cerrada' | 'perdida'

interface Seguimiento {
  id: string | null
  eventos: EventoEjecucion[]
  conexion: ConexionEventos
}

/**
 * Sigue una ejecución con Server-Sent Events hasta el evento «fin». Si se corta la conexión,
 * EventSource se reconecta solo y el motor reenvía lo que faltaba (Last-Event-ID).
 */
export function useEventosEjecucion(idEjecucion: string | null): Omit<Seguimiento, 'id'> {
  const [seguimiento, setSeguimiento] = useState<Seguimiento>({
    id: null,
    eventos: [],
    conexion: 'conectando',
  })

  useEffect(() => {
    if (idEjecucion === null) return
    const fuente = new EventSource(rutaEventos(idEjecucion))
    // Cada cambio se guarda junto al id: al pasar a otra ejecución, lo de la anterior se descarta.
    const actualizar = (cambio: (previo: Seguimiento) => Partial<Seguimiento>) => {
      setSeguimiento((previo) => {
        const base: Seguimiento =
          previo.id === idEjecucion
            ? previo
            : { id: idEjecucion, eventos: [], conexion: 'conectando' }
        return { ...base, ...cambio(base) }
      })
    }

    fuente.onopen = () => actualizar(() => ({ conexion: 'abierta' }))
    fuente.onmessage = (mensaje: MessageEvent<string>) => {
      const evento = JSON.parse(mensaje.data) as EventoEjecucion
      if (evento.tipo === 'fin') fuente.close()
      actualizar((previo) => ({
        eventos: previo.eventos.some((e) => e.id === evento.id)
          ? previo.eventos
          : [...previo.eventos, evento],
        conexion: evento.tipo === 'fin' ? 'cerrada' : previo.conexion,
      }))
    }
    fuente.onerror = () => {
      const cerrada = fuente.readyState === EventSource.CLOSED
      actualizar(() => ({ conexion: cerrada ? 'perdida' : 'reconectando' }))
    }
    return () => fuente.close()
  }, [idEjecucion])

  if (idEjecucion === null || seguimiento.id !== idEjecucion) {
    return { eventos: [], conexion: 'conectando' }
  }
  return { eventos: seguimiento.eventos, conexion: seguimiento.conexion }
}
