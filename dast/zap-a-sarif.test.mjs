// Pruebas del conversor: node --test dast/zap-a-sarif.test.mjs
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';
import { convertir, reglasQueFallan, rutaDe, sinSecretos, textoPlano } from './zap-a-sarif.mjs';

const CARPETA = dirname(fileURLToPath(import.meta.url));
const EJEMPLO = join(CARPETA, 'pruebas', 'zap-ejemplo.json');
const REGLAS = join(CARPETA, 'zap-reglas.conf');
const zap = () => JSON.parse(readFileSync(EJEMPLO, 'utf-8'));
const fallan = () => reglasQueFallan(readFileSync(REGLAS, 'utf-8'));

function regla(sarif, id) {
  return sarif.runs[0].tool.driver.rules.find((r) => r.id === id);
}
function resultadosDe(sarif, id) {
  return sarif.runs[0].results.filter((r) => r.ruleId === id);
}

describe('convertir', () => {
  it('genera SARIF 2.1.0 con ZAP como herramienta', () => {
    const sarif = convertir(zap());
    assert.equal(sarif.version, '2.1.0');
    assert.equal(sarif.runs[0].tool.driver.name, 'ZAP');
    assert.equal(sarif.runs[0].tool.driver.semanticVersion, '2.17.0');
  });

  it('traduce el riesgo de ZAP a nivel y puntuación', () => {
    const sarif = convertir(zap());
    assert.equal(regla(sarif, 'ZAP-40018').defaultConfiguration.level, 'error');
    assert.equal(regla(sarif, 'ZAP-40018').properties['security-severity'], '8.0');
    assert.equal(regla(sarif, 'ZAP-10054-1').defaultConfiguration.level, 'warning');
    assert.equal(regla(sarif, 'ZAP-10054-1').properties['security-severity'], '5.0');
    assert.equal(regla(sarif, 'ZAP-100001').defaultConfiguration.level, 'note');
    assert.equal(regla(sarif, 'ZAP-100001').properties['security-severity'], '2.0');
  });

  it('publica la CWE y omite la desconocida (-1)', () => {
    const sarif = convertir(zap());
    assert.ok(regla(sarif, 'ZAP-40018').properties.tags.includes('external/cwe/cwe-89'));
    assert.deepEqual(regla(sarif, 'ZAP-100001').properties.tags, ['security', 'dast']);
  });

  it('agrupa los ataques al mismo parámetro en un solo resultado', () => {
    assert.equal(resultadosDe(convertir(zap()), 'ZAP-40018').length, 2);
  });

  it('excluye las alertas informativas y sus reglas', () => {
    const sarif = convertir(zap());
    assert.equal(regla(sarif, 'ZAP-100000-1'), undefined);
    assert.equal(resultadosDe(sarif, 'ZAP-100000-1').length, 0);
  });

  it('suprime los falsos positivos sin borrarlos', () => {
    const [resultado] = resultadosDe(convertir(zap()), 'ZAP-10037');
    assert.equal(resultado.suppressions[0].kind, 'external');
  });

  it('usa ids distintos para alertas distintas del mismo plugin', () => {
    const copia = zap();
    copia.site[0].alerts[5].riskcode = '1';
    const sarif = convertir(copia);
    assert.ok(regla(sarif, 'ZAP-100000-1'));
    assert.ok(regla(sarif, 'ZAP-100000-2'));
  });

  it('acepta un reporte sin alertas', () => {
    assert.deepEqual(convertir({ site: [] }).runs[0].results, []);
    assert.deepEqual(convertir({ site: [{ alerts: [] }] }).runs[0].results, []);
  });

  it('rechaza lo que no es un reporte de ZAP', () => {
    assert.throws(() => convertir({}), /falta la lista "site"/);
    assert.throws(() => convertir(null), /falta la lista "site"/);
  });
});

describe('reglas FAIL', () => {
  it('lee solo las reglas con acción FAIL', () => {
    assert.ok(fallan().has('100000'));
    assert.ok(!fallan().has('90001'));
    assert.deepEqual([...reglasQueFallan('# comentario\n90001\tIGNORE\t(x)\n')], []);
  });

  it('eleva a alta una regla FAIL de riesgo bajo, para que OPA la bloquee', () => {
    const sarif = convertir(zap(), fallan());
    assert.equal(regla(sarif, 'ZAP-100000-2').properties['security-severity'], '8.0');
    assert.equal(resultadosDe(sarif, 'ZAP-100000-2')[0].level, 'error');
  });

  it('sin el archivo de reglas se mantiene el riesgo de ZAP', () => {
    assert.equal(regla(convertir(zap()), 'ZAP-100000-2').properties['security-severity'], '2.0');
  });

  it('no eleva las informativas del mismo plugin', () => {
    assert.equal(regla(convertir(zap(), fallan()), 'ZAP-100000-1'), undefined);
  });
});

describe('huella y ubicación', () => {
  const huellas = (sarif) => sarif.runs[0].results.map((r) => r.partialFingerprints['zapHallazgo/v1']);

  it('no depende del host: el mismo hallazgo se reconoce entre entornos', () => {
    const otro = JSON.parse(JSON.stringify(zap()).replaceAll('usuarios:3000', 'servicio:8080'));
    assert.deepEqual(huellas(convertir(zap())), huellas(convertir(otro)));
  });

  it('no depende del ataque ni de la evidencia', () => {
    const otro = zap();
    otro.site[0].alerts[0].instances[0].attack = 'otro ataque';
    otro.site[0].alerts[0].instances[0].evidence = 'otra evidencia';
    assert.deepEqual(huellas(convertir(zap())), huellas(convertir(otro)));
  });

  it('distingue método, ruta y parámetro', () => {
    const lista = huellas(convertir(zap()));
    assert.equal(new Set(lista).size, lista.length);
  });

  it('ubica el hallazgo en la ruta, sin host ni consulta', () => {
    const [primero] = convertir(zap()).runs[0].results;
    const { physicalLocation, logicalLocations } = primero.locations[0];
    assert.equal(physicalLocation.artifactLocation.uri, 'api/usuarios');
    assert.equal(physicalLocation.region.startLine, 1);
    assert.equal(logicalLocations[0].fullyQualifiedName, 'GET /api/usuarios');
  });

  it('codifica las rutas para que sean URI válidas', () => {
    const copia = zap();
    copia.site[0].alerts[0].instances = [
      { uri: 'http://usuarios:3000/api/con espacio', method: 'GET', param: '' },
    ];
    const [primero] = convertir(copia).runs[0].results;
    assert.equal(primero.locations[0].physicalLocation.artifactLocation.uri, 'api/con%20espacio');
  });
});

describe('utilidades', () => {
  it('textoPlano quita el HTML y decodifica entidades', () => {
    assert.equal(textoPlano('<p>a &lt;b&gt; &amp; c</p><p>d</p>'), 'a <b> & c\nd');
    assert.equal(textoPlano(undefined), '');
  });

  it('sinSecretos oculta tokens y recorta la evidencia', () => {
    assert.equal(sinSecretos('Authorization: Bearer abc.def-123'), 'Authorization: Bearer [OCULTO]');
    assert.equal(sinSecretos('x eyJhbGc.eyJzdWI.firma y'), 'x [OCULTO] y');
    assert.equal(sinSecretos('a'.repeat(500)).length, 200);
  });

  it('nunca publica un token en el SARIF', () => {
    assert.doesNotMatch(JSON.stringify(convertir(zap())), /abc\.def-123/);
  });

  it('rutaDe tolera direcciones no válidas', () => {
    assert.equal(rutaDe('http://h:1/a/b?c=1'), 'a/b');
    assert.equal(rutaDe('http://h:1/'), '.');
    assert.equal(rutaDe('/sin/host'), 'sin/host');
  });
});

describe('línea de comandos', () => {
  const programa = join(CARPETA, 'zap-a-sarif.mjs');
  const opciones = { stdio: 'pipe' };

  it('escribe el archivo SARIF', () => {
    const salida = join(mkdtempSync(join(tmpdir(), 'zap-')), 'zap.sarif');
    execFileSync(process.execPath, [programa, EJEMPLO, salida, REGLAS], opciones);
    assert.equal(JSON.parse(readFileSync(salida, 'utf-8')).version, '2.1.0');
  });

  it('termina con código 2 si falta un argumento', () => {
    assert.throws(() => execFileSync(process.execPath, [programa], opciones), { status: 2 });
  });

  it('termina con código 2 si la entrada no es válida', () => {
    const carpeta = mkdtempSync(join(tmpdir(), 'zap-'));
    const entrada = join(carpeta, 'malo.json');
    writeFileSync(entrada, '{}');
    assert.throws(
      () => execFileSync(process.execPath, [programa, entrada, join(carpeta, 's.sarif')], opciones),
      { status: 2 },
    );
  });
});
