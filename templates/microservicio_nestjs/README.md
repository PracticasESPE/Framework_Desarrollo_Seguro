# Plantilla `microservicio_nestjs`

Plantilla [Copier](https://copier.readthedocs.io) de la fase 3 (plan técnico, 7.3). Genera el
esqueleto determinista de cada microservicio de `arquitectura.json`; el LLM solo completará la lógica
de negocio en los puntos que marque la plantilla.

| Parte | Issue | Qué añade | Estado |
|---|---|---|---|
| 1 | #61 | Módulo, entidades Prisma y DTO con class-validator | Lista |
| 2 | #63 | Servicio, controlador y decoradores de Swagger | Lista |
| 3 | #65 | Guard de Keycloak, ValidationPipe, Helmet y filtro de errores | Lista |
| 4 | #67 | Dockerfile, Jest base y configuración por entorno | Lista |

## Uso

```powershell
python -m uv run python -m orchestrator.cli servicio generar templates/microservicio_nestjs/ejemplos/pedidos.yml
```

Crea `salida/servicios/pedidos` (o la carpeta de `--destino`). Nunca escribe sobre un servicio que
ya existe. Para compilarlo y probarlo, desde esa carpeta:

```powershell
npm ci                           # las versiones exactas de package-lock.json
$env:DATABASE_URL = "postgresql://pedidos:CAMBIAR@localhost:5432/pedidos_db"
npm run prisma:generate
npm run typecheck
npm run build
npm test                         # pruebas generadas: sin base de datos ni Keycloak
docker build -t fw-pedidos:local .
```

El job `plantilla` del workflow hace lo mismo con el ejemplo en cada PR. Además genera su
contrato OpenAPI sin base de datos (`npm run openapi`), lo que comprueba que el módulo arranca;
ejecuta la prueba de los controles transversales con un PostgreSQL de servicio; pasa Hadolint por
el Dockerfile generado, y construye la imagen y la prueba como en producción (ver más abajo).

### Probarlo con una base de datos y ver Swagger

```powershell
docker run -d --rm --name pedidos-db -e POSTGRES_USER=pedidos -e POSTGRES_PASSWORD=CAMBIAR -e POSTGRES_DB=pedidos_db -p 127.0.0.1:5434:5432 postgres:16-alpine
Copy-Item .env.example .env      # y cambiar el puerto de DATABASE_URL a 5434
npm run prisma:push              # crea las tablas del esquema
npm run start:prod               # Swagger en http://localhost:3002/docs
docker stop pedidos-db           # al terminar (--rm borra el contenedor)
```

Sin `KEYCLOAK_ISSUER` y `KEYCLOAK_AUDIENCE` el servicio no arranca. Con Keycloak apagado arranca,
pero toda ruta responde 401 sin token y 503 con uno. Para usar «Try it out» hace falta un token
de acceso con la audiencia `<servicio>-api` (botón **Authorize** de Swagger). El realm actual
solo la emite para `usuarios-api`; los clientes por servicio llegan con la integración (sprint 5).

### Probar los controles transversales

Con el servicio compilado y su base de datos accesible (`DATABASE_URL` en el entorno o en `.env`),
desde la carpeta del servicio:

```powershell
node <repo>\templates\microservicio_nestjs\verificacion\probar-controles.mjs
```

El script no necesita Keycloak: crea sus propias claves RSA, publica el JWKS en `127.0.0.1` y
firma los tokens. Arranca el servicio en el puerto 3099, hace 37 comprobaciones (cabeceras de
seguridad, tokens válidos e inválidos, validación y formato de los errores), lo detiene y termina
con código 1 si alguna falla. Es el mismo paso que ejecuta el CI.

## La especificación

YAML o JSON. Es lo que preguntaría Copier; el generador del 23/11 la construirá a partir de
`arquitectura.json`.

```yaml
servicio: pedidos               # nombre en arquitectura.json: [a-z][a-z0-9_]{1,39}
descripcion: Pedidos de los clientes   # opcional, una línea
base_datos: pedidos_db          # por defecto <servicio>_db
puerto: 3002                    # por defecto 3000
entidades:
  - nombre: pedido              # snake_case; la clase será Pedido y la tabla «pedido»
    descripcion: Compra de un cliente
    campos:
      - {nombre: cliente_id, tipo: uuid}
      - {nombre: estado, tipo: enumeracion, valores: [pendiente, pagado]}
      - {nombre: total, tipo: decimal, min: 0, max: 99999999.99}
      - {nombre: notas, tipo: texto, max: 500, requerido: false}
```

Cada entidad lleva además `id` (UUID), `creadoEn` y `actualizadoEn`; esos tres nombres no se pueden
usar como campos.

### Tipos de campo

| Tipo | Prisma | Validación del DTO | Opciones (valor por defecto) |
|---|---|---|---|
| `texto` | `String @db.VarChar(max)` | Recorta espacios, longitud, sin caracteres de control | `min` (1), `max` (255, hasta 10000) |
| `correo` | `String @db.VarChar(254)` | `@IsEmail`, en minúsculas | |
| `entero` | `Int` | `@IsInt`, `@Min`, `@Max` | `min` (0), `max` (2147483647) |
| `decimal` | `Decimal @db.Decimal(p, escala)` | `@IsNumber` con los decimales de la escala, `@Min`, `@Max` | `min` (0), `max` (9999999999.99), `escala` (2) |
| `booleano` | `Boolean` | `@IsBoolean` | |
| `fecha` | `DateTime @db.Date` | Solo `AAAA-MM-DD` y una fecha real | |
| `fecha_hora` | `DateTime @db.Timestamptz(3)` | ISO 8601 estricto | |
| `uuid` | `String @db.Uuid` con índice | `@IsUUID` | Para ids de otros servicios: sin relación |
| `enumeracion` | `enum <Entidad><Campo>` | `@IsIn` | `valores` (obligatorio, snake_case) |
| `referencia` | Relación con otra entidad del servicio, con índice | `@IsUUID` | `entidad` (obligatoria); el campo se llama `<algo>_id` |

Todos admiten `requerido` (true), `unico` (false) y `descripcion`. La precisión de un decimal se
calcula a partir de sus límites. Una referencia crea la relación en las dos entidades: en la
referenciada aparece, por ejemplo, `lineaPedidoPorPedido LineaPedido[]`.

## Qué genera

| Archivo | Contenido |
|---|---|
| `prisma/schema.prisma` | Un modelo por entidad, con `@map` a snake_case, enums, relaciones e índices |
| `src/dto/crear-<entidad>.dto.ts` | class-validator y `@ApiProperty` con los mismos límites |
| `src/dto/actualizar-<entidad>.dto.ts` | Los mismos campos y límites, todos opcionales; un obligatorio no admite `null` |
| `src/dto/<entidad>-respuesta.dto.ts` | El contrato de salida, con límite en cada propiedad (Gate 2, OWASP API4) |
| `src/dto/<entidad>-pagina.dto.ts` | Una página del listado: `elementos` (máximo 100), `total`, `pagina` y `tamano` |
| `src/<entidad>.controller.ts` | Las 5 rutas de la entidad con sus decoradores de Swagger |
| `src/<entidad>.service.ts` | El CRUD con Prisma, la traducción de errores y el punto de extensión de la lógica de negocio |
| `src/<servicio>.module.ts`, `src/prisma.service.ts`, `src/main.ts` | Módulo (registra el guard, el `ValidationPipe` y el filtro de errores), acceso a la base y arranque con Helmet y Swagger en `/docs` |
| `src/seguridad/` | Los controles transversales: guard de Keycloak, `ValidationPipe`, filtro de errores y capa HTTP (Helmet, solo JSON, límite del cuerpo) |
| `src/openapi/` | El contrato OpenAPI: en `/docs` y en un archivo para el Gate 2 (`npm run openapi`) |
| `src/comun/` | Validación, paginación, errores de Prisma, conversión de fechas y DTO de error |
| `package.json`, `tsconfig*.json`, `.npmrc`, `.env.example`, `README.md` | Proyecto listo para compilar |
| `.copier-answers.yml` | Respuestas usadas, para `copier update` cuando cambie la plantilla |

## Rutas

Cada entidad tiene sus rutas bajo `/api/<servicio>/<entidad>` (la que enrutará Traefik), por
ejemplo `/api/pedidos/linea-pedido`:

| Ruta | Respuesta | Errores |
|---|---|---|
| `POST /` | 201 con el registro | 400 (validación o referencia que no existe), 409 si hay campos únicos, 413, 415 |
| `GET /?pagina=1&tamano=20` | 200 con una página (máximo 100 registros) | 400 si `pagina` o `tamano` se salen del rango |
| `GET /:id` | 200 con el registro | 400 si el id no es un UUID, 404 |
| `PATCH /:id` | 200 con el registro actualizado | 400, 404, 409 si hay campos únicos, 413, 415 |
| `DELETE /:id` | 204 | 400, 404, 409 si otros registros dependen de este |

Todas exigen un token de Keycloak y pueden responder además 401 (sin token o inválido), 500 (error
inesperado, sin detalles) y 503 (Keycloak no responde).

El servicio convierte los errores de Prisma (valor repetido, registro inexistente, relación rota)
en 400, 404 o 409. Si se dejaran pasar, la API respondería 500 y el DAST de la fase 9 lo contaría
como hallazgo. El 409 solo se documenta cuando puede ocurrir.

## Punto de extensión: la lógica de negocio (para la #64)

Cada `<entidad>.service.ts` termina con un bloque entre dos marcas fijas:

```ts
  // @framework:logica-negocio:inicio linea_pedido
  protected reglasAlCrear(datos: CrearLineaPedidoDto): Promise<void> { ... }
  protected reglasAlActualizar(actual: LineaPedido, cambios: ActualizarLineaPedidoDto): Promise<void> { ... }
  protected reglasAlEliminar(actual: LineaPedido): Promise<void> { ... }
  // @framework:logica-negocio:fin linea_pedido
```

- El generador de lógica de negocio solo reescribe lo que hay **entre las marcas**. El resto del
  archivo (el acceso a la base, la traducción de errores y la llamada a cada regla) lo genera la
  plantilla y no cambia.
- `crear`, `actualizar` y `eliminar` llaman a su regla **antes** de tocar la base, con datos que el
  DTO ya validó. `actualizar` y `eliminar` reciben además el registro actual.
- Una regla incumplida lanza `BadRequestException`, `ConflictException` o `NotFoundException`, que
  el servicio ya importa. Para consultar otros registros tiene `this.prisma`.
- Sin reglas, los tres métodos no hacen nada y la operación sigue tal cual. Las marcas llevan el
  nombre de la entidad en snake_case: hay una pareja por archivo.

## Controles transversales (parte 3)

Se aplican a todas las rutas sin que el controlador ni el LLM tengan que acordarse: el guard, el
`ValidationPipe` y el filtro se registran en el módulo (`APP_GUARD`, `APP_PIPE`, `APP_FILTER`) y la
capa HTTP en `main.ts`, antes de cualquier ruta.

| Control | Archivo | Qué garantiza | Referencia |
|---|---|---|---|
| Guard de Keycloak | `seguridad/jwt-auth.guard.ts` | Token RS256 con firma, emisor, audiencia (`<servicio>-api`) y vencimiento válidos; si no, 401 con `WWW-Authenticate: Bearer`. Si Keycloak no responde, 503. Sin configuración, el servicio no arranca. Nunca registra el token | OWASP API2, ASVS V3.5, RFC 8725 |
| `ValidationPipe` | `seguridad/validacion-global.ts` | Lista blanca: una propiedad no declarada se rechaza con 400 (asignación masiva). Los errores no incluyen el valor recibido | OWASP API3, ASVS V5.1 |
| Helmet | `seguridad/http.ts` | En la API: CSP `default-src 'none'; frame-ancestors 'none'`, `nosniff`, `X-Frame-Options: DENY`, HSTS de un año, `Referrer-Policy: no-referrer`, COOP y CORP `same-origin` y `Cache-Control: no-store`. En `/docs`, la CSP que necesita Swagger UI (sin `unsafe-eval`). Sin `X-Powered-By` | ASVS V14.4 |
| Solo JSON y límite | `seguridad/http.ts` | Un cuerpo que no es JSON da 415 y uno de más de 100 kB, 413. No hay lector de formularios | OWASP API4 |
| Filtro de errores | `seguridad/filtro-errores.ts` | Todo error sale como `{statusCode, message, error}`. Un 500 nunca describe la causa (queda en el registro con su traza) y ni el JSON mal formado ni la ruta inexistente se repiten en la respuesta | OWASP API8, CWE-209 |

Antes de la parte 3, el servicio generado respondía sin cabeceras de seguridad, con
`X-Powered-By: Express`, procesaba formularios y repetía el texto recibido en el 400 de un JSON mal
formado (`<script>` incluido) y en el 404 de una ruta inexistente.

Fuera de esta parte: la autorización por roles (cuando la arquitectura los defina) y el límite de
peticiones por cliente (Traefik, sprint 5). La documentación en `/docs` solo fuera de producción y
la configuración por entorno llegan en la parte 4.

## Dockerfile, pruebas y configuración por entorno (parte 4)

Con esta parte, el servicio generado se compila, se prueba y se empaqueta sin tocar nada a mano.

**Configuración por entorno** (`src/configuracion/entorno.ts`). `main.ts` valida todas las
variables antes de crear nada y, si alguna falta o no es válida, el servicio no arranca. El error
las reúne todas y nombra cada variable, nunca su valor (`DATABASE_URL` lleva la contraseña).

| | `development` | `test` | `production` (o sin `NODE_ENV`) |
|---|---|---|---|
| Swagger en `/docs` y `/docs-json` | Sí | Sí | No: 404 |
| Registro de Nest | Todo, con depuración | Advertencias y errores | Sin depuración |
| Contraseña `CAMBIAR` de `.env.example` o sin contraseña | Se admite | Se admite | Rechazada |

Sin `NODE_ENV` se asume producción, el entorno más restrictivo (seguro por defecto). También se
validan el puerto (1024 a 65535), que `DATABASE_URL` sea `postgresql://` y que las URL de Keycloak
sean `http(s)`. `main.ts` activa además `enableShutdownHooks`, para cerrar las conexiones con la
base al recibir SIGTERM.

**Pruebas generadas** (Jest: 70 en el ejemplo, unas 30 por entidad). No necesitan base de datos ni
Keycloak, así que la fase 9 del pipeline las puede ejecutar en cualquier servicio generado
(`npm run test:cov`).

| Archivo | Qué prueba |
|---|---|
| `src/<entidad>.service.spec.ts` | El servicio con Prisma simulado: las reglas de negocio se aplican antes de escribir y una regla incumplida evita la escritura; paginación con orden estable; P2002, P2003 y P2025 se traducen a 409, 400 y 404; un error desconocido no se oculta |
| `test/<servicio>.e2e-spec.ts` | La API completa con su módulo real y la capa HTTP de `main.ts`: tokens sin firma (`alg=none`), de otra audiencia, vencidos o de otra clave dan 401; cabeceras de seguridad; 404 sin eco y 415. Por entidad: crear (201), propiedad no declarada (400), listar, tope de página, id que no es UUID, 404, actualizar y eliminar |
| `src/configuracion/entorno.spec.ts` | La validación de la configuración de cada entorno |

Los datos de prueba salen de `_macros/pruebas.jinja`: un valor válido por tipo de campo, dentro de
sus límites. Las pruebas sustituyen las reglas de negocio que escribe el LLM, para comprobar lo que
genera la plantilla aunque cambien las reglas.

**Imagen** (`Dockerfile`), con el mismo diseño que el servicio de referencia:

- Tres etapas: compilación, dependencias de producción e imagen final distroless (sin shell ni
  npm), con el usuario 65532, `NODE_ENV=production` y un `HEALTHCHECK` que hace el propio node.
- `npm ci` con el `package-lock.json` que genera la plantilla, sin scripts de instalación.
- `--omit=optional` además de `--omit=dev`. El CLI de `prisma` y `typescript` son *peers*
  opcionales de `@prisma/client`, y npm los deja en producción aunque sean de desarrollo: sin esta
  opción la imagen llevaba 131 paquetes de más (el CLI, Prisma Studio con React, d3...) y ocupaba
  726 MB en lugar de 405 MB. La imagen de `services/usuarios` tiene el mismo problema.
- El generador del contrato OpenAPI, las pruebas, las fuentes y `.env` no entran en la imagen.

**El `package-lock.json`** (`plantilla/package-lock.json.jinja`) fija la versión exacta y la
integridad SHA-512 de los 777 paquetes. Del servicio solo depende su nombre, que es la única
variable del archivo. Cuando cambian las dependencias de `package.json.jinja`, se regenera desde
un servicio recién generado:

```powershell
npm install --package-lock-only --ignore-scripts
node <repo>\templates\microservicio_nestjs\herramientas\actualizar-lock.mjs
```

`npm audit` da 0 vulnerabilidades en las dependencias de producción y 19 moderadas en las de
desarrollo (`glob` y `minimatch`, a través de Jest y `@nestjs/cli`), que no llegan a la imagen.

### Probar la imagen

Desde la carpeta del servicio, con Docker:

```powershell
docker build -t fw-pedidos:local .
node <repo>\templates\microservicio_nestjs\verificacion\probar-imagen.mjs fw-pedidos:local
```

El script levanta un PostgreSQL desechable con una contraseña aleatoria en una red interna y hace
17 comprobaciones:

- **Cómo está construida:** usuario 65532, `NODE_ENV=production`, `HEALTHCHECK`, un solo puerto,
  sin shell y sin fuentes, pruebas, `.env` ni dependencias de desarrollo.
- **Falla cerrado:** sin configuración, o con la contraseña de ejemplo, no arranca.
- **Con la base:** Prisma consulta la base con las dependencias de la imagen.
- **En marcha:** arranca en solo lectura y sin capacidades de Linux, y responde 401 con las
  cabeceras de seguridad. `/docs` y `/docs-json` dan 404.
- **Registro y parada:** el registro no contiene la contraseña y el contenedor se detiene con
  SIGTERM, sin esperar al SIGKILL.

Al terminar borra los contenedores y la red. Es el mismo paso que ejecuta el CI.

## Gate 2 sobre el servicio generado

El contrato del ejemplo pasa las reglas propias del framework (`spectral/reglas-propias.yaml`) y
los límites del OWASP API Top 10: cada texto con `maxLength` y `pattern` o `format`, cada número
con su rango y cada lista con `maxItems`. Con la parte 3 cada operación declara además el token
(`bearer`) y las respuestas 401, 500 y 503, y Spectral da **0 errores**:

| Resultado | Regla | Se resuelve en |
|---|---|---|
| ~~30 errores~~ | `owasp:api2:2023-read-restricted`, `write-restricted` y `define-error-responses-401` | Resuelto en la parte 3: guard de Keycloak |
| ~~Avisos~~ | `define-error-responses-500` | Resuelto en la parte 3: filtro de errores |
| 65 avisos | `rate-limit`, `rate-limit-responses-429` | Traefik (sprint 5), como en el servicio de referencia |

Para repetirlo, desde la raíz del repositorio y con el servicio compilado:

```powershell
cd <servicio>; npm run openapi -- openapi\pedidos.json; cd <raíz>
spectral\node_modules\.bin\spectral lint <servicio>\openapi\pedidos.json --ruleset spectral\.spectral.yaml
```

## Seguridad

La especificación vendrá del LLM, así que la plantilla la trata como entrada no confiable:

- **`copier.yml` la valida antes de escribir nada.** Todo lo que acaba como identificador en
  TypeScript o en Prisma (servicio, entidades, campos, valores de enumeración) debe cumplir una
  expresión regular. Los tipos salen de una lista cerrada, las claves desconocidas se rechazan (una
  errata como `requerida` no pasa en silencio) y los límites se comprueban.
- **Los textos libres no pueden romper el código.** Las descripciones no admiten saltos de línea ni
  caracteres de control, y en TypeScript se escriben como literales escapados.
- **No ejecuta nada.** Sin `_tasks`, `_migrations` ni extensiones de Jinja, y el motor llama a
  Copier con `unsafe=False`.
- **El servicio generado nace con defensas.** `.npmrc` desactiva los scripts de instalación y el
  `.env` real queda fuera de Git. Todas las rutas exigen un token de Keycloak y pasan por los
  controles transversales de la parte 3. Los ids se validan como UUID, los listados tienen tope y
  los textos no admiten caracteres de control.
- **Dependencias fijadas.** La plantilla solo añade dos dependencias de seguridad, `helmet` y
  `jose`; `jose` va en la versión exacta del servicio de referencia (la 6 solo se publica como ESM).
  El `package-lock.json` generado fija todo el árbol con su integridad, y tanto el Dockerfile como
  el CI instalan con `npm ci`.
- **Seguro por defecto también al desplegar.** Sin `NODE_ENV` el servicio se comporta como en
  producción, la imagen no tiene shell ni corre como root, y con la contraseña de ejemplo no
  arranca.

## Estructura de la plantilla

| Ruta | Qué es |
|---|---|
| `copier.yml` | Preguntas, validaciones y nombres derivados (clase, archivo, propiedad) |
| `_macros/tipos.jinja` | Traducción de cada tipo a Prisma, TypeScript, Swagger y class-validator |
| `plantilla/` | Lo que se copia al servicio. Los archivos `.jinja` se renderizan |
| `ejemplos/pedidos.yml` | Especificación de ejemplo: el servicio de pedidos de la tienda en línea |
| `_macros/pruebas.jinja` | Datos válidos de cada tipo de campo para las pruebas generadas |
| `verificacion/probar-controles.mjs` | Prueba en ejecución de los controles de un servicio generado (no se copia al servicio) |
| `verificacion/probar-imagen.mjs` | Prueba de la imagen de Docker de un servicio generado (no se copia al servicio) |
| `herramientas/actualizar-lock.mjs` | Regenera `plantilla/package-lock.json.jinja` al cambiar las dependencias |

Los archivos de cada entidad (DTO, controlador y servicio) se generan uno por entidad con la
etiqueta `{% yield %}` de Copier en el nombre del archivo.
Los nombres de archivo no usan filtros de Jinja, porque Windows no admite el carácter `|`: por eso
`copier.yml` calcula antes los nombres derivados.

Lo que aún no cubre: relaciones entre servicios (se guardan como `uuid`, cada servicio es dueño de
sus datos), relaciones de muchos a muchos, y filtros y búsquedas en los listados. Las entidades no pueden llamarse
`prisma`, `paginacion`, `error_respuesta`, `error_validacion`, `app` ni `main`, porque sus clases
chocarían con las de la plantilla.
