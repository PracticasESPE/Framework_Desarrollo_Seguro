import {
  ExecutionContext,
  InternalServerErrorException,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { createServer, Server } from 'node:http';
import { AddressInfo } from 'node:net';
import {
  createRemoteJWKSet,
  exportJWK,
  generateKeyPair,
  KeyLike,
  SignJWT,
} from 'jose';
import {
  JwtAuthGuard,
  OpcionesJwt,
  SolicitudAutenticada,
  validarConfiguracionJwt,
} from './jwt-auth.guard';

const EMISOR = 'http://localhost:8081/realms/framework';
const AUDIENCIA = 'usuarios-api';

function contexto(autorizacion?: string): {
  ctx: ExecutionContext;
  req: SolicitudAutenticada;
} {
  const req: SolicitudAutenticada = {
    headers: autorizacion ? { authorization: autorizacion } : {},
  };
  const ctx = {
    switchToHttp: () => ({ getRequest: () => req }),
  } as unknown as ExecutionContext;
  return { ctx, req };
}

/** Servidor HTTP local que imita el endpoint de claves (JWKS) de Keycloak. */
async function servidorJwks(
  estado: number,
  cuerpo: unknown,
): Promise<{ url: URL; cerrar: () => Promise<void> }> {
  const servidor: Server = createServer((_req, res) => {
    res.writeHead(estado, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(cuerpo));
  });
  await new Promise<void>((listo) =>
    servidor.listen(0, '127.0.0.1', () => listo()),
  );
  const { port } = servidor.address() as AddressInfo;
  return {
    url: new URL(`http://127.0.0.1:${port}/certs`),
    cerrar: () => new Promise<void>((listo) => servidor.close(() => listo())),
  };
}

describe('JwtAuthGuard', () => {
  let privada: KeyLike;
  let otraPrivada: KeyLike;
  let opciones: OpcionesJwt;

  const firmar = (
    claves: Partial<{
      iss: string;
      aud: string;
      exp: string | number;
      key: KeyLike;
      kid: string;
    }> = {},
  ) =>
    new SignJWT({ preferred_username: 'ana' })
      .setProtectedHeader({ alg: 'RS256', kid: claves.kid })
      .setSubject('usuario-1')
      .setIssuer(claves.iss ?? EMISOR)
      .setAudience(claves.aud ?? AUDIENCIA)
      .setIssuedAt()
      .setExpirationTime(claves.exp ?? '5m')
      .sign(claves.key ?? privada);

  beforeAll(async () => {
    const par = await generateKeyPair('RS256');
    const otro = await generateKeyPair('RS256');
    privada = par.privateKey;
    otraPrivada = otro.privateKey;
    opciones = {
      emisor: EMISOR,
      audiencia: AUDIENCIA,
      claves: () => Promise.resolve(par.publicKey),
    };
  });

  it('deja pasar un token válido y expone los datos del usuario', async () => {
    const { ctx, req } = contexto(`Bearer ${await firmar()}`);
    await expect(new JwtAuthGuard(opciones).canActivate(ctx)).resolves.toBe(
      true,
    );
    expect(req.user?.sub).toBe('usuario-1');
  });

  it.each([
    ['sin cabecera', undefined],
    ['esquema Basic', 'Basic YW5hOjEyMw=='],
    ['Bearer sin token', 'Bearer '],
    ['token con partes de más', 'Bearer a b'],
    ['token que no es JWT', 'Bearer abc'],
  ])('rechaza con 401: %s', async (_nombre, cabecera) => {
    const { ctx } = contexto(cabecera);
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza un token vencido', async () => {
    const { ctx } = contexto(
      `Bearer ${await firmar({ exp: Math.floor(Date.now() / 1000) - 60 })}`,
    );
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza un emisor distinto', async () => {
    const { ctx } = contexto(
      `Bearer ${await firmar({ iss: 'http://otro/realms/x' })}`,
    );
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza una audiencia distinta', async () => {
    const { ctx } = contexto(`Bearer ${await firmar({ aud: 'otra-api' })}`);
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza un token firmado con otra clave', async () => {
    const { ctx } = contexto(`Bearer ${await firmar({ key: otraPrivada })}`);
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza un token sin firma (alg=none)', async () => {
    const b64 = (o: object) =>
      Buffer.from(JSON.stringify(o)).toString('base64url');
    const sinFirma = `${b64({ alg: 'none', typ: 'JWT' })}.${b64({ sub: 'x', iss: EMISOR, aud: AUDIENCIA })}.`;
    const { ctx } = contexto(`Bearer ${sinFirma}`);
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('rechaza HS256 aunque lo firmen con la clave pública (confusión de algoritmo)', async () => {
    const publica = await exportJWK((await generateKeyPair('RS256')).publicKey);
    const token = await new SignJWT({})
      .setProtectedHeader({ alg: 'HS256' })
      .setIssuer(EMISOR)
      .setAudience(AUDIENCIA)
      .setExpirationTime('5m')
      .sign(new TextEncoder().encode(JSON.stringify(publica)));
    const { ctx } = contexto(`Bearer ${token}`);
    await expect(
      new JwtAuthGuard(opciones).canActivate(ctx),
    ).rejects.toBeInstanceOf(UnauthorizedException);
  });

  it('responde 503 si no se pueden obtener las claves de Keycloak', async () => {
    const caido: OpcionesJwt = {
      ...opciones,
      claves: () => Promise.reject(new TypeError('fetch failed')),
    };
    const { ctx } = contexto(`Bearer ${await firmar()}`);
    await expect(
      new JwtAuthGuard(caido).canActivate(ctx),
    ).rejects.toBeInstanceOf(ServiceUnavailableException);
  });

  it('responde 503 (no 401) si Keycloak contesta con un error HTTP', async () => {
    const jwks = await servidorJwks(502, { error: 'bad gateway' });
    try {
      const guard = new JwtAuthGuard({
        ...opciones,
        claves: createRemoteJWKSet(jwks.url),
      });
      const { ctx } = contexto(`Bearer ${await firmar({ kid: 'k1' })}`);
      await expect(guard.canActivate(ctx)).rejects.toBeInstanceOf(
        ServiceUnavailableException,
      );
    } finally {
      await jwks.cerrar();
    }
  });

  it('rechaza con 401 un token cuya clave no está en el JWKS de Keycloak', async () => {
    const publica = await exportJWK((await generateKeyPair('RS256')).publicKey);
    const jwks = await servidorJwks(200, {
      keys: [{ ...publica, kid: 'otra-clave', alg: 'RS256', use: 'sig' }],
    });
    try {
      const guard = new JwtAuthGuard({
        ...opciones,
        claves: createRemoteJWKSet(jwks.url),
      });
      const { ctx } = contexto(`Bearer ${await firmar({ kid: 'k1' })}`);
      await expect(guard.canActivate(ctx)).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
    } finally {
      await jwks.cerrar();
    }
  });

  it('cierra el acceso (500) si falta la configuración', async () => {
    const guardado = { ...process.env };
    delete process.env.KEYCLOAK_ISSUER;
    delete process.env.KEYCLOAK_AUDIENCE;
    try {
      const { ctx } = contexto(`Bearer ${await firmar()}`);
      await expect(new JwtAuthGuard().canActivate(ctx)).rejects.toBeInstanceOf(
        InternalServerErrorException,
      );
    } finally {
      process.env = guardado;
    }
  });

  it('impide arrancar el servicio sin configuración de seguridad', () => {
    expect(() => validarConfiguracionJwt({})).toThrow(/KEYCLOAK_ISSUER/);
    expect(() =>
      validarConfiguracionJwt({
        KEYCLOAK_ISSUER: EMISOR,
        KEYCLOAK_AUDIENCE: AUDIENCIA,
      }),
    ).not.toThrow();
  });
});
