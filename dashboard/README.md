# Dashboard del framework

Interfaz web del framework de desarrollo seguro, hecha con React + Vite (plan técnico, 4.3). Se
compila a archivos estáticos que sirve la propia API del motor (`orchestrator/api.py`), así que no
necesita servidor propio ni CORS. No forma parte de lo que genera el framework.

## Versión 0 (sprint 3, #49)

- **Carga del documento de requisitos.** Se arrastra el archivo o se elige, y la API lo guarda en
  `salida/documentos/` con un nombre generado por el servidor. El dashboard muestra su nombre,
  formato, tamaño, SHA-256 e identificador.
- **Escribir los requisitos.** En la pestaña «Escribir requisitos» se pueden escribir o pegar los
  requisitos o historias de usuario. Se envían como `requisitos-escritos.md` por la misma ruta y con
  las mismas validaciones que un archivo, así que para la fase 1 son un documento más.
- **Documentos cargados.** Lista de lo subido, del más reciente al más antiguo.
- **Fases del pipeline.** Las 11 fases que publica el motor en `/fases`, con los gates resaltados.
- **Estado del motor.** Versión de la API, o aviso si no está levantada.

## Versión 1: progreso por fase con Server-Sent Events (#51)

- **Procesar un documento.** El botón «Procesar documento» (al subirlo) o «Procesar» (en la lista)
  llama a `POST /ejecuciones`, que lanza la fase 1 en segundo plano: extracción con Docling,
  normalización y clasificación con el LLM.
- **Progreso en tiempo real.** El dashboard abre un `EventSource` a
  `/ejecuciones/{id}/eventos` y muestra cada evento en cuanto llega:
  - la fase en curso resaltada en «Fases del pipeline», con su barra y el paso actual;
  - la barra general y el registro de eventos con la hora de cada uno.
- **Requisitos identificados.** Al terminar, se muestran los requisitos con su tipo (RF o RNF),
  el servicio sugerido y las etiquetas de seguridad. El modelo queda en
  `salida/requisitos/<id del documento>.modelo_requisitos.json`.
- **Registro en Neo4j.** Al terminar la fase 1, los requisitos se guardan solos como nodos
  `Requisito` de una ejecución nueva, como `framework requisitos registrar`. La tarjeta muestra el
  id de esa ejecución, que se puede consultar con `framework requisitos listar`.
  - Si Neo4j no está levantado, la fase termina igual y el registro de eventos lo avisa.
  - Los requisitos se pueden registrar después con `framework requisitos registrar`.

## Versión 2: fase 2 con un punto de control

La fase 2 gasta llamadas al LLM, así que **no arranca sola**. Al terminar la fase 1, bajo la tabla
de requisitos aparece la tarjeta «Siguiente paso: fase 2». La persona revisa los requisitos
(tipo, servicio sugerido, etiquetas de seguridad) y, si están bien, pulsa **Continuar a la fase 2**.
Hasta ese momento el motor no recibe ninguna petición de la fase 2.

- **Lanzar.** El botón llama a `POST /ejecuciones` con `{"documento": "<id>", "fase": 2}`. La fase 2
  es una ejecución aparte que parte del `modelo_requisitos.json` guardado en disco, así que no
  depende de que la ejecución de la fase 1 siga en memoria. Si el documento no pasó por la fase 1,
  la API responde 409.
- **Progreso.** Mismo mecanismo SSE que la fase 1, en una tarjeta «Progreso de la fase 2»: cada
  intento del ciclo LLM ↔ OPA, los motivos de rechazo de OPA, la redacción de cada ADR y el
  diagrama. Se puede cancelar: se detiene antes de la siguiente llamada al LLM.
- **Arquitectura propuesta.** Al terminar: el ciclo intento por intento, los servicios con su base
  de datos y dependencias, las decisiones, los patrones que infiere OPA, los ADR generados y el
  diagrama de contenedores.
- **Diagrama.** Se dibuja con SVG propio (`src/diagrama.ts` y `DiagramaArquitectura.tsx`) a partir
  de los datos estructurados del resumen de la fase 2: usuarios, API Gateway si OPA infirió ese
  patrón, identidad si algún requisito pide autenticación o autorización, un contenedor por
  servicio con su base de datos, las llamadas HTTP entre servicios (arcos) y el bus de eventos
  (líneas punteadas). No usa librerías ni estilos en línea, así que no relaja la CSP. Es un dibujo
  propio y más simple que el C4 de Mermaid; por eso, debajo se deja el **código Mermaid exacto**
  del documento `<id>.arquitectura.md` (contexto y contenedores) y, junto a cada bloque, el enlace
  «Abrir en Mermaid Live» para dibujarlo y compararlo. El código va en el fragmento del enlace
  (`#base64:…`), que el navegador no envía a ningún servidor; la página que se abre sí es externa.
  No se empaqueta Mermaid en el dashboard porque dibuja con estilos en línea (los bloquea
  `style-src 'self'`) y añadiría entre 1 y 2 MB.
- **Si OPA rechaza todas las propuestas** (3 intentos), la fase queda «Fallida», se muestran los
  motivos y la última propuesta para revisarla, no se generan ADR ni diagrama y el botón pasa a
  «Volver a intentar la fase 2».
- **Archivos.** En `salida/arquitectura/`: `<id>.arquitectura.json`, `<id>.intentos.json`,
  `<id>.adr/` (un ADR por decisión y por patrón, más su índice) y `<id>.arquitectura.md`. Las
  decisiones se guardan en Neo4j como nodos `Decision` enlazados a los requisitos; si Neo4j no
  está levantado, la fase termina igual y el registro de eventos lo avisa.
- **Requisitos del entorno.** OPA instalado (`winget install open-policy-agent.opa`) y el proveedor
  de LLM configurado. Sin OPA, la fase falla con un mensaje claro en cuanto debe validar la primera
  propuesta (ya habrá gastado esa llamada al LLM).

Al recargar la página, el dashboard vuelve a mostrar la última sesión que recuerda el motor, esté
en marcha o terminada: pide `GET /ejecuciones`, toma la ejecución en curso (o, si no hay, la más
reciente) y recupera las dos fases de ese documento. El flujo de eventos reenvía todo lo ocurrido,
así que reaparecen los requisitos, el botón «Continuar a la fase 2» si todavía no se pulsó y la
arquitectura si la fase 2 ya terminó. Una fase 2 anterior a la última fase 1 del documento se
ignora. El motor guarda las últimas 20 ejecuciones **en memoria**: si se reinicia la API, la
sesión se pierde y los resultados siguen en `salida/`.

Cada evento lleva un número correlativo. Si se corta la conexión, EventSource se reconecta solo
con `Last-Event-ID` y el motor le reenvía lo que faltaba. Las fases 4 a 11 aparecen pendientes
hasta que existan en el motor.

## Versión 3: fase 3, los microservicios

Igual que la fase 2, **no arranca sola**: cuando la fase 2 termina y OPA aprobó la arquitectura,
bajo ella aparece «Siguiente paso: fase 3». La persona revisa los servicios, las bases de datos y
las dependencias y pulsa **Continuar a la fase 3**. Si OPA rechazó la arquitectura, no se ofrece.

- **Lanzar.** `POST /ejecuciones` con `{"documento": "<id>", "fase": 3}`. Parte de
  `salida/arquitectura/<id>.arquitectura.json` y del modelo de requisitos; si falta alguno, la API
  responde 409. Cada ejecución escribe en una carpeta nueva, `salida/servicios/<id>-<fecha>/`.
- **Qué hace el motor por cada servicio** (`orchestrator/generation/sistema.py`): parámetros desde
  la arquitectura; campos de las entidades con el LLM (exactamente las entidades de la
  arquitectura); plantilla Copier con su estructura validada; dependencias contra la lista
  permitida; instalación y `tsc`; lógica de negocio de cada entidad con el LLM, verificada con tsc;
  y sus pruebas Jest, verificadas ejecutándolas. Un servicio que falla no detiene los demás.
- **Más rápido.** Todos los servicios generados tienen el mismo `package-lock.json` salvo el
  nombre, así que las dependencias se instalan una sola vez en `salida/servicios/.dependencias/`
  y cada servicio enlaza ahí su `node_modules` (unión de directorios en Windows, sin permisos de
  administrador). Lo comparten todos los servicios y todas las ejecuciones: con la arquitectura de
  prueba, el primer servicio tarda unos 36 s en instalarlas y cada uno de los siguientes, 5 s.
- **Progreso.** Tarjeta «Progreso de la fase 3», con el servicio y el paso en curso
  («pedidos (2/5): lógica de negocio de pedido»). Se puede cancelar entre pasos.
- **Microservicios generados.** Al terminar: cuántos quedaron completos, las advertencias de la
  arquitectura (p. ej. una entidad en varios servicios) y, por servicio, su puerto, base de datos y
  rutas, si la estructura coincide con la plantilla, si las dependencias son las permitidas, si
  compila, y por entidad el estado de la lógica de negocio (aceptada, sin lógica para revisión,
  error o no generada), los requisitos que implementa, lo que el LLM dejó pendiente y las pruebas
  aceptadas y descartadas. Todo se muestra como texto; el código no, queda en la carpeta para
  revisarlo.
- **Si ningún servicio se completa**, la fase queda «Fallida» con el detalle de cada uno y el
  botón pasa a «Volver a intentar la fase 3».
- **Contexto de seguridad.** Con Neo4j levantado (`NEO4J_PASSWORD`), cada prompt lleva el contexto
  GraphRAG del servicio; si no responde, la fase sigue sin él y el registro de eventos lo avisa.
- **Requisitos del entorno.** Node.js 22 y el proveedor de LLM configurado.

Volver a lanzar la fase 1 o la 2 descarta la fase 3 que se estaba mostrando, porque partiría de un
resultado anterior. Al recargar la página se recuperan las tres fases del documento.

Con los endpoints de estado (#53):

- **Cancelar.** Mientras la ejecución está en curso, el botón «Cancelar» llama a
  `POST /ejecuciones/{id}/cancelar`. El motor se detiene en su siguiente paso, y la fase y la
  ejecución quedan como «Cancelada».
- **Retomar al recargar.** Al abrir la página, el dashboard pregunta por
  `GET /ejecuciones?estado=en_curso`. Si hay una ejecución en marcha, vuelve a seguirla y recibe
  todos sus eventos desde el principio.

## Uso

Con la API del motor sirviendo el dashboard compilado:

```bash
cd dashboard
npm ci                # .npmrc desactiva los scripts de instalación
npm run build         # genera dashboard/dist
cd ..
uv run framework api  # http://127.0.0.1:8000
```

En desarrollo, con recarga automática: `uv run framework api` en una terminal y `npm run dev` en
otra (http://127.0.0.1:5173). Vite reenvía a la API las rutas `/salud`, `/fases`, `/configuracion`,
`/documentos` y `/ejecuciones`.

| Comando | Qué hace |
|---|---|
| `npm run lint` | ESLint con `eslint-plugin-security`, reglas con tipos y hooks de React |
| `npm test` | Pruebas con Vitest y Testing Library |
| `npm run build` | Comprueba los tipos (`tsc -b`) y compila con Vite |

## Seguridad de la carga

El documento es la entrada menos confiable del framework. El dashboard avisa antes de subir, pero
quien decide es la API (`orchestrator/documentos.py`):

| Riesgo | Control |
|---|---|
| Archivo peligroso con otra extensión (CWE-434) | Lista permitida (PDF, DOCX, TXT y MD) y comprobación del contenido: cabecera `%PDF-`, estructura del DOCX o texto UTF-8 sin bytes nulos |
| Recorrido de rutas (CWE-22) | El nombre guardado lo genera el servidor; el original solo se muestra |
| Archivo enorme (CWE-400) | Máximo 10 MB, cortando la lectura del cuerpo al superarlo |
| DOCX que se descomprime en gigas (CWE-409) | Límite de entradas y de tamaño descomprimido |
| Inyección de contenido en la página | Cabeceras CSP `default-src 'self'`, `nosniff` y `frame-ancestors 'none'` |

El archivo viaja como cuerpo binario (`application/octet-stream`) y no como formulario
`multipart`. Así no hace falta otra dependencia para interpretar formularios, y el tamaño se
controla mientras llega el cuerpo.

La API escucha solo en `127.0.0.1` porque aún no tiene autenticación.

## Seguridad de las ejecuciones

| Riesgo | Control |
|---|---|
| Lanzar muchas ejecuciones y agotar la CPU o la cuota del LLM (CWE-400) | Una ejecución a la vez: la segunda recibe 409. El registro en memoria guarda como mucho 20 |
| Pasar una ruta en vez de un documento (CWE-22) | `documento` debe ser un id de 32 hexadecimales generado por el servidor; campos extra, 422 |
| Mostrar detalles internos en un error (CWE-209) | Los errores esperados (documento, LLM) muestran su motivo. Los demás van al log de la API, y el dashboard solo ve un aviso genérico |
| Texto del documento con HTML o scripts | React escapa todo el texto de los requisitos; no se usa `dangerouslySetInnerHTML`. La CSP sigue en `connect-src 'self'` |

## Por qué no está en el Gate 1

El Gate 1 analiza el código que genera el framework. Sus SARIF alimentan la decisión de OPA y las
métricas de cada ejecución, y mezclar ahí el dashboard falsearía esas métricas. Por eso el workflow
tiene un job propio, `dashboard`, que aplica las mismas herramientas: `npm ci --ignore-scripts`,
ESLint con `eslint-plugin-security`, `tsc`, pruebas y Semgrep. Trivy fs y Gitleaks del Gate 1 ya
revisan `dashboard/package-lock.json` y el historial.
