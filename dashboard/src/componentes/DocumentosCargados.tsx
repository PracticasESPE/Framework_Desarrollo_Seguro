import type { DocumentoCargado } from '../api'
import { formatearTamano } from '../validacion'

const FECHA = new Intl.DateTimeFormat('es-EC', { dateStyle: 'short', timeStyle: 'short' })

interface Props {
  documentos: DocumentoCargado[]
  onProcesar?: (documento: DocumentoCargado) => void
  /** Hay una ejecución en curso: el motor procesa un documento a la vez. */
  ocupado?: boolean
}

export function DocumentosCargados({ documentos, onProcesar, ocupado = false }: Props) {
  return (
    <section className="tarjeta" aria-labelledby="titulo-documentos">
      <h2 id="titulo-documentos">Documentos cargados</h2>
      {documentos.length === 0 ? (
        <p className="vacio">Todavía no se ha cargado ningún documento.</p>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Nombre</th>
                <th scope="col">Formato</th>
                <th scope="col" className="numero">
                  Tamaño
                </th>
                <th scope="col">Cargado</th>
                <th scope="col">SHA-256</th>
                {onProcesar && (
                  <th scope="col">
                    <span className="oculto">Acción</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {documentos.map((documento) => (
                <tr key={documento.id}>
                  <td className="tabla__nombre">{documento.nombre}</td>
                  <td>{documento.formato.toUpperCase()}</td>
                  <td className="numero">{formatearTamano(documento.tamano)}</td>
                  <td>{FECHA.format(new Date(documento.fecha))}</td>
                  <td>
                    <code title={documento.sha256}>{documento.sha256.slice(0, 12)}…</code>
                  </td>
                  {onProcesar && (
                    <td>
                      <button
                        type="button"
                        className="boton boton--secundario"
                        disabled={ocupado}
                        onClick={() => onProcesar(documento)}
                        aria-label={`Procesar ${documento.nombre}`}
                      >
                        Procesar
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
