#!/usr/bin/env node
/**
 * Prueba de los controles transversales de un servicio generado con la plantilla: cabeceras de
 * seguridad (Helmet), guard de Keycloak, ValidationPipe y filtro de errores.
 *
 * Se ejecuta desde la carpeta del servicio, ya compilado y con su base de datos accesible:
 *
 *   node <repo>/templates/microservicio_nestjs/verificacion/probar-controles.mjs
 *
 * Necesita DATABASE_URL (en el entorno o en el .env del servicio). No necesita Keycloak: el
 * script crea sus propias claves RSA, publica el JWKS en 127.0.0.1 y firma los tokens de prueba.
 * Arranca el servicio en PUERTO_PRUEBA (3099 por defecto) y lo detiene al terminar.
 */
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import process from 'node:process';

// jose se carga de las dependencias del servicio, no del repositorio del framework.
const requerir = createRequire(join(process.cwd(), 'package.json'));
const { SignJWT, exportJWK, generateKeyPair } = requerir('jose');
const paquete = JSON.parse(readFileSync(join(process.cwd(), 'package.json'), 'utf-8'));
const servicio = paquete.name;

const PUERTO = Number(process.env.PUERTO_PRUEBA ?? 3099);
const BASE = `http://127.0.0.1:${PUERTO}`;
const AUDIENCIA = `${servicio}-api`;

// ---------- Keycloak simulado ----------
const claves = await generateKeyPair('RS256');
const otrasClaves = await generateKeyPair('RS256');
const jwk = { ...(await exportJWK(claves.publicKey)), kid: 'prueba', alg: 'RS256', use: 'sig' };
const jwks = createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify({ keys: [jwk] }));
});
await new Promise((ok) => jwks.listen(0, '127.0.0.1', ok));
const EMISOR = `http://127.0.0.1:${jwks.address().port}/realms/prueba`;

function token({ clave = claves.privateKey, audiencia = AUDIENCIA, vence = '5m' } = {}) {
  return new SignJWT({ preferred_username: 'ana' })
    .setProtectedHeader({ alg: 'RS256', kid: 'prueba' })
    .setIssuer(EMISOR)
    .setAudience(audiencia)
    .setSubject('prueba')
    .setIssuedAt()
    .setExpirationTime(vence)
    .sign(clave);
}

const b64 = (objeto) => Buffer.from(JSON.stringify(objeto)).toString('base64url');
const ahora = () => Math.floor(Date.now() / 1000);
// alg=none: sin firma. Un guard que no fije el algoritmo lo aceptaría.
const tokenSinFirma = `${b64({ alg: 'none', typ: 'JWT' })}.${b64({ iss: EMISOR, aud: AUDIENCIA, sub: 'x', exp: ahora() + 300 })}.`;

// ---------- Servicio ----------
const proceso = spawn(process.execPath, ['dist/main.js'], {
  cwd: process.cwd(),
  env: {
    ...process.env,
    // Desarrollo, para comprobar también las cabeceras de /docs: en producción no se publica
    // (eso lo comprueba probar-imagen.mjs sobre la imagen).
    NODE_ENV: 'development',
    PORT: String(PUERTO),
    KEYCLOAK_ISSUER: EMISOR,
    KEYCLOAK_AUDIENCE: AUDIENCIA,
    KEYCLOAK_JWKS_URI: `${EMISOR}/protocol/openid-connect/certs`,
  },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let registro = '';
proceso.stdout.on('data', (d) => (registro += d));
proceso.stderr.on('data', (d) => (registro += d));

async function esperarServicio() {
  for (let i = 0; i < 60; i++) {
    if (proceso.exitCode !== null) break;
    try {
      if ((await fetch(`${BASE}/docs-json`)).ok) return;
    } catch {
      // todavía arrancando
    }
    await new Promise((ok) => setTimeout(ok, 500));
  }
  throw new Error(`El servicio no arrancó en ${BASE}.\n${registro}`);
}

// ---------- Comprobaciones ----------
const resultados = [];
function comprobar(nombre, condicion, detalle = '') {
  resultados.push({ nombre, ok: Boolean(condicion), detalle });
}

async function pedir(ruta, { metodo = 'GET', token: t, cuerpo, tipo = 'application/json' } = {}) {
  const cabeceras = {};
  if (t) cabeceras.Authorization = `Bearer ${t}`;
  if (cuerpo !== undefined) cabeceras['Content-Type'] = tipo;
  const res = await fetch(`${BASE}${ruta}`, { method: metodo, headers: cabeceras, body: cuerpo });
  const texto = await res.text();
  let json;
  try {
    json = JSON.parse(texto);
  } catch {
    json = undefined;
  }
  return { estado: res.status, h: res.headers, texto, json };
}

const formatoDeError = (r) =>
  r.json && r.json.statusCode === r.estado && typeof r.json.error === 'string' && 'message' in r.json;

function cabecerasDeApi(nombre, r) {
  const csp = r.h.get('content-security-policy') ?? '';
  comprobar(`${nombre}: CSP default-src 'none' y frame-ancestors 'none'`,
    csp.includes("default-src 'none'") && csp.includes("frame-ancestors 'none'"), csp);
  comprobar(`${nombre}: X-Content-Type-Options nosniff`, r.h.get('x-content-type-options') === 'nosniff');
  comprobar(`${nombre}: X-Frame-Options DENY`, r.h.get('x-frame-options') === 'DENY');
  const hsts = r.h.get('strict-transport-security') ?? '';
  comprobar(`${nombre}: Strict-Transport-Security de al menos 1 año`,
    Number(/max-age=(\d+)/.exec(hsts)?.[1] ?? 0) >= 31536000, hsts);
  comprobar(`${nombre}: Referrer-Policy no-referrer`, r.h.get('referrer-policy') === 'no-referrer');
  comprobar(`${nombre}: Cross-Origin-Opener-Policy same-origin`, r.h.get('cross-origin-opener-policy') === 'same-origin');
  comprobar(`${nombre}: Cross-Origin-Resource-Policy same-origin`, r.h.get('cross-origin-resource-policy') === 'same-origin');
  comprobar(`${nombre}: Cache-Control no-store`, r.h.get('cache-control') === 'no-store');
  comprobar(`${nombre}: sin X-Powered-By`, !r.h.has('x-powered-by'));
}

let fallo = null;
try {
  await esperarServicio();
  const docs = await (await fetch(`${BASE}/docs-json`)).json();
  // La primera entidad: la ruta del listado (sin {id}).
  const ruta = Object.keys(docs.paths).find((p) => !p.includes('{'));
  const valido = await token();

  // 1. Guard de Keycloak
  const sinToken = await pedir(ruta);
  comprobar('Sin token: 401', sinToken.estado === 401, String(sinToken.estado));
  comprobar('Sin token: WWW-Authenticate Bearer', sinToken.h.get('www-authenticate') === 'Bearer');
  comprobar('Sin token: cuerpo {statusCode, message, error}', formatoDeError(sinToken), sinToken.texto);
  cabecerasDeApi('Respuesta 401', sinToken);

  const casos = [
    ['Token firmado con otra clave: 401', await token({ clave: otrasClaves.privateKey })],
    ['Token para otra audiencia: 401', await token({ audiencia: 'otro-api' })],
    ['Token vencido: 401', await token({ vence: ahora() - 60 })],
    ['Token sin firma (alg=none): 401', tokenSinFirma],
    ['Token mal formado: 401', 'esto.no.es-un-jwt'],
  ];
  for (const [nombre, t] of casos) {
    const r = await pedir(ruta, { token: t });
    comprobar(nombre, r.estado === 401, String(r.estado));
  }

  const conToken = await pedir(ruta, { token: valido });
  comprobar('Token válido de Keycloak: 200', conToken.estado === 200, `${conToken.estado} ${conToken.texto.slice(0, 120)}`);
  cabecerasDeApi('Respuesta 200', conToken);

  // 2. ValidationPipe y lectura del cuerpo
  const extra = await pedir(ruta, { metodo: 'POST', token: valido, cuerpo: JSON.stringify({ esAdmin: true }) });
  comprobar('Propiedad no declarada (esAdmin): 400', extra.estado === 400 && extra.texto.includes('esAdmin should not exist'), extra.texto.slice(0, 120));

  const malformado = await pedir(ruta, { metodo: 'POST', token: valido, cuerpo: '{"total": <script>alert(1)</script>' });
  comprobar('JSON mal formado: 400 sin repetir lo recibido', malformado.estado === 400 && !malformado.texto.includes('<script>'), malformado.texto);

  const texto = await pedir(ruta, { metodo: 'POST', token: valido, cuerpo: 'a=1', tipo: 'application/x-www-form-urlencoded' });
  comprobar('Cuerpo que no es JSON (formulario): 415', texto.estado === 415 && formatoDeError(texto), texto.texto);

  const grande = await pedir(ruta, { metodo: 'POST', token: valido, cuerpo: JSON.stringify({ x: 'a'.repeat(200_000) }) });
  comprobar('Cuerpo de 200 kB: 413', grande.estado === 413 && formatoDeError(grande), grande.texto);

  // 3. Filtro de errores
  const inexistente = await pedir('/api/no-existe%3Cb%3E', { token: valido });
  comprobar('Ruta inexistente: 404 sin repetir la ruta', inexistente.estado === 404 && !inexistente.texto.includes('no-existe'), inexistente.texto);
  comprobar('Errores con el mismo formato', [malformado, inexistente].every(formatoDeError));

  // 4. Swagger UI
  const pagina = await fetch(`${BASE}/docs`);
  const cspDocs = pagina.headers.get('content-security-policy') ?? '';
  comprobar('/docs: 200', pagina.status === 200);
  comprobar("/docs: CSP con script-src 'self' y frame-ancestors 'none'",
    cspDocs.includes("script-src 'self'") && cspDocs.includes("frame-ancestors 'none'") && !cspDocs.includes('unsafe-eval'), cspDocs);
  comprobar('/docs: X-Content-Type-Options nosniff y sin X-Powered-By',
    pagina.headers.get('x-content-type-options') === 'nosniff' && !pagina.headers.has('x-powered-by'));

  // El registro no debe contener ningún token.
  comprobar('El registro del servicio no contiene tokens', !registro.includes(valido.slice(0, 40)));
} catch (error) {
  fallo = error;
} finally {
  proceso.kill();
  jwks.close();
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
console.log(`\n${resultados.length - fallidas} de ${resultados.length} comprobaciones correctas (servicio ${servicio}).`);
process.exit(fallidas ? 1 : 0);
