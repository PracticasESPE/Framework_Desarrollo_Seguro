import type { EntidadGenerada, EstadoLogica, ResumenFase3, ServicioGenerado } from '../api'

const LOGICA: Record<EstadoLogica, string> = {
  aceptada: 'Aceptada',
  sin_logica: 'Sin lógica (para revisión)',
  error: 'Error al pedirla',
  omitida: 'No generada',
}

/** Cuántos problemas de cada lista se muestran; el resto queda en sistema.json. */
const MAXIMO_PROBLEMAS = 5

/**
 * Resultado de la fase 3: un microservicio por servicio de la arquitectura. Los nombres, los
 * mensajes de error y lo que el LLM dejó pendiente se muestran como texto (React lo escapa); el
 * código generado no se muestra aquí, queda en la carpeta del servicio para revisarlo.
 */
export function ServiciosGenerados({ resumen }: { resumen: ResumenFase3 }) {
  const total = resumen.servicios.length
  const entidades = resumen.servicios.flatMap((s) => s.entidades)
  const conLogica = entidades.filter((e) => e.logica === 'aceptada').length
  const pruebas = entidades.reduce((suma, e) => suma + e.pruebas_aceptadas, 0)
  const todos = resumen.completos === total
  const usos = Object.values(resumen.uso_llm ?? {})
  const tokens = usos.reduce((suma, u) => suma + u.tokens_entrada + u.tokens_salida, 0)
  const llamadas = usos.reduce((suma, u) => suma + u.llamadas, 0)

  return (
    <section className="tarjeta" aria-labelledby="titulo-servicios">
      <div className="tarjeta__cabecera">
        <h2 id="titulo-servicios">Microservicios generados</h2>
        <span className={`estado ${todos ? 'estado--ok' : 'estado--error'}`}>
          {resumen.completos} de {total} completos
        </span>
      </div>
      <p className="tarjeta__intro">
        En <code>salida/servicios/{resumen.carpeta}</code>, con un resumen de cada uno en{' '}
        <code>sistema.json</code>.
        {!resumen.compilado && ' Se generaron sin compilar: falta comprobarlos con tsc y Jest.'}
      </p>

      {resumen.advertencias.length > 0 && (
        <div className="aviso" role="note">
          <p className="aviso__titulo">Advertencias de la arquitectura</p>
          <ul>
            {resumen.advertencias.map((advertencia, posicion) => (
              <li key={posicion}>{advertencia}</li>
            ))}
          </ul>
        </div>
      )}

      <dl className="cifras">
        <div>
          <dt>Servicios</dt>
          <dd>{total}</dd>
        </div>
        <div>
          <dt>Entidades</dt>
          <dd>{entidades.length}</dd>
        </div>
        <div>
          <dt>Con lógica del LLM</dt>
          <dd>{conLogica}</dd>
        </div>
        <div>
          <dt>Pruebas aceptadas</dt>
          <dd>{pruebas}</dd>
        </div>
        {usos.length > 0 && (
          <div>
            <dt>Tokens del LLM</dt>
            <dd title={`${llamadas} llamadas al proveedor`}>{tokens.toLocaleString('es')}</dd>
          </div>
        )}
      </dl>
      {resumen.nivel_pruebas === 'rapido' && (
        <p className="tarjeta__intro">
          Las pruebas Jest se pidieron con el modelo rápido (LLM_NIVEL_PRUEBAS=rapido), que gasta
          menos cuota.
        </p>
      )}

      {resumen.servicios.map((servicio) => (
        <Servicio key={servicio.servicio} servicio={servicio} />
      ))}
    </section>
  )
}

function Servicio({ servicio }: { servicio: ServicioGenerado }) {
  const titulo = `servicio-${servicio.servicio}`
  return (
    <article className="ficha" aria-labelledby={titulo}>
      <div className="tarjeta__cabecera">
        <h3 id={titulo}>{servicio.servicio}</h3>
        <span className={`estado ${servicio.completo ? 'estado--ok' : 'estado--error'}`}>
          {servicio.completo ? 'Completo' : 'Incompleto'}
        </span>
      </div>
      <p className="tarjeta__intro">
        Puerto {servicio.puerto} · base <code>{servicio.base_datos}</code> · rutas en{' '}
        <code>{servicio.prefijo}</code>
        {servicio.archivos > 0 && ` · ${servicio.archivos} archivos`}
      </p>

      {servicio.error && (
        <p className="aviso aviso--error" role="alert">
          {servicio.error}
        </p>
      )}

      <ul className="pasos" aria-label={`Comprobaciones de ${servicio.servicio}`}>
        <li>
          Estructura:{' '}
          {servicio.archivos === 0
            ? 'no se generó'
            : servicio.estructura_valida
              ? 'coincide con la plantilla'
              : 'no coincide con la plantilla'}
          <Problemas lista={servicio.problemas_estructura} />
        </li>
        <li>
          Dependencias:{' '}
          {servicio.dependencias_permitidas === null
            ? 'sin comprobar'
            : servicio.dependencias_permitidas
              ? 'todas en la lista permitida'
              : 'hay paquetes fuera de la lista permitida'}
          {servicio.dependencias_compartidas && ' (instaladas una vez para todos los servicios)'}
          <Problemas lista={servicio.problemas_dependencias} />
        </li>
        <li>
          Compilación:{' '}
          {servicio.compila === null ? 'no se compiló' : servicio.compila ? 'compila con tsc' : 'no compila con tsc'}
          <Problemas lista={servicio.errores_tsc} />
        </li>
      </ul>

      {servicio.entidades.length > 0 && (
        <div className="tabla-contenedor">
          <table className="tabla">
            <caption className="oculto">Entidades de {servicio.servicio}</caption>
            <thead>
              <tr>
                <th scope="col">Entidad</th>
                <th scope="col">Ruta</th>
                <th scope="col">Lógica de negocio</th>
                <th scope="col">Requisitos</th>
                <th scope="col">Pruebas</th>
              </tr>
            </thead>
            <tbody>
              {servicio.entidades.map((entidad) => (
                <Entidad key={entidad.nombre} entidad={entidad} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  )
}

function Entidad({ entidad }: { entidad: EntidadGenerada }) {
  const pruebas = entidad.pruebas_aceptadas + entidad.pruebas_descartadas
  return (
    <tr>
      <th scope="row" className="tabla__nombre">
        {entidad.nombre}
      </th>
      <td>
        <code>{entidad.ruta}</code>
      </td>
      <td>
        {LOGICA[entidad.logica]}
        {entidad.intentos_logica > 1 && ` (${entidad.intentos_logica} intentos)`}
        {entidad.detalle && <span className="vacio"> · {entidad.detalle}</span>}
        {entidad.pendientes.length > 0 && (
          <ul>
            {entidad.pendientes.map((pendiente, posicion) => (
              <li key={posicion}>Pendiente: {pendiente}</li>
            ))}
          </ul>
        )}
      </td>
      <td>{entidad.requisitos.join(', ') || '-'}</td>
      <td>
        {pruebas === 0
          ? '-'
          : `${entidad.pruebas_aceptadas} aceptadas${
              entidad.pruebas_descartadas > 0 ? `, ${entidad.pruebas_descartadas} descartadas` : ''
            }`}
      </td>
    </tr>
  )
}

function Problemas({ lista }: { lista: string[] }) {
  if (lista.length === 0) return null
  return (
    <ul>
      {lista.slice(0, MAXIMO_PROBLEMAS).map((problema, posicion) => (
        <li key={posicion}>{problema}</li>
      ))}
      {lista.length > MAXIMO_PROBLEMAS && <li>y {lista.length - MAXIMO_PROBLEMAS} más</li>}
    </ul>
  )
}
