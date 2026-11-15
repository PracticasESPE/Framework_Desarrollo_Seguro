<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0008: Aplicar el patrón API Gateway

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere un punto único de entrada para gestionar autenticación, registro y limitación de peticiones. Además, se necesita centralizar el control de acceso y la protección de datos sensibles. El uso de Traefik como API Gateway permite cumplir con los requisitos de cifrado, bloqueo de cuentas y eliminación de datos. Esta arquitectura facilita la aplicación de controles ASVS y mitigación de CWE-284 y CWE-306.

## Decisión

Se aplica API Gateway: punto único de entrada para los clientes. Implementación prevista: traefik.

## Justificación

Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones

## Consecuencias

Positivas:

- Centraliza la autenticación y el registro, reduciendo duplicación de lógica en cada microservicio.
- Permite aplicar rate limiting y bloqueo de cuentas en un solo punto, cumpliendo RNF-06 y RF-03.
- Aplica controles de acceso en capa de confianza, alineándose con ASVS-V4.1.1 y ASVS-V1.4.1, mitigando CWE-284 y CWE-306.
- Facilita auditoría y trazabilidad de peticiones, mejorando la visibilidad de la actividad del cliente.

Negativas:

- Introduce un punto único de fallo; si Traefik falla, toda la API queda inaccesible.
- Requiere alta disponibilidad y configuración de balanceo de carga, aumentando la complejidad operativa.
- Aumenta la latencia de cada petición al pasar por el gateway, impactando el rendimiento.
- Necesita gestión de sesiones y tokens en el gateway, lo que añade complejidad de implementación y mantenimiento.

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
| RF-02 | El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe. |
| RF-03 | Para entrar a su cuenta, el cliente usa su correo y su contraseña; después de cinco intentos fallidos seguidos, la cuenta queda bloqueada durante quince minutos. |
| RF-05 | Cuando el cliente cierra la sesión, su acceso deja de servir de inmediato y debe volver a identificarse para seguir comprando. |
| RF-21 | Como cliente, quiero eliminar mi cuenta y mis datos personales, salvo los que la ley obligue a conservar de mis compras, para dejar de figurar como cliente de la tienda. |
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
