<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0008: Aplicar el patrón API Gateway

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere autenticación robusta y control de acceso centralizado, además de limitar el número de peticiones por minuto y garantizar que toda la comunicación sea cifrada. Para cumplir con los requisitos de autenticación de pacientes y personal, así como con la limitación de peticiones y la necesidad de un punto único de entrada, se decide implementar un API Gateway con Traefik. Este enfoque permite centralizar la gestión de TLS, la autenticación con Keycloak y la aplicación de políticas de rate‑limiting, reduciendo la complejidad de cada microservicio.

## Decisión

Se aplica API Gateway: punto único de entrada para los clientes. Implementación prevista: traefik.

## Justificación

Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones

## Consecuencias

Positivas:

- Centraliza la autenticación y autorización, reduciendo la duplicación de lógica de acceso en cada microservicio y garantizando que los controles de acceso se apliquen en una capa de confianza, conforme a ASVS-V4.1.1 y ASVS-V1.4.1.
- Facilita la aplicación de políticas de rate‑limiting y protección contra ataques de denegación de servicio, cumpliendo con el requisito RNF‑10 de limitar peticiones a 60/minuto y 20 búsquedas de horarios libres.
- Simplifica la gestión de TLS y la redirección de tráfico, asegurando que toda la comunicación viaje cifrada y que los usuarios accedan siempre por una única dirección, como exige RNF‑09.
- Mejora la observabilidad y el monitoreo centralizado del tráfico de entrada, permitiendo registrar métricas y logs de manera uniforme sin modificar cada microservicio.

Negativas:

- Introduce un punto único de falla; si Traefik se cae, todo el sistema queda inaccesible, lo que aumenta el riesgo de interrupciones operativas.
- Añade latencia adicional al enrutar cada solicitud a través del gateway, lo que puede afectar el rendimiento de los microservicios, especialmente bajo alta carga.
- Requiere mantenimiento y configuración adicional del gateway, incrementando la complejidad operativa y el coste de operación, aunque no implica licencias.

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
| RF-02 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RNF-02 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RNF-03 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
| RNF-04 | La sesión del personal se cierra sola tras 10 minutos sin actividad, y la de los pacientes tras 30 minutos. |
| RF-18 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RNF-09 | Toda la comunicación con el sistema debe viajar cifrada, y pacientes y personal deben entrar siempre por una única dirección. |
| RNF-10 | Ninguna persona ni ningún equipo puede hacer más de 60 peticiones por minuto, y como máximo 20 de ellas pueden ser búsquedas de horarios libres. |
