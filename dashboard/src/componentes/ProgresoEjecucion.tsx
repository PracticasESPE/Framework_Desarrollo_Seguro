import { useEffect, useRef, useState } from 'react'
import type { EstadoEjecucion, EventoEjecucion } from '../api'
import { finDe, type ConexionEventos } from '../progreso'

const HORA = new Intl.DateTimeFormat('es-EC', { timeStyle: 'medium' })

interface Props {
  nombreDocumento: string
  eventos: EventoEjecucion[]
  conexion: ConexionEventos
  /** Pide al motor que cancele la ejecución; si falla, se muestra el motivo. */
  onCancelar?: () => Promise<void>
}

type Cancelacion = { tipo: 'nada' } | { tipo: 'pedida' } | { tipo: 'error'; mensaje: string }

export function ProgresoEjecucion({ nombreDocumento, eventos, conexion, onCancelar }: Props) {
  const fin = finDe(eventos)
  const progreso = eventos.findLast((evento) => evento.progreso !== null)?.progreso ?? 0
  const estado = fin?.estado ?? 'en_curso'
  const porcentaje = estado === 'completada' ? 100 : Math.round(progreso * 100)
  const registro = useRef<HTMLOListElement>(null)
  const [cancelacion, setCancelacion] = useState<Cancelacion>({ tipo: 'nada' })
  const puedeCancelar = onCancelar && !fin && conexion !== 'perdida'

  async function cancelar() {
    if (!onCancelar) return
    setCancelacion({ tipo: 'pedida' })
    try {
      await onCancelar()
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo cancelar la ejecución'
      setCancelacion({ tipo: 'error', mensaje })
    }
  }

  // El registro tiene altura fija: cada evento nuevo lo desplaza hasta el final.
  useEffect(() => {
    const lista = registro.current
    if (lista) lista.scrollTop = lista.scrollHeight
  }, [eventos.length])

  return (
    <section className="tarjeta" aria-labelledby="titulo-progreso">
      <div className="tarjeta__cabecera">
        <h2 id="titulo-progreso">Progreso de la ejecución</h2>
        <Insignia estado={estado} conexion={conexion} />
      </div>
      <p className="tarjeta__intro">
        Fase 1 con <strong>{nombreDocumento}</strong>: extracción, normalización y clasificación
        de los requisitos con el LLM. Los eventos llegan en tiempo real desde el motor.
      </p>

      <div className="progreso">
        <progress
          className={`progreso__barra progreso__barra--${estado}`}
          max={100}
          value={porcentaje}
          aria-label="Progreso de la ejecución"
        />
        <span className="progreso__valor">{porcentaje} %</span>
        {puedeCancelar && (
          <button
            type="button"
            className="boton boton--peligro"
            disabled={cancelacion.tipo === 'pedida'}
            onClick={() => void cancelar()}
          >
            {cancelacion.tipo === 'pedida' ? 'Cancelando…' : 'Cancelar'}
          </button>
        )}
      </div>
      {cancelacion.tipo === 'pedida' && !fin && (
        <p className="vacio" role="status">
          El motor se detendrá en cuanto termine el paso en curso.
        </p>
      )}
      {cancelacion.tipo === 'error' && !fin && (
        <p className="aviso aviso--error" role="alert">
          {cancelacion.mensaje}
        </p>
      )}

      {conexion === 'perdida' && !fin && (
        <p className="aviso aviso--error" role="alert">
          Se perdió la conexión con el motor. Si se reinició la API, vuelve a procesar el documento.
        </p>
      )}
      {fin?.estado === 'fallida' && (
        <p className="aviso aviso--error" role="alert">
          {fin.mensaje}
        </p>
      )}
      {fin?.estado === 'cancelada' && (
        <p className="aviso" role="status">
          {fin.mensaje}. Puedes volver a procesar el documento cuando quieras.
        </p>
      )}

      <ol className="eventos" role="log" aria-label="Eventos de la ejecución" ref={registro}>
        {eventos.map((evento) => (
          <li
            key={evento.id}
            className={`evento evento--${evento.tipo}${evento.estado ? ` evento--${evento.estado}` : ''}`}
          >
            <time className="evento__hora" dateTime={evento.fecha}>
              {HORA.format(new Date(evento.fecha))}
            </time>
            <span>{textoDelEvento(evento)}</span>
          </li>
        ))}
        {eventos.length === 0 && <li className="evento vacio">Esperando al motor…</li>}
      </ol>
    </section>
  )
}

function textoDelEvento(evento: EventoEjecucion): string {
  if (evento.tipo !== 'fase' || evento.fase === null || evento.estado === null) {
    return evento.mensaje
  }
  return `${accionDeFase(evento.estado)} la fase ${evento.fase}: ${evento.mensaje}`
}

function accionDeFase(estado: EstadoEjecucion): string {
  switch (estado) {
    case 'en_curso':
      return 'Empieza'
    case 'completada':
      return 'Termina'
    case 'fallida':
      return 'Falla'
    case 'cancelada':
      return 'Se cancela'
  }
}

function Insignia({ estado, conexion }: { estado: EstadoEjecucion; conexion: ConexionEventos }) {
  if (estado === 'completada') return <span className="estado estado--ok">Completada</span>
  if (estado === 'fallida') return <span className="estado estado--error">Fallida</span>
  if (estado === 'cancelada') return <span className="estado">Cancelada</span>
  if (conexion === 'reconectando') return <span className="estado">Reconectando…</span>
  if (conexion === 'perdida') return <span className="estado estado--error">Sin conexión</span>
  return <span className="estado estado--curso">En curso</span>
}
