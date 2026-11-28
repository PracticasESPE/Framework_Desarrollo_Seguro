// Trazabilidad de la fase 3: archivos de cada servicio generado en una ejecución.
// (:Requisito)-[:IMPLEMENTA_EN]->(:Componente)-[:CONTIENE]->(:Archivo)
// El Componente ya tiene su restricción en 01_restricciones (ejecucion_id, id).
// Idempotente (IF NOT EXISTS), como el resto de scripts de graph/.

CREATE CONSTRAINT archivo_ejecucion IF NOT EXISTS
FOR (n:Archivo) REQUIRE (n.ejecucion_id, n.ruta) IS UNIQUE;
