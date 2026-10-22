// Convierte la salida JSON de Spectral a SARIF 2.1.0 para publicarla en GitHub Security.
// Se hace aparte porque el formateador SARIF de Spectral falla con el conjunto OWASP
// (una regla trae la descripción vacía y el generador lo rechaza: SARIF_BUILDER_INVALID).
// Uso: node spectral/convertir-a-sarif.mjs <spectral.json> <salida.sarif>
import { readFileSync, writeFileSync } from 'node:fs';
import { isAbsolute, relative } from 'node:path';

const [entrada, salida] = process.argv.slice(2);
if (!entrada || !salida) {
  console.error('Uso: node convertir-a-sarif.mjs <spectral.json> <salida.sarif>');
  process.exit(2);
}

const NIVEL = { 0: 'error', 1: 'warning', 2: 'note', 3: 'note' };
const hallazgos = JSON.parse(readFileSync(entrada, 'utf-8') || '[]');

// GitHub enlaza cada alerta con su archivo usando rutas relativas a la raíz del repositorio.
const rutaRelativa = (fuente) =>
  (fuente && isAbsolute(fuente) ? relative(process.cwd(), fuente) : fuente ?? '')
    .replaceAll('\\', '/');

const reglas = new Map();
const resultados = hallazgos.map((h) => {
  const id = String(h.code);
  const nivel = NIVEL[h.severity] ?? 'warning';
  if (!reglas.has(id)) {
    reglas.set(id, {
      id,
      shortDescription: { text: h.message },
      defaultConfiguration: { level: nivel },
      properties: { tags: ['security', 'openapi'] },
    });
  }
  return {
    ruleId: id,
    level: nivel,
    message: { text: h.message },
    locations: [
      {
        physicalLocation: {
          artifactLocation: { uri: rutaRelativa(h.source) },
          region: {
            startLine: h.range.start.line + 1,
            startColumn: h.range.start.character + 1,
            endLine: h.range.end.line + 1,
            endColumn: h.range.end.character + 1,
          },
        },
        logicalLocations: [{ fullyQualifiedName: (h.path ?? []).join('.') }],
      },
    ],
  };
});

const sarif = {
  $schema: 'https://json.schemastore.org/sarif-2.1.0.json',
  version: '2.1.0',
  runs: [
    {
      tool: {
        driver: {
          name: 'Spectral',
          informationUri: 'https://github.com/stoplightio/spectral',
          rules: [...reglas.values()],
        },
      },
      results: resultados,
    },
  ],
};

writeFileSync(salida, JSON.stringify(sarif, null, 2), 'utf-8');
console.log(`SARIF escrito en ${salida}: ${resultados.length} hallazgo(s), ${reglas.size} regla(s)`);
