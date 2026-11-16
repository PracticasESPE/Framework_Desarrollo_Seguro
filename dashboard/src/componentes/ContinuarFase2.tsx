interface Props {
  nombreDocumento: string
  /** Cantidad de requisitos que se acaban de identificar, para que la persona sepa qué revisa. */
  requisitos: number
  /** Hay una ejecución en curso: el motor procesa una a la vez. */
  ocupado?: boolean
  /** La fase 2 ya se lanzó y no terminó bien: el botón pasa a ser un reintento. */
  reintento?: boolean
  /** Motivo por el que no se pudo lanzar la fase 2. */
  error?: string
  onContinuar: () => void
}

/**
 * Punto de control entre las fases 1 y 2. La fase 2 gasta llamadas al LLM, así que no arranca sola:
 * la persona revisa antes los requisitos identificados y decide si continuar.
 */
export function ContinuarFase2({
  nombreDocumento,
  requisitos,
  ocupado = false,
  reintento = false,
  error,
  onContinuar,
}: Props) {
  return (
    <section className="tarjeta tarjeta--paso" aria-labelledby="titulo-continuar">
      <h2 id="titulo-continuar">Siguiente paso: fase 2</h2>
      <p className="tarjeta__intro">
        Revisa los {requisitos} requisitos de <strong>{nombreDocumento}</strong> en la tabla de
        arriba: tipo, servicio sugerido y etiquetas de seguridad. La fase 2 parte de ellos y gasta
        llamadas al LLM, por eso no empieza sola.
      </p>
      <ul className="pasos">
        <li>
          El LLM propone la arquitectura (servicios, bases de datos y dependencias) y OPA la
          valida con reglas fijas. Si la rechaza, el LLM la corrige: hasta 3 intentos.
        </li>
        <li>
          Si OPA la aprueba, se redacta un ADR por decisión y por patrón de seguridad, y se genera
          el diagrama C4.
        </li>
        <li>Las decisiones quedan en Neo4j, enlazadas a los requisitos.</li>
      </ul>
      {error && (
        <p className="aviso aviso--error" role="alert">
          {error}
        </p>
      )}
      <button type="button" className="boton" disabled={ocupado} onClick={onContinuar}>
        {reintento ? 'Volver a intentar la fase 2' : 'Continuar a la fase 2'}
      </button>
    </section>
  )
}
