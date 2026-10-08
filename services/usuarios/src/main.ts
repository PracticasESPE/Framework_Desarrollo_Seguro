import 'dotenv/config';
import { ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { UsuariosModule } from './usuarios.module';

async function bootstrap(): Promise<void> {
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

  const config = new DocumentBuilder()
    .setTitle('Servicio de usuarios')
    .setDescription(
      'Microservicio de referencia del framework de desarrollo seguro',
    )
    .setVersion('1.0')
    .build();
  SwaggerModule.setup('docs', app, SwaggerModule.createDocument(app, config));

  await app.listen(process.env.PORT ?? 3000);
}

void bootstrap();
