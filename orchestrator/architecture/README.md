# Propuesta arquitectónica (fase 2)

A partir del modelo de requisitos de la fase 1, el LLM de razonamiento propone los bounded
contexts, la división en microservicios y las decisiones arquitectónicas con su justificación
(plan técnico, sección 7.2, paso 1). El resultado es `arquitectura.json`.

```bash
uv run framework arquitectura proponer salida/requisitos/requisitos-pdf.modelo_requisitos.json --proveedor groq
uv run python -m evaluation.fase2.evaluar salida/arquitectura/requisitos-pdf.arquitectura.json salida/requisitos/requisitos-pdf.modelo_requisitos.json evaluation/datasets/01_tienda_en_linea
```

El primero guarda `salida/arquitectura/<nombre>.arquitectura.json`. `--nivel rapido` usa el
modelo rápido del proveedor si el de razonamiento no está disponible. El segundo, que es parte de
la evaluación y no del framework, compara la propuesta con los servicios de la referencia del
dataset.

## Qué contiene `arquitectura.json`

| Campo | Qué es | Quién lo usa después |
|---|---|---|
| `servicios` | Nombre, bounded context, responsabilidad, entidades, requisitos que cubre, base de datos y dependencias (síncronas por HTTP o asíncronas por eventos) | OPA (base de datos propia, sin ciclos), generación del código (fase 3), diagrama C4 |
| `servicios[].etiquetas` | Etiquetas de seguridad de sus requisitos, calculadas por el motor | OPA, para inferir patrones y controles |
| `transversales` | Requisitos que aplican a todo el sistema (HTTPS, rendimiento, copias) | OPA y la plantilla de los servicios |
| `decisiones` | Qué se decidió, por qué y qué requisitos lo motivan | ADR y nodos `Decision` |
| `documento` | Nombre y huella SHA-256 del documento de requisitos | Trazabilidad |

El JSON Schema está en `docs/esquemas/arquitectura.schema.json`. Si cambia el modelo, se
regenera con:

```bash
uv run framework arquitectura esquema --salida docs/esquemas/arquitectura.schema.json
```

## Validación

- Pydantic rechaza nombres de servicio que no son identificadores (`^[a-z][a-z0-9_]{1,39}$`),
  campos de más o de menos y textos vacíos.
- El motor exige que cada requisito quede asignado exactamente una vez (a un servicio o como
  transversal), que no aparezcan ids inventados y que cada dependencia apunte a otro servicio de
  la propuesta. Si algo falla, vuelve a pedir la propuesta con los motivos, hasta tres intentos.
- Las reglas arquitectónicas y la inferencia de patrones son de OPA (`policies/arquitectura`).
  `proponer_arquitectura` acepta los motivos de un rechazo anterior (`retroalimentacion`) para el
  ciclo LLM ↔ OPA.

El texto de los requisitos viene del documento del cliente: va entre marcas con un código
aleatorio y el mensaje de sistema indica que es un dato, nunca una instrucción, como en la
clasificación de la fase 1.

## ADR en Markdown

```bash
uv run framework arquitectura adr salida/arquitectura/requisitos-docx.arquitectura.json \
  --requisitos salida/requisitos/requisitos-docx.modelo_requisitos.json
```

Escribe en `docs/adr/` (o en `--destino`) un ADR por cada decisión de `arquitectura.json` y otro
por cada patrón que infiere OPA, además del índice `README.md` con la validación.

1. **Primero valida con OPA.** Si OPA rechaza la arquitectura, no genera nada y muestra los
   motivos: un ADR registra una decisión aceptada.
2. **Los hechos no pasan por el LLM.** Salen de datos ya validados: la decisión, la justificación,
   los requisitos con su texto, los servicios afectados, los controles ASVS y las CWE con su nombre
   (de la base de conocimiento).
3. **El LLM rápido solo redacta** el contexto y las consecuencias (plan técnico, tabla 6.1).
   - Si su texto cita requisitos, controles o CWE que no son de ese ADR, se descarta.
   - Si el LLM falla o no hay (`--sin-llm`), se usa la plantilla del motor.
   - Cada ADR indica en «Redacción» cómo se escribió.
   - Ante el límite por minuto, espera lo que pide el proveedor, igual que la clasificación.
4. **El texto se escapa antes de escribirlo.** Viene del documento del cliente y del LLM, así que
   no puede abrir HTML, imágenes ni enlaces, ni romper las tablas.
5. **Al regenerar** se borran solo los ADR que llevan la marca de generados; los escritos a mano se
   conservan, y si uno coincide en nombre, no se pisa.

Los ADR del documento 1 del dataset están en `docs/adr/`, con sus entradas en `docs/adr/entrada/`.

## Diagrama C4 en Mermaid

```bash
uv run framework arquitectura diagrama salida/arquitectura/requisitos-docx.arquitectura.json \
  --requisitos salida/requisitos/requisitos-docx.modelo_requisitos.json --nombre "Tienda en línea"
```

Escribe `docs/arquitectura.md` (o `--salida`), que GitHub dibuja sin herramientas adicionales:

1. **Contexto** (C4 nivel 1, sintaxis `C4Context`): las personas que usan el sistema, sacadas de
   los actores de los requisitos.
2. **Contenedores** (C4 nivel 2):
   - qué contiene: el gateway, la identidad y el bus de eventos, solo si la arquitectura los
     necesita; cada microservicio con su base de datos; y las dependencias, síncronas (HTTP,
     flecha continua) o asíncronas (eventos, flecha punteada);
   - cómo se dibuja: con un `flowchart` con los colores y las formas de C4, porque la sintaxis
     `C4Container` coloca las piezas en una rejilla fija y, con una base de datos por servicio,
     las flechas se superponen hasta no poder leerse.
3. **Tablas** de servicios y dependencias, los patrones de OPA con enlace a su ADR (`--adr`,
   por defecto `docs/adr`) y la validación.

Como los ADR, valida antes con OPA y no dibuja una arquitectura rechazada. No usa LLM: dibuja
exactamente lo que se validó. El texto que escribió el LLM (responsabilidades y motivos) va sin
comillas, saltos de línea ni `<>|#;`, así que no puede romper el diagrama ni añadir instrucciones
de Mermaid. Si `docs/arquitectura.md` no lo generó el framework, no se pisa.

El de `docs/arquitectura.md` se dibujó con Mermaid 11 y 12 antes de subirlo.

## Resultado con el documento 1

Con `openai/gpt-oss-120b` en Groq, al primer intento: 6 servicios (`usuarios`, `catalogo`,
`pedidos`, `pagos`, `notificaciones` y `auditoria`), 5 requisitos transversales y 5 decisiones.
Los 5 servicios de la referencia aparecen con el mismo nombre; la agrupación de requisitos por
pares tiene precisión 100 %, exhaustividad 94 % y F1 0.97. La diferencia: el LLM separa la
auditoría en su propio servicio.
