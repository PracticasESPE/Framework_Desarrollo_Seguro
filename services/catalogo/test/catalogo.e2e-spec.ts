import type { NestExpressApplication } from '@nestjs/platform-express';
import { Test } from '@nestjs/testing';
import { exportJWK, generateKeyPair, SignJWT } from 'jose';
import { createServer } from 'node:http';
import type { Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import request from 'supertest';
import { PrismaService } from '../src/prisma.service';
import { configurarHttp } from '../src/seguridad/http';
import { TOKEN_INVALIDO } from '../src/seguridad/jwt-auth.guard';
import { CatalogoModule } from '../src/catalogo.module';
import { ProductoService } from '../src/producto.service';
import { CategoriaService } from '../src/categoria.service';
import { FotoService } from '../src/foto.service';

/*
 * Pruebas de la API de catalogo, generadas por la plantilla: el módulo real (guard de
 * Keycloak, ValidationPipe, filtro de errores y controladores) con la misma capa HTTP que main.ts.
 * No necesitan base de datos ni Keycloak: Prisma es un doble y la prueba crea sus propias claves
 * RSA y publica el JWKS en 127.0.0.1. Las reglas de negocio del LLM se sustituyen: aquí se prueba
 * el contrato de la API, no las reglas.
 */

type Reglas = Record<
  'reglasAlCrear' | 'reglasAlActualizar' | 'reglasAlEliminar',
  (...argumentos: unknown[]) => Promise<void>
>;
type ClavePrivada = Parameters<SignJWT['sign']>[0];

// Prisma devuelve los decimales como objetos Decimal; el servicio solo usa toNumber().
const decimal = (valor: number) => ({ toNumber: () => valor });

const AUDIENCIA = 'catalogo-api';
const ID = '7d9f3c2a-1b4e-4f6a-8c5d-2e3f4a5b6c7d';
const CREADO_EN = '2026-01-15T12:00:00.000Z';
const ACTUALIZADO_EN = '2026-01-16T12:00:00.000Z';

const prisma = {
  $transaction: jest.fn(),
  producto: {
    count: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  categoria: {
    count: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
  foto: {
    count: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
};

let app: NestExpressApplication;
let jwks: Server;
let emisor: string;
let clavePrivada: ClavePrivada;
let token: string;
const entornoOriginal = { ...process.env };

function firmar({
  audiencia = AUDIENCIA,
  clave = clavePrivada,
  vence = '5m' as string | number,
} = {}): Promise<string> {
  return new SignJWT({ preferred_username: 'ana' })
    .setProtectedHeader({ alg: 'RS256', kid: 'pruebas' })
    .setIssuer(emisor)
    .setAudience(audiencia)
    .setSubject('usuario-de-prueba')
    .setIssuedAt()
    .setExpirationTime(vence)
    .sign(clave);
}

const api = () => request(app.getHttpServer());

beforeAll(async () => {
  // Keycloak simulado: un par de claves RSA y su JWKS en un puerto libre de 127.0.0.1.
  const claves = await generateKeyPair('RS256');
  clavePrivada = claves.privateKey;
  const jwk = { ...(await exportJWK(claves.publicKey)), kid: 'pruebas', alg: 'RS256', use: 'sig' };
  jwks = createServer((_peticion, respuesta) => {
    respuesta.setHeader('Content-Type', 'application/json');
    respuesta.end(JSON.stringify({ keys: [jwk] }));
  });
  await new Promise<void>((listo) => jwks.listen(0, '127.0.0.1', listo));
  emisor = `http://127.0.0.1:${(jwks.address() as AddressInfo).port}/realms/pruebas`;
  process.env.KEYCLOAK_ISSUER = emisor;
  process.env.KEYCLOAK_AUDIENCE = AUDIENCIA;
  process.env.KEYCLOAK_JWKS_URI = `${emisor}/protocol/openid-connect/certs`;
  token = await firmar();

  const modulo = await Test.createTestingModule({ imports: [CatalogoModule] })
    .overrideProvider(PrismaService)
    .useValue(prisma)
    .compile();
  app = modulo.createNestApplication<NestExpressApplication>({
    bodyParser: false,
    logger: false,
  });
  configurarHttp(app);
  app.setGlobalPrefix('api');
  await app.init();
});

afterAll(async () => {
  await app?.close();
  jwks?.close();
  process.env = entornoOriginal;
});

beforeEach(() => {
  jest.resetAllMocks();
  prisma.$transaction.mockImplementation((consultas: Promise<unknown>[]) =>
    Promise.all(consultas),
  );
  const reglasProducto = app.get(ProductoService) as unknown as Reglas;
  jest.spyOn(reglasProducto, 'reglasAlCrear').mockResolvedValue(undefined);
  jest.spyOn(reglasProducto, 'reglasAlActualizar').mockResolvedValue(undefined);
  jest.spyOn(reglasProducto, 'reglasAlEliminar').mockResolvedValue(undefined);
  const reglasCategoria = app.get(CategoriaService) as unknown as Reglas;
  jest.spyOn(reglasCategoria, 'reglasAlCrear').mockResolvedValue(undefined);
  jest.spyOn(reglasCategoria, 'reglasAlActualizar').mockResolvedValue(undefined);
  jest.spyOn(reglasCategoria, 'reglasAlEliminar').mockResolvedValue(undefined);
  const reglasFoto = app.get(FotoService) as unknown as Reglas;
  jest.spyOn(reglasFoto, 'reglasAlCrear').mockResolvedValue(undefined);
  jest.spyOn(reglasFoto, 'reglasAlActualizar').mockResolvedValue(undefined);
  jest.spyOn(reglasFoto, 'reglasAlEliminar').mockResolvedValue(undefined);
});

describe('Controles transversales de catalogo', () => {
  const RUTA = '/api/catalogo/producto';

  it('sin token responde 401 con WWW-Authenticate y las cabeceras de seguridad', async () => {
    const r = await api().get(RUTA);

    expect(r.status).toBe(401);
    expect(r.body).toEqual({ statusCode: 401, message: TOKEN_INVALIDO, error: 'Unauthorized' });
    expect(r.headers['www-authenticate']).toBe('Bearer');
    expect(r.headers['content-security-policy']).toContain("default-src 'none'");
    expect(r.headers['x-content-type-options']).toBe('nosniff');
    expect(r.headers['x-frame-options']).toBe('DENY');
    expect(r.headers['cache-control']).toBe('no-store');
    expect(r.headers['x-powered-by']).toBeUndefined();
  });

  const b64 = (objeto: object) => Buffer.from(JSON.stringify(objeto)).toString('base64url');
  const ahora = () => Math.floor(Date.now() / 1000);

  it.each([
    ['para otra audiencia', () => firmar({ audiencia: 'otro-api' })],
    ['vencido', () => firmar({ vence: ahora() - 60 })],
    [
      'firmado con otra clave',
      async () => firmar({ clave: (await generateKeyPair('RS256')).privateKey }),
    ],
    [
      'sin firma (alg=none)',
      () =>
        Promise.resolve(
          `${b64({ alg: 'none', typ: 'JWT' })}.${b64({ iss: emisor, aud: AUDIENCIA, exp: ahora() + 300 })}.`,
        ),
    ],
  ])('rechaza un token %s (401)', async (_caso, crear) => {
    const r = await api().get(RUTA).auth(await crear(), { type: 'bearer' });

    expect(r.status).toBe(401);
  });

  it('una ruta inexistente responde 404 sin repetir la ruta', async () => {
    const r = await api().get('/api/ruta-inexistente').auth(token, { type: 'bearer' });

    expect(r.status).toBe(404);
    expect(r.text).not.toContain('ruta-inexistente');
  });

  it('un cuerpo que no es JSON responde 415', async () => {
    const r = await api()
      .post(RUTA)
      .auth(token, { type: 'bearer' })
      .type('form')
      .send('a=1');

    expect(r.status).toBe(415);
  });
});

describe('Producto: /api/catalogo/producto', () => {
  const RUTA = '/api/catalogo/producto';
  const tabla = prisma.producto;
  const entrada = {
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
    precio: 0.0,
    unidadesDisponibles: 0,
    categoriaId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    retirado: true,
  };
  const fila = {
    id: ID,
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
    precio: decimal(0.0),
    unidadesDisponibles: 0,
    categoriaId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    retirado: true,
    creadoEn: new Date(CREADO_EN),
    actualizadoEn: new Date(ACTUALIZADO_EN),
  };
  const respuesta = {
    id: ID,
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
    precio: 0.0,
    unidadesDisponibles: 0,
    categoriaId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    retirado: true,
    creadoEn: CREADO_EN,
    actualizadoEn: ACTUALIZADO_EN,
  };

  it('crea un registro con un cuerpo válido (201)', async () => {
    tabla.create.mockResolvedValue(fila);

    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(201);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza una propiedad no declarada sin llegar a la base (400)', async () => {
    const r = await api()
      .post(RUTA)
      .auth(token, { type: 'bearer' })
      .send({ ...entrada, esAdmin: true });

    expect(r.status).toBe(400);
    expect(r.body.message).toContain('property esAdmin should not exist');
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('rechaza un cuerpo sin los campos obligatorios (400)', async () => {
    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send({});

    expect(r.status).toBe(400);
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('lista con la paginación por defecto (200)', async () => {
    tabla.count.mockResolvedValue(1);
    tabla.findMany.mockResolvedValue([fila]);

    const r = await api().get(RUTA).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual({ elementos: [respuesta], total: 1, pagina: 1, tamano: 20 });
  });

  it('rechaza una página de más de 100 elementos (400)', async () => {
    const r = await api().get(`${RUTA}?tamano=101`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findMany).not.toHaveBeenCalled();
  });

  it('devuelve un registro por su id (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza un id que no es un UUID (400)', async () => {
    const r = await api().get(`${RUTA}/123`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findUnique).not.toHaveBeenCalled();
  });

  it('responde 404 si el registro no existe', async () => {
    tabla.findUnique.mockResolvedValue(null);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(404);
  });

  it('actualiza un registro (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.update.mockResolvedValue(fila);

    const r = await api().patch(`${RUTA}/${ID}`).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('elimina un registro (204)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.delete.mockResolvedValue(fila);

    const r = await api().delete(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(204);
    expect(tabla.delete).toHaveBeenCalledWith({ where: { id: ID } });
  });
});

describe('Categoria: /api/catalogo/categoria', () => {
  const RUTA = '/api/catalogo/categoria';
  const tabla = prisma.categoria;
  const entrada = {
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
  };
  const fila = {
    id: ID,
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
    creadoEn: new Date(CREADO_EN),
    actualizadoEn: new Date(ACTUALIZADO_EN),
  };
  const respuesta = {
    id: ID,
    nombre: 'Texto de prueba',
    descripcion: 'Texto de prueba',
    creadoEn: CREADO_EN,
    actualizadoEn: ACTUALIZADO_EN,
  };

  it('crea un registro con un cuerpo válido (201)', async () => {
    tabla.create.mockResolvedValue(fila);

    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(201);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza una propiedad no declarada sin llegar a la base (400)', async () => {
    const r = await api()
      .post(RUTA)
      .auth(token, { type: 'bearer' })
      .send({ ...entrada, esAdmin: true });

    expect(r.status).toBe(400);
    expect(r.body.message).toContain('property esAdmin should not exist');
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('rechaza un cuerpo sin los campos obligatorios (400)', async () => {
    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send({});

    expect(r.status).toBe(400);
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('lista con la paginación por defecto (200)', async () => {
    tabla.count.mockResolvedValue(1);
    tabla.findMany.mockResolvedValue([fila]);

    const r = await api().get(RUTA).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual({ elementos: [respuesta], total: 1, pagina: 1, tamano: 20 });
  });

  it('rechaza una página de más de 100 elementos (400)', async () => {
    const r = await api().get(`${RUTA}?tamano=101`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findMany).not.toHaveBeenCalled();
  });

  it('devuelve un registro por su id (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza un id que no es un UUID (400)', async () => {
    const r = await api().get(`${RUTA}/123`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findUnique).not.toHaveBeenCalled();
  });

  it('responde 404 si el registro no existe', async () => {
    tabla.findUnique.mockResolvedValue(null);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(404);
  });

  it('actualiza un registro (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.update.mockResolvedValue(fila);

    const r = await api().patch(`${RUTA}/${ID}`).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('elimina un registro (204)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.delete.mockResolvedValue(fila);

    const r = await api().delete(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(204);
    expect(tabla.delete).toHaveBeenCalledWith({ where: { id: ID } });
  });
});

describe('Foto: /api/catalogo/foto', () => {
  const RUTA = '/api/catalogo/foto';
  const tabla = prisma.foto;
  const entrada = {
    url: 'Texto de prueba',
    productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    tipo: 'jpg',
    orden: 1,
  };
  const fila = {
    id: ID,
    url: 'Texto de prueba',
    productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    tipo: 'jpg',
    orden: 1,
    creadoEn: new Date(CREADO_EN),
    actualizadoEn: new Date(ACTUALIZADO_EN),
  };
  const respuesta = {
    id: ID,
    url: 'Texto de prueba',
    productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
    tipo: 'jpg',
    orden: 1,
    creadoEn: CREADO_EN,
    actualizadoEn: ACTUALIZADO_EN,
  };

  it('crea un registro con un cuerpo válido (201)', async () => {
    tabla.create.mockResolvedValue(fila);

    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(201);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza una propiedad no declarada sin llegar a la base (400)', async () => {
    const r = await api()
      .post(RUTA)
      .auth(token, { type: 'bearer' })
      .send({ ...entrada, esAdmin: true });

    expect(r.status).toBe(400);
    expect(r.body.message).toContain('property esAdmin should not exist');
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('rechaza un cuerpo sin los campos obligatorios (400)', async () => {
    const r = await api().post(RUTA).auth(token, { type: 'bearer' }).send({});

    expect(r.status).toBe(400);
    expect(tabla.create).not.toHaveBeenCalled();
  });

  it('lista con la paginación por defecto (200)', async () => {
    tabla.count.mockResolvedValue(1);
    tabla.findMany.mockResolvedValue([fila]);

    const r = await api().get(RUTA).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual({ elementos: [respuesta], total: 1, pagina: 1, tamano: 20 });
  });

  it('rechaza una página de más de 100 elementos (400)', async () => {
    const r = await api().get(`${RUTA}?tamano=101`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findMany).not.toHaveBeenCalled();
  });

  it('devuelve un registro por su id (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('rechaza un id que no es un UUID (400)', async () => {
    const r = await api().get(`${RUTA}/123`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(400);
    expect(tabla.findUnique).not.toHaveBeenCalled();
  });

  it('responde 404 si el registro no existe', async () => {
    tabla.findUnique.mockResolvedValue(null);

    const r = await api().get(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(404);
  });

  it('actualiza un registro (200)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.update.mockResolvedValue(fila);

    const r = await api().patch(`${RUTA}/${ID}`).auth(token, { type: 'bearer' }).send(entrada);

    expect(r.status).toBe(200);
    expect(r.body).toEqual(respuesta);
  });

  it('elimina un registro (204)', async () => {
    tabla.findUnique.mockResolvedValue(fila);
    tabla.delete.mockResolvedValue(fila);

    const r = await api().delete(`${RUTA}/${ID}`).auth(token, { type: 'bearer' });

    expect(r.status).toBe(204);
    expect(tabla.delete).toHaveBeenCalledWith({ where: { id: ID } });
  });
});
