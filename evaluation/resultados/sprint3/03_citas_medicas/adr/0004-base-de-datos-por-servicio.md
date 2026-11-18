<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0004: Base de datos por servicio

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-04 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere que cada dominio de negocio mantenga su propia base de datos para permitir actualizaciones independientes y garantizar la confidencialidad de las historias clínicas. Además, se necesita cumplir con la retención de datos a largo plazo y la separación de responsabilidades entre servicios. Por ello se decide que cada microservicio tendrá su propia instancia PostgreSQL aislada.

## Decisión

Cada microservicio posee su propia base PostgreSQL aislada, sin compartir esquemas.

## Justificación

Garantiza independencia de datos y permite cumplir RF‑30 (actualizaciones independientes) y RNF‑05 (cifrado y retención por dominio).

## Consecuencias

Positivas:

- Independencia de despliegue: actualizaciones de esquema sin afectar otros servicios.
- Seguridad de datos: cifrado y retención aplicados por dominio sin compartir esquema.
- Escalabilidad: cada servicio puede escalar su base de datos según demanda.
- Cumplimiento de requisitos RF-30 y RNF-05.

Negativas:

- Mayor complejidad operativa: gestión de múltiples bases de datos y backups.
- Incremento de costos de infraestructura: más instancias de PostgreSQL.
- Dificultad en consultas transversales: no se pueden hacer joins entre dominios.
- Mayor latencia en operaciones que requieren datos de varios dominios.

## Trazabilidad

Servicios afectados: `historia_clinica`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-30 | La agenda, la historia clínica, el laboratorio y los pagos deben poder actualizarse por separado, cada uno con sus propios datos, y a los datos de la historia clínica solo accede su propio servicio. |
| RNF-05 | Las historias clínicas se guardan cifradas y se conservan al menos 15 años, aunque el paciente cierre su cuenta. |
