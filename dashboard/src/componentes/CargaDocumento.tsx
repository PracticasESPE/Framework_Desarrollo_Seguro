import { useId, useState, type ChangeEvent, type DragEvent } from 'react'
import { cargarDocumento, type DocumentoCargado } from '../api'
import { EXTENSIONES, TAMANO_MAXIMO, formatearTamano, validarArchivo } from '../validacion'

type Estado =
  | { tipo: 'inactivo' }
  | { tipo: 'subiendo'; nombre: string }
  | { tipo: 'error'; mensaje: string }
  | { tipo: 'listo'; documento: DocumentoCargado }

interface Props {
  onCargado: (documento: DocumentoCargado) => void
}

export function CargaDocumento({ onCargado }: Props) {
  const [estado, setEstado] = useState<Estado>({ tipo: 'inactivo' })
  const [arrastrando, setArrastrando] = useState(false)
  const idAyuda = useId()
  const subiendo = estado.tipo === 'subiendo'

  async function subir(archivo: File) {
    const problema = validarArchivo(archivo)
    if (problema !== null) {
      setEstado({ tipo: 'error', mensaje: problema })
      return
    }
    setEstado({ tipo: 'subiendo', nombre: archivo.name })
    try {
      const documento = await cargarDocumento(archivo)
      setEstado({ tipo: 'listo', documento })
      onCargado(documento)
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo subir el documento'
      setEstado({ tipo: 'error', mensaje })
    }
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

  return (
    <section className="tarjeta" aria-labelledby="titulo-carga">
      <h2 id="titulo-carga">Documento de requisitos</h2>
      <p className="tarjeta__intro">
        Sube el documento del cliente para empezar la fase 1. Se guarda con un nombre generado por
        el motor y nunca se ejecuta.
      </p>

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
          aria-describedby={idAyuda}
        />
        <svg className="zona__icono" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 16V4m0 0-4.5 4.5M12 4l4.5 4.5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
        </svg>
        <span className="zona__titulo">Arrastra el documento aquí</span>
        <span>
          o <span className="zona__enlace">elige un archivo</span>
        </span>
        <span id={idAyuda} className="zona__ayuda">
          PDF, DOCX, TXT o Markdown, hasta {TAMANO_MAXIMO / (1024 * 1024)} MB
        </span>
      </label>

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
