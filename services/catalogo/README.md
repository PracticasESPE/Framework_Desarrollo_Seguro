# Servicio catalogo

Ofrece búsqueda y visualización de productos, permite a administradores crear, modificar y retirar productos con gestión de imágenes, y conserva la información de productos retirados en pedidos históricos, cumpliendo con requisitos de rendimiento de búsqueda.

Generado por la plantilla `microservicio_nestjs` del Framework de Desarrollo Seguro a partir de
`arquitectura.json`. Base de datos propia: `catalogo_db`.

## Entidades

| Entidad | Tabla | Campos |
|---|---|---|
| `Producto` | `producto` | `nombre` (texto), `descripcion` (texto), `precio` (decimal), `unidadesDisponibles` (entero), `categoriaId` (referencia), `retirado` (booleano) |
| `Categoria` | `categoria` | `nombre` (texto), `descripcion` (texto, opcional) |
| `Foto` | `foto` | `url` (texto), `productoId` (referencia), `tipo` (enumeracion), `orden` (entero, opcional) |

Todas llevan además `id` (UUID), `creadoEn` y `actualizadoEn`.

## Rutas

Documentadas en Swagger, en `/docs`, solo fuera de producción (`NODE_ENV=development` o `test`).

| Entidad | Ruta | Operaciones |
|---|---|---|
| `Producto` | `/api/catalogo/producto` | `POST /`, `GET /` (paginado), `GET /:id`, `PATCH /:id`, `DELETE /:id` |
| `Categoria` | `/api/catalogo/categoria` | `POST /`, `GET /` (paginado), `GET /:id`, `PATCH /:id`, `DELETE /:id` |
| `Foto` | `/api/catalogo/foto` | `POST /`, `GET /` (paginado), `GET /:id`, `PATCH /:id`, `DELETE /:id` |

Los listados devuelven como mucho 100 registros por página (`?pagina=1&tamano=20`).

Todas las rutas exigen un token de acceso de Keycloak (`Authorization: Bearer <token>`) con la
audiencia `catalogo-api`. Los errores siempre tienen la forma `{statusCode, message, error}`.

## Estructura

| Archivo | Qué contiene |
|---|---|
| `prisma/schema.prisma` | Entidades y tipos de la base de datos |
| `src/catalogo.module.ts` | Módulo del servicio |
| `src/<entidad>.controller.ts` | Rutas de la entidad y su documentación de Swagger |
| `src/<entidad>.service.ts` | Acceso a la base y reglas de negocio (bloque `@framework:logica-negocio`) |
| `src/dto/crear-<entidad>.dto.ts` | Validación de la entrada (class-validator) y contrato OpenAPI |
| `src/dto/actualizar-<entidad>.dto.ts` | Los mismos campos, todos opcionales |
| `src/dto/<entidad>-respuesta.dto.ts`, `<entidad>-pagina.dto.ts` | Lo que devuelve la API |
| `src/openapi/` | Configuración de Swagger y generador del contrato (`npm run openapi`) |
| `src/comun/` | Utilidades que comparten los DTO, los servicios y los controladores |
| `src/seguridad/` | Guard de Keycloak, `ValidationPipe`, filtro de errores y cabeceras de seguridad (Helmet) |
| `src/configuracion/entorno.ts` | Lectura y validación de las variables de entorno |
| `src/**/*.spec.ts`, `test/` | Pruebas generadas (Jest) |
| `Dockerfile`, `.dockerignore` | Imagen de producción |

## Compilar

```bash
cp .env.example .env            # y cambiar la contraseña
npm ci                          # exactamente las versiones de package-lock.json
npm run prisma:generate
npm run format                  # formato de Prettier
npm run typecheck
npm run build
```

`.npmrc` desactiva los scripts de instalación de las dependencias (cadena de suministro): por eso
el cliente de Prisma se genera con `npm run prisma:generate`.

## Ejecutar

Con PostgreSQL en la dirección de `DATABASE_URL` y `KEYCLOAK_ISSUER` y `KEYCLOAK_AUDIENCE` en el
`.env` (sin ellas el servicio no arranca):

```bash
npm run prisma:push             # crea las tablas (en desarrollo; en producción, migraciones)
npm run start:prod              # http://localhost:3002/docs
```

Para el Gate 2, `npm run openapi -- openapi/catalogo.json` escribe el contrato sin necesitar
la base de datos.

## Configuración por entorno

`src/configuracion/entorno.ts` valida todas las variables al arrancar. Si falta alguna o no es
válida, el servicio no arranca y el error dice cuál, nunca su valor.

| Variable | Obligatoria | Qué es |
|---|---|---|
| `NODE_ENV` | No | `development`, `test` o `production`. Sin ella se asume `production` |
| `PORT` | No | Puerto HTTP, de 1024 a 65535 (por defecto, 3002) |
| `DATABASE_URL` | Sí | `postgresql://usuario:contraseña@servidor:5432/catalogo_db` |
| `KEYCLOAK_ISSUER` | Sí | URL del realm que emite los tokens |
| `KEYCLOAK_AUDIENCE` | Sí | Audiencia que deben llevar los tokens (`catalogo-api`) |
| `KEYCLOAK_JWKS_URI` | No | Claves públicas, si no están en la dirección estándar del emisor |

| | `development` | `test` | `production` |
|---|---|---|---|
| Swagger en `/docs` | Sí | Sí | No (404) |
| Registro | Todo, con depuración | Advertencias y errores | Sin depuración |
| Contraseña `CAMBIAR` de `.env.example` | Se admite | Se admite | Rechazada: no arranca |

## Pruebas

```bash
npm test                        # unitarias y de la API, sin base de datos ni Keycloak
npm run test:cov                # con cobertura (coverage/)
```

- `src/<entidad>.service.spec.ts`: el servicio de cada entidad con Prisma simulado (orden de las
  reglas de negocio, paginación y traducción de los errores de Prisma).
- `test/catalogo.e2e-spec.ts`: la API completa con sus controles (token, validación,
  cabeceras y errores) y las cinco operaciones de cada entidad.
- `src/configuracion/entorno.spec.ts`: la validación de la configuración.

Las pruebas sustituyen las reglas de negocio del bloque `@framework:logica-negocio`: comprueban lo
que genera la plantilla, que no cambia aunque cambien las reglas.

## Imagen

```bash
docker build -t catalogo:local .
docker run --rm -p 3002:3002 --read-only --cap-drop ALL \
  -e DATABASE_URL=... -e KEYCLOAK_ISSUER=... -e KEYCLOAK_AUDIENCE=catalogo-api catalogo:local
```

Tres etapas: compilación, dependencias de producción y una imagen final distroless (sin shell
ni npm) que corre con el usuario 65532 y `NODE_ENV=production`. Solo lleva el JavaScript compilado
y las dependencias de producción, y su `HEALTHCHECK` comprueba que el puerto responde.
