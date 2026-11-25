import { useEffect, useState } from 'react'
import {
  cancelarEjecucion,
  iniciarEjecucion,
  iniciarFase2,
  iniciarFase3,
  listarDocumentos,
  listarEjecuciones,
  obtenerFases,
  obtenerSalud,
  type DocumentoCargado,
  type Fase,
  type Salud,
} from './api'
import { ArquitecturaPropuesta } from './componentes/ArquitecturaPropuesta'
import { CargaDocumento } from './componentes/CargaDocumento'
import { ContinuarFase2 } from './componentes/ContinuarFase2'
import { ContinuarFase3 } from './componentes/ContinuarFase3'
import { DocumentosCargados } from './componentes/DocumentosCargados'
import { ListaFases } from './componentes/ListaFases'
import { ProgresoEjecucion } from './componentes/ProgresoEjecucion'
import { RequisitosIdentificados } from './componentes/RequisitosIdentificados'
import { ServiciosGenerados } from './componentes/ServiciosGenerados'
import {
  arquitecturaDe,
  estadoDeFases,
  finDe,
  recuperarSesion,
  resultadoDe,
  serviciosDe,
  useEventosEjecucion,
} from './progreso'

type Conexion = { tipo: 'conectando' } | { tipo: 'conectado'; salud: Salud } | { tipo: 'sin-conexion' }

type Inicio = { tipo: 'inactivo' } | { tipo: 'iniciando' } | { tipo: 'error'; mensaje: string }

interface Seguida {
  /** Id de la ejecución que se sigue. */
  id: string
  /** Id del documento que procesa. */
  documento: string
  nombreDocumento: string
}

export default function App() {
  const [conexion, setConexion] = useState<Conexion>({ tipo: 'conectando' })
  const [fases, setFases] = useState<Fase[]>([])
  const [documentos, setDocumentos] = useState<DocumentoCargado[]>([])
  // Cada fase es una ejecución aparte del motor: la 2 parte del modelo de requisitos que dejó la 1
  // y la 3 de la arquitectura que aprobó la 2.
  const [seguida, setSeguida] = useState<Seguida | null>(null)
  const [seguida2, setSeguida2] = useState<Seguida | null>(null)
  const [seguida3, setSeguida3] = useState<Seguida | null>(null)
  const [inicio, setInicio] = useState<Inicio>({ tipo: 'inactivo' })
  const [inicio2, setInicio2] = useState<Inicio>({ tipo: 'inactivo' })
  const [inicio3, setInicio3] = useState<Inicio>({ tipo: 'inactivo' })
  const { eventos, conexion: conexionEventos } = useEventosEjecucion(seguida?.id ?? null)
  const { eventos: eventos2, conexion: conexionEventos2 } = useEventosEjecucion(
    seguida2?.id ?? null,
  )
  const { eventos: eventos3, conexion: conexionEventos3 } = useEventosEjecucion(
    seguida3?.id ?? null,
  )

  const resultado = resultadoDe(eventos)
  const arquitectura = arquitecturaDe(eventos2)
  const servicios = serviciosDe(eventos3)
  const terminada = finDe(eventos) !== null || conexionEventos === 'perdida'
  const terminada2 = finDe(eventos2) !== null || conexionEventos2 === 'perdida'
  const terminada3 = finDe(eventos3) !== null || conexionEventos3 === 'perdida'
  const ocupado =
    inicio.tipo === 'iniciando' ||
    inicio2.tipo === 'iniciando' ||
    inicio3.tipo === 'iniciando' ||
    (seguida !== null && !terminada) ||
    (seguida2 !== null && !terminada2) ||
    (seguida3 !== null && !terminada3)
  // El botón de la fase 2 aparece cuando la fase 1 terminó bien y la 2 no está en marcha ni
  // terminó bien: así la persona revisa los requisitos antes de gastar llamadas al LLM.
  const fase1Completada = finDe(eventos)?.estado === 'completada' && resultado !== null
  const fase2Completada = finDe(eventos2)?.estado === 'completada'
  const ofrecerFase2 =
    seguida !== null && fase1Completada && !fase2Completada && (seguida2 === null || terminada2)
  // Igual con la fase 3: solo si OPA aprobó la arquitectura y la persona la revisó.
  const fase3Completada = finDe(eventos3)?.estado === 'completada'
  const ofrecerFase3 =
    seguida2 !== null &&
    fase2Completada &&
    arquitectura?.aprobada === true &&
    !fase3Completada &&
    (seguida3 === null || terminada3)

  async function procesar(documento: DocumentoCargado) {
    setInicio({ tipo: 'iniciando' })
    try {
      const ejecucion = await iniciarEjecucion(documento.id)
      setSeguida({ id: ejecucion.id, documento: documento.id, nombreDocumento: documento.nombre })
      setSeguida2(null)
      setSeguida3(null)
      setInicio({ tipo: 'inactivo' })
      setInicio2({ tipo: 'inactivo' })
      setInicio3({ tipo: 'inactivo' })
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo iniciar la ejecución'
      setInicio({ tipo: 'error', mensaje })
    }
  }

  async function continuarConLaFase2(origen: Seguida) {
    setInicio2({ tipo: 'iniciando' })
    try {
      const ejecucion = await iniciarFase2(origen.documento)
      setSeguida2({ ...origen, id: ejecucion.id })
      // Una arquitectura nueva deja sin valor los servicios generados con la anterior.
      setSeguida3(null)
      setInicio2({ tipo: 'inactivo' })
      setInicio3({ tipo: 'inactivo' })
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo iniciar la fase 2'
      setInicio2({ tipo: 'error', mensaje })
    }
  }

  async function continuarConLaFase3(origen: Seguida) {
    setInicio3({ tipo: 'iniciando' })
    try {
      const ejecucion = await iniciarFase3(origen.documento)
      setSeguida3({ ...origen, id: ejecucion.id })
      setInicio3({ tipo: 'inactivo' })
    } catch (error) {
      const mensaje = error instanceof Error ? error.message : 'No se pudo iniciar la fase 3'
      setInicio3({ tipo: 'error', mensaje })
    }
  }

  useEffect(() => {
    let vigente = true
    Promise.all([obtenerSalud(), obtenerFases(), listarDocumentos(), listarEjecuciones()])
      .then(([salud, fasesDelMotor, cargados, ejecuciones]) => {
        if (!vigente) return
        setConexion({ tipo: 'conectado', salud })
        setFases(fasesDelMotor)
        setDocumentos(cargados)
        // Al recargar se vuelve a mostrar la última sesión que recuerda el motor (en marcha o
        // terminada): el flujo de eventos reenvía todo lo ocurrido desde el principio.
        const sesion = recuperarSesion(ejecuciones)
        setSeguida(sesion.fase1)
        setSeguida2(sesion.fase2)
        setSeguida3(sesion.fase3)
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
          No se pudo conectar con la API del motor. Levántala desde la carpeta del proyecto con{" "}
          <code>uv run python -m orchestrator.cli api</code>.
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
          {ofrecerFase2 && (
            <ContinuarFase2
              nombreDocumento={seguida.nombreDocumento}
              requisitos={resultado.requisitos.length}
              ocupado={ocupado}
              reintento={seguida2 !== null}
              error={inicio2.tipo === 'error' ? inicio2.mensaje : undefined}
              onContinuar={() => void continuarConLaFase2(seguida)}
            />
          )}
          {seguida2 && (
            <ProgresoEjecucion
              key={seguida2.id}
              fase={2}
              nombreDocumento={seguida2.nombreDocumento}
              eventos={eventos2}
              conexion={conexionEventos2}
              onCancelar={async () => {
                await cancelarEjecucion(seguida2.id)
              }}
            />
          )}
          {arquitectura && <ArquitecturaPropuesta resumen={arquitectura} />}
          {ofrecerFase3 && (
            <ContinuarFase3
              nombreDocumento={seguida2.nombreDocumento}
              servicios={arquitectura.servicios.length}
              ocupado={ocupado}
              reintento={seguida3 !== null}
              error={inicio3.tipo === 'error' ? inicio3.mensaje : undefined}
              onContinuar={() => void continuarConLaFase3(seguida2)}
            />
          )}
          {seguida3 && (
            <ProgresoEjecucion
              key={seguida3.id}
              fase={3}
              nombreDocumento={seguida3.nombreDocumento}
              eventos={eventos3}
              conexion={conexionEventos3}
              onCancelar={async () => {
                await cancelarEjecucion(seguida3.id)
              }}
            />
          )}
          {servicios && <ServiciosGenerados resumen={servicios} />}
          <DocumentosCargados
            documentos={documentos}
            onProcesar={(documento) => void procesar(documento)}
            ocupado={ocupado}
          />
        </div>
        <ListaFases
          fases={fases}
          estados={
            new Map([
              ...estadoDeFases(eventos),
              ...estadoDeFases(eventos2),
              ...estadoDeFases(eventos3),
            ])
          }
        />
      </main>

      <footer className="pie">Dashboard v2 · ESPE, Ingeniería de Software</footer>
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
