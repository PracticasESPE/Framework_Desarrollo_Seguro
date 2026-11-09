import { useEffect, useState } from 'react'
import { rutaEventos, type EstadoEjecucion, type EventoEjecucion, type ResumenFase1 } from './api'

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
      // Al empezar o terminar se conserva el último avance; si falla, se muestra el motivo.
      const mensaje =
        evento.estado === 'fallida' ? evento.mensaje : (anterior?.mensaje ?? evento.mensaje)
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

export function finDe(eventos: EventoEjecucion[]): EventoEjecucion | null {
  return eventos.find((evento) => evento.tipo === 'fin') ?? null
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
