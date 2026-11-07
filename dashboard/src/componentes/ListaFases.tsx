import type { Fase } from '../api'

// Por ahora todas las fases aparecen pendientes. El progreso en tiempo real (Server-Sent Events)
// llega con la API de ejecución del motor.
export function ListaFases({ fases }: { fases: Fase[] }) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-fases">
      <h2 id="titulo-fases">Fases del pipeline</h2>
      {fases.length === 0 ? (
        <p className="vacio">Sin datos de las fases.</p>
      ) : (
        <ol className="fases">
          {fases.map((fase) => (
            <li key={fase.numero} className={`fase${fase.es_gate ? ' fase--gate' : ''}`}>
              <span className="fase__numero">{fase.numero}</span>
              <span className="fase__nombre">{fase.nombre}</span>
              <span className="fase__estado">Pendiente</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
