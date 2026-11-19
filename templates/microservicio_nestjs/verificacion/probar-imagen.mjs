#!/usr/bin/env node
/**
 * Prueba de la imagen de Docker de un servicio generado con la plantilla.
 *
 * Se ejecuta desde la carpeta del servicio, con la imagen ya construida:
 *
 *   docker build -t fw-<servicio>:local .
 *   node <repo>/templates/microservicio_nestjs/verificacion/probar-imagen.mjs fw-<servicio>:local
 *
 * Solo necesita Docker: levanta un PostgreSQL desechable con una contraseña aleatoria en una red
 * privada y arranca el contenedor como en producción (NODE_ENV de la imagen, solo lectura, sin
 * capacidades de Linux). Comprueba cómo está construida la imagen, que falla cerrado sin
 * configuración y cómo responde ya arrancada. Al terminar borra todo lo que creó.
 */
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import process from 'node:process';

const imagen = process.argv[2];
if (!imagen) {
  console.error('Uso: node probar-imagen.mjs <imagen>   (desde la carpeta del servicio)');
  process.exit(2);
}

const servicio = JSON.parse(readFileSync(join(process.cwd(), 'package.json'), 'utf-8')).name;
// La ruta de la primera entidad, tal como la declara su controlador.
const ruta = readdirSync(join(process.cwd(), 'src'))
  .filter((archivo) => archivo.endsWith('.controller.ts'))
  .sort()
  .map((archivo) => /@Controller\('([^']+)'\)/.exec(readFileSync(join(process.cwd(), 'src', archivo), 'utf-8'))?.[1])
  .find(Boolean);

const PUERTO = Number(process.env.PUERTO_PRUEBA ?? 3098);
const sufijo = randomBytes(3).toString('hex');
const RED = `fw-prueba-imagen-${sufijo}`;
const BASE = `fw-prueba-bd-${sufijo}`;
const CONTENEDOR = `fw-prueba-servicio-${sufijo}`;
const CLAVE = randomBytes(18).toString('base64url');
const DATABASE_URL = `postgresql://${servicio}:${CLAVE}@${BASE}:5432/${servicio}_db`;
const KEYCLOAK = ['-e', 'KEYCLOAK_ISSUER=http://keycloak.invalid/realms/framework', '-e', `KEYCLOAK_AUDIENCE=${servicio}-api`];

function docker(argumentos, { tiempo = 120_000 } = {}) {
  const r = spawnSync('docker', argumentos, { encoding: 'utf-8', timeout: tiempo });
  return { codigo: r.status ?? -1, salida: `${r.stdout ?? ''}${r.stderr ?? ''}`.trim() };
}

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));

const resultados = [];
function comprobar(nombre, condicion, detalle = '') {
  resultados.push({ nombre, ok: Boolean(condicion), detalle });
}

async function pedir(camino) {
  const r = await fetch(`http://127.0.0.1:${PUERTO}${camino}`);
  return { estado: r.status, h: r.headers, texto: await r.text() };
}

let fallo = null;
try {
  // ---------- 1. Cómo está construida ----------
  const inspeccion = docker(['image', 'inspect', imagen, '--format', '{{json .Config}}']);
  if (inspeccion.codigo !== 0) throw new Error(`No existe la imagen ${imagen}: ${inspeccion.salida}`);
  const config = JSON.parse(inspeccion.salida);
  const env = Object.fromEntries((config.Env ?? []).map((v) => [v.split('=')[0], v.slice(v.indexOf('=') + 1)]));
  const PUERTO_INTERNO = Number(env.PORT);

  comprobar('Usuario sin privilegios (65532, no root)', config.User === '65532:65532', config.User);
  comprobar('NODE_ENV=production en la imagen', env.NODE_ENV === 'production', env.NODE_ENV);
  comprobar('HEALTHCHECK declarado', config.Healthcheck?.Test?.length > 0);
  comprobar(`Expone solo el puerto ${PUERTO_INTERNO}`,
    JSON.stringify(Object.keys(config.ExposedPorts ?? {})) === JSON.stringify([`${PUERTO_INTERNO}/tcp`]));

  const shell = docker(['run', '--rm', '--entrypoint', '/bin/sh', imagen, '-c', 'true']);
  comprobar('Sin shell (distroless)', shell.codigo !== 0, shell.salida.slice(0, 100));

  // Lo que no debe viajar en la imagen: fuentes, pruebas, secretos y herramientas de desarrollo.
  const contenido = docker(['run', '--rm', imagen, '-e', `
    const fs = require('fs');
    const prohibidos = ['src', 'test', '.env', 'prisma', 'dist/openapi/generar-openapi.js',
      'node_modules/jest', 'node_modules/typescript', 'node_modules/prisma', 'node_modules/ts-jest',
      'node_modules/@nestjs/cli', 'node_modules/@nestjs/testing', 'node_modules/supertest'];
    const presentes = prohibidos.filter((p) => fs.existsSync(p));
    const pruebas = fs.readdirSync('dist', { recursive: true }).filter((f) => /spec\\.js$/.test(f));
    console.log(JSON.stringify({ presentes, pruebas }));
  `]);
  const { presentes = ['(no se pudo leer)'], pruebas = [] } = JSON.parse(contenido.salida.split('\n').pop() || '{}');
  comprobar('Sin fuentes, pruebas, .env ni dependencias de desarrollo', presentes.length === 0 && pruebas.length === 0,
    [...presentes, ...pruebas].join(', '));

  // ---------- 2. Falla cerrado ----------
  const sinConfig = docker(['run', '--rm', imagen], { tiempo: 60_000 });
  comprobar('Sin configuración no arranca y nombra lo que falta', sinConfig.codigo !== 0
    && sinConfig.salida.includes('Falta DATABASE_URL') && sinConfig.salida.includes('Falta KEYCLOAK_ISSUER'),
    sinConfig.salida.slice(0, 200));

  const claveDeEjemplo = docker(['run', '--rm', '-e', `DATABASE_URL=postgresql://${servicio}:CAMBIAR@bd:5432/x`, ...KEYCLOAK, imagen], { tiempo: 60_000 });
  comprobar('Con la contraseña de .env.example no arranca (producción)', claveDeEjemplo.codigo !== 0
    && claveDeEjemplo.salida.includes('DATABASE_URL') && !claveDeEjemplo.salida.includes('CAMBIAR'),
    claveDeEjemplo.salida.slice(0, 200));

  // ---------- 3. En marcha, como en producción ----------
  // La base vive en una red interna, sin salida ni puertos publicados.
  docker(['network', 'create', '--internal', RED]);
  const bd = docker(['run', '-d', '--name', BASE, '--network', RED, '-e', `POSTGRES_USER=${servicio}`,
    '-e', `POSTGRES_PASSWORD=${CLAVE}`, '-e', `POSTGRES_DB=${servicio}_db`, 'postgres:16-alpine'], { tiempo: 300_000 });
  if (bd.codigo !== 0) throw new Error(`No arrancó PostgreSQL: ${bd.salida}`);
  for (let i = 0; i < 60 && docker(['exec', BASE, 'pg_isready', '-U', servicio]).codigo !== 0; i++) await esperar(1000);

  // El cliente de Prisma, su adaptador y el driver de PostgreSQL funcionan con las dependencias
  // de producción de la imagen: una consulta real a la base con el PrismaService del servicio.
  const consulta = docker(['run', '--rm', '--network', RED, '-e', `DATABASE_URL=${DATABASE_URL}`, imagen, '-e', `
    const { PrismaService } = require('./dist/prisma.service');
    const prisma = new PrismaService();
    prisma.$queryRawUnsafe('SELECT 1 AS ok')
      .then((filas) => { console.log(JSON.stringify(filas)); return prisma.$disconnect(); })
      .catch((error) => { console.error(error.message); process.exit(1); });
  `], { tiempo: 60_000 });
  comprobar('Prisma consulta la base con las dependencias de la imagen', consulta.codigo === 0
    && consulta.salida.includes('"ok":1'), consulta.salida.slice(0, 200));

  // El servicio publica su puerto en 127.0.0.1 (red bridge) y se une a la red de la base antes de
  // arrancar. --health-interval acorta la espera de la prueba; el HEALTHCHECK es el de la imagen.
  const creado = docker(['create', '--name', CONTENEDOR, '-p', `127.0.0.1:${PUERTO}:${PUERTO_INTERNO}`,
    '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
    '--health-interval', '2s', '--health-start-period', '30s',
    '-e', `DATABASE_URL=${DATABASE_URL}`, ...KEYCLOAK, imagen]);
  if (creado.codigo !== 0) throw new Error(`No se pudo crear el contenedor: ${creado.salida}`);
  docker(['network', 'connect', RED, CONTENEDOR]);
  const iniciado = docker(['start', CONTENEDOR]);
  if (iniciado.codigo !== 0) throw new Error(`No arrancó el servicio: ${iniciado.salida}`);

  let salud = '';
  for (let i = 0; i < 60; i++) {
    salud = docker(['inspect', CONTENEDOR, '--format', '{{.State.Status}} {{.State.Health.Status}}']).salida;
    if (salud === 'running healthy' || !salud.startsWith('running')) break;
    await esperar(1000);
  }
  comprobar('Arranca en solo lectura y sin capacidades, y el HEALTHCHECK da healthy', salud === 'running healthy', salud);
  if (salud !== 'running healthy') throw new Error(`El servicio no quedó sano (${salud}):\n${docker(['logs', CONTENEDOR]).salida}`);

  const api = await pedir(`/api/${ruta}`);
  comprobar(`GET /api/${ruta} sin token: 401`, api.estado === 401, String(api.estado));
  comprobar('Cabeceras de seguridad (CSP, nosniff, DENY, no-store, sin X-Powered-By)',
    (api.h.get('content-security-policy') ?? '').includes("default-src 'none'")
      && api.h.get('x-content-type-options') === 'nosniff' && api.h.get('x-frame-options') === 'DENY'
      && api.h.get('cache-control') === 'no-store' && !api.h.has('x-powered-by'));
  for (const camino of ['/docs', '/docs-json']) {
    const r = await pedir(camino);
    comprobar(`${camino}: 404 en producción`, r.estado === 404, String(r.estado));
  }

  const registro = docker(['logs', CONTENEDOR]).salida;
  comprobar('El registro indica entorno production y /docs desactivado', registro.includes('entorno production, /docs desactivado'));
  comprobar('El registro no contiene la contraseña de la base', !registro.includes(CLAVE));

  const inicio = Date.now();
  docker(['stop', '-t', '10', CONTENEDOR], { tiempo: 30_000 });
  const segundos = (Date.now() - inicio) / 1000;
  const salida = docker(['inspect', CONTENEDOR, '--format', '{{.State.ExitCode}}']).salida;
  comprobar('Se detiene con SIGTERM sin esperar al SIGKILL', salida !== '137' && segundos < 10,
    `código ${salida} en ${segundos.toFixed(1)} s`);
} catch (error) {
  fallo = error;
} finally {
  docker(['rm', '-f', CONTENEDOR, BASE]);
  docker(['network', 'rm', RED]);
}

if (fallo) {
  console.error(fallo.message ?? fallo);
  process.exit(1);
}
const ancho = Math.max(...resultados.map((r) => r.nombre.length));
for (const r of resultados) {
  const marca = r.ok ? 'OK   ' : 'FALLO';
  console.log(`${marca}  ${r.nombre.padEnd(ancho)}${r.ok || !r.detalle ? '' : `  -> ${r.detalle}`}`);
}
const fallidas = resultados.filter((r) => !r.ok).length;
console.log(`\n${resultados.length - fallidas} de ${resultados.length} comprobaciones correctas (imagen ${imagen}).`);
process.exit(fallidas ? 1 : 0);
