/**
 * Escribe el contrato OpenAPI del servicio en un archivo, sin base de datos ni red.
 * Uso (después de `npm run build`): npm run openapi -- <destino.json>
 * Lo usa el pipeline (Gate 2, Spectral); la imagen de producción no lo necesita.
 */
import { Test } from '@nestjs/testing';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { PrismaService } from '../prisma.service';
import { CatalogoModule } from '../catalogo.module';
import { crearDocumentoOpenApi } from './configuracion';

async function generar(destino: string): Promise<void> {
  // PrismaService se sustituye para no necesitar DATABASE_URL ni conectarse a la base.
  const modulo = await Test.createTestingModule({ imports: [CatalogoModule] })
    .overrideProvider(PrismaService)
    .useValue({})
    .compile();
  const app = modulo.createNestApplication();
  app.setGlobalPrefix('api');
  const documento = crearDocumentoOpenApi(app);
  // La ruta la fija el pipeline, no un usuario.
  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, JSON.stringify(documento, null, 2), 'utf-8');
  await app.close();
  console.log(`OpenAPI escrito en ${destino}`);
}

const destino = resolve(process.argv[2] ?? 'openapi/catalogo.json');
generar(destino).catch((error: unknown) => {
  console.error('No se pudo generar el OpenAPI:', error);
  process.exit(1);
});
