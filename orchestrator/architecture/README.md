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

## Resultado con el documento 1

Con `openai/gpt-oss-120b` en Groq, al primer intento: 6 servicios (`usuarios`, `catalogo`,
`pedidos`, `pagos`, `notificaciones` y `auditoria`), 5 requisitos transversales y 5 decisiones.
Los 5 servicios de la referencia aparecen con el mismo nombre; la agrupación de requisitos por
pares tiene precisión 100 %, exhaustividad 94 % y F1 0.97. La diferencia: el LLM separa la
auditoría en su propio servicio.
