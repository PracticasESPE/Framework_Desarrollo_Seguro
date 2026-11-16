# Plantilla `microservicio_nestjs`

Plantilla [Copier](https://copier.readthedocs.io) de la fase 3 (plan técnico, 7.3). Genera el
esqueleto determinista de cada microservicio de `arquitectura.json`; el LLM solo completará la lógica
de negocio en los puntos que marque la plantilla.

| Parte | Issue | Qué añade | Estado |
|---|---|---|---|
| 1 | #61 | Módulo, entidades Prisma y DTO con class-validator | Lista |
| 2 | #63 | Servicio, controlador y decoradores de Swagger | Pendiente (17/11) |
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

El job `plantilla` del workflow hace lo mismo con el ejemplo en cada PR.

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
| `src/dto/actualizar-<entidad>.dto.ts` | `PartialType` del anterior: mismas validaciones, todo opcional |
| `src/dto/<entidad>-respuesta.dto.ts` | El contrato de salida, con límite en cada propiedad (Gate 2, OWASP API4) |
| `src/<servicio>.module.ts`, `src/prisma.service.ts`, `src/main.ts` | Módulo, acceso a la base y arranque con `ValidationPipe` de lista blanca |
| `src/comun/validacion.ts` | Utilidades compartidas por los DTO |
| `package.json`, `tsconfig*.json`, `.npmrc`, `.env.example`, `README.md` | Proyecto listo para compilar |
| `.copier-answers.yml` | Respuestas usadas, para `copier update` cuando cambie la plantilla |

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
  `.env` real queda fuera de Git y `main.ts` activa `ValidationPipe` con lista blanca. El resto de
  los controles transversales llega en la parte 3.

## Estructura de la plantilla

| Ruta | Qué es |
|---|---|
| `copier.yml` | Preguntas, validaciones y nombres derivados (clase, archivo, propiedad) |
| `_macros/tipos.jinja` | Traducción de cada tipo a Prisma, TypeScript, Swagger y class-validator |
| `plantilla/` | Lo que se copia al servicio. Los archivos `.jinja` se renderizan |
| `ejemplos/pedidos.yml` | Especificación de ejemplo: el servicio de pedidos de la tienda en línea |

Los DTO se generan uno por entidad con la etiqueta `{% yield %}` de Copier en el nombre del archivo.
Los nombres de archivo no usan filtros de Jinja, porque Windows no admite el carácter `|`: por eso
`copier.yml` calcula antes los nombres derivados.

Lo que aún no cubre: relaciones entre servicios (se guardan como `uuid`, cada servicio es dueño de
sus datos), relaciones de muchos a muchos y `package-lock.json` (llega con el Dockerfile, en la
parte 4).
