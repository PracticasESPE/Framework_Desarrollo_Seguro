import { describe, expect, it } from 'vitest'
import { estadoDeFases, finDe, resultadoDe } from './progreso'
import { evento } from './pruebas/eventSourceSimulado'

const RESUMEN = {
  archivo: 'x.modelo_requisitos.json',
  funcionales: 1,
  no_funcionales: 0,
  descartadas: 0,
  etiquetas: {},
  requisitos: [],
}

describe('estadoDeFases', () => {
  it('sigue el último avance y el estado de cada fase', () => {
    const eventos = [
      evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición', progreso: 0 }),
      evento({ tipo: 'avance', fase: 1, mensaje: 'Extrayendo', progreso: 0.1 }),
      evento({ tipo: 'avance', fase: 1, mensaje: 'Clasificando «3. Cuenta»', progreso: 0.5 }),
    ]
    expect(estadoDeFases(eventos).get(1)).toEqual({
      estado: 'en_curso',
      mensaje: 'Clasificando «3. Cuenta»',
      progreso: 0.5,
    })
    expect(estadoDeFases(eventos).has(2)).toBe(false) // sin eventos: pendiente
  })

  it('una fase fallida muestra el motivo', () => {
    const eventos = [
      evento({ tipo: 'fase', fase: 1, estado: 'en_curso', mensaje: 'Adquisición' }),
      evento({ tipo: 'avance', fase: 1, mensaje: 'Clasificando', progreso: 0.4 }),
      evento({ tipo: 'fase', fase: 1, estado: 'fallida', mensaje: 'Groq rechazó la clave' }),
    ]
    expect(estadoDeFases(eventos).get(1)).toEqual({
      estado: 'fallida',
      mensaje: 'Groq rechazó la clave',
      progreso: 0.4,
    })
  })

  it('el evento «fin» no tiene fase y no cambia ninguna', () => {
    const fin = evento({ tipo: 'fin', estado: 'completada', mensaje: 'Ejecución completada' })
    expect(estadoDeFases([fin]).size).toBe(0)
    expect(finDe([fin])).toBe(fin)
  })

  it('devuelve el resultado de la fase', () => {
    expect(resultadoDe([evento({ tipo: 'avance', fase: 1 })])).toBeNull()
    expect(resultadoDe([evento({ tipo: 'resultado', fase: 1, resultado: RESUMEN })])).toBe(RESUMEN)
  })
})
