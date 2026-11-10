<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0006: Aplicar el patrón Database per Service

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema está compuesto por múltiples microservicios, cada uno con su propia base de datos PostgreSQL. Para garantizar la independencia y la seguridad de los datos, se decide aplicar el patrón Database per Service. Con esta arquitectura, cada microservicio es propietario de su base de datos y no permite el acceso directo desde otros servicios. Esta decisión facilita la gestión de permisos y reduce la superficie de ataque, alineándose con los controles &lt;requisito-CODIGO ASVS-V4.1.3&gt;Se aplica el principio de mínimo privilegio; cada usuario solo accede a los recursos para los que tiene autorización específica;&lt;/requisito-CODIGO&gt; y &lt;requisito-CODIGO ASVS-V13.1.4&gt;Las decisiones de autorización se toman tanto en la ruta (URI) como en el recurso;&lt;/requisito-CODIGO&gt;, así como con los CWE &lt;requisito-CODIGO CWE-284&gt;Improper Access Control;&lt;/requisito-CODIGO&gt; y &lt;requisito-CODIGO CWE-668&gt;Exposure of Resource to Wrong Sphere;&lt;/requisito-CODIGO&gt;.

## Decisión

Se aplica Database per Service: cada microservicio es dueño de su base de datos; ningún otro servicio accede a ella. Implementación prevista: prisma\_postgresql.

## Justificación

Cada servicio tiene su propia base de datos

## Consecuencias

Positivas:

- Mayor aislamiento de datos, reduciendo la posibilidad de que un fallo en un servicio afecte a otros.
- Facilita la escalabilidad independiente de cada microservicio, ya que cada base de datos puede crecer según sus necesidades.
- Mejora la seguridad al aplicar el principio de mínimo privilegio, limitando el acceso a los datos solo al servicio propietario.

Negativas:

- Incrementa la complejidad operativa, ya que se deben gestionar y respaldar múltiples bases de datos PostgreSQL.
- Aumenta el consumo de recursos (memoria, CPU, almacenamiento) al duplicar la infraestructura de base de datos.
- Complica la gestión de transacciones distribuidas y la consistencia de datos entre servicios.

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
