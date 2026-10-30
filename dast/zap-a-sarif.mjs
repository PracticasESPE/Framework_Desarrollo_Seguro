// Convierte el reporte JSON de OWASP ZAP (zap.json) a SARIF 2.1.0, el formato común de los
// resultados (principio P2 del plan). Lo leen la pestaña Security de GitHub y el motor
// (orchestrator/gates/sarif.py). Uso:
//   node dast/zap-a-sarif.mjs <zap.json> <salida.sarif> [zap-reglas.conf]
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

// riesgo de ZAP -> nivel SARIF y puntuación. El motor traduce la puntuación a severidad:
// >= 7 alta, >= 4 media, > 0 baja.
const POR_RIESGO = {
  3: { nivel: 'error', puntuacion: '8.0' },
  2: { nivel: 'warning', puntuacion: '5.0' },
  1: { nivel: 'note', puntuacion: '2.0' },
};
const RIESGO_INFORMATIVO = 0;
const CONFIANZA_FALSO_POSITIVO = 0;
const PRECISION = { 1: 'low', 2: 'medium', 3: 'high', 4: 'very-high' };
const MAXIMO_EVIDENCIA = 200;

/** ZAP escribe descripciones en HTML; SARIF espera texto. */
export function textoPlano(html = '') {
  return String(html)
    .replace(/<\/(p|li|div)>/gi, '\n')
    .replace(/<[^>]*>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{2,}/g, '\n')
    .trim();
}

/** Los reportes se publican: un token nunca debe llegar al SARIF, aunque ZAP lo capture. */
export function sinSecretos(texto = '') {
  return String(texto)
    .replace(/Bearer\s+[\w.~+/=-]+/gi, 'Bearer [OCULTO]')
    .replace(/eyJ[\w-]+\.[\w-]+\.[\w-]*/g, '[OCULTO]')
    .slice(0, MAXIMO_EVIDENCIA);
}

/** Ruta codificada de la petición, sin host ni consulta: la huella no depende del entorno. */
export function rutaDe(uri) {
  try {
    return new URL(uri).pathname.replace(/^\/+/, '') || '.';
  } catch {
    return encodeURI(String(uri)).replace(/^\/+/, '') || '.';
  }
}

/** Ids de zap-reglas.conf con acción FAIL: bloquean el Gate aunque ZAP les dé riesgo bajo. */
export function reglasQueFallan(textoConf = '') {
  const ids = new Set();
  for (const linea of textoConf.split(/\r?\n/)) {
    const [id, accion] = linea.split('\t');
    if (accion === 'FAIL' && /^\d+$/.test(id)) ids.add(id);
  }
  return ids;
}

// Sin esto, una regla FAIL de riesgo bajo no bloquearía cuando el Gate lo decida OPA, que solo
// bloquea severidad alta o crítica. Ejemplo: ZAP da riesgo bajo a un error 500.
function clasificar(alerta, fallan) {
  if (fallan.has(String(alerta.pluginid))) return POR_RIESGO[3];
  return POR_RIESGO[Number(alerta.riskcode)] ?? POR_RIESGO[1];
}

function reglaSarif(id, alerta, clase) {
  const cwe = Number(alerta.cweid);
  const descripcion = textoPlano(alerta.desc) || alerta.name;
  const solucion = textoPlano(alerta.solution);
  const referencia = textoPlano(alerta.reference).split('\n')[0];
  return {
    id,
    name: alerta.name,
    shortDescription: { text: alerta.name },
    fullDescription: { text: descripcion },
    ...(solucion && { help: { text: solucion } }),
    ...(/^https?:\/\//.test(referencia) && { helpUri: referencia }),
    defaultConfiguration: { level: clase.nivel },
    properties: {
      tags: ['security', 'dast', ...(cwe > 0 ? [`external/cwe/cwe-${cwe}`] : [])],
      precision: PRECISION[Number(alerta.confidence)] ?? 'medium',
      'security-severity': clase.puntuacion,
    },
  };
}

function resultadoSarif(id, alerta, clase, instancia, ruta, parametro) {
  const metodo = instancia.method || 'GET';
  const huella = createHash('sha256')
    .update([id, metodo, ruta, parametro].join('|'))
    .digest('hex')
    .slice(0, 32);
  const evidencia = sinSecretos(instancia.evidence);
  return {
    ruleId: id,
    level: clase.nivel,
    message: {
      text: `${alerta.name}: ${metodo} /${ruta}${parametro ? ` (parámetro ${parametro})` : ''}`,
    },
    locations: [
      {
        physicalLocation: {
          artifactLocation: { uri: ruta },
          // GitHub exige una línea. Un hallazgo DAST no tiene: se usa siempre la 1.
          region: { startLine: 1 },
        },
        logicalLocations: [{ fullyQualifiedName: `${metodo} /${ruta}` }],
      },
    ],
    partialFingerprints: { 'zapHallazgo/v1': huella },
    ...(evidencia && { properties: { evidencia } }),
    // ZAP lo marcó como falso positivo: el motor y GitHub lo omiten, pero queda constancia.
    ...(Number(alerta.confidence) === CONFIANZA_FALSO_POSITIVO && {
      suppressions: [{ kind: 'external', justification: 'Falso positivo según ZAP' }],
    }),
  };
}

/** Convierte el reporte de ZAP; una entrada sin la lista "site" no es un reporte válido. */
export function convertir(zap, fallan = new Set()) {
  if (!zap || !Array.isArray(zap.site)) {
    throw new Error('el archivo no es un reporte JSON de ZAP: falta la lista "site"');
  }
  const reglas = new Map();
  const resultados = new Map();
  for (const sitio of zap.site) {
    for (const alerta of sitio.alerts ?? []) {
      // Las informativas no son hallazgos: por ejemplo, cada 404 ante una ruta de prueba como
      // /.env. Algunas rutas son aleatorias y darían huellas distintas en cada ejecución.
      // Siguen disponibles en zap.html y zap.json.
      if (Number(alerta.riskcode) === RIESGO_INFORMATIVO) continue;
      const id = `ZAP-${alerta.alertRef || alerta.pluginid}`;
      const clase = clasificar(alerta, fallan);
      if (!reglas.has(id)) reglas.set(id, reglaSarif(id, alerta, clase));
      for (const instancia of alerta.instances ?? []) {
        const ruta = rutaDe(instancia.uri);
        const parametro = instancia.param || '';
        // Un resultado por regla, método, ruta y parámetro: ZAP repite la misma alerta
        // con distintos ataques, y cada uno no es un hallazgo nuevo.
        const clave = [id, instancia.method, ruta, parametro].join('|');
        if (!resultados.has(clave)) {
          resultados.set(clave, resultadoSarif(id, alerta, clase, instancia, ruta, parametro));
        }
      }
    }
  }
  return {
    $schema: 'https://json.schemastore.org/sarif-2.1.0.json',
    version: '2.1.0',
    runs: [
      {
        tool: {
          driver: {
            name: 'ZAP',
            ...(zap['@version'] && { semanticVersion: zap['@version'] }),
            informationUri: 'https://www.zaproxy.org/',
            rules: [...reglas.values()],
          },
        },
        results: [...resultados.values()],
      },
    ],
  };
}

function principal() {
  const [entrada, salida, conf] = process.argv.slice(2);
  if (!entrada || !salida) {
    console.error('Uso: node zap-a-sarif.mjs <zap.json> <salida.sarif> [zap-reglas.conf]');
    process.exit(2);
  }
  try {
    const fallan = reglasQueFallan(conf ? readFileSync(conf, 'utf-8') : '');
    const sarif = convertir(JSON.parse(readFileSync(entrada, 'utf-8')), fallan);
    writeFileSync(salida, JSON.stringify(sarif, null, 2), 'utf-8');
    const { rules } = sarif.runs[0].tool.driver;
    const { results } = sarif.runs[0];
    console.log(`SARIF escrito en ${salida}: ${results.length} resultado(s), ${rules.length} regla(s)`);
  } catch (error) {
    console.error(`No se pudo convertir ${entrada}: ${error.message}`);
    process.exit(2);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) principal();
