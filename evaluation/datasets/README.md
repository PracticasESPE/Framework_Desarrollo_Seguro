# Dataset de evaluación: documentos de requisitos

Tres documentos de requisitos de dominios distintos y complejidad creciente, para los experimentos
del ciclo DSR (plan técnico, 11.3.1). Cada documento se ejecuta tres veces con cada configuración
(B0, B1 y F) para medir la variabilidad.

| Carpeta | Dominio | Complejidad | Estado |
|---|---|---|---|
| `01_tienda_en_linea/` | Tienda en línea | Baja | Listo (04/11/2026, #45) |
| `02_gestion_academica/` | Gestión académica | Media | Listo (05/11/2026, #47) |
| `03_citas_medicas/` | Citas médicas | Alta | Listo (05/11/2026, #47) |

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

## Los tres documentos

| | 1. Tienda en línea | 2. Gestión académica | 3. Citas médicas |
|---|---|---|---|
| Requisitos (funcionales / no funcionales) | 30 (23 / 7) | 38 (28 / 10) | 43 (31 / 12) |
| Historias de usuario | 2 | 4 | 3 |
| No funcionales dentro de secciones funcionales | 1 | 2 | 4 |
| Requisitos con etiquetas de seguridad / sin ellas | 19 / 11 | 25 / 13 | 28 / 15 |
| Controles ASVS usados | 23 | 20 | 19 |
| Riesgos del OWASP API Top 10 | 8 | 9 | 8 |
| Servicios / patrones orientativos | 5 / 5 | 6 / 4 | 6 / 6 |
| Frases fuera del alcance | 4 | 4 | 4 |

Entre los tres suman 111 requisitos y cubren los 10 riesgos del OWASP API Top 10. Los requisitos
sin etiquetas sirven para medir también los falsos positivos de la clasificación.

La complejidad crece en los perfiles, en las integraciones y en lo que hay que deducir:

- **Tienda en línea.** Una pequeña empresa de artesanías abre su tienda: visitante, cliente y
  administrador, pago con una pasarela externa y control del stock.
- **Gestión académica.** Un instituto con 1.200 estudiantes y cinco perfiles. Añade una matriz de
  permisos en una tabla, una carga masiva desde CSV, el doble factor para el personal, la consulta
  automática de la biblioteca con su versionado (API9) y la vista previa de enlaces externos
  (SSRF, API7).
- **Citas médicas.** Una red de tres clínicas con datos de salud. Añade el acceso de un padre a las
  citas de sus hijos, el acceso de urgencia a cualquier historia con aviso a la dirección, el
  registro de quién consulta cada historia, el laboratorio y la pasarela externos, recordatorios
  sin datos de salud y aplicaciones distintas para pacientes y personal (patrón `bff`).

Algunos requisitos esconden un control que el documento no nombra, como un código de verificación
que no se debe poder adivinar o una vista previa que descarga direcciones ajenas. Su `nota` lo
indica: la fase 2 debe inferirlo.

## Huecos de la base de conocimiento v1

La referencia solo puede citar controles que existen en `knowledge_base/`. Cuando un requisito
necesita uno que falta, su `controles_asvs` queda incompleto y su `nota` lo dice. Son candidatos para
la siguiente revisión de la base:

| Falta en la base v1 | Requisitos afectados |
|---|---|
| ASVS V8, protección de datos | Doc. 1: RF-14 y RF-23 · Doc. 2: RNF-07 · Doc. 3: RNF-02, RF-22, RNF-04, RF-31 y RNF-12 |
| ASVS V7.1 a V7.3, registro de seguridad | Doc. 1: RF-20 · Doc. 2: RF-17 · Doc. 3: RF-15 y RF-17 |
| ASVS V2.7 y V2.8, doble factor | Doc. 2: RF-04 · Doc. 3: RF-05 |
| ASVS V2.3, contraseñas iniciales | Doc. 2: RF-03 |
| ASVS V6.1, cifrado de datos guardados | Doc. 3: RNF-02 |
| CWE-1236, inyección de fórmulas en hojas de cálculo | Doc. 2: RF-27 |

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
