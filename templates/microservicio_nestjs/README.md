# Plantilla `microservicio_nestjs`

Plantilla [Copier](https://copier.readthedocs.io) de la fase 3 (plan técnico, 7.3). Genera el
esqueleto determinista de cada microservicio de `arquitectura.json`; el LLM solo completará la lógica
de negocio en los puntos que marque la plantilla.

| Parte | Issue | Qué añade | Estado |
|---|---|---|---|
| 1 | #61 | Módulo, entidades Prisma y DTO con class-validator | Lista |
| 2 | #63 | Servicio, controlador y decoradores de Swagger | Lista |
| 3 | #65 | Guard de Keycloak, Helmet y filtro de errores | Pendiente (18/11) |
| 4 | #67 | Dockerfile, Jest base y configuración por entorno | Pendiente (19/11) |

## Uso

```powershell
python -m uv run python -m orchestrator.cli servicio generar templates/microservicio_nestjs/ejemplos/pedidos.yml
```

Crea `salida/servicios/pedidos` (o la carpeta de `--destino`). Nunca escribe sobre un servicio que
ya existe. Para compilarlo, desde esa carpeta:

```powershell
npm install
$env:DATABASE_URL = "postgresql://pedidos:CAMBIAR@localhost:5432/pedidos_db"
npm run prisma:generate
npm run typecheck
npm run build
```

El job `plantilla` del workflow hace lo mismo con el ejemplo en cada PR, y además genera su
contrato OpenAPI sin base de datos (`npm run openapi`), lo que comprueba que el módulo arranca.

### Probarlo con una base de datos y ver Swagger

```powershell
docker run -d --rm --name pedidos-db -e POSTGRES_USER=pedidos -e POSTGRES_PASSWORD=CAMBIAR -e POSTGRES_DB=pedidos_db -p 127.0.0.1:5434:5432 postgres:16-alpine
Copy-Item .env.example .env      # y cambiar el puerto de DATABASE_URL a 5434
npm run prisma:push              # crea las tablas del esquema
npm run start:prod               # Swagger en http://localhost:3002/docs
docker stop pedidos-db           # al terminar (--rm borra el contenedor)
```

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
| `src/<servicio>.module.ts`, `src/prisma.service.ts`, `src/main.ts` | Módulo, acceso a la base y arranque con `ValidationPipe` de lista blanca y Swagger en `/docs` |
| `src/openapi/` | El contrato OpenAPI: en `/docs` y en un archivo para el Gate 2 (`npm run openapi`) |
| `src/comun/` | Validación, paginación, errores de Prisma, conversión de fechas y DTO de error |
| `package.json`, `tsconfig*.json`, `.npmrc`, `.env.example`, `README.md` | Proyecto listo para compilar |
| `.copier-answers.yml` | Respuestas usadas, para `copier update` cuando cambie la plantilla |

## Rutas

Cada entidad tiene sus rutas bajo `/api/<servicio>/<entidad>` (la que enrutará Traefik), por
ejemplo `/api/pedidos/linea-pedido`:

| Ruta | Respuesta | Errores |
|---|---|---|
| `POST /` | 201 con el registro | 400 (validación o referencia que no existe), 409 si hay campos únicos |
| `GET /?pagina=1&tamano=20` | 200 con una página (máximo 100 registros) | 400 si `pagina` o `tamano` se salen del rango |
| `GET /:id` | 200 con el registro | 400 si el id no es un UUID, 404 |
| `PATCH /:id` | 200 con el registro actualizado | 400, 404, 409 si hay campos únicos |
| `DELETE /:id` | 204 | 400, 404, 409 si otros registros dependen de este |

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

## Gate 2 sobre el servicio generado

El contrato del ejemplo pasa las reglas propias del framework (`spectral/reglas-propias.yaml`) y
los límites del OWASP API Top 10: cada texto con `maxLength` y `pattern` o `format`, cada número
con su rango y cada lista con `maxItems`. Con la parte 2, Spectral solo da:

| Resultado | Regla | Se resuelve en |
|---|---|---|
| 30 errores | `owasp:api2:2023-read-restricted`, `write-restricted` y `define-error-responses-401`: las rutas aún no exigen token | Parte 3 (#65), guard de Keycloak |
| Avisos | `rate-limit`, `rate-limit-responses-429` | Traefik (sprint 5), como en el servicio de referencia |
| Avisos | `define-error-responses-500` | Parte 3 (#65), filtro de errores |

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
- **El servicio generado nace con defensas.** `.npmrc` desactiva los scripts de instalación, el
  `.env` real queda fuera de Git y `main.ts` activa `ValidationPipe` con lista blanca: una
  propiedad que el DTO no declara (por ejemplo `esAdmin`) se rechaza con 400. Los ids se validan
  como UUID, los listados tienen tope y los textos no admiten caracteres de control. El resto de los
  controles transversales llega en la parte 3.

## Estructura de la plantilla

| Ruta | Qué es |
|---|---|
| `copier.yml` | Preguntas, validaciones y nombres derivados (clase, archivo, propiedad) |
| `_macros/tipos.jinja` | Traducción de cada tipo a Prisma, TypeScript, Swagger y class-validator |
| `plantilla/` | Lo que se copia al servicio. Los archivos `.jinja` se renderizan |
| `ejemplos/pedidos.yml` | Especificación de ejemplo: el servicio de pedidos de la tienda en línea |

Los archivos de cada entidad (DTO, controlador y servicio) se generan uno por entidad con la
etiqueta `{% yield %}` de Copier en el nombre del archivo.
Los nombres de archivo no usan filtros de Jinja, porque Windows no admite el carácter `|`: por eso
`copier.yml` calcula antes los nombres derivados.

Lo que aún no cubre: relaciones entre servicios (se guardan como `uuid`, cada servicio es dueño de
sus datos), relaciones de muchos a muchos, filtros y búsquedas en los listados, y
`package-lock.json` (llega con el Dockerfile, en la parte 4). Las entidades no pueden llamarse
`prisma`, `paginacion`, `error_respuesta`, `error_validacion`, `app` ni `main`, porque sus clases
chocarían con las de la plantilla.
