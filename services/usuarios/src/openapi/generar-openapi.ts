/**
 * Escribe el contrato OpenAPI del servicio en un archivo, sin base de datos ni red.
 * Uso (después de `npm run build`): node dist/openapi/generar-openapi.js <destino.json>
 * Solo lo usa el pipeline (Gate 2); la imagen de producción no lo incluye (ver Dockerfile).
 */
import { Test } from '@nestjs/testing';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { PrismaService } from '../prisma.service';
import { UsuariosModule } from '../usuarios.module';
import { crearDocumentoOpenApi } from './configuracion';

async function generar(destino: string): Promise<void> {
  // PrismaService se sustituye para no necesitar DATABASE_URL ni conectarse a la base.
  const modulo = await Test.createTestingModule({ imports: [UsuariosModule] })
    .overrideProvider(PrismaService)
    .useValue({})
    .compile();
  const app = modulo.createNestApplication();
  app.setGlobalPrefix('api');
  const documento = crearDocumentoOpenApi(app);
  // La ruta la fija el pipeline, no un usuario.
  // eslint-disable-next-line security/detect-non-literal-fs-filename
  mkdirSync(dirname(destino), { recursive: true });
  // eslint-disable-next-line security/detect-non-literal-fs-filename
  writeFileSync(destino, JSON.stringify(documento, null, 2), 'utf-8');
  await app.close();
  console.log(`OpenAPI escrito en ${destino}`);
}

const destino = resolve(process.argv[2] ?? 'salida/openapi/usuarios.json');
generar(destino).catch((error: unknown) => {
  console.error('No se pudo generar el OpenAPI:', error);
  process.exit(1);
});
