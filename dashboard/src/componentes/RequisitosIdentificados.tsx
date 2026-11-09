import type { ResumenFase1 } from '../api'

/** Resultado de la fase 1. El texto viene del documento del cliente: React lo escapa al mostrarlo. */
export function RequisitosIdentificados({ resumen }: { resumen: ResumenFase1 }) {
  const etiquetas = Object.entries(resumen.etiquetas)
  return (
    <section className="tarjeta" aria-labelledby="titulo-requisitos">
      <h2 id="titulo-requisitos">Requisitos identificados</h2>
      <dl className="cifras">
        <div>
          <dt>Total</dt>
          <dd>{resumen.requisitos.length}</dd>
        </div>
        <div>
          <dt>Funcionales</dt>
          <dd>{resumen.funcionales}</dd>
        </div>
        <div>
          <dt>No funcionales</dt>
          <dd>{resumen.no_funcionales}</dd>
        </div>
        <div>
          <dt>Descartados</dt>
          <dd>{resumen.descartadas}</dd>
        </div>
      </dl>

      {etiquetas.length > 0 && (
        <ul className="chips" aria-label="Etiquetas de seguridad">
          {etiquetas.map(([etiqueta, veces]) => (
            <li key={etiqueta} className="chip">
              {legible(etiqueta)} <span className="chip__numero">{veces}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="tabla-contenedor">
        <table className="tabla tabla--requisitos">
          <thead>
            <tr>
              <th scope="col">Id</th>
              <th scope="col">Requisito</th>
              <th scope="col">Servicio</th>
              <th scope="col">Etiquetas</th>
            </tr>
          </thead>
          <tbody>
            {resumen.requisitos.map((requisito) => (
              <tr key={requisito.id}>
                <td>
                  <span className={`tipo tipo--${requisito.tipo}`}>{requisito.id}</span>
                </td>
                <td className="tabla__texto tabla__requisito">
                  {requisito.texto}
                  <span className="tabla__ubicacion">Sección {requisito.ubicacion}</span>
                </td>
                <td>{requisito.servicio_sugerido}</td>
                <td className="tabla__texto">{requisito.etiquetas.map(legible).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="vacio">
        Guardado en <code>salida/requisitos/{resumen.archivo}</code>
      </p>
    </section>
  )
}

function legible(etiqueta: string): string {
  return etiqueta.replaceAll('_', ' ')
}
