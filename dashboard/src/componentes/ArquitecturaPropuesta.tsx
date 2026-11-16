import type { ResumenFase2 } from '../api'
import { DiagramaArquitectura } from './DiagramaArquitectura'

/**
 * Resultado de la fase 2. Todo el texto lo escribió el LLM a partir de un documento del cliente:
 * React lo escapa al mostrarlo y el diagrama se muestra como código, nunca como HTML.
 */
export function ArquitecturaPropuesta({ resumen }: { resumen: ResumenFase2 }) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-arquitectura">
      <div className="tarjeta__cabecera">
        <h2 id="titulo-arquitectura">Arquitectura propuesta</h2>
        {resumen.aprobada ? (
          <span className="estado estado--ok">Aprobada por OPA</span>
        ) : (
          <span className="estado estado--error">Rechazada por OPA</span>
        )}
      </div>

      {!resumen.aprobada && (
        <p className="aviso aviso--error" role="alert">
          OPA no aprobó ninguna de las {resumen.intentos.length} propuestas, así que la arquitectura
          queda para revisión humana. Abajo está la última propuesta y los motivos del rechazo; no
          se generaron ADR ni diagrama.
        </p>
      )}

      <dl className="cifras">
        <div>
          <dt>Servicios</dt>
          <dd>{resumen.servicios.length}</dd>
        </div>
        <div>
          <dt>Decisiones</dt>
          <dd>{resumen.decisiones.length}</dd>
        </div>
        <div>
          <dt>Patrones</dt>
          <dd>{resumen.patrones.length}</dd>
        </div>
        <div>
          <dt>ADR</dt>
          <dd>{resumen.adr.length}</dd>
        </div>
      </dl>

      <h3>Ciclo LLM ↔ OPA</h3>
      <ol className="intentos">
        {resumen.intentos.map((intento) => (
          <li key={intento.numero} className={intento.aprobado ? 'intento intento--ok' : 'intento'}>
            <strong>
              Intento {intento.numero}
              {intento.origen === 'inicial' ? ' (arquitectura inicial)' : ''}:{' '}
              {intento.aprobado ? 'OPA aprueba' : 'OPA rechaza'}
            </strong>
            <span>{intento.justificacion}</span>
            {intento.bloqueantes.length > 0 && (
              <ul>
                {intento.bloqueantes.map((motivo, posicion) => (
                  <li key={posicion}>{motivo}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>

      <h3>Servicios</h3>
      <div className="tabla-contenedor">
        <table className="tabla tabla--requisitos">
          <thead>
            <tr>
              <th scope="col">Servicio</th>
              <th scope="col">Responsabilidad</th>
              <th scope="col">Base de datos</th>
              <th scope="col">Requisitos</th>
              <th scope="col">Depende de</th>
            </tr>
          </thead>
          <tbody>
            {resumen.servicios.map((servicio) => (
              <tr key={servicio.nombre}>
                <td>
                  <strong>{servicio.nombre}</strong>
                  <span className="tabla__ubicacion">{servicio.contexto}</span>
                </td>
                <td className="tabla__texto tabla__requisito">{servicio.responsabilidad}</td>
                <td>
                  <code>{servicio.base_datos}</code>
                </td>
                <td className="tabla__texto">{servicio.requisitos.join(', ')}</td>
                <td className="tabla__texto">
                  {servicio.depende_de.map((d) => `${d.servicio} (${d.tipo})`).join(', ') ||
                    'Ninguno'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {resumen.transversales.length > 0 && (
        <p className="vacio">Requisitos transversales: {resumen.transversales.join(', ')}</p>
      )}

      <h3>Decisiones</h3>
      <ul className="decisiones">
        {resumen.decisiones.map((decision) => (
          <li key={decision.id}>
            <strong>
              {decision.id} · {decision.titulo}
            </strong>
            <span>{decision.decision}</span>
            <span className="vacio">
              {decision.justificacion} ({decision.requisitos.join(', ')})
            </span>
          </li>
        ))}
      </ul>

      {resumen.patrones.length > 0 && (
        <>
          <h3>Patrones que infiere OPA</h3>
          <ul className="decisiones">
            {resumen.patrones.map((patron, posicion) => (
              <li key={posicion}>
                <strong>
                  {patron.patron.replaceAll('_', ' ')} · {patron.implementacion}
                </strong>
                <span>{patron.motivo}</span>
                <span className="vacio">Controles: {patron.controles.join(', ')}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {resumen.adr.length > 0 && (
        <>
          <h3>ADR generados</h3>
          <ul className="decisiones">
            {resumen.adr.map((adr) => (
              <li key={adr.archivo}>
                <strong>{adr.titulo}</strong>
                <span className="vacio">
                  <code>{adr.archivo}</code> · redactado por {adr.redactado_por}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {resumen.aprobada && (
        <>
          <h3>Diagrama de la arquitectura</h3>
          <DiagramaArquitectura resumen={resumen} />
        </>
      )}

      <h3>Archivos</h3>
      <ul className="archivos">
        {resumen.archivo_arquitectura && (
          <li>
            <code>salida/arquitectura/{resumen.archivo_arquitectura}</code>
          </li>
        )}
        <li>
          <code>salida/arquitectura/{resumen.archivo_intentos}</code> (registro de intentos)
        </li>
        {resumen.carpeta_adr && (
          <li>
            <code>salida/arquitectura/{resumen.carpeta_adr}/</code> (ADR)
          </li>
        )}
        {resumen.archivo_diagrama && (
          <li>
            <code>salida/arquitectura/{resumen.archivo_diagrama}</code> (diagrama C4)
          </li>
        )}
      </ul>
      {resumen.ejecucion_neo4j ? (
        <p className="vacio">
          {resumen.decisiones_neo4j} decisiones registradas en Neo4j en la ejecución{' '}
          <code>{resumen.ejecucion_neo4j}</code>
        </p>
      ) : (
        <p className="vacio">Sin registrar en Neo4j: el motivo está en el registro de eventos.</p>
      )}
    </section>
  )
}
