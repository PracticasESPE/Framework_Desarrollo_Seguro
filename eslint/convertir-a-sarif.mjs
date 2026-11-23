#!/usr/bin/env node
/**
 * Convierte el informe JSON de ESLint (`eslint -f json`) a SARIF 2.1.0, el formato común de los
 * resultados del framework (principio P2), para el motor y para GitHub code scanning.
 *
 * Sin dependencias: el formateador de Microsoft (@microsoft/eslint-formatter-sarif) arrastra
 * ESLint 8 y una dependencia en la versión «latest», sin fijar.
 *
 * Uso: node convertir-a-sarif.mjs <eslint.json> <salida.sarif> <raíz del repositorio>
 * Las rutas del SARIF quedan relativas a la raíz del repositorio, como pide GitHub.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { relative, resolve, sep } from 'node:path';
import process from 'node:process';

const [entrada, salida, raiz = process.cwd()] = process.argv.slice(2);
if (!entrada || !salida) {
  console.error('Uso: node convertir-a-sarif.mjs <eslint.json> <salida.sarif> [raíz]');
  process.exit(2);
}

const informe = JSON.parse(readFileSync(entrada, 'utf-8'));
const NIVEL = { 1: 'warning', 2: 'error' };
const reglas = new Map();
const resultados = [];

function ayuda(regla) {
  if (regla.startsWith('@typescript-eslint/')) {
    return `https://typescript-eslint.io/rules/${regla.slice('@typescript-eslint/'.length)}`;
  }
  if (regla.startsWith('security/')) {
    return `https://github.com/eslint-community/eslint-plugin-security/blob/main/docs/rules/${regla.slice('security/'.length)}.md`;
  }
  if (!regla.includes('/')) return `https://eslint.org/docs/latest/rules/${regla}`;
  return undefined;
}

for (const archivo of informe) {
  const uri = relative(resolve(raiz), resolve(archivo.filePath)).split(sep).join('/');
  for (const m of archivo.messages) {
    // Sin ruleId: el archivo no se pudo analizar (error de sintaxis o de configuración).
    const regla = m.ruleId ?? 'eslint/error-de-analisis';
    if (!reglas.has(regla)) {
      reglas.set(regla, {
        id: regla,
        shortDescription: { text: regla },
        ...(ayuda(regla) ? { helpUri: ayuda(regla) } : {}),
      });
    }
    console.log(`${uri}:${m.line ?? 1}:${m.column ?? 1}  ${NIVEL[m.severity] ?? 'error'}  ${regla}  ${m.message}`);
    resultados.push({
      ruleId: regla,
      level: m.fatal ? 'error' : (NIVEL[m.severity] ?? 'warning'),
      message: { text: m.message },
      locations: [
        {
          physicalLocation: {
            artifactLocation: { uri },
            region: {
              startLine: m.line ?? 1,
              startColumn: m.column ?? 1,
              ...(m.endLine ? { endLine: m.endLine } : {}),
              ...(m.endColumn ? { endColumn: m.endColumn } : {}),
            },
          },
        },
      ],
    });
  }
}

const sarif = {
  version: '2.1.0',
  $schema: 'https://json.schemastore.org/sarif-2.1.0.json',
  runs: [
    {
      tool: {
        driver: {
          name: 'ESLint',
          informationUri: 'https://eslint.org',
          rules: [...reglas.values()],
        },
      },
      results: resultados,
    },
  ],
};
writeFileSync(salida, `${JSON.stringify(sarif, null, 2)}\n`, 'utf-8');
console.log(`ESLint: ${resultados.length} resultados en ${salida}`);
