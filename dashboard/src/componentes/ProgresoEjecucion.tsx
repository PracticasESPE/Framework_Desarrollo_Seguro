import { useEffect, useRef } from 'react'
import type { EstadoEjecucion, EventoEjecucion } from '../api'
import { finDe, type ConexionEventos } from '../progreso'

const HORA = new Intl.DateTimeFormat('es-EC', { timeStyle: 'medium' })

interface Props {
  nombreDocumento: string
  eventos: EventoEjecucion[]
  conexion: ConexionEventos
}

export function ProgresoEjecucion({ nombreDocumento, eventos, conexion }: Props) {
  const fin = finDe(eventos)
  const progreso = eventos.findLast((evento) => evento.progreso !== null)?.progreso ?? 0
  const estado = fin?.estado ?? 'en_curso'
  const porcentaje = estado === 'completada' ? 100 : Math.round(progreso * 100)
  const registro = useRef<HTMLOListElement>(null)

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
      </div>

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

      <ol className="eventos" role="log" aria-label="Eventos de la ejecución" ref={registro}>
        {eventos.map((evento) => (
          <li key={evento.id} className={`evento evento--${evento.tipo}`}>
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
  }
}

function Insignia({ estado, conexion }: { estado: EstadoEjecucion; conexion: ConexionEventos }) {
  if (estado === 'completada') return <span className="estado estado--ok">Completada</span>
  if (estado === 'fallida') return <span className="estado estado--error">Fallida</span>
  if (conexion === 'reconectando') return <span className="estado">Reconectando…</span>
  if (conexion === 'perdida') return <span className="estado estado--error">Sin conexión</span>
  return <span className="estado estado--curso">En curso</span>
}
