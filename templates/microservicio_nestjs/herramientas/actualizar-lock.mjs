#!/usr/bin/env node
/**
 * Actualiza plantilla/package-lock.json.jinja a partir del package-lock.json de un servicio
 * generado. Hace falta cada vez que cambian las dependencias de plantilla/package.json.jinja.
 *
 * Uso, desde la carpeta de un servicio recién generado:
 *
 *   npm install --package-lock-only --ignore-scripts
 *   node <repo>/templates/microservicio_nestjs/herramientas/actualizar-lock.mjs
 *
 * El lock de npm solo depende del servicio por su nombre: se sustituye por la variable de Copier.
 * Todo lo demás (versiones exactas e integridad SHA-512 de cada paquete) es igual en todos los
 * servicios, y `npm ci` en el Dockerfile y en el CI instala exactamente eso.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const MARCA = '__NOMBRE_DEL_SERVICIO__';
const destino = join(dirname(fileURLToPath(import.meta.url)), '..', 'plantilla', 'package-lock.json.jinja');

const lock = JSON.parse(readFileSync(join(process.cwd(), 'package-lock.json'), 'utf-8'));
const raiz = lock.packages?.[''];
if (lock.lockfileVersion !== 3 || !raiz || raiz.name !== lock.name) {
  console.error('package-lock.json no es un lock de npm (versión 3) de un servicio generado');
  process.exit(1);
}

lock.name = MARCA;
raiz.name = MARCA;
const texto = `${JSON.stringify(lock, null, 2)}\n`;

// Copier renderiza el archivo con Jinja: nada del lock puede parecer una de sus etiquetas.
if (/\{\{|\{%|\{#/.test(texto)) {
  console.error('El lock contiene «{{», «{%» o «{#»: Jinja lo interpretaría');
  process.exit(1);
}

writeFileSync(destino, texto.replaceAll(`"${MARCA}"`, '{{ servicio | tojson }}'), 'utf-8');
console.log(`Escrito ${destino} (${Object.keys(lock.packages).length - 1} paquetes)`);
