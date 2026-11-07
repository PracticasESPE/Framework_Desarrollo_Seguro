import { useId, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import { cargarDocumento, type DocumentoCargado } from '../api'
import {
  EXTENSIONES,
  NOMBRE_ESCRITO,
  TAMANO_MAXIMO,
  formatearTamano,
  validarArchivo,
} from '../validacion'

type Estado =
  | { tipo: 'inactivo' }
  | { tipo: 'subiendo'; nombre: string }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; documento: DocumentoCargado }

type Modo = 'archivo' | 'texto'

interface Props {
  onCargado: (documento: DocumentoCargado) => void
}

const EJEMPLO = `Ejemplo:
1. El cliente se registra con su correo y una contraseña de al menos 12 caracteres.
2. El administrador gestiona el catálogo de productos.
- Como cliente, quiero ver el estado de mis pedidos para saber cuándo llegan.`

export function CargaDocumento({ onCargado }: Props) {
  const [modo, setModo] = useState<Modo>('archivo')
  const [estado, setEstado] = useState<Estado>({ tipo: 'inactivo' })
  const [arrastrando, setArrastrando] = useState(false)
  const [texto, setTexto] = useState('')
  const id = useId()
  const subiendo = estado.tipo === 'subiendo'

  async function subir(archivo: File): Promise<boolean> {
    const problema = validarArchivo(archivo)
    if (problema !== null) {
      setEstado({ tipo: 'error', mensaje: problema })
      return false
    }
    setEstado({ tipo: 'subiendo', nombre: archivo.name })
    try {
      const documento = await cargarDocumento(archivo)
      setEstado({ tipo: 'listo', documento })
      onCargado(documento)
      return true
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo subir el documento'
      setEstado({ tipo: 'error', mensaje })
      return false
    }
  }

  function cambiarModo(nuevo: Modo) {
    if (nuevo === modo || subiendo) return
    setModo(nuevo)
    setEstado({ tipo: 'inactivo' })
  }

  function alElegir(evento: ChangeEvent<HTMLInputElement>) {
    const archivo = evento.target.files?.[0]
    evento.target.value = '' // permite volver a elegir el mismo archivo
    if (archivo) void subir(archivo)
  }

  function alArrastrar(evento: DragEvent<HTMLLabelElement>) {
    evento.preventDefault()
    if (!subiendo) setArrastrando(true)
  }

  function alSoltar(evento: DragEvent<HTMLLabelElement>) {
    evento.preventDefault()
    setArrastrando(false)
    const archivo = evento.dataTransfer.files[0]
    if (archivo && !subiendo) void subir(archivo)
  }

  // Lo escrito viaja como un documento Markdown más: misma ruta, mismas validaciones en la API.
  async function alEnviarTexto(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (texto.trim() === '') return
    const archivo = new File([texto], NOMBRE_ESCRITO, { type: 'text/markdown' })
    if (await subir(archivo)) setTexto('')
  }

  const tamanoTexto = new TextEncoder().encode(texto).length

  return (
    <section className="tarjeta" aria-labelledby="titulo-carga">
      <h2 id="titulo-carga">Documento de requisitos</h2>
      <p className="tarjeta__intro">
        Sube el documento del cliente o escribe los requisitos para empezar la fase 1. Se guarda con
        un nombre generado por el motor y nunca se ejecuta.
      </p>

      <div className="pestanas" role="tablist" aria-label="Forma de entregar los requisitos">
        <button
          type="button"
          role="tab"
          id={`${id}-pestana-archivo`}
          aria-selected={modo === 'archivo'}
          aria-controls={`${id}-panel-archivo`}
          className="pestana"
          onClick={() => cambiarModo('archivo')}
        >
          Subir archivo
        </button>
        <button
          type="button"
          role="tab"
          id={`${id}-pestana-texto`}
          aria-selected={modo === 'texto'}
          aria-controls={`${id}-panel-texto`}
          className="pestana"
          onClick={() => cambiarModo('texto')}
        >
          Escribir requisitos
        </button>
      </div>

      {modo === 'archivo' ? (
        <div role="tabpanel" id={`${id}-panel-archivo`} aria-labelledby={`${id}-pestana-archivo`}>
          <label
            className={`zona${arrastrando ? ' zona--activa' : ''}${subiendo ? ' zona--ocupada' : ''}`}
            onDragOver={alArrastrar}
            onDragLeave={() => setArrastrando(false)}
            onDrop={alSoltar}
          >
            <input
              type="file"
              className="oculto"
              accept={EXTENSIONES.join(',')}
              onChange={alElegir}
              disabled={subiendo}
              aria-describedby={`${id}-ayuda-archivo`}
            />
            <svg className="zona__icono" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
            </svg>
            <span className="zona__titulo">Arrastra el documento aquí</span>
            <span>
              o <span className="zona__enlace">elige un archivo</span>
            </span>
            <span id={`${id}-ayuda-archivo`} className="zona__ayuda">
              PDF, DOCX, TXT o Markdown, hasta {TAMANO_MAXIMO / (1024 * 1024)} MB
            </span>
          </label>
        </div>
      ) : (
        <form
          role="tabpanel"
          id={`${id}-panel-texto`}
          aria-labelledby={`${id}-pestana-texto`}
          className="escritura"
          onSubmit={(evento) => void alEnviarTexto(evento)}
        >
          <label htmlFor={`${id}-texto`} className="escritura__etiqueta">
            Requisitos o historias de usuario
          </label>
          <textarea
            id={`${id}-texto`}
            className="escritura__texto"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
            placeholder={EJEMPLO}
            rows={10}
            disabled={subiendo}
            aria-describedby={`${id}-ayuda-texto`}
          />
          <div className="escritura__pie">
            <span id={`${id}-ayuda-texto`} className="zona__ayuda">
              Uno por línea, en lenguaje natural. Se guarda como {NOMBRE_ESCRITO} ·{' '}
              {formatearTamano(tamanoTexto)} de {TAMANO_MAXIMO / (1024 * 1024)} MB
            </span>
            <button
              type="submit"
              className="boton"
              disabled={subiendo || texto.trim() === ''}
            >
              Enviar requisitos
            </button>
          </div>
        </form>
      )}

      {estado.tipo === 'subiendo' && (
        <p className="aviso" role="status">
          Subiendo {estado.nombre}…
        </p>
      )}
      {estado.tipo === 'error' && (
        <p className="aviso aviso--error" role="alert">
          {estado.mensaje}
        </p>
      )}
      {estado.tipo === 'listo' && <DocumentoRecibido documento={estado.documento} />}
    </section>
  )
}

function DocumentoRecibido({ documento }: { documento: DocumentoCargado }) {
  return (
    <div className="aviso aviso--ok" role="status">
      <p className="aviso__titulo">Documento recibido</p>
      <dl className="ficha">
        <dt>Nombre</dt>
        <dd>{documento.nombre}</dd>
        <dt>Formato</dt>
        <dd>{documento.formato.toUpperCase()}</dd>
        <dt>Tamaño</dt>
        <dd>{formatearTamano(documento.tamano)}</dd>
        <dt>SHA-256</dt>
        <dd>
          <code title={documento.sha256}>{documento.sha256.slice(0, 16)}…</code>
        </dd>
        <dt>Identificador</dt>
        <dd>
          <code>{documento.id}</code>
        </dd>
      </dl>
    </div>
  )
}
