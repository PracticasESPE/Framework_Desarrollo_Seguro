interface Props {
  nombreDocumento: string
  /** Servicios de la arquitectura aprobada, para que la persona sepa qué se va a generar. */
  servicios: number
  /** Hay una ejecución en curso: el motor procesa una a la vez. */
  ocupado?: boolean
  /** La fase 3 ya se lanzó y no terminó bien: el botón pasa a ser un reintento. */
  reintento?: boolean
  /** Motivo por el que no se pudo lanzar la fase 3. */
  error?: string
  onContinuar: () => void
}

/**
 * Punto de control entre las fases 2 y 3. La fase 3 gasta llamadas al LLM (la especificación de
 * cada servicio, y la lógica de negocio y las pruebas de cada entidad), así que no arranca sola:
 * la persona revisa antes la arquitectura aprobada y decide si continuar.
 */
export function ContinuarFase3({
  nombreDocumento,
  servicios,
  ocupado = false,
  reintento = false,
  error,
  onContinuar,
}: Props) {
  return (
    <section className="tarjeta tarjeta--paso" aria-labelledby="titulo-continuar-fase3">
      <h2 id="titulo-continuar-fase3">Siguiente paso: fase 3</h2>
      <p className="tarjeta__intro">
        Revisa la arquitectura de <strong>{nombreDocumento}</strong> que aprobó OPA: sus{' '}
        {servicios} servicios, las bases de datos y las dependencias. La fase 3 genera un
        microservicio por cada uno y gasta llamadas al LLM, por eso no empieza sola.
      </p>
      <ul className="pasos">
        <li>
          Cada servicio sale de la plantilla con las entidades de la arquitectura, sus rutas y los
          controles de seguridad, y se valida su estructura. El LLM solo propone los campos.
        </li>
        <li>
          Se comprueban las dependencias contra la lista permitida antes de instalar nada, y el
          servicio se compila con tsc.
        </li>
        <li>
          El LLM escribe la lógica de negocio de cada entidad y sus pruebas Jest: solo se queda lo
          que compila y lo que pasa.
        </li>
      </ul>
      {error && (
        <p className="aviso aviso--error" role="alert">
          {error}
        </p>
      )}
      <button type="button" className="boton" disabled={ocupado} onClick={onContinuar}>
        {reintento ? 'Volver a intentar la fase 3' : 'Continuar a la fase 3'}
      </button>
    </section>
  )
}
