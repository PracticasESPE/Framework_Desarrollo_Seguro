<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0001: División en 7 microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-01 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El instituto necesita un sistema en línea que permita a estudiantes, docentes y personal administrativo gestionar sus procesos académicos desde cualquier lugar, con trazabilidad de cambios y cumplimiento de periodos académicos. Para cumplir con los requisitos funcionales y de seguridad, se decide dividir la aplicación en siete microservicios alineados a los bounded contexts del dominio académico y de seguridad.

## Decisión

Se crean siete microservicios (usuarios, catalogo, matriculas, notas, asistencia, certificados, notificaciones) alineados a bounded contexts del dominio académico y de seguridad.

## Justificación

Los requisitos funcionales están agrupados por áreas de negocio (identidad, catálogo académico, matrícula, notas, asistencia, certificados y notificaciones). Esta división evita servicios diminutos y permite que cada servicio sea dueño de sus entidades, cumpliendo con RF-01, RF-03, RF-11, RF-16, RF-15, RF-21 y RF-24.

## Consecuencias

Positivas:

- Aislamiento de responsabilidades: cada microservicio gestiona un dominio específico, lo que facilita el mantenimiento y la evolución independiente de cada área.
- Escalabilidad horizontal: los servicios que experimentan mayor carga, como el de notas o certificaciones, pueden escalarse de forma independiente sin afectar al resto del sistema.
- Resiliencia mejorada: fallos en un microservicio no provocan caídas globales, ya que los demás servicios continúan operando.
- Cumplimiento de requisitos: la división permite asignar de manera clara los controles de seguridad y auditoría a cada servicio, facilitando la trazabilidad de cambios y la generación de certificados.

Negativas:

- Mayor complejidad operativa: la gestión de siete contenedores, bases de datos y colas RabbitMQ aumenta la carga de administración y el riesgo de errores de configuración.
- Incremento de latencia interservicios: las llamadas entre microservicios añaden tiempo de respuesta, especialmente en flujos que requieren datos de varios dominios.
- Sobrecarga de recursos: cada microservicio necesita su propia instancia de PostgreSQL y su propio entorno, lo que eleva el consumo de CPU y memoria en el clúster.
- Mayor esfuerzo de pruebas: asegurar la coherencia de datos y la correcta interacción entre servicios exige pruebas de integración más extensas y complejas.

## Trazabilidad

Servicios afectados: `usuarios`, `catalogo`, `matriculas`, `notas`, `asistencia`, `certificados`, `notificaciones`

| Requisito | Texto del documento |
|---|---|
| RF-01 | El instituto quiere un sistema en línea para estudiantes, docentes y personal administrativo, que se pueda usar desde cualquier lugar y que deje constancia de cada cambio en las notas. Tiene dos periodos académicos al año. |
| RF-03 | Las cuentas de estudiantes y docentes las crea la secretaría, y nadie puede registrarse por su cuenta. |
| RF-07 | La secretaría registra a los estudiantes uno a uno o en bloque desde un archivo CSV de hasta 2.000 filas, y si alguna fila tiene datos inválidos el sistema rechaza el archivo completo e indica cuáles son. |
| RF-11 | El estudiante se matricula en línea, y solo entre las fechas de matrícula que fija la coordinación para cada periodo. |
| RF-16 | El docente registra tres notas parciales por estudiante, cada una entre 0 y 10 con dos decimales, y el sistema calcula el promedio final. |
| RF-15 | El docente registra la asistencia de cada clase, y solo en los paralelos que tiene asignados. |
| RF-21 | El estudiante pide en línea certificados de matrícula y de notas, y los recibe en PDF en menos de un día hábil. |
| RF-24 | El estudiante recibe un correo cuando se publican sus notas y cuando su matrícula queda confirmada. |
