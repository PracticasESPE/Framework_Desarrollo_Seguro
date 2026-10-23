// Prueba de la protección JWT del servicio de referencia:
//   1) petición sin token                -> debe responder 401
//   2) petición con un token manipulado  -> debe responder 401
//   3) petición con un token de Keycloak -> debe responder 200
// Uso (desde la raíz del repo, con el servicio y Keycloak levantados):
//   node --env-file=.env scripts/probar-jwt.mjs
// No imprime el token ni la contraseña: la salida se puede capturar sin riesgo.
const API = process.env.API_URL ?? 'http://localhost:3000/api/usuarios';
const KEYCLOAK = process.env.KEYCLOAK_URL ?? `http://localhost:${process.env.KEYCLOAK_PORT ?? 8081}`;
const REALM = process.env.KEYCLOAK_REALM ?? 'framework';
const USUARIO = process.env.KEYCLOAK_PRUEBA_USUARIO ?? 'ana';
const CLAVE = process.env.KEYCLOAK_PRUEBA_PASSWORD;

if (!CLAVE) {
  console.error('Falta KEYCLOAK_PRUEBA_PASSWORD (ejecuta: node --env-file=.env scripts/probar-jwt.mjs)');
  process.exit(2);
}

const resultados = [];
function registrar(nombre, esperado, obtenido) {
  const ok = esperado === obtenido;
  resultados.push(ok);
  console.log(`${ok ? 'OK   ' : 'FALLO'}  ${nombre.padEnd(34)} esperado ${esperado}  obtenido ${obtenido}`);
}

async function estado(cabeceras = {}) {
  const r = await fetch(API, { headers: cabeceras });
  return r.status;
}

console.log(`Servicio: ${API}`);
console.log(`Keycloak: ${KEYCLOAK}/realms/${REALM}\n`);

registrar('GET sin token', 401, await estado());

const r = await fetch(`${KEYCLOAK}/realms/${REALM}/protocol/openid-connect/token`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({ grant_type: 'password', client_id: 'usuarios-cli', username: USUARIO, password: CLAVE }),
});
if (!r.ok) {
  console.error(`\nKeycloak no entregó el token (HTTP ${r.status}): ${(await r.text()).slice(0, 200)}`);
  process.exit(1);
}
const { access_token: token } = await r.json();
const datos = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString());
console.log(
  `Token recibido: usuario=${datos.preferred_username} aud=${JSON.stringify(datos.aud)} ` +
    `vence en ${Math.round((datos.exp * 1000 - Date.now()) / 60000)} min\n`,
);

const manipulado = token.slice(0, -4) + (token.endsWith('AAAA') ? 'BBBB' : 'AAAA');
registrar('GET con token manipulado', 401, await estado({ Authorization: `Bearer ${manipulado}` }));
registrar('GET con token de Keycloak', 200, await estado({ Authorization: `Bearer ${token}` }));

console.log(`\n${resultados.filter(Boolean).length}/${resultados.length} comprobaciones correctas`);
process.exit(resultados.every(Boolean) ? 0 : 1);
