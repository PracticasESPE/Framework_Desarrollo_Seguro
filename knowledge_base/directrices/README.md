# Directrices Secure by Design

Un archivo YAML por directriz. Son los principios generales de diseño seguro que el framework
aplica a todo lo que genera; los patrones (`../patrones/`) y los controles (`../controles/`) son
formas concretas de cumplirlos.

Campos obligatorios:

| Campo | Contenido |
|---|---|
| `id` | `sbd.<tema>.<NNN>`, único en toda la base de conocimiento |
| `directriz` | Igual al nombre del archivo, sin `.yaml` |
| `descripcion` | Qué exige la directriz, en una frase |
| `aplica_a` | Componentes afectados: `servicio`, `gateway`, `base_datos`, `contenedor`, `identidad`, `pipeline` |
| `practicas` | Comprobaciones concretas que la hacen cumplir en el código generado |
| `controles_asociados` | Controles de OWASP ASVS 4.0.3 (`ASVS-V<capítulo>.<sección>.<requisito>`) |
| `cwe_mitigadas` | Debilidades del catálogo CWE que evita (`CWE-<número>`) |
| `verificacion` | Herramientas del pipeline que comprueban las prácticas |

Los mapeos a ASVS y CWE se revisaron contra ASVS 4.0.3 el 20/10; las correcciones están en
`../controles/README.md`.

Validación: `uv run framework conocimiento validar`.
