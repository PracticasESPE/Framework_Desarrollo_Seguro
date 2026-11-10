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

Cada evento lleva un número correlativo. Si se corta la conexión, EventSource se reconecta solo
con `Last-Event-ID` y el motor le reenvía lo que faltaba. Las fases 2 a 11 aparecen pendientes
hasta que existan en el motor.

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
