<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0006: Aplicar el patrón Database per Service

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema está compuesto por múltiples microservicios, cada uno con su propia base de datos PostgreSQL. Se decide aplicar el patrón Database per Service para garantizar la independencia de datos y la seguridad mediante el principio de mínimo privilegio.

## Decisión

Se aplica Database per Service: cada microservicio es dueño de su base de datos; ningún otro servicio accede a ella. Implementación prevista: prisma\_postgresql.

## Justificación

Cada servicio tiene su propia base de datos

## Consecuencias

Positivas:

- Aislamiento de datos reduce el riesgo de filtraciones entre servicios y facilita la aplicación de controles de acceso específicos por servicio.
- Escalabilidad independiente de cada servicio, permitiendo ajustar recursos según la carga sin afectar a los demás.
- Facilita la gestión de cambios de esquema, ya que cada microservicio puede evolucionar su base de datos sin coordinar con otros.
- Mejora la trazabilidad y auditoría de acceso a datos, ya que cada servicio registra sus propias operaciones de manera aislada.

Negativas:

- Incrementa la complejidad operativa al gestionar múltiples bases de datos PostgreSQL, requiriendo más tareas de mantenimiento y monitoreo.
- Aumenta el consumo de recursos y costos de infraestructura, ya que cada servicio necesita su propia instancia de base de datos.
- Dificulta la realización de consultas transversales entre servicios, ya que los datos están aislados y no se pueden unir directamente.
- Requiere más esfuerzo en la configuración de backups, replicación y políticas de retención, ya que cada base de datos debe ser gestionada de forma independiente.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V4.1.3 | Se aplica el principio de mínimo privilegio; cada usuario solo accede a los recursos para los que tiene autorización específica |
| ASVS-V13.1.4 | Las decisiones de autorización se toman tanto en la ruta (URI) como en el recurso |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-284 | Improper Access Control |
| CWE-668 | Exposure of Resource to Wrong Sphere |

## Trazabilidad

Servicios afectados: todos

No la motiva un requisito concreto: OPA la deduce de la estructura.
