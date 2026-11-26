<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0001: División en 6 microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Decisión D-01 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Se necesita dividir el sistema en microservicios para alinearlo con los dominios funcionales y permitir escalabilidad independiente. Cada microservicio gestiona su propia base de datos PostgreSQL y se comunica mediante RabbitMQ, garantizando aislamiento de datos. Esta arquitectura facilita la evolución de cada dominio sin afectar a los demás.

## Decisión

Se crean seis microservicios (auth, citas, historia, laboratorio, pagos, gestion) alineados con bounded contexts claros y con bases de datos independientes.

## Justificación

Los requisitos funcionales están agrupados por dominio (autenticación, agenda, historia clínica, resultados de laboratorio, pagos y gestión operativa). Evita servicios diminutos y permite escalar cada dominio de forma independiente, cumpliendo con RF-01, RF-07, RF-14, RF-21, RF-24 y RF-30.

## Consecuencias

Positivas:

- Escalabilidad independiente: cada dominio puede escalar según demanda sin afectar a otros servicios.
- Aislamiento de datos y seguridad: la separación de bases de datos reduce el riesgo de filtraciones y facilita el cumplimiento de requisitos de protección de datos.
- Mantenimiento y despliegue más sencillo: cambios en un microservicio no requieren redeploy de todo el sistema, reduciendo tiempo de inactividad.
- Mejora de la resiliencia: fallos en un servicio no bloquean el funcionamiento de los demás, cumpliendo con requisitos de disponibilidad.

Negativas:

- Mayor complejidad operativa: se deben gestionar múltiples contenedores, bases de datos y orquestación, aumentando la carga de administración.
- Incremento de recursos: cada microservicio necesita su propia instancia de PostgreSQL y RabbitMQ, elevando consumo de CPU y memoria.
- Latencia inter-servicios: las llamadas entre microservicios añaden tiempo de respuesta, lo que puede afectar la experiencia del usuario en escenarios críticos.
- Coste de monitoreo y trazabilidad: se requiere un sistema de observabilidad más robusto para rastrear transacciones a través de varios servicios.

## Trazabilidad

Servicios afectados: `auth`, `citas`, `historia`, `laboratorio`, `pagos`, `gestion`

| Requisito | Texto del documento |
|---|---|
| RF-01 | La red quiere que los pacientes reserven y paguen sus citas en línea, que la historia clínica sea electrónica y compartida entre las tres sedes, y que los resultados del laboratorio externo lleguen solos. La dirección es consciente de que los datos de salud son datos personales especialmente protegidos y de que una filtración afectaría a la confianza de sus pacientes. |
| RF-02 | Cada perfil solo ve de la historia clínica lo que indica la siguiente tabla. |
| RF-03 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RF-04 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RF-05 | Un paciente puede gestionar desde su propia cuenta las citas de sus hijos menores de edad, y solo las de ellos. |
| RF-06 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
| RF-07 | Cada médico define su propio horario de atención por sede y por día, en bloques de 20 o 40 minutos según la especialidad. |
| RF-08 | El paciente busca horarios libres por especialidad, médico, sede y fecha, y reserva una cita en línea. |
| RF-09 | Un mismo horario nunca puede quedar reservado para dos pacientes, aunque lo reserven en el mismo instante desde la web y desde recepción. |
| RF-10 | Un paciente puede tener como máximo dos citas pendientes por especialidad, para que nadie acapare la agenda. |
| RF-11 | Si un paciente falta a tres citas en seis meses sin cancelarlas, durante el mes siguiente solo puede reservar a través de recepción. |
| RF-12 | Recepción reserva, cambia y cancela citas en nombre de cualquier paciente que llame o acuda a la sede. |
| RF-13 | El paciente cancela o cambia su cita sin costo hasta 24 horas antes de la hora reservada. |
| RF-14 | Durante la consulta, el médico registra el motivo, la exploración, el diagnóstico con su código CIE-10 y el tratamiento. |
| RF-15 | El médico solo puede abrir la historia clínica de los pacientes que tienen o tuvieron una cita con él. |
| RF-16 | En una urgencia, un médico puede abrir la historia de cualquier paciente indicando el motivo; ese acceso queda registrado y la dirección médica recibe un aviso en el momento. |
| RF-17 | Una nota de consulta firmada ya no se puede modificar, y cualquier corrección se añade como una nota nueva que hace referencia a la anterior. |
| RF-18 | Queda registro de cada persona que consulta una historia clínica, con la fecha y el motivo, y el paciente puede ver quién ha consultado la suya. |
| RF-19 | El médico emite recetas electrónicas con un código que la farmacia usa para comprobar que la receta es auténtica. |
| RF-20 | El paciente descarga en PDF su historia clínica completa cuando la necesite. |
| RF-21 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RF-22 | Cuando llega un resultado, el médico que pidió el examen recibe un aviso, y el paciente lo ve en su cuenta solo después de que el médico lo haya revisado. |
| RF-23 | Si el laboratorio no responde, el resto del sistema sigue funcionando y los resultados se reciben cuando vuelva a estar disponible. |
| RF-24 | El paciente paga el copago de la cita en línea con tarjeta, a través de una pasarela de pagos externa, y la red nunca guarda los datos de la tarjeta. |
| RF-25 | Una cita reservada en línea solo queda confirmada cuando se aprueba su pago, y si no se paga en 15 minutos el horario vuelve a quedar libre. |
| RF-26 | Si el médico cancela una cita ya pagada, el pago se devuelve al paciente de forma automática. |
| RF-27 | La pasarela avisa de cada pago aprobado o devuelto, y el sistema solo acepta los avisos que demuestren venir de la pasarela. |
| RF-28 | El paciente recibe un recordatorio por correo y por mensaje de texto 24 horas antes de su cita. |
| RF-29 | Los recordatorios y los correos nunca incluyen el motivo de la consulta, el diagnóstico ni la especialidad, solo la fecha, la hora y la sede. |
| RF-30 | La dirección médica consulta indicadores de ocupación de la agenda, de ausencias y de tiempos de espera por sede y especialidad, sin ver datos que identifiquen a los pacientes. |
| RF-31 | La dirección médica gestiona los médicos, sus especialidades y las sedes donde atiende cada uno. |
| RF-32 | Como paciente, quiero entrar a una teleconsulta desde el enlace que aparece en mi cita, para no ir a la clínica cuando mi médico lo permita. |
| RF-33 | Como médico, quiero ver en una sola pantalla mis citas del día en todas las sedes, para organizar mis traslados. |
| RF-34 | Como paciente, quiero pedir que se corrijan mis datos personales y que se eliminen los que ya no sean necesarios, para ejercer mis derechos sobre ellos. |
| RF-35 | La web de los pacientes y la aplicación del personal son distintas, y cada una recibe solo la información que necesita. |
| RF-36 | La agenda, la historia clínica, el laboratorio y los pagos deben poder actualizarse por separado, cada uno con sus propios datos, y a los datos de la historia clínica solo accede su propio servicio. |
