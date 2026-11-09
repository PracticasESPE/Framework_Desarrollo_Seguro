import { act } from '@testing-library/react'
import type { EventoEjecucion } from '../api'

/** EventSource de mentira: jsdom no lo implementa, y así las pruebas deciden qué llega y cuándo. */
export class EventSourceSimulado {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  static instancias: EventSourceSimulado[] = []

  readyState = EventSourceSimulado.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((mensaje: MessageEvent<string>) => void) | null = null
  onerror: (() => void) | null = null

  readonly url: string

  constructor(url: string) {
    this.url = url
    EventSourceSimulado.instancias.push(this)
  }

  close() {
    this.readyState = EventSourceSimulado.CLOSED
  }

  abrir() {
    act(() => {
      this.readyState = EventSourceSimulado.OPEN
      this.onopen?.()
    })
  }

  emitir(evento: EventoEjecucion) {
    act(() => {
      this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(evento) }))
    })
  }

  fallar(cerrar: boolean) {
    act(() => {
      this.readyState = cerrar ? EventSourceSimulado.CLOSED : EventSourceSimulado.CONNECTING
      this.onerror?.()
    })
  }
}

let siguiente = 1

/** Evento con los campos que no importan rellenos. */
export function evento(campos: Partial<EventoEjecucion> & Pick<EventoEjecucion, 'tipo'>) {
  return {
    id: siguiente++,
    fecha: '2026-11-09T15:00:00Z',
    mensaje: '',
    fase: null,
    estado: null,
    progreso: null,
    resultado: null,
    ...campos,
  } satisfies EventoEjecucion
}
