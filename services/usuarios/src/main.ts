import 'dotenv/config';
import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { validarConfiguracionJwt } from './auth/jwt-auth.guard';
import { configurarSwagger } from './openapi/configuracion';
import { UsuariosModule } from './usuarios.module';

async function bootstrap(): Promise<void> {
  // Sin emisor y audiencia de Keycloak el servicio no arranca (falla cerrado).
  validarConfiguracionJwt();
  const app = await NestFactory.create(UsuariosModule);

  // Coincide con la ruta /api/usuarios que usará el gateway Traefik (01/12).
  app.setGlobalPrefix('api');

  // Lista blanca: rechaza propiedades que el DTO no declara.
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  // Swagger en /docs con el mismo contrato que analiza el Gate 2 (Spectral).
  configurarSwagger(app);

  await app.listen(process.env.PORT ?? 3000);
}

void bootstrap();
