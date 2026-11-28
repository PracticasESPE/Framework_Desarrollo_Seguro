# Sprint 4: trazabilidad requisito -> componente -> archivo (25/11)

Enlace en Neo4j de los requisitos del documento 1 con los servicios generados y sus archivos.

```
(:Requisito)-[:IMPLEMENTA_EN]->(:Componente)-[:CONTIENE]->(:Archivo)
```

Ejecución: `ej-20261128-015949-12dae0` (requisitos del documento 1, registrados con
`framework requisitos registrar`).

Comando:

```powershell
uv run framework servicio trazabilidad salida/arquitectura/requisitos-pdf.arquitectura.json --servicios services --ejecucion ej-20261128-015949-12dae0
```

Resultado:

| Concepto | Valor |
|---|---|
| Servicios enlazados | 6 |
| Archivos enlazados | 352 |
| Requisitos enlazados | 26 |
| Requisitos sin nodo | 0 |

Consulta de la cadena de un requisito (RF-10):

```cypher
MATCH (r:Requisito {ejecucion_id: "ej-20261128-015949-12dae0", id: "RF-10"})-[:IMPLEMENTA_EN]->(c:Componente)-[:CONTIENE]->(a:Archivo)
RETURN r.id AS requisito, c.id AS servicio, count(a) AS archivos, collect(a.ruta)[0..3] AS ejemplos;
```

| requisito | servicio | archivos | ejemplos |
|---|---|---|---|
| RF-10 | pedidos | 73 | pedidos/nest-cli.json, pedidos/src/dto/crear-pedido.dto.ts, pedidos/src/configuracion/entorno.spec.ts |

Los archivos excluyen `node_modules`, `.dependencias`, `dist`, `coverage` y `.git`.
