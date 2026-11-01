# Prueba comparativa de bases de datos: Neo4j vs PostgreSQL + pgvector

Anexo del plan técnico (sección 5.1.4). El framework eligió Neo4j por su ajuste al modelo de datos
(el conocimiento de seguridad es un grafo) y no por velocidad. Esta prueba respalda la decisión con
datos: la misma base de conocimiento, con los mismos embeddings, se carga en Neo4j y en PostgreSQL
con pgvector, y se mide la latencia media, la mediana y el percentil 95 de tres consultas.

## Método

| Consulta | Qué pregunta | Neo4j | PostgreSQL |
|---|---|---|---|
| Trazabilidad a 3 saltos | Controles que implementan las prácticas que mitigan las CWE de un riesgo del API Top 10 | Un patrón de grafo de 3 saltos | 3 tablas unidas con `JOIN` |
| Controles de una CWE | Controles que la cubren directamente o se implementan con una práctica que la mitiga | `CALL { ... UNION ... }` | `UNION` de dos consultas |
| Búsqueda vectorial | Los 5 fragmentos más parecidos a una pregunta | Índice vectorial `fragmento_embedding` | `ORDER BY embedding <=> vector LIMIT 5` |

- **Mismos datos**: 86 elementos de conocimiento, 108 relaciones y 86 fragmentos con embeddings de
  384 dimensiones del modelo `paraphrase-multilingual-MiniLM-L12-v2`. Los vectores se calculan una
  sola vez y se cargan iguales en las dos bases.
- **Mismo tipo de índice vectorial**: HNSW con similitud coseno en las dos.
- **Parámetros que varían**: la trazabilidad recorre los 10 riesgos, los controles las 42 CWE y la
  búsqueda vectorial 10 preguntas distintas.
- **Medición**: 30 consultas de calentamiento y 300 medidas por consulta y motor. Se registran:
  - la latencia vista desde el cliente en Python, con la conexión reutilizada en los dos motores;
  - el tiempo dentro de cada base: el resumen de Neo4j y `EXPLAIN ANALYZE` de PostgreSQL;
  - Neo4j con una transacción por consulta (`execute_query`), que es como lo usa hoy el motor.
- **Verificación**: antes de medir se comprueba que las dos bases devuelven los mismos resultados.

Resultados completos en [resultados.md](resultados.md) y [resultados.json](resultados.json).

## Resultados (28 de octubre de 2026)

Latencia media en milisegundos:

| Consulta | Neo4j (cliente) | PostgreSQL (cliente) | Neo4j (servidor) | PostgreSQL (servidor) |
|---|---|---|---|---|
| Trazabilidad a 3 saltos | 10,2 | 1,3 | 4,8 | 0,4 |
| Controles de una CWE | 6,1 | 1,8 | 2,6 | 0,3 |
| Búsqueda vectorial top 5 | 7,9 | 1,5 | 3,0 | 0,2 |

Las dos bases devolvieron los mismos controles en todos los casos (10 de 10 riesgos y 42 de 42
CWE). En la búsqueda vectorial, el top 5 coincidió en un 88 %, lo esperable con índices HNSW, que
son aproximados.

## Conclusión

1. **A la escala del proyecto, PostgreSQL es más rápido en las tres consultas**: entre 3 y 8 veces
   vista desde el cliente, y unas 10 a 15 veces dentro de la base. Con tan pocos datos, las tablas
   y sus índices caben enteros en memoria, y PostgreSQL resuelve los `JOIN` sin coste apreciable.
   La ventaja de Neo4j en recorridos de varios saltos, que preveía el plan, no se manifiesta con
   cientos de nodos; aparece con grafos mucho más grandes y recorridos más profundos.
2. **La diferencia no afecta al framework**: el peor p95 de Neo4j es de unos 17 ms, mientras que una
   llamada al LLM tarda segundos, y los escáneres y el DAST, minutos. La base de datos no cambia de
   forma apreciable el tiempo total del pipeline, como anticipaba el plan.
3. **Se mantiene Neo4j**: la elección se basó en el modelo de datos (un grafo de patrones, CWE,
   controles y riesgos, más la trazabilidad de cada ejecución), en tener grafo e índice vectorial
   en una sola base y en poder mostrar la trazabilidad visualmente en Neo4j Browser. Nada de eso
   depende de unos milisegundos de diferencia.

## Limitaciones

- Una sola máquina (Windows 11 con Docker Desktop) y una sola escala de datos. No se probó con
  datos multiplicados.
- Neo4j informa su tiempo interno en milisegundos enteros, así que su columna de servidor tiene
  una resolución de 1 ms.
- Las dos bases corren con su configuración por defecto, sin ajustes de memoria ni de caché.

## Cómo repetirla

1. Define `BENCHMARK_DB_PASSWORD` en `.env`.
2. Levanta PostgreSQL con pgvector y Neo4j:

```bash
docker compose --env-file .env -f evaluation/benchmark_bd/docker-compose.yml up -d
docker compose -f docker-compose.dev.yml up -d neo4j
```

3. Ejecuta la prueba:

```bash
uv run python -m evaluation.benchmark_bd.benchmark --iteraciones 300
```

PostgreSQL se usa solo en esta prueba: no forma parte del framework. Para apagarlo:

```bash
docker compose -f evaluation/benchmark_bd/docker-compose.yml down
```
