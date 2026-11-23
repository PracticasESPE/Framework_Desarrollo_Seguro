import 'dotenv/config';
import { Logger } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import type { NestExpressApplication } from '@nestjs/platform-express';
import { ConfiguracionInvalida, leerEntorno } from './configuracion/entorno';
import { configurarSwagger } from './openapi/configuracion';
import { configurarHttp } from './seguridad/http';
import { CatalogoModule } from './catalogo.module';

async function bootstrap(): Promise<void> {
  // Toda la configuración se valida antes de crear nada: si falta un valor o no es válido, el
  // servicio no arranca (falla cerrado). Sin NODE_ENV se asume producción.
  const entorno = leerEntorno(process.env, 3002);

  // Sin el lector por defecto: configurarHttp solo acepta JSON y con límite de tamaño.
  const app = await NestFactory.create<NestExpressApplication>(CatalogoModule, {
    bodyParser: false,
    logger: entorno.registro,
  });

  // Helmet, sin X-Powered-By y solo JSON, antes de cualquier ruta (también de /docs).
  // El guard de Keycloak, el ValidationPipe y el filtro de errores los registra el módulo.
  configurarHttp(app);

  // Coincide con la ruta /api/catalogo que usará el gateway Traefik.
  app.setGlobalPrefix('api');

  // Swagger en /docs, con el mismo contrato que analiza el Gate 2 (Spectral), solo fuera de
  // producción: allí el contrato lo publica el pipeline y la API no muestra su propio mapa.
  if (entorno.documentacion) {
    configurarSwagger(app);
  }

  // Cierra las conexiones con la base al recibir SIGTERM (docker stop).
  app.enableShutdownHooks();

  await app.listen(entorno.puerto);
  new Logger('Arranque').log(
    `Servicio catalogo en el puerto ${entorno.puerto} (entorno ${entorno.nombre}, /docs ${entorno.documentacion ? 'activo' : 'desactivado'})`,
  );
}

bootstrap().catch((error: unknown) => {
  if (error instanceof ConfiguracionInvalida) {
    // El mensaje nombra las variables (nunca sus valores); la traza no aporta nada.
    console.error(`El servicio no arrancó. ${error.message}`);
  } else {
    new Logger('Arranque').error('El servicio no arrancó', (error as Error).stack);
  }
  process.exit(1);
});
