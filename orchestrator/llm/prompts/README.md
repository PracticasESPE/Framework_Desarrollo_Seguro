# Prompts de generación (fase 3)

Prompts con los que el LLM de razonamiento participa en la generación de cada microservicio, con
el contexto de seguridad recuperado por GraphRAG desde Neo4j (plan técnico 6.1 y 7.3).

| Prompt | Qué pide | Respuesta (Pydantic) | Quién la verifica después |
|---|---|---|---|
| `especificacion` | Las entidades y campos de un servicio de `arquitectura.json` | `EntidadesPropuestas`, con las mismas reglas que `templates/microservicio_nestjs/copier.yml` | Copier al generar el servicio |
| `logica` | El cuerpo de `reglasAlCrear`, `reglasAlActualizar` y `reglasAlEliminar` del punto de extensión de una entidad | `LogicaEntidad`: el código, los requisitos que implementa, los controles ASVS que aplica y lo que queda pendiente | El generador (#64): tsc, Semgrep, ESLint y pruebas |

Cada prompt es un `Prompt` con nombre, versión, mensaje de sistema, mensaje, esquema y nivel del
modelo, y su **huella** SHA-256, que identifica el texto exacto que recibió el LLM (plan técnico
6.5, registro de prompts y respuestas).

## Contexto GraphRAG

`contexto.py` arma el contexto de un servicio a partir de las etiquetas de seguridad de sus
requisitos:

1. Una pregunta base (validación de entrada y errores, para cualquier API) y una pregunta fija por
   etiqueta (`PREGUNTAS_POR_ETIQUETA`). El LLM y el documento del cliente no escriben las preguntas:
   la recuperación es reproducible y el documento no puede dirigir qué conocimiento llega.
2. Cada pregunta se consulta con GraphRAG (`orchestrator/knowledge/graphrag.py`): los fragmentos más
   parecidos y, por el grafo, las CWE, los patrones, las directrices, los controles ASVS y los
   riesgos del API Top 10 relacionados.
3. Las respuestas se combinan: cada fragmento una vez, con su mejor puntuación, hasta 12; cada
   elemento una vez, en orden de aparición.

Sin Neo4j o sin embeddings, el prompt lo dice («No se encontró conocimiento relacionado») en lugar
de inventar contexto.

## Seguridad

- **Datos no confiables marcados.** Los requisitos vienen del documento del cliente y los nombres
  de un LLM anterior: van entre marcas con un código aleatorio por prompt, también en los
  atributos, y el mensaje de sistema indica que son datos, nunca instrucciones.
- **Lo decidido no lo vuelve a decidir el LLM.** En la especificación, el nombre del servicio, su
  base de datos y su puerto los pone el motor desde `arquitectura.json`; el LLM solo propone las
  entidades. Las referencias solo pueden apuntar a entidades del mismo servicio (cada servicio
  tiene su base de datos).
- **Reglas del código en el mensaje de sistema** del prompt de lógica: solo el cuerpo de los
  métodos, sin `import` ni `require`, sin `eval`, `process`, `fs`, red ni consultas
  `$queryRawUnsafe`, sin datos personales en la consola ni detalles internos en los mensajes. El
  prompt da los nombres y tipos exactos de TypeScript de cada propiedad y modelo de Prisma, para que
  el código compile con tsc en modo estricto.
- **Lo que el LLM no puede hacer, lo declara.** Si una regla necesita algo que el método no recibe
  (el usuario autenticado, datos de otro servicio), va a `pendientes` en lugar de inventarse.

## Probarlos

```bash
uv run framework servicio prompt salida/arquitectura/requisitos-docx.arquitectura.json \
  --requisitos salida/requisitos/requisitos-docx.modelo_requisitos.json --servicio pedidos
```

Muestra el prompt completo con su contexto GraphRAG (`--sin-graphrag` sin Neo4j). Con `--enviar`
lo manda al LLM y muestra la respuesta validada; en la tarea `especificacion`, `--salida pedidos.yml`
guarda la especificación lista para `servicio generar`. La tarea `logica` necesita además
`--especificacion pedidos.yml --entidad pedido`.

Con el servicio `pedidos` de la tienda en línea (documento 1 del dataset), la especificación que
devolvió `gpt-oss-120b` pasó el esquema y Copier generó el servicio sin errores; el prompt de
lógica devolvió las reglas de RF-10 a RF-13 y RF-20 con los nombres de Prisma correctos y dejó en
pendientes lo que el método no puede hacer (correos, cancelación automática, dueño del pedido).
