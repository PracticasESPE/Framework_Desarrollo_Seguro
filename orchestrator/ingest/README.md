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
fuera del alcance). Las pruebas con PDF son lentas y se activan con `DOCLING_PDF=1`.

| Formato | Conversión (documento 1, Windows, CPU) |
|---|---|
| TXT, MD | menos de 0,1 s |
| DOCX | 0,4 s |
| PDF | 20 a 50 s; la primera vez descarga además los modelos (unos 500 MB, en `~/.cache/huggingface`) |

Cargar Docling y PyTorch tarda además unos 30 segundos por proceso. PyTorch se instala en su
variante para CPU (ver `pyproject.toml`).
