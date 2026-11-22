# Pruebas Jest de la lógica de negocio generadas por el LLM (sprint 4, 19/11)

Servicio `pedidos` de la tienda en línea, generado con la plantilla actual a partir de
`../pedidos/especificacion.yml`. La lógica de negocio de `pedido`, `carrito_item` y `stock` la
escribió el LLM (`servicio logica`, con GraphRAG) y sus pruebas también (`servicio pruebas`).
Proveedor: Groq, `openai/gpt-oss-120b`.

| Entidad | Requisitos | Pruebas del LLM | Intentos | Cobertura de su service.ts |
|---|---|---|---|---|
| `carrito_item` | RF-10, RF-12 | 10, todas pasan | 1 | 97 % de líneas |
| `pedido` | RF-11, RF-12, RF-13, RF-16, RF-20 | 8, todas pasan | 1 | 97 % de líneas |
| `stock` | RF-12, RF-13 | 10, todas pasan | 1 | 100 % de líneas |

Con las de la plantilla, el servicio completo tiene **12 archivos y 218 pruebas, todas en verde**
(`reporte-jest.txt`, con la cobertura de cada archivo). Las entidades sin pruebas de sus reglas se
quedan en 84 %: lo que les falta es justamente el bloque de las reglas de negocio.

- `src/*.reglas.spec.ts`: las pruebas generadas. El encabezado (imports, doble de Prisma, acceso a
  los métodos) lo escribe el motor; el LLM solo el cuerpo de cada caso, con el requisito que
  comprueba en el título.
- `src/*.service.ts`: el código que prueban (el punto de extensión que escribió el LLM).
- `pruebas/*.json` y `logica/*.json`: el registro de cada generación (intentos, casos, estado,
  huella del prompt y respuesta).

## Para revisar

- Las pruebas usan `as any` en algunos dobles de Prisma; compila en modo estricto, pero tipar los
  registros con su clase sería más preciso.
- Si la lógica se genera sin GraphRAG (Neo4j apagado), el LLM tiende a citar controles ASVS que no
  recibió y el motor los rechaza: conviene generar la lógica con el contexto cargado.
