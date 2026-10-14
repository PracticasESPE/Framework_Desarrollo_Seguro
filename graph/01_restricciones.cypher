// Restricciones de unicidad del grafo del framework.
// Cada restricción crea además el índice que la respalda.
// Los scripts son idempotentes (IF NOT EXISTS): se pueden ejecutar en cada arranque del motor.

// --- Base de conocimiento: identificador global ---
CREATE CONSTRAINT patron_id IF NOT EXISTS
FOR (n:Patron) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT directriz_id IF NOT EXISTS
FOR (n:Directriz) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT control_id IF NOT EXISTS
FOR (n:Control) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT cwe_id IF NOT EXISTS
FOR (n:CWE) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT regla_id IF NOT EXISTS
FOR (n:Regla) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT fragmento_id IF NOT EXISTS
FOR (n:Fragmento) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT decision_validada_id IF NOT EXISTS
FOR (n:DecisionValidada) REQUIRE n.id IS UNIQUE;

// --- Ejecuciones del pipeline ---
CREATE CONSTRAINT ejecucion_id IF NOT EXISTS
FOR (n:Ejecucion) REQUIRE n.id IS UNIQUE;

// Los nodos de una ejecución se identifican dentro de ella: el mismo RF-01
// aparece en cada ejecución del mismo documento.
CREATE CONSTRAINT requisito_ejecucion IF NOT EXISTS
FOR (n:Requisito) REQUIRE (n.ejecucion_id, n.id) IS UNIQUE;

CREATE CONSTRAINT decision_ejecucion IF NOT EXISTS
FOR (n:Decision) REQUIRE (n.ejecucion_id, n.id) IS UNIQUE;

CREATE CONSTRAINT componente_ejecucion IF NOT EXISTS
FOR (n:Componente) REQUIRE (n.ejecucion_id, n.id) IS UNIQUE;

// Un hallazgo es el mismo entre iteraciones si conserva su huella SARIF.
CREATE CONSTRAINT hallazgo_ejecucion IF NOT EXISTS
FOR (n:Hallazgo) REQUIRE (n.ejecucion_id, n.huella) IS UNIQUE;

CREATE CONSTRAINT iteracion_ejecucion IF NOT EXISTS
FOR (n:Iteracion) REQUIRE (n.ejecucion_id, n.numero) IS UNIQUE;

CREATE CONSTRAINT resultado_gate_ejecucion IF NOT EXISTS
FOR (n:ResultadoGate) REQUIRE (n.ejecucion_id, n.id) IS UNIQUE;
