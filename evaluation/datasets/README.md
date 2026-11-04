# Dataset de evaluación: documentos de requisitos

Tres documentos de requisitos de dominios distintos y complejidad creciente, para los experimentos
del ciclo DSR (plan técnico, 11.3.1). Cada documento se ejecuta tres veces con cada configuración
(B0, B1 y F) para medir la variabilidad.

| Carpeta | Dominio | Complejidad | Estado |
|---|---|---|---|
| `01_tienda_en_linea/` | Tienda en línea | Baja | Listo (04/11/2026) |
| `02_gestion_academica/` | Gestión académica | Media | Pendiente (05/11, #47) |
| `03_citas_medicas/` | Citas médicas | Alta | Pendiente (05/11, #47) |

## Estructura de cada documento

| Archivo | Qué es | Lo recibe el framework |
|---|---|---|
| `requisitos.md` | Fuente del documento | Sí |
| `requisitos.pdf`, `.docx`, `.txt` | El mismo documento en los formatos de entrada de la fase 1 | Sí |
| `referencia.yaml` | Respuesta esperada: requisitos, tipo, etiquetas, controles, servicios y patrones | **No, nunca** |
| `formatos.json` | Huellas de la fuente y de los formatos generados | No |

`vocabulario.yaml` fija los valores comunes de todas las referencias: tipos, etiquetas de seguridad
y el servicio `transversal`.

## Reglas del dataset

- **El framework solo recibe `requisitos.*`.** Si la referencia llegara al LLM, la evaluación
  mediría una copia y no una extracción.
- **El documento está escrito como lo haría el cliente.** No lleva identificadores RF/RNF ni
  etiquetas de seguridad, y mezcla a propósito algunos requisitos no funcionales con los funcionales
  y algunas historias de usuario. Clasificarlos es trabajo de la fase 1.
- **Cada `texto` de la referencia es una frase literal del documento.** Así se puede comprobar de
  forma automática qué requisitos encontró la fase 1, sin interpretar.
- **`fuera_de_alcance` recoge frases que no son requisitos.** Si la fase 1 las convierte en
  requisitos, cuentan como falsos positivos.
- **Servicios y patrones son orientativos.** Hay más de una arquitectura válida: sirven para
  comparar la propuesta de la fase 2, no para exigir una en concreto.

## Qué permite medir

| Campo de `referencia.yaml` | Métrica (plan técnico, 11.2) |
|---|---|
| `texto` | Requisitos encontrados por la fase 1 y requisitos cubiertos o trazados al final |
| `tipo` | Acierto de la clasificación funcional / no funcional |
| `etiquetas` | Cobertura de las etiquetas de seguridad, como en `evaluation/comparacion_llm` |
| `controles_asvs`, `riesgos_api` | Porcentaje de controles de seguridad satisfechos |
| `servicio`, `servicios`, `patrones` | Comparación de la propuesta arquitectónica de la fase 2 |
| `fuera_de_alcance` | Falsos positivos de la fase 1 |

## Documento 1: tienda en línea

Una pequeña empresa de artesanías que hoy vende por redes sociales abre su tienda en línea. Tiene
tres tipos de usuario: visitante, cliente y administrador.

- **Requisitos:** 30, de los que 23 son funcionales y 7 no funcionales. Dos están escritos como
  historias de usuario y uno no funcional (RNF-01) está dentro de una sección funcional.
- **Seguridad:** 19 requisitos llevan etiquetas de seguridad y 11 ninguna, para medir también los
  falsos positivos. Usan 23 controles ASVS y 8 de los 10 riesgos del OWASP API Top 10.
- **Arquitectura orientativa:** cinco servicios (usuarios, catálogo, pedidos, pagos y
  notificaciones) y cinco patrones (`api_gateway`, `database_per_service`, `event_driven`, `saga` y
  `circuit_breaker`).
- **Fuera del alcance:** 4 frases.
- **Huecos conocidos de la base de conocimiento v1:** no tiene controles de protección de datos
  (ASVS V8) ni de registro (ASVS V7.1 a V7.3). Los requisitos afectados (RF-14, RF-20 y RF-23) lo
  indican en su `nota`.

## Regenerar los formatos

Después de editar un `requisitos.md`:

```bash
uv run evaluation/datasets/generar_formatos.py    # todos los documentos, o pasar la carpeta
uv run pytest tests/test_datasets.py
```

El script tiene sus propias dependencias (python-docx, fpdf2 y pypdf) y no las añade a `uv.lock`.
Genera el TXT, el DOCX y el PDF y comprueba que cada frase de la referencia aparece en los cuatro
formatos. Guarda las huellas en `formatos.json` y, con la fecha fija en los metadatos, regenerar sin
cambios en la fuente produce los mismos archivos.

Las pruebas fallan si se edita la fuente sin regenerar, si un formato cambia a mano, si la referencia
usa una etiqueta, un control, un riesgo o un patrón que no existe, o si el documento revela la
clasificación.

La fuente admite un subconjunto de Markdown: títulos (`#`), párrafos, listas numeradas o con
viñetas y tablas. Debe poder escribirse en Latin-1, porque el PDF usa una fuente estándar: sin
rayas largas, comillas tipográficas ni símbolos como `≤`. Las comillas `« »` sí se pueden usar.

## Añadir un documento

1. Crear la carpeta `NN_dominio/` con `requisitos.md`, siguiendo las reglas anteriores.
2. Escribir `referencia.yaml` con la misma estructura que la del documento 1.
3. Ejecutar `generar_formatos.py` y las pruebas.
