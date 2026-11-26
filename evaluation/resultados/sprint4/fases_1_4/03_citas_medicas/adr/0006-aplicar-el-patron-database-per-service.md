<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0006: Aplicar el patrón Database per Service

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para garantizar la independencia de datos y la seguridad de cada microservicio, se decide que cada uno posea su propia base de datos PostgreSQL, evitando accesos cruzados y cumpliendo con los principios de mínimo privilegio y autorización por recurso.

## Decisión

Se aplica Database per Service: cada microservicio es dueño de su base de datos; ningún otro servicio accede a ella. Implementación prevista: prisma\_postgresql.

## Justificación

Cada servicio tiene su propia base de datos

## Consecuencias

Positivas:

- Aislamiento de datos que previene filtraciones entre servicios y facilita la aplicación de controles de acceso específicos (ASVS-V4.1.3, ASVS-V13.1.4).
- Escalabilidad independiente: cada servicio puede crecer y optimizar su base sin afectar a los demás.
- Independencia de despliegue y pruebas: cambios en la estructura de datos de un servicio no rompen la funcionalidad de los demás.
- Resiliencia: fallos en una base de datos no propagarán caídas a otros servicios.

Negativas:

- Mayor número de instancias de PostgreSQL, incrementando consumo de recursos y costos operativos.
- Complejidad en la gestión de backups y restauraciones, ya que cada base debe ser respaldada por separado.
- Dificultad para realizar consultas transversales entre servicios, requiriendo patrones de integración adicionales.
- Incremento de la carga operativa de monitoreo y mantenimiento de múltiples bases de datos.

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
