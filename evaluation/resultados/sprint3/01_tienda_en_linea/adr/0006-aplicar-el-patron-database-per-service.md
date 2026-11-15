<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0006: Aplicar el patrón Database per Service

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El patrón Database per Service se adopta para garantizar la independencia de datos entre microservicios, reduciendo acoplamientos y mejorando la seguridad mediante el principio de mínimo privilegio. Cada servicio gestiona su propia base PostgreSQL, lo que facilita la escalabilidad y la gestión de cambios sin afectar a otros componentes.

## Decisión

Se aplica Database per Service: cada microservicio es dueño de su base de datos; ningún otro servicio accede a ella. Implementación prevista: prisma\_postgresql.

## Justificación

Cada servicio tiene su propia base de datos

## Consecuencias

Positivas:

- Mayor aislamiento de datos, reduciendo la posibilidad de filtraciones entre servicios y cumpliendo con ASVS-V4.1.3 y CWE-284.
- Escalabilidad independiente, permitiendo ajustar recursos y versiones de la base de datos por servicio sin interrumpir el resto del sistema.

Negativas:

- Incremento en la cantidad de bases de datos PostgreSQL, lo que eleva el consumo de recursos y la complejidad operativa.
- Mayor esfuerzo de mantenimiento y monitoreo, ya que cada base requiere backups, actualizaciones y gestión de conexiones separadas.

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
