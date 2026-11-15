<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Bases de datos aisladas

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-05 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para cumplir con RNF-09, cada microservicio debe poder escalar y fallar de forma independiente, evitando que la caída de uno afecte a los demás.

## Decisión

Cada microservicio posee su propia base PostgreSQL, sin compartir esquemas.

## Justificación

RNF-09 exige que cada componente pueda escalar y fallar independientemente.

## Consecuencias

Positivas:

- Permite escalar cada servicio según su carga sin afectar a los demás.
- Mejora la resiliencia al aislar fallos y evitar cascadas de errores.
- Facilita la aplicación de políticas de seguridad específicas por servicio.
- Simplifica el mantenimiento y despliegue al tratar cada base de datos como un módulo autónomo.

Negativas:

- Incrementa el consumo de recursos (memoria, CPU, almacenamiento) por servicio.
- Aumenta la complejidad operativa al gestionar múltiples bases de datos y sus backups.
- Complica las consultas que requieran datos de varios servicios, ya que deben orquestarse a través de eventos o APIs.
- Genera mayores costes de operación y monitoreo al duplicar infraestructuras de base de datos.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
