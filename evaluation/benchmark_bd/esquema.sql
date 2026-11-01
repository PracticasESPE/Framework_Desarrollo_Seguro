-- Misma base de conocimiento que en Neo4j, modelada de forma relacional para la comparación.
-- Las relaciones del grafo pasan a ser tablas de unión con índices en sus dos columnas.
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS fragmento, incluye, previene, cubre, implementa, mitiga,
    riesgo, control, practica, cwe CASCADE;

CREATE TABLE cwe      (id TEXT PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE practica (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, nombre TEXT NOT NULL); -- patrones y directrices
CREATE TABLE control  (id TEXT PRIMARY KEY, descripcion TEXT NOT NULL);
CREATE TABLE riesgo   (id TEXT PRIMARY KEY, nombre TEXT NOT NULL);

-- (Patron|Directriz)-[:MITIGA]->(CWE)
CREATE TABLE mitiga (practica_id TEXT REFERENCES practica, cwe_id TEXT REFERENCES cwe,
                     PRIMARY KEY (practica_id, cwe_id));
-- (Control)-[:SE_IMPLEMENTA_CON]->(Patron|Directriz)
CREATE TABLE implementa (control_id TEXT REFERENCES control, practica_id TEXT REFERENCES practica,
                         PRIMARY KEY (control_id, practica_id));
-- (Control)-[:CUBRE]->(CWE)
CREATE TABLE cubre (control_id TEXT REFERENCES control, cwe_id TEXT REFERENCES cwe,
                    PRIMARY KEY (control_id, cwe_id));
-- (Control)-[:PREVIENE]->(RiesgoApi)
CREATE TABLE previene (control_id TEXT REFERENCES control, riesgo_id TEXT REFERENCES riesgo,
                       PRIMARY KEY (control_id, riesgo_id));
-- (RiesgoApi)-[:INCLUYE]->(CWE)
CREATE TABLE incluye (riesgo_id TEXT REFERENCES riesgo, cwe_id TEXT REFERENCES cwe,
                      PRIMARY KEY (riesgo_id, cwe_id));

-- Índices para recorrer cada relación también en sentido inverso.
CREATE INDEX ON mitiga (cwe_id);
CREATE INDEX ON implementa (practica_id);
CREATE INDEX ON cubre (cwe_id);
CREATE INDEX ON previene (riesgo_id);
CREATE INDEX ON incluye (cwe_id);

-- (Fragmento)-[:DESCRIBE]->(...), con el mismo embedding de 384 dimensiones que en Neo4j.
CREATE TABLE fragmento (
    id        TEXT PRIMARY KEY,
    origen_id TEXT NOT NULL,
    texto     TEXT NOT NULL,
    embedding vector(384) NOT NULL
);
-- Índice HNSW con distancia coseno, el mismo tipo de índice que usa Neo4j.
CREATE INDEX ON fragmento USING hnsw (embedding vector_cosine_ops);
