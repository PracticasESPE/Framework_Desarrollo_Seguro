<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0008: Aplicar el patrón API Gateway

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere autenticación fuerte y un punto único de entrada para garantizar la protección de datos de salud y cumplir con los requisitos de acceso y limitación de peticiones. Se decide implementar un API Gateway con Traefik para centralizar la autenticación, el control de acceso y la limitación de tráfico, alineándose con los controles ASVS y mitigando CWEs de acceso indebido.

## Decisión

Se aplica API Gateway: punto único de entrada para los clientes. Implementación prevista: traefik.

## Justificación

Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones

## Consecuencias

Positivas:

- Centralización de autenticación y autorización, reduciendo la duplicación de lógica en cada microservicio y facilitando la aplicación de políticas de acceso coherentes (ASVS-V1.4.1, ASVS-V4.1.1).
- Implementación de rate limiting y control de peticiones (RNF-04) en un solo punto, simplificando la gestión de límites y reduciendo la carga de cada servicio.
- Mejora de la trazabilidad y auditoría, ya que todas las solicitudes pasan por Traefik, lo que facilita la generación de logs y la detección de anomalías.
- Facilita la incorporación de TLS y la gestión de certificados, garantizando que toda la comunicación (RNF-03) sea cifrada y que los clientes accedan siempre a través de una única dirección.

Negativas:

- Introducción de un punto único de falla; si Traefik se cae, todo el sistema queda inaccesible, requiriendo alta disponibilidad y redundancia.
- Incremento de la latencia y sobrecarga de procesamiento, ya que cada petición debe pasar por el gateway antes de llegar al microservicio, lo que puede afectar el rendimiento bajo alta carga.
- Mayor complejidad operativa y de despliegue, ya que se necesita configurar y mantener Traefik, certificados TLS y reglas de enrutamiento, además de la integración con Keycloak.
- Necesidad de escalar el gateway de forma independiente, lo que implica costos adicionales de recursos y gestión de contenedores, especialmente en un entorno autoalojado.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V4.1.1 | Las reglas de control de acceso se aplican en una capa de servicio de confianza, aunque exista un control en el cliente |
| ASVS-V1.4.1 | El control de acceso se aplica en puntos de confianza (gateway, servidor, funciones), nunca en el cliente |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-284 | Improper Access Control |
| CWE-306 | Missing Authentication for Critical Function |

## Trazabilidad

Servicios afectados: todos

| Requisito | Texto del documento |
|---|---|
| RF-01 | La red quiere que los pacientes reserven y paguen sus citas en línea, que la historia clínica sea electrónica y compartida entre las tres sedes, y que los resultados del laboratorio externo lleguen solos. La dirección es consciente de que los datos de salud son datos personales especialmente protegidos y de que una filtración afectaría a la confianza de sus pacientes. |
| RF-03 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RF-04 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RF-06 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
| RNF-01 | La sesión del personal se cierra sola tras 10 minutos sin actividad, y la de los pacientes tras 30 minutos. |
| RF-21 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RF-27 | La pasarela avisa de cada pago aprobado o devuelto, y el sistema solo acepta los avisos que demuestren venir de la pasarela. |
| RNF-03 | Toda la comunicación con el sistema debe viajar cifrada, y pacientes y personal deben entrar siempre por una única dirección. |
| RNF-04 | Ninguna persona ni ningún equipo puede hacer más de 60 peticiones por minuto, y como máximo 20 de ellas pueden ser búsquedas de horarios libres. |
