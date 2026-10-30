# Prueba comparativa: Neo4j vs PostgreSQL + pgvector

Ejecutada el 2026-10-29 00:46 UTC en Windows 11, Python 3.12.15. 300 mediciones por consulta y motor, tras 30 de calentamiento. Latencias en milisegundos, medidas desde el cliente en Python (incluyen la ida y vuelta por la red local de Docker).

Datos: 86 elementos de conocimiento, 108 relaciones y 86 fragmentos con embeddings de 384 dimensiones, idénticos en las dos bases.

## Latencia vista desde el motor del framework (cliente)

Conexión reutilizada en los dos casos: una sesión de Neo4j y una conexión de PostgreSQL.

| Consulta | Motor | Media | Mediana (p50) | p95 | Más rápido |
|---|---|---|---|---|---|
| Trazabilidad a 3 saltos (riesgo → CWE → práctica → control) | Neo4j | 10.226 | 9.354 | 17.181 | PostgreSQL (8.0×) |
| | PostgreSQL | 1.276 | 1.26 | 1.702 | |
| Controles que protegen frente a una CWE | Neo4j | 6.128 | 6.02 | 7.751 | PostgreSQL (3.4×) |
| | PostgreSQL | 1.784 | 1.609 | 3.23 | |
| 5 fragmentos más parecidos (búsqueda vectorial) | Neo4j | 7.854 | 7.758 | 10.426 | PostgreSQL (5.1×) |
| | PostgreSQL | 1.549 | 1.446 | 2.215 | |

## Tiempo dentro de cada base (servidor)

Neo4j: tiempo hasta tener y entregar el resultado, según el resumen de la consulta. PostgreSQL: planificación más ejecución, según EXPLAIN ANALYZE. Excluye la red y el driver.

| Consulta | Motor | Media | Mediana (p50) | p95 | Más rápido |
|---|---|---|---|---|---|
| Trazabilidad a 3 saltos (riesgo → CWE → práctica → control) | Neo4j | 4.783 | 4.0 | 10.0 | PostgreSQL (12.7×) |
| | PostgreSQL | 0.377 | 0.328 | 0.54 | |
| Controles que protegen frente a una CWE | Neo4j | 2.57 | 3.0 | 4.0 | PostgreSQL (10.2×) |
| | PostgreSQL | 0.252 | 0.239 | 0.317 | |
| 5 fragmentos más parecidos (búsqueda vectorial) | Neo4j | 3.003 | 3.0 | 5.0 | PostgreSQL (15.2×) |
| | PostgreSQL | 0.198 | 0.183 | 0.289 | |

## Neo4j con una transacción gestionada por consulta

Es lo que hace hoy el motor (driver.execute_query): cada consulta abre su propia transacción con reintentos automáticos.

| Consulta | Media | Mediana (p50) | p95 |
|---|---|---|---|
| Trazabilidad a 3 saltos (riesgo → CWE → práctica → control) | 10.212 | 8.938 | 11.787 |
| Controles que protegen frente a una CWE | 10.368 | 8.36 | 14.48 |
| 5 fragmentos más parecidos (búsqueda vectorial) | 8.513 | 8.348 | 10.41 |

## Verificación de resultados

- Trazabilidad: las dos bases devuelven los mismos controles en 10 de 10 riesgos.
- Controles por CWE: mismos controles en 42 de 42 CWE.
- Búsqueda vectorial: coincidencia media del top 5 entre las dos bases del 88% (los índices HNSW son aproximados).
