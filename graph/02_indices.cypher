// Índices para las consultas frecuentes del motor, los gates y las métricas.
// El índice vectorial de los fragmentos (fragmento_embedding) se crea cuando se fije
// el modelo de embeddings, porque su dimensión depende de él.

// Todos los nodos de una ejecución, para la trazabilidad y el informe.
CREATE INDEX requisito_por_ejecucion IF NOT EXISTS
FOR (n:Requisito) ON (n.ejecucion_id);

CREATE INDEX hallazgo_por_ejecucion IF NOT EXISTS
FOR (n:Hallazgo) ON (n.ejecucion_id);

CREATE INDEX iteracion_por_ejecucion IF NOT EXISTS
FOR (n:Iteracion) ON (n.ejecucion_id);

// Filtros de los gates y del dashboard.
CREATE INDEX hallazgo_severidad IF NOT EXISTS
FOR (n:Hallazgo) ON (n.severidad);

CREATE INDEX hallazgo_herramienta IF NOT EXISTS
FOR (n:Hallazgo) ON (n.herramienta);

CREATE INDEX resultado_gate_gate IF NOT EXISTS
FOR (n:ResultadoGate) ON (n.gate);

// Historial de ejecuciones ordenado por fecha.
CREATE INDEX ejecucion_fecha IF NOT EXISTS
FOR (n:Ejecucion) ON (n.fecha);
