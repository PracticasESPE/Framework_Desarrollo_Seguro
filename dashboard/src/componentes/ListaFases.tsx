import type { EstadoEjecucion, Fase } from '../api'
import type { EstadoFase } from '../progreso'

function etiqueta(estado: EstadoEjecucion | 'pendiente'): string {
  switch (estado) {
    case 'pendiente':
      return 'Pendiente'
    case 'en_curso':
      return 'En curso'
    case 'completada':
      return 'Completada'
    case 'fallida':
      return 'Fallida'
  }
}

interface Props {
  fases: Fase[]
  /** Estado de las fases de la ejecución que se está siguiendo; las que faltan, pendientes. */
  estados?: Map<number, EstadoFase>
}

export function ListaFases({ fases, estados = new Map() }: Props) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-fases">
      <h2 id="titulo-fases">Fases del pipeline</h2>
      {fases.length === 0 ? (
        <p className="vacio">Sin datos de las fases.</p>
      ) : (
        <ol className="fases">
          {fases.map((fase) => {
            const estado = estados.get(fase.numero)
            const clave = estado?.estado ?? 'pendiente'
            return (
              <li
                key={fase.numero}
                className={`fase fase--${clave}${fase.es_gate ? ' fase--gate' : ''}`}
                aria-current={clave === 'en_curso' ? 'step' : undefined}
              >
                <span className="fase__numero">{fase.numero}</span>
                <span className="fase__nombre">{fase.nombre}</span>
                <span className={`fase__estado fase__estado--${clave}`}>{etiqueta(clave)}</span>
                {estado && clave !== 'completada' && (
                  <span className="fase__detalle">{estado.mensaje}</span>
                )}
                {estado?.progreso != null && clave === 'en_curso' && (
                  <progress
                    className="fase__barra"
                    max={1}
                    value={estado.progreso}
                    aria-label={`Progreso de la fase ${fase.numero}`}
                  />
                )}
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}
