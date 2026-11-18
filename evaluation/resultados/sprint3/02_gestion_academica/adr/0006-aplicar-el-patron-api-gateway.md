<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0006: Aplicar el patrón API Gateway

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | plantilla del motor (se descartó la de groq: cita requisitos que no son de este ADR: RNF-06) |

## Contexto

Los requisitos que motivan esta decisión piden lo siguiente. RF-03: Las cuentas de estudiantes y docentes las crea la secretaría, y nadie puede registrarse por su cuenta; RF-04: La primera vez que una persona entra al sistema, debe cambiar la contraseña temporal que recibió por correo; RF-05: Los docentes, la secretaría y la coordinación entran con su contraseña y además con un código de un solo uso que les da una aplicación de autenticación en el m…; RF-06: Si una sesión pasa 15 minutos sin actividad, se cierra sola, porque muchos equipos del instituto son compartidos; y 3 requisitos más.

## Decisión

Se aplica API Gateway: punto único de entrada para los clientes. Implementación prevista: traefik.

## Justificación

Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones

## Consecuencias

Positivas:

- Da respuesta a 7 requisito(s) del documento.
- Mitiga CWE-284, CWE-306.
- Aplica los controles ASVS-V4.1.1, ASVS-V1.4.1.

Negativas:

- El gateway es un punto único de fallo: necesita alta disponibilidad y monitorización.

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
| RF-03 | Las cuentas de estudiantes y docentes las crea la secretaría, y nadie puede registrarse por su cuenta. |
| RF-04 | La primera vez que una persona entra al sistema, debe cambiar la contraseña temporal que recibió por correo. |
| RF-05 | Los docentes, la secretaría y la coordinación entran con su contraseña y además con un código de un solo uso que les da una aplicación de autenticación en el móvil. |
| RF-06 | Si una sesión pasa 15 minutos sin actividad, se cierra sola, porque muchos equipos del instituto son compartidos. |
| RNF-02 | Para evitar programas que reserven cupos de forma automática, cada estudiante puede hacer como máximo 20 cambios en su matrícula por día. |
| RNF-03 | Todo el acceso al sistema debe viajar cifrado y pasar por una única dirección, tanto desde el campus como desde fuera. |
| RNF-05 | Ninguna persona ni ningún equipo puede hacer más de 60 peticiones por minuto. |
