# Generación de cada microservicio (fase 3)

| Paso | Módulo | Comando |
|---|---|---|
| Parámetros de la plantilla de cada servicio (nombre, entidades y rutas) | `parametros.py` | `framework servicio parametros <arquitectura.json>` |
| Especificación del servicio (entidades y campos) con el LLM | `orchestrator/llm/prompts` | `framework servicio prompt … --enviar --salida <servicio>.yml` |
| Esqueleto determinista con la plantilla Copier, con su estructura validada | `plantilla.py`, `estructura.py` | `framework servicio generar <servicio>.yml` |
| Validar la estructura de un servicio ya generado | `estructura.py` | `framework servicio validar <carpeta>` |
| Lógica de negocio en los puntos de extensión con el LLM | `logica.py` | `framework servicio logica <carpeta>` |
| Ver todo lo anterior que no usa LLM, de una vez | `demostracion.py` | `framework servicio demo` |
| Dependencias npm contra la lista permitida | `dependencias.py` | `framework servicio dependencias <carpeta>` |
| Pruebas Jest de la lógica de negocio con el LLM | `pruebas.py` | `framework servicio pruebas <carpeta>` |

## Pruebas de la lógica de negocio (`pruebas.py`)

La plantilla ya prueba lo que genera ella y sustituye las reglas de negocio por dobles. Para cada
entidad con reglas aceptadas (`logica/<entidad>.json`), el LLM de razonamiento escribe los casos
que las prueban con el prompt `pruebas`: el código de las reglas, los requisitos que implementan y
los nombres y tipos de la entidad; lo que quedó pendiente no se prueba.

1. **El motor arma `src/<entidad>.reglas.spec.ts`**: imports, el doble de Prisma (cada modelo con
   sus métodos como `jest.fn()`) y el acceso a los métodos. El LLM solo escribe el cuerpo de cada
   caso, con el requisito que comprueba en su título.
2. **Analiza cada caso** como la lógica (sin `import`, `require`, `process`, consola, red...) y
   además sin `jest.mock` ni `describe`/`it`/`test` anidados.
3. **Lo ejecuta con Jest.** Si el archivo no compila o algún caso falla, vuelve a pedirlo con los
   errores (hasta 3 intentos).
4. **Si siguen fallando casos, los quita**, comprueba que el resto pasa y los registra como
   descartados: una prueba que falla puede estar mal escrita o señalar un error real de la lógica,
   y eso lo decide una persona.

```bash
uv run framework servicio pruebas salida/servicios/pedidos \
  --requisitos salida/requisitos/requisitos-docx.modelo_requisitos.json --cobertura
```

`--cobertura` ejecuta al final todas las pruebas del servicio con `jest --coverage`.

## Demostración con un solo comando (`demostracion.py`)

`framework servicio demo` muestra hasta dónde llega hoy la fase 3, sin LLM, sin Docker y sin red:

1. los parámetros de cada servicio de la arquitectura del documento 1;
2. un servicio generado con la plantilla (`ejemplos/pedidos.yml`);
3. su estructura validada;
4. sus dependencias contra la lista permitida;
5. un **control negativo de la estructura**: a una copia se le quita el guard JWT y el Dockerfile, y
   la validación tiene que detectarlo;
6. un **control negativo de las dependencias**: a otra copia se le añade un paquete inventado, y la
   lista permitida tiene que rechazarlo.

Al final dice qué comandos usan el LLM y qué falta todavía en el motor. Si un control negativo no
detecta el problema, el comando termina con código 1: la demostración no solo enseña, también
comprueba que las defensas funcionan.

```bash
uv run framework servicio demo                       # en salida/servicios-demo
uv run framework servicio demo --arquitectura salida/arquitectura/<id>.arquitectura.json
uv run framework servicio demo --arbol               # con el árbol de archivos
uv run framework servicio demo --compilar            # además: npm ci, prisma generate y tsc
```

Escribe solo en su carpeta (`--destino`, por defecto `salida/servicios-demo`) y la marca con un
archivo propio: si la carpeta existe, no está vacía y no la creó la demostración, se niega a
usarla, para no borrar nunca nada ajeno. Las copias de los controles negativos se borran siempre
al terminar.

## Parámetros por servicio (`parametros.py`)

`arquitectura.json` ya fija de cada servicio lo que el LLM no debe decidir al generarlo.
`parametros_de_arquitectura()` lo calcula para los N servicios de una vez y valida el conjunto
antes de generar nada:

| Parámetro | De dónde sale | Ejemplo (`pedidos`) |
|---|---|---|
| `servicio`, `base_datos` | La arquitectura | `pedidos`, `pedidos_db` |
| `descripcion` | La responsabilidad, en una línea de 300 caracteres como mucho | |
| `puerto` | 3001 + su posición en la arquitectura (3000 es `services/usuarios`): estable entre ejecuciones | `3002` |
| `entidades` | Cada entidad de la arquitectura en snake_case sin tildes: «LineaPedido» → `linea_pedido`, «Línea de pedido» → `linea_de_pedido` | `pedido`, `linea_pedido` |
| `prefijo` y `rutas` | `/api/<servicio>` y `/api/<servicio>/<entidad>`, con guiones | `/api/pedidos/linea-pedido` |
| `audiencia` | La audiencia que deben llevar sus tokens | `pedidos-api` |

**Errores** (no se genera nada y se informan todos a la vez): una entidad que no da un
identificador válido (p. ej. «2FA»), que choca con un nombre reservado de la plantilla (`prisma`,
`app`...) o que se repite en el mismo servicio («Pedido» y «pedido»), y dos servicios con la misma
base de datos o el mismo prefijo de rutas.

**Advertencias** (no impiden generar):

- *Una entidad en varios servicios.* Pasa en 3 de las 4 arquitecturas de `salida/` (`Mascota` en
  usuarios e historias, `Reserva` en reservas y pagos...). Cada servicio tiene su propia base, así
  que son tablas independientes, normalmente una proyección de lectura. Si además no hay una
  dependencia declarada entre esos servicios, la copia no tiene de dónde actualizarse, y la
  advertencia lo dice.
- *Un servicio sin entidades en la arquitectura.* Las propone el LLM, sin poder contrastarlas.

**Las entidades del LLM deben ser exactamente las de la arquitectura**: ni más ni menos. Una tabla
que no está en la arquitectura aprobada no tendría trazabilidad hasta sus requisitos ni sus ADR.
El prompt `especificacion` (v1.1) da los identificadores y el esquema de la respuesta
(`esquema_de_la_respuesta()`) lo comprueba, así que el proveedor reintenta si el LLM se inventa o se
salta una. `especificacion(parametros, propuesta)` junta las dos partes en la entrada de la
plantilla y vuelve a comprobarlo, por si la especificación se editó a mano.

```bash
uv run framework servicio parametros salida/arquitectura/<documento>.arquitectura.json \
  --salida salida/servicios/parametros.json
```

## Estructura generada (`estructura.py`)

`generar_servicio()` valida lo que acaba de generar Copier y, si no coincide con la
especificación, borra el servicio y lanza `ErrorPlantilla` con todos los problemas: un servicio a
medias nunca queda en el destino.

- **El árbol de archivos** es exactamente el de la plantilla para esas entidades. La lista sale de
  la propia plantilla (cada archivo de `plantilla/`, y los de `{% yield %}` una vez por entidad),
  y los archivos de los controles de seguridad (guard, filtro de errores, Helmet, ValidationPipe,
  configuración por entorno, Dockerfile, `.npmrc`, `package-lock.json`...) son obligatorios aunque
  alguien los quite de la plantilla.
- **Nada sin renderizar** (`{{`, `{%`) y ningún enlace simbólico.
- **El contenido coincide con los parámetros**: el nombre del paquete; la ruta de cada controlador;
  los controladores y servicios del módulo con sus tres controles globales; un modelo Prisma por
  entidad con su tabla; las marcas del punto de extensión del LLM; y el puerto, la audiencia, la
  base de datos y el usuario sin privilegios del Dockerfile, de `main.ts` y de `.env.example`.

Lo que crean después la instalación, la compilación, las pruebas y `logica.py` (`node_modules`,
`dist`, `coverage`, `src/generated`, `openapi/`, `logica/`, `.env`) no cuenta como sobrante, así que
`servicio validar` sirve en cualquier momento de la vida del servicio. Sin especificación, usa las
respuestas que guardó Copier en `.copier-answers.yml`.

```bash
uv run framework servicio validar salida/servicios/pedidos     # árbol, rutas y problemas
python orchestrator/generation/estructura.py salida/servicios/pedidos   # sin el motor (CI)
```

## Dependencias permitidas (`dependencias.py`)

Defensa contra los paquetes npm alucinados («slopsquatting», plan técnico 6.5): un LLM puede
inventar el nombre de un paquete, o cambiarle una letra, y un atacante puede haberlo publicado con
código malicioso. Ninguna dependencia entra en un servicio si no está en
`knowledge_base/dependencias_permitidas.yaml`, en su sección y con su rango de versiones; cada
paquete de la lista lleva el motivo por el que se aprobó, y la lista solo cambia por pull request
revisado.

- **package.json**: cada paquete de `dependencies`, `devDependencies` y `overrides` está en la
  lista, con el mismo rango o una versión exacta dentro de él; nada de URLs de git o http,
  archivos locales, alias `npm:`, `latest` ni `*`; sin `optionalDependencies`, `peerDependencies`
  ni `bundleDependencies`, y sin scripts que se ejecuten al instalar.
- **package-lock.json**: todo se descarga del registro de la lista con huella sha512, nada se
  enlaza desde el disco y las versiones resueltas de las dependencias directas están en el rango.
  Las indirectas las revisa Trivy en el Gate 1.

`preparar()` (antes de compilar la lógica de negocio) comprueba package.json **antes** de
`npm install`, así que un paquete no permitido nunca se descarga, y el package-lock.json después.
El job de la plantilla en CI hace lo mismo; como el módulo solo usa Pydantic y PyYAML, se ejecuta
como script sin instalar el motor:

```bash
python orchestrator/generation/dependencias.py salida/servicios/pedidos
```

## Lógica de negocio (`logica.py`)

La plantilla deja en `src/<entidad>.service.ts` un punto de extensión por entidad, entre
`// @framework:logica-negocio:inicio <entidad>` y `...:fin <entidad>`, con `reglasAlCrear`,
`reglasAlActualizar` y `reglasAlEliminar`. Por cada entidad:

1. **El LLM de razonamiento escribe el cuerpo de los tres métodos** con el prompt `logica`: los
   requisitos del servicio, los nombres y tipos de TypeScript de la entidad y el contexto de
   seguridad de GraphRAG.
2. **El motor analiza el código antes de escribirlo**, fuera de cadenas y comentarios: sin
   `import`, `require`, `eval`, `Function`, `process`, `fs`, `child_process`, `$queryRaw` ni
   `$executeRaw`, red, temporizadores, `console`, prototipos, ni más miembros de la clase que
   `this.prisma`. Las llaves deben estar equilibradas, para que el cuerpo no cierre el método y
   escriba fuera de él, y las marcas del punto de extensión no pueden aparecer ni en un comentario.
3. **Comprueba la trazabilidad**: los requisitos que cita son del servicio y los controles ASVS
   están en el contexto que recibió.
4. **Lo inserta y compila** con `tsc --noEmit` (la primera vez instala las dependencias con
   `npm install --ignore-scripts` y genera el cliente de Prisma).
5. **Si algo falla, vuelve a pedirlo con los motivos**: los problemas del análisis o los errores
   de tsc de ese archivo, hasta 3 intentos. Si no lo consigue, el archivo queda como lo generó la
   plantilla: el servicio compila, sin reglas, y la entidad queda para revisión.

El bloque generado indica los requisitos que implementa, los controles ASVS que aplica y lo que el
LLM no pudo implementar en esos métodos (`Pendiente: …`). El registro de cada entidad (intentos,
problemas, errores de tsc, huella del prompt y respuesta) queda en `<carpeta>/logica/<entidad>.json`.

```bash
uv run framework servicio logica salida/servicios/pedidos \
  --arquitectura salida/arquitectura/requisitos-docx.arquitectura.json \
  --requisitos salida/requisitos/requisitos-docx.modelo_requisitos.json
```

`--entidad` limita las entidades (se puede repetir), `--sin-compilar` omite tsc y
`--sin-graphrag` no consulta Neo4j. El servicio se genera antes con `servicio generar`.

Lo que el análisis y tsc no ven (lógica incorrecta, condiciones de carrera, reglas de autorización
que faltan) lo revisan después Semgrep y ESLint en el Gate 1 y las pruebas de la fase 9.
