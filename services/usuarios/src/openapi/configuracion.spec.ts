import { INestApplication } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { OpenAPIObject } from '@nestjs/swagger';
import { PrismaService } from '../prisma.service';
import { UsuariosModule } from '../usuarios.module';
import { MAXIMO_POR_LISTADO } from '../usuarios.service';
import { configurarSwagger, crearDocumentoOpenApi } from './configuracion';

interface Esquema {
  type?: string;
  maxLength?: number;
  maxItems?: number;
  properties?: Record<string, Esquema>;
}

describe('Contrato OpenAPI (Gate 2)', () => {
  let app: INestApplication;
  let documento: OpenAPIObject;

  beforeAll(async () => {
    const modulo = await Test.createTestingModule({ imports: [UsuariosModule] })
      .overrideProvider(PrismaService)
      .useValue({})
      .compile();
    app = modulo.createNestApplication();
    app.setGlobalPrefix('api');
    documento = crearDocumentoOpenApi(app);
  });

  afterAll(async () => {
    await app.close();
  });

  it('usa versión semántica y un servidor interno', () => {
    expect(documento.info.version).toMatch(/^\d+\.\d+\.\d+$/);
    expect(documento.servers).toEqual([
      expect.objectContaining({ 'x-internal': true }),
    ]);
  });

  it('cuelga todas las rutas de /api/', () => {
    for (const ruta of Object.keys(documento.paths)) {
      expect(ruta.startsWith('/api/')).toBe(true);
    }
  });

  it('limita el listado al mismo máximo que el servicio', () => {
    const contenido = documento.paths['/api/usuarios'].get?.responses[
      '200'
    ] as {
      content: Record<string, { schema: Esquema }>;
    };
    expect(contenido.content['application/json'].schema.maxItems).toBe(
      MAXIMO_POR_LISTADO,
    );
  });

  it('declara maxLength en todas las cadenas de los esquemas', () => {
    const esquemas = documento.components?.schemas as Record<string, Esquema>;
    const sinLimite: string[] = [];
    for (const [nombre, esquema] of Object.entries(esquemas)) {
      for (const [campo, propiedad] of Object.entries(
        esquema.properties ?? {},
      )) {
        if (propiedad.type === 'string' && propiedad.maxLength === undefined) {
          sinLimite.push(`${nombre}.${campo}`);
        }
      }
    }
    expect(sinLimite).toEqual([]);
  });

  it('configurarSwagger publica el mismo contrato', () => {
    expect(configurarSwagger(app).info.version).toBe(documento.info.version);
  });
});
