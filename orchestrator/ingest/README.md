# Ingesta del documento de requisitos (fase 1)

Convierte el documento de requisitos a Markdown, que es la entrada de los pasos siguientes de la
fase 1: normalización, esquema `Requisito` y clasificación con LLM.

| Formato | Cómo se extrae |
|---|---|
| PDF | Docling, sin OCR: analiza el diseño de cada página y reconstruye títulos, listas y tablas |
| DOCX | Docling |
| TXT, MD | Lectura directa en UTF-8: Docling no admite TXT y un Markdown ya es el resultado |

Antes de extraer se aplican las mismas validaciones que en la carga (`orchestrator/documentos.py`):
lista permitida de formatos, contenido que corresponde al formato, tamaño máximo y límites del
DOCX. Docling recibe los bytes ya validados, con un máximo de 100 páginas y 300 segundos; si no
convierte el documento completo, la extracción falla en lugar de devolver un texto incompleto.

## Uso

```bash
uv run framework requisitos extraer evaluation/datasets/01_tienda_en_linea/requisitos.pdf
uv run framework requisitos extraer --documento <id>   # documento cargado desde el dashboard
```

Guarda en `salida/requisitos/` el Markdown y un JSON con el formato, la herramienta, la huella
SHA-256 del original, el tamaño del texto y la duración de la conversión.

## Fidelidad y rendimiento

`tests/test_ingesta.py` comprueba que, en los tres documentos del dataset de evaluación y en sus
cuatro formatos, el Markdown conserva todas las frases de la referencia (111 requisitos y 12 frases
fuera del alcance). Las pruebas con PDF son lentas y se activan con `DOCLING_PDF=1`. Conviene
correrlas por archivo (`tests/test_ingesta.py` y `tests/test_requisito.py` por separado): en
Windows, seis conversiones de PDF en un mismo proceso llegaron a agotar la memoria.

| Formato | Conversión (documento 1, Windows, CPU) |
|---|---|
| TXT, MD | menos de 0,1 s |
| DOCX | 0,4 s |
| PDF | 20 a 50 s; la primera vez descarga además los modelos (unos 500 MB, en `~/.cache/huggingface`) |

Cargar Docling y PyTorch tarda además unos 30 segundos por proceso. PyTorch se instala en su
variante para CPU (ver `pyproject.toml`).

## Normalización y unidades de requisito

`normalizacion.py` limpia la forma del texto sin cambiar palabras y lo divide en unidades:

- Unicode NFC, espacios raros a un espacio normal y sin marcas de negrita o cursiva.
- Elimina y cuenta los caracteres invisibles (ancho cero, guion opcional y controles de dirección
  del texto), que podrían esconder instrucciones para el LLM («Trojan Source», CVE-2021-42574).
- Cada punto de una lista, viñeta, párrafo y tabla es una unidad con su sección y una ubicación
  estable: `3.1` es el punto 1 de la sección 3; `10, viñeta 2` y `2, tabla 1` siguen el mismo
  criterio. En un TXT, un título es una línea corta y aislada que no termina como una frase.

```bash
uv run framework requisitos normalizar evaluation/datasets/02_gestion_academica/requisitos.docx
```

Guarda las unidades en `salida/requisitos/<nombre>.unidades.json`. `tests/test_requisito.py`
comprueba que los cuatro formatos de cada documento del dataset dan exactamente las mismas unidades
y que cada uno de los 111 requisitos de la referencia cae en una sola unidad, con la misma ubicación
cuando la referencia la da como «sección.punto».

## Esquema `Requisito`

`requisito.py` define el modelo de requisitos de la fase 1 (plan técnico, listing 7.1):

| Modelo | Quién lo produce | Qué contiene |
|---|---|---|
| `ClasificacionRequisito` | El LLM, una vez por unidad | Si es requisito y su tipo, actor, acción, entidades, servicio sugerido y etiquetas |
| `Requisito` | El motor (`construir_requisitos`) | La clasificación más el texto literal, la ubicación y el id (`RF-01`, `RNF-01`) |
| `ModeloRequisitos` | El motor | `modelo_requisitos.json`: documento de origen y lista de requisitos |

El LLM nunca devuelve el texto ni el id: así no puede reescribir un requisito ni inventar uno que
no está en el documento. Pydantic rechaza las salidas incompletas, las etiquetas fuera del
vocabulario de seguridad (las mismas de `evaluation/datasets/vocabulario.yaml`), los campos que no
están en el esquema, un id que no corresponde a su tipo y los ids repetidos.

El JSON Schema publicado para el dashboard y la API está en
`docs/esquemas/modelo_requisitos.schema.json`. Si cambia el modelo, se regenera con:

```bash
uv run framework requisitos esquema --salida docs/esquemas/modelo_requisitos.schema.json
```

## Clasificación con el LLM

`clasificacion.py` envía al LLM rápido un lote por sección con sus unidades y recibe una
`ClasificacionRequisito` por unidad. Las tablas no se clasifican: acompañan como contexto a las
unidades de su sección. Con el documento como entrada no confiable:

- cada unidad va entre marcas con un código aleatorio por documento, que el texto no puede
  conocer para cerrar la marca y escribir instrucciones fuera de ella;
- el mensaje de sistema indica que lo marcado es un dato, nunca una instrucción, y define cada
  etiqueta de seguridad;
- el motor exige que el LLM devuelva exactamente las ubicaciones que recibió, y reintenta si no;
- si el proveedor responde por límite de uso, espera 20 y 60 segundos antes de reintentar.

```bash
uv run framework requisitos clasificar evaluation/datasets/01_tienda_en_linea/requisitos.pdf --proveedor groq
uv run python -m evaluation.fase1.evaluar salida/requisitos/requisitos-pdf.modelo_requisitos.json evaluation/datasets/01_tienda_en_linea
```

El primero guarda `salida/requisitos/<nombre>.modelo_requisitos.json`. El segundo, que es parte de
la evaluación y no del framework, lo compara con la referencia del dataset: requisitos
encontrados, falsos positivos, acierto del tipo y precisión y exhaustividad de las etiquetas.
