import { INestApplication } from '@nestjs/common';
import { DocumentBuilder, OpenAPIObject, SwaggerModule } from '@nestjs/swagger';

/** Única fuente del contrato OpenAPI: la usan main.ts (/docs) y el generador del Gate 2. */
export function crearDocumentoOpenApi(app: INestApplication): OpenAPIObject {
  const config = new DocumentBuilder()
    .setTitle('Servicio de usuarios')
    .setDescription(
      'Microservicio de referencia del framework de desarrollo seguro',
    )
    .setVersion('1.0.0')
    .addBearerAuth(
      {
        type: 'http',
        scheme: 'bearer',
        bearerFormat: 'JWT',
        description:
          'Token de acceso JWT emitido por Keycloak; se valida con las buenas prácticas de RFC8725 (firma RS256, emisor, audiencia y vencimiento).',
      },
      'bearer',
    )
    .addTag('usuarios', 'Gestión de usuarios')
    .addServer('https://usuarios.fw.local', 'Entorno local de referencia')
    .build();
  const documento = SwaggerModule.createDocument(app, config);
  // OWASP API9: cada servidor declara si es interno (el builder no admite extensiones).
  for (const servidor of documento.servers ?? []) {
    (servidor as unknown as Record<string, unknown>)['x-internal'] = true;
  }
  return documento;
}

/** Publica la documentación interactiva en /docs con el mismo contrato que analiza el Gate 2. */
export function configurarSwagger(app: INestApplication): OpenAPIObject {
  const documento = crearDocumentoOpenApi(app);
  SwaggerModule.setup('docs', app, documento);
  return documento;
}
