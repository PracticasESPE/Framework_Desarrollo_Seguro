# Patrones de microservicios

Un archivo YAML por patrón. Campos obligatorios: `id`, `patron`, `descripcion`,
`aplica_cuando`, `controles_asociados`, `cwe_mitigadas`, `implementacion`.

- `id`: `arq.<tema>.<NNN>`, único en toda la base.
- `aplica_cuando`: lista de condiciones (`etiqueta` o `numero_servicios_minimo`) que usará OPA para inferir el patrón.
- Los mapeos a ASVS y CWE son una primera propuesta; se revisan contra ASVS 4.0.3 y el catálogo CWE en la tarea de controles (20/10).
