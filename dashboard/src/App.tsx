import { useEffect, useState } from 'react'
import {
  cancelarEjecucion,
  iniciarEjecucion,
  listarDocumentos,
  listarEjecuciones,
  obtenerFases,
  obtenerSalud,
  type DocumentoCargado,
  type Fase,
  type Salud,
} from './api'
import { CargaDocumento } from './componentes/CargaDocumento'
import { DocumentosCargados } from './componentes/DocumentosCargados'
import { ListaFases } from './componentes/ListaFases'
import { ProgresoEjecucion } from './componentes/ProgresoEjecucion'
import { RequisitosIdentificados } from './componentes/RequisitosIdentificados'
import { estadoDeFases, finDe, resultadoDe, useEventosEjecucion } from './progreso'

type Conexion = { tipo: 'conectando' } | { tipo: 'conectado'; salud: Salud } | { tipo: 'sin-conexion' }

type Inicio = { tipo: 'inactivo' } | { tipo: 'iniciando' } | { tipo: 'error'; mensaje: string }

interface Seguida {
  id: string
  nombreDocumento: string
}

export default function App() {
  const [conexion, setConexion] = useState<Conexion>({ tipo: 'conectando' })
  const [fases, setFases] = useState<Fase[]>([])
  const [documentos, setDocumentos] = useState<DocumentoCargado[]>([])
  const [seguida, setSeguida] = useState<Seguida | null>(null)
  const [inicio, setInicio] = useState<Inicio>({ tipo: 'inactivo' })
  const { eventos, conexion: conexionEventos } = useEventosEjecucion(seguida?.id ?? null)

  const resultado = resultadoDe(eventos)
  const terminada = finDe(eventos) !== null || conexionEventos === 'perdida'
  const ocupado = inicio.tipo === 'iniciando' || (seguida !== null && !terminada)

  async function procesar(documento: DocumentoCargado) {
    setInicio({ tipo: 'iniciando' })
    try {
      const ejecucion = await iniciarEjecucion(documento.id)
      setSeguida({ id: ejecucion.id, nombreDocumento: documento.nombre })
      setInicio({ tipo: 'inactivo' })
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo iniciar la ejecución'
      setInicio({ tipo: 'error', mensaje })
    }
  }

  useEffect(() => {
    let vigente = true
    Promise.all([obtenerSalud(), obtenerFases(), listarDocumentos(), listarEjecuciones('en_curso')])
      .then(([salud, fasesDelMotor, cargados, enCurso]) => {
        if (!vigente) return
        setConexion({ tipo: 'conectado', salud })
        setFases(fasesDelMotor)
        setDocumentos(cargados)
        // Si al recargar la página había una ejecución en marcha, se retoma: el flujo de eventos
        // reenvía todo lo ocurrido desde el principio.
        const enMarcha = enCurso[0]
        if (enMarcha) setSeguida({ id: enMarcha.id, nombreDocumento: enMarcha.nombre_documento })
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
          <CargaDocumento
            onCargado={(documento) => setDocumentos((previos) => [documento, ...previos])}
            onProcesar={(documento) => void procesar(documento)}
            ocupado={ocupado}
          />
          {inicio.tipo === 'error' && (
            <p className="aviso aviso--error" role="alert">
              {inicio.mensaje}
            </p>
          )}
          {seguida && (
            <ProgresoEjecucion
              key={seguida.id}
              nombreDocumento={seguida.nombreDocumento}
              eventos={eventos}
              conexion={conexionEventos}
              onCancelar={async () => {
                await cancelarEjecucion(seguida.id)
              }}
            />
          )}
          {resultado && <RequisitosIdentificados resumen={resultado} />}
          <DocumentosCargados
            documentos={documentos}
            onProcesar={(documento) => void procesar(documento)}
            ocupado={ocupado}
          />
        </div>
        <ListaFases fases={fases} estados={estadoDeFases(eventos)} />
      </main>

      <footer className="pie">Dashboard v1 · ESPE, Ingeniería de Software</footer>
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
