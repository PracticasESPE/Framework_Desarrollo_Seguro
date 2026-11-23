import { INestApplication } from '@nestjs/common';
import { DocumentBuilder, OpenAPIObject, SwaggerModule } from '@nestjs/swagger';

/** Única fuente del contrato OpenAPI: la usan main.ts (/docs) y el generador del Gate 2. */
export function crearDocumentoOpenApi(app: INestApplication): OpenAPIObject {
  const config = new DocumentBuilder()
    .setTitle('Servicio catalogo')
    .setDescription(
      'Ofrece búsqueda y visualización de productos, permite a administradores crear, modificar y retirar productos con gestión de imágenes, y conserva la información de productos retirados en pedidos históricos, cumpliendo con requisitos de rendimiento de búsqueda.',
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
    .addTag('Producto', 'Producto del catálogo')
    .addTag('Categoria', 'Categoría de productos')
    .addTag('Foto', 'Imágenes asociadas a un producto')
    .addServer('https://catalogo.fw.local', 'Entorno local')
    .build();
  const documento = SwaggerModule.createDocument(app, config);
  // OWASP API9: cada servidor declara si es interno (el builder no admite extensiones).
  for (const servidor of documento.servers ?? []) {
    (servidor as unknown as Record<string, unknown>)['x-internal'] = true;
  }
  return documento;
}

/**
 * Publica la documentación interactiva en /docs con el mismo contrato que analiza el Gate 2,
 * salvo el servidor: «Try it out» envía las peticiones a la misma dirección desde la que se abre
 * /docs (localhost o Traefik), no a un nombre que quizá no resuelva en esa máquina.
 */
export function configurarSwagger(app: INestApplication): OpenAPIObject {
  const documento = crearDocumentoOpenApi(app);
  const servidor = { url: '/', description: 'Este mismo servicio', 'x-internal': true };
  SwaggerModule.setup('docs', app, { ...documento, servers: [servidor] });
  return documento;
}
