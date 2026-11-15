<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0001: División en microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-01 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema debe soportar funcionalidades críticas de salud, como reservas, pagos, historia clínica y laboratorio, con requisitos de seguridad y disponibilidad. Dividir en microservicios permite agrupar dominios cohesivos y evitar servicios diminutos, facilitando la independencia de datos y despliegues. Esta arquitectura responde a la necesidad de escalabilidad y cumplimiento de normativas de protección de datos.

## Decisión

Se definieron seis microservicios (usuarios, citas, historia\_clinica, pagos, laboratorio y administracion) para agrupar funcionalidades cohesivas y evitar servicios diminutos.

## Justificación

Los requisitos funcionales y no funcionales se agrupan naturalmente en estos dominios; el número de servicios (6) está dentro del rango recomendado (3‑7) y permite independencia de datos y despliegues.

## Consecuencias

Positivas:

- Mayor independencia de datos y despliegues, lo que permite actualizar cada dominio sin afectar a los demás y facilita la escalabilidad horizontal.
- Mejor aislamiento de fallos; un problema en el servicio de laboratorio no interrumpe la agenda o la historia clínica.
- Facilita la aplicación de controles de seguridad específicos por dominio, cumpliendo requisitos de confidencialidad y auditoría.

Negativas:

- Incremento de la complejidad operativa: más contenedores, bases de datos y orquestación, lo que exige mayor esfuerzo de DevOps y monitoreo.
- Mayor consumo de recursos y costos de infraestructura, ya que cada microservicio necesita su propia base de datos PostgreSQL y su instancia de RabbitMQ.
- Aumento de latencia en interacciones entre dominios, ya que las llamadas entre microservicios atraviesan la red y RabbitMQ.

## Trazabilidad

Servicios afectados: `usuarios`, `citas`, `historia_clinica`, `pagos`, `laboratorio`, `administracion`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-01 | La red quiere que los pacientes reserven y paguen sus citas en línea, que la historia clínica sea electrónica y compartida entre las tres sedes, y que los resultados del laboratorio externo lleguen solos. La dirección es consciente de que los datos de salud son datos personales especialmente protegidos y de que una filtración afectaría a la confianza de sus pacientes. |
| RF-02 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RF-03 | Un paciente puede gestionar desde su propia cuenta las citas de sus hijos menores de edad, y solo las de ellos. |
| RF-04 | Cada médico define su propio horario de atención por sede y por día, en bloques de 20 o 40 minutos según la especialidad. |
| RF-05 | El paciente busca horarios libres por especialidad, médico, sede y fecha, y reserva una cita en línea. |
| RF-06 | Un mismo horario nunca puede quedar reservado para dos pacientes, aunque lo reserven en el mismo instante desde la web y desde recepción. |
| RF-07 | Un paciente puede tener como máximo dos citas pendientes por especialidad, para que nadie acapare la agenda. |
| RF-08 | Si un paciente falta a tres citas en seis meses sin cancelarlas, durante el mes siguiente solo puede reservar a través de recepción. |
| RF-09 | Recepción reserva, cambia y cancela citas en nombre de cualquier paciente que llame o acuda a la sede. |
| RF-10 | El paciente cancela o cambia su cita sin costo hasta 24 horas antes de la hora reservada. |
| RF-11 | Durante la consulta, el médico registra el motivo, la exploración, el diagnóstico con su código CIE-10 y el tratamiento. |
| RF-12 | El médico solo puede abrir la historia clínica de los pacientes que tienen o tuvieron una cita con él. |
| RF-13 | En una urgencia, un médico puede abrir la historia de cualquier paciente indicando el motivo; ese acceso queda registrado y la dirección médica recibe un aviso en el momento. |
| RF-14 | Una nota de consulta firmada ya no se puede modificar, y cualquier corrección se añade como una nota nueva que hace referencia a la anterior. |
| RF-15 | Queda registro de cada persona que consulta una historia clínica, con la fecha y el motivo, y el paciente puede ver quién ha consultado la suya. |
| RF-16 | El médico emite recetas electrónicas con un código que la farmacia usa para comprobar que la receta es auténtica. |
| RF-17 | El paciente descarga en PDF su historia clínica completa cuando la necesite. |
| RF-18 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RF-19 | Cuando llega un resultado, el médico que pidió el examen recibe un aviso, y el paciente lo ve en su cuenta solo después de que el médico lo haya revisado. |
| RF-20 | El paciente paga el copago de la cita en línea con tarjeta, a través de una pasarela de pagos externa, y la red nunca guarda los datos de la tarjeta. |
| RF-21 | Una cita reservada en línea solo queda confirmada cuando se aprueba su pago, y si no se paga en 15 minutos el horario vuelve a quedar libre. |
| RF-22 | Si el médico cancela una cita ya pagada, el pago se devuelve al paciente de forma automática. |
| RF-23 | El paciente recibe un recordatorio por correo y por mensaje de texto 24 horas antes de su cita. |
| RF-24 | La dirección médica consulta indicadores de ocupación de la agenda, de ausencias y de tiempos de espera por sede y especialidad, sin ver datos que identifiquen a los pacientes. |
| RF-25 | La dirección médica gestiona los médicos, sus especialidades y las sedes donde atiende cada uno. |
| RF-26 | Como paciente, quiero entrar a una teleconsulta desde el enlace que aparece en mi cita, para no ir a la clínica cuando mi médico lo permita. |
| RF-27 | Como médico, quiero ver en una sola pantalla mis citas del día en todas las sedes, para organizar mis traslados. |
| RF-28 | Como paciente, quiero pedir que se corrijan mis datos personales y que se eliminen los que ya no sean necesarios, para ejercer mis derechos sobre ellos. |
| RF-29 | La web de los pacientes y la aplicación del personal son distintas, y cada una recibe solo la información que necesita. |
| RF-30 | La agenda, la historia clínica, el laboratorio y los pagos deben poder actualizarse por separado, cada uno con sus propios datos, y a los datos de la historia clínica solo accede su propio servicio. |
| RNF-01 | Cada perfil solo ve de la historia clínica lo que indica la siguiente tabla. |
| RNF-02 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RNF-03 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
| RNF-04 | La sesión del personal se cierra sola tras 10 minutos sin actividad, y la de los pacientes tras 30 minutos. |
| RNF-05 | Las historias clínicas se guardan cifradas y se conservan al menos 15 años, aunque el paciente cierre su cuenta. |
| RNF-06 | Si el laboratorio no responde, el resto del sistema sigue funcionando y los resultados se reciben cuando vuelva a estar disponible. |
| RNF-07 | La pasarela avisa de cada pago aprobado o devuelto, y el sistema solo acepta los avisos que demuestren venir de la pasarela. |
| RNF-08 | Los recordatorios y los correos nunca incluyen el motivo de la consulta, el diagnóstico ni la especialidad, solo la fecha, la hora y la sede. |
| RNF-09 | Toda la comunicación con el sistema debe viajar cifrada, y pacientes y personal deben entrar siempre por una única dirección. |
| RNF-10 | Ninguna persona ni ningún equipo puede hacer más de 60 peticiones por minuto, y como máximo 20 de ellas pueden ser búsquedas de horarios libres. |
| RNF-11 | El sistema debe estar disponible el 99,5 % del tiempo en el horario de atención de las clínicas, de 07:00 a 20:00. |
| RNF-12 | Los mensajes de error no muestran detalles internos del sistema. |
| RNF-13 | Las claves del laboratorio, de la pasarela, del envío de mensajes y de las bases de datos se guardan en un almacén de secretos y nunca en el código. |
| RNF-14 | Se hace un respaldo cifrado cada día, y cada tres meses se comprueba que se puede restaurar. |
