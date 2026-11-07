import { useEffect, useState } from 'react'
import {
  listarDocumentos,
  obtenerFases,
  obtenerSalud,
  type DocumentoCargado,
  type Fase,
  type Salud,
} from './api'
import { CargaDocumento } from './componentes/CargaDocumento'
import { DocumentosCargados } from './componentes/DocumentosCargados'
import { ListaFases } from './componentes/ListaFases'

type Conexion = { tipo: 'conectando' } | { tipo: 'conectado'; salud: Salud } | { tipo: 'sin-conexion' }

export default function App() {
  const [conexion, setConexion] = useState<Conexion>({ tipo: 'conectando' })
  const [fases, setFases] = useState<Fase[]>([])
  const [documentos, setDocumentos] = useState<DocumentoCargado[]>([])

  useEffect(() => {
    let vigente = true
    Promise.all([obtenerSalud(), obtenerFases(), listarDocumentos()])
      .then(([salud, fasesDelMotor, cargados]) => {
        if (!vigente) return
        setConexion({ tipo: 'conectado', salud })
        setFases(fasesDelMotor)
        setDocumentos(cargados)
      })
      .catch(() => {
        if (vigente) setConexion({ tipo: 'sin-conexion' })
      })
    return () => {
      vigente = false
    }
  }, [])

  return (
    <div className="pagina">
      <header className="cabecera">
        <img className="cabecera__logo" src="/escudo.svg" alt="" width="36" height="36" />
        <div>
          <h1>Framework de desarrollo seguro</h1>
          <p className="cabecera__lema">Del documento de requisitos a microservicios seguros</p>
        </div>
        <EstadoMotor conexion={conexion} />
      </header>

      {conexion.tipo === 'sin-conexion' && (
        <p className="aviso aviso--error" role="alert">
          No se pudo conectar con la API del motor. Levántala con <code>uv run framework api</code>.
        </p>
      )}

      <main className="rejilla">
        <div className="columna">
          <CargaDocumento onCargado={(documento) => setDocumentos((previos) => [documento, ...previos])} />
          <DocumentosCargados documentos={documentos} />
        </div>
        <ListaFases fases={fases} />
      </main>

      <footer className="pie">Dashboard v0 · ESPE, Ingeniería de Software</footer>
    </div>
  )
}

function EstadoMotor({ conexion }: { conexion: Conexion }) {
  switch (conexion.tipo) {
    case 'conectando':
      return <span className="estado">Conectando…</span>
    case 'conectado':
      return <span className="estado estado--ok">Motor v{conexion.salud.version}</span>
    case 'sin-conexion':
      return <span className="estado estado--error">Motor sin conexión</span>
  }
}
