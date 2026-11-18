<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Seguridad y autenticación

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Se requiere garantizar la confidencialidad, autenticación y autorización de los usuarios, así como proteger la tienda contra abusos y cumplir con los requisitos de registro y eliminación de datos. Para ello se decide integrar Keycloak como IdP, usar JWT en Traefik, aplicar TLS en todas las comunicaciones y limitar peticiones por IP.

## Decisión

Integrar Keycloak como IdP y usar JWT en el gateway Traefik. Aplicar TLS en todas las comunicaciones y límite de peticiones.

## Justificación

Requisitos RNF-05, RNF-06, RNF-04, RF-01, RF-02, RF-04 y RF-20 requieren autenticación, autorización y protección contra abuso.

## Consecuencias

Positivas:

- Mejora la seguridad al cifrar todas las comunicaciones y centralizar la gestión de identidades con Keycloak.
- Facilita la implementación de políticas de acceso y auditoría gracias a los tokens JWT y la trazabilidad de sesiones.
- Cumple con los requisitos de registro, bloqueo y eliminación de cuentas, garantizando la protección de datos personales.
- Reduce la superficie de ataque al limitar el número de peticiones por IP y evitar abusos de la API.

Negativas:

- Aumenta la complejidad operativa al requerir la gestión y renovación de certificados TLS y la configuración de Keycloak.
- Puede introducir latencia adicional en la autenticación y autorización al pasar por el gateway y el IdP.
- El límite de 100 peticiones/minuto puede afectar la experiencia de usuarios legítimos con tráfico alto.
- Requiere monitoreo y mantenimiento continuo de la infraestructura de Keycloak y Traefik, incrementando costos de operación.

## Trazabilidad

Servicios afectados: `usuarios`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
| RNF-04 | Solo el personal de la empresa puede ser administrador, y ninguna función de administración está disponible para los clientes. |
| RF-01 | El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe. |
| RF-02 | Para entrar a su cuenta, el cliente usa su correo y su contraseña; después de cinco intentos fallidos seguidos, la cuenta queda bloqueada durante quince minutos. |
| RF-04 | Cuando el cliente cierra la sesión, su acceso deja de servir de inmediato y debe volver a identificarse para seguir comprando. |
| RF-20 | Como cliente, quiero eliminar mi cuenta y mis datos personales, salvo los que la ley obligue a conservar de mis compras, para dejar de figurar como cliente de la tienda. |
