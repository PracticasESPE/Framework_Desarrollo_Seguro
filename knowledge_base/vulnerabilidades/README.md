# Catálogos de vulnerabilidades

| Archivo | Contenido |
|---|---|
| `cwe.yaml` | Debilidades del catálogo CWE (Common Weakness Enumeration, la lista de MITRE de tipos de fallos de software) citadas por la base de conocimiento |
| `owasp_api_top10.yaml` | Los diez riesgos del OWASP API Security Top 10, edición 2023, con sus CWE y los controles ASVS que los mitigan |

En `owasp_api_top10.yaml`, las CWE son las referencias que publica OWASP para cada riesgo
(solo debilidades, no categorías CWE) y los controles son una propuesta del proyecto.
API6 no tiene CWE porque OWASP no le asocia ninguna; API9 no tiene control porque ninguno de
los requisitos del catálogo actual lo cubre.

El validador (`uv run framework conocimiento validar`) exige que toda CWE citada en patrones,
directrices, controles o riesgos exista en `cwe.yaml`.

Las descripciones largas de CWE y de las guías de OWASP se convertirán en fragmentos con
embeddings (representaciones numéricas del significado de un texto) para la búsqueda GraphRAG,
en la tarea del 22/10.
