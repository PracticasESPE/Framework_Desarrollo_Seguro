import { useId } from 'react'
import type { ResumenFase2 } from '../api'
import { bloquesMermaid, disenarDiagrama, enlaceMermaidLive, type Caja } from '../diagrama'

const TIPOS_DE_FLECHA = ['https', 'http', 'sql', 'evento'] as const

/**
 * Diagrama de contenedores de la arquitectura (SVG propio) y, debajo, el código Mermaid del que
 * sale el documento C4, con un enlace para abrirlo y comprobarlo en Mermaid Live.
 *
 * El nombre de los servicios lo eligió el LLM: se dibuja como texto SVG, nunca como HTML.
 */
export function DiagramaArquitectura({ resumen }: { resumen: ResumenFase2 }) {
  const idBase = useId().replaceAll(':', '')
  const diseno = disenarDiagrama(resumen)
  const titulo = `${idBase}-titulo`
  const descripcion = `${idBase}-descripcion`
  const bloques = resumen.diagrama ? bloquesMermaid(resumen.diagrama) : []

  return (
    <div className="diagrama">
      <div className="diagrama__lienzo">
        <svg
          className="dg"
          role="img"
          aria-labelledby={`${titulo} ${descripcion}`}
          viewBox={`0 0 ${diseno.ancho} ${diseno.alto}`}
          width={diseno.ancho}
          height={diseno.alto}
        >
          <title id={titulo}>Diagrama de contenedores de la arquitectura</title>
          <desc id={descripcion}>{diseno.descripcion}</desc>
          <defs>
            {TIPOS_DE_FLECHA.map((tipo) => (
              <marker
                key={tipo}
                id={`${idBase}-punta-${tipo}`}
                className={`dg-punta dg-punta--${tipo}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" />
              </marker>
            ))}
          </defs>

          <rect
            className="dg-sistema"
            x="8"
            y={diseno.marcoY}
            width={diseno.ancho - 16}
            height={diseno.alto - diseno.marcoY - 6}
            rx="10"
          />

          {diseno.flechas.map((flecha, i) => (
            <g key={i}>
              <path
                className={`dg-flecha dg-flecha--${flecha.tipo}`}
                d={flecha.trazado}
                markerEnd={flecha.sinPunta ? undefined : `url(#${idBase}-punta-${flecha.tipo})`}
              />
              {flecha.etiqueta && flecha.x !== undefined && flecha.y !== undefined && (
                <text className="dg-etiqueta" x={flecha.x} y={flecha.y}>
                  {flecha.etiqueta}
                </text>
              )}
            </g>
          ))}

          {diseno.cajas.map((caja) => (
            <CajaSvg key={caja.id} caja={caja} />
          ))}
        </svg>
      </div>

      <ul className="leyenda" aria-label="Leyenda del diagrama">
        <li>
          <span className="leyenda__trazo leyenda__trazo--http" aria-hidden="true" /> Llamada HTTP
          (síncrona)
        </li>
        <li>
          <span className="leyenda__trazo leyenda__trazo--evento" aria-hidden="true" /> Evento por
          el bus (asíncrono)
        </li>
        <li>
          <span className="leyenda__trazo leyenda__trazo--sql" aria-hidden="true" /> Acceso a su
          base de datos
        </li>
      </ul>

      {bloques.length > 0 && (
        <details className="mermaid">
          <summary>Código Mermaid del documento C4</summary>
          <p className="vacio">
            Es el contenido de <code>{resumen.archivo_diagrama}</code>. El SVG de arriba se calcula
            con los mismos datos que el diagrama de contenedores; este código es el que dibujan
            GitHub y la vista previa de Markdown de VS Code, y sirve para comprobarlo.
          </p>
          {bloques.map((bloque) => (
            <div key={bloque.titulo} className="mermaid__bloque">
              <div className="mermaid__cabecera">
                <h4>{bloque.titulo}</h4>
                <a
                  className="boton boton--secundario"
                  href={enlaceMermaidLive(bloque.codigo)}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Abrir en Mermaid Live
                </a>
              </div>
              <pre>
                <code>{bloque.codigo}</code>
              </pre>
            </div>
          ))}
          <p className="vacio">
            «Abrir en Mermaid Live» abre una página externa (mermaid.live) con el diagrama cargado.
            El código va en el fragmento del enlace (después del <code>#</code>), que el navegador no
            envía a ningún servidor.
          </p>
        </details>
      )}
    </div>
  )
}

function CajaSvg({ caja }: { caja: Caja }) {
  const cx = caja.x + caja.ancho / 2
  return (
    <g className={`dg-caja dg-caja--${caja.tipo}`}>
      {caja.tipo === 'datos' ? (
        <>
          <path
            d={`M ${caja.x} ${caja.y + 8} v ${caja.alto - 16} a ${caja.ancho / 2} 8 0 0 0 ${caja.ancho} 0 v ${-(caja.alto - 16)}`}
          />
          <ellipse cx={cx} cy={caja.y + 8} rx={caja.ancho / 2} ry="8" />
        </>
      ) : (
        <rect x={caja.x} y={caja.y} width={caja.ancho} height={caja.alto} rx="8" />
      )}
      <text className="dg-caja__titulo" x={cx} y={caja.y + caja.alto / 2 - 2} textAnchor="middle">
        {caja.titulo}
      </text>
      <text className="dg-caja__detalle" x={cx} y={caja.y + caja.alto / 2 + 14} textAnchor="middle">
        {caja.detalle}
      </text>
    </g>
  )
}
