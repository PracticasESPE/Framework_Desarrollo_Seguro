# Generación de cada microservicio (fase 3)

| Paso | Módulo | Comando |
|---|---|---|
| Especificación del servicio (entidades y campos) con el LLM | `orchestrator/llm/prompts` | `framework servicio prompt … --enviar --salida <servicio>.yml` |
| Esqueleto determinista con la plantilla Copier | `plantilla.py` | `framework servicio generar <servicio>.yml` |
| Lógica de negocio en los puntos de extensión con el LLM | `logica.py` | `framework servicio logica <carpeta>` |

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
