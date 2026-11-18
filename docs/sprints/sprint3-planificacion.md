# Sprint 3: planificación (fases 1 y 2)

Del 4 al 13 de noviembre de 2026: 8 días y 64 horas de equipo (32 por integrante).

**Objetivo del plan técnico:** del documento de requisitos al modelo estructurado, la arquitectura
validada por OPA, los ADR y el diagrama C4. Dataset de evaluación y primera versión del dashboard.

El sprint no tiene hito de control propio. El siguiente es el del 27 de noviembre (fases 1 a 4), y
este sprint le entrega su entrada: `modelo_requisitos.json` y `arquitectura.json`.

## Punto de partida

La regla de avance del plan pide cumplir el hito del 30 de octubre antes de empezar. Los tres gates
pasan en CI con decisión de OPA y avisos en Telegram (ver
[sprint2-demostracion.md](sprint2-demostracion.md)). El hito se cierra con la demostración.

Las carpetas de este sprint están vacías o no existen: `orchestrator/ingest/`,
`orchestrator/architecture/`, `policies/arquitectura/`, `dashboard/`, `evaluation/datasets/` y
`docs/adr/`. El esquema de Neo4j ya tiene las restricciones de `Requisito` y `Decision`.

## Cronograma

| Fecha | Marcelo (motor e IA) | Abner (plataforma y seguridad) |
|---|---|---|
| 04/11 mié | #46 Docling: extracción de PDF, DOCX y TXT | #45 Dataset: documento 1 (tienda en línea) |
| 05/11 jue | #48 Normalización y esquema Pydantic `Requisito` | #47 Documentos 2 y 3 (gestión académica, citas médicas) |
| 06/11 vie | #50 Clasificación RF/RNF y etiquetas de seguridad con LLM | #49 Dashboard React + Vite: estructura y carga del documento |
| 09/11 lun | #52 Requisitos como nodos en Neo4j | #51 Dashboard: progreso por fase con Server-Sent Events |
| 10/11 mar | #54 Propuesta de arquitectura con LLM | #53 API del motor: endpoints de ejecución y estado |
| 11/11 mié | #56 OPA: reglas arquitectónicas e inferencia de patrones | #55 Generación de ADR en Markdown |
| 12/11 jue | #58 Ciclo LLM ↔ OPA (máximo 3 intentos) y nodos `Decision` | #57 Diagrama C4 en Mermaid |
| 13/11 vie | #60 Fases 1 y 2 con los 3 documentos y demostración | #59 Revisión de ADR y diagramas, correcciones del dashboard e informe del sprint 3 |

## Entregables y evidencias

| Entregable | Responsable | Evidencia |
|---|---|---|
| Módulo `ingest` | Marcelo | Markdown extraído de un documento de prueba |
| Dataset de evaluación (3 documentos) | Abner | Archivos en `evaluation/datasets/` |
| Esquema `Requisito` | Marcelo | PR aprobado y pruebas unitarias |
| `modelo_requisitos.json` | Marcelo | JSON generado a partir del documento 1 |
| Nodos `Requisito` | Marcelo | Consulta Cypher de requisitos registrados |
| Dashboard v0 y vista de progreso | Abner | Capturas de la carga de archivo y del progreso en tiempo real |
| Endpoints de la API del motor | Abner | Captura de `/docs` de FastAPI |
| `arquitectura.json` preliminar | Marcelo | JSON generado para el documento 1 |
| `policies/arquitectura` | Marcelo | Salida de `opa test` |
| Nodos `Decision` enlazados a reglas | Marcelo | Registro de intentos y consulta Cypher |
| `docs/adr/*.md` y `docs/arquitectura.md` | Abner | ADR en el repositorio y diagrama renderizado en GitHub |
| Requisitos, arquitectura y ADR de los 3 documentos | Marcelo | Capturas de las salidas |
| Informe del sprint 3 | Abner | Informe en el repositorio |

## Pendientes del sprint 2

| Pendiente | Responsable | Para el |
|---|---|---|
| Informe del sprint 2 (#44) | Marcelo | 04/11 |
| Cerrar #39 y #41: sus PR (#170 y #176) ya están fusionados | Marcelo | 04/11 |
| Cerrar el hito #43 tras la demostración | Ambos | 04/11 |
| Exigir el check `Pipeline por fases` en los rulesets. Hoy solo piden aprobación: un PR con un gate en rojo se puede fusionar | Abner | 04/11 |
| Activar las alertas de Dependabot, que exige el capítulo 10 del plan y están desactivadas | Abner | 06/11 |
| Promover `dev` a `test` y a `main`: llevan 38 commits de retraso. También habilita **Run workflow** | Ambos | 13/11 |
| Unificar quién decide cada gate (ver más abajo) | Ambos | Antes del 27/11 |
| Conservar los resultados de Neo4j de CI: el grafo muere con cada ejecución y las decisiones solo quedan en el log | Marcelo | Antes de la evaluación |

### Quién decide cada gate

El principio P1 pide que decidan las reglas, y el informe del sprint 1 acordó que los scripts se
limitarían a ejecutar las herramientas. Hoy decide cada gate el script y también OPA, y hay que
pasar los dos:

- `gate1.sh` usa `semgrep --error` y `hadolint --failure-threshold warning`, así que un hallazgo
  medio detiene la cadena, mientras que `gate1.rego` lo trata como advertencia. En ese caso Neo4j
  registraría un Gate 1 aprobado en un pipeline detenido.
- ESLint no genera SARIF, de modo que OPA no lo ve. Si el script deja de decidir, un fallo de ESLint
  dejaría de bloquear. Hay que incluirlo en la entrada de `gate1.rego` antes de cambiar el script.

Decisión a tomar entre ambos: si los hallazgos medios de Semgrep y Hadolint bloquean o no. Después,
los scripts solo deben fallar por errores de la herramienta.

## Dependencias entre tareas

- **Documento 1 (04/11)** es la entrada de #46 el mismo día. Conviene tenerlo a primera hora y en
  los tres formatos (PDF, DOCX y TXT). También hay que comprobar el TXT: Docling no lo incluye entre
  sus formatos habituales y puede hacer falta leerlo directamente.
- **API antes que el progreso.** #51 (09/11) consume el flujo de eventos que crea #53 (10/11).
  **Propuesta:** intercambiar las dos tareas, que son de Abner y no afectan a las de Marcelo. El
  06/11, #49 trabaja con un contrato acordado para la carga del documento.
- **Formato de `arquitectura.json`.** #55 y #57 lo consumen, pero la versión final llega con #58
  (12/11). Hay que acordar el esquema antes del 10/11 y generar ADR y C4 con la versión preliminar
  del documento 1.
- **Claves de LLM en CI.** El workflow no pasa ninguna clave de LLM y `GROQ_API_KEY` no está entre
  los secretos del repositorio, que solo tiene `GEMINI_API_KEY` y los de Telegram. Hay que añadirla
  antes del 06/11 si las fases 1 y 2 van a correr en CI.

## Cambios en el pipeline

- Las fases 1 y 2 pasan de `omitir` a `ejecutar` en el workflow, con los mismos nombres de
  `orchestrator/notify/cli.py`. `tests/test_notify_cli.py` falla si no coinciden.
- **Decisión a tomar:** las fases 1 y 2 consumen cuota de LLM y el workflow corre en cada PR.
  Recomendación: en PR, usar un `modelo_requisitos.json` y un `arquitectura.json` fijos y llamar al
  LLM solo en `push` a `dev`. Así, una caída del proveedor no bloquea un PR.
- La carpeta `requirements/` del plan técnico no existe. Mientras tanto, CI toma el documento de
  `evaluation/datasets/`.
- Docling añade dependencias pesadas. `uv.lock` crecerá, Trivy fs lo revisa en el Gate 1 y la
  duración del pipeline, hoy de 11 minutos sobre un límite de 30, puede aumentar. Hay que medirlo el
  04/11.

## Seguridad del código nuevo

- **Dashboard (#49).** El Gate 1 solo analiza `services/usuarios` con tsc, ESLint y Semgrep. Hay que
  añadir `dashboard/` o justificar por qué no, y aplicar `npm ci --ignore-scripts` y `.npmrc` como
  en el servicio. Trivy fs ya revisará su `package-lock.json`.
- **API del motor (#53).** Hoy no tiene autenticación y escucha en `127.0.0.1`, y debe seguir así
  mientras no la tenga. La carga de documentos es la entrada más expuesta del framework: lista
  permitida de extensiones, límite de tamaño y nombre de archivo generado por el servidor (CWE-22 y
  CWE-434). El dashboard se sirve desde la propia API, así que no necesita CORS.
- **Documentos de requisitos.** Son entrada no confiable para el LLM (#50 y #54), y la salida debe
  validarse siempre con Pydantic. Su contenido no se envía a Telegram: solo resúmenes y enlaces.

## Riesgos y contingencia

| Riesgo | Mitigación |
|---|---|
| Docling tarda más de lo previsto en instalarse o rompe el Gate 1 | Medirlo el 04/11 y, si bloquea, usar un `override` como el de `pillow` |
| El ciclo LLM ↔ OPA no converge en 3 intentos | Registrar el rechazo como `Decision` y pasarlo a revisión humana |
| Cuota del LLM agotada durante las pruebas | Caché de respuestas y modelo rápido por defecto, como indica el plan |
| El dashboard no llega al 13/11 | Es una tarea deseable del plan. Primero se recorta SSE por refresco periódico; como último recurso, Streamlit |

Si el sprint se retrasa, se recorta primero el dashboard. No se recortan las tareas de los
requisitos, la arquitectura y OPA, porque de ellas depende el hito del 27 de noviembre.
