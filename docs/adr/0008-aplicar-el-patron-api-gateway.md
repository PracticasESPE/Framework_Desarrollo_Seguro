<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0008: Aplicar el patrón API Gateway

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Se necesita un punto único de entrada para centralizar la autenticación y aplicar límites de tasa, cumpliendo con los requisitos de seguridad y rendimiento. El gateway permite que los clientes se autentiquen una sola vez y que la comunicación sea cifrada y dirigida a una única dirección. Además, facilita la gestión de políticas de acceso y la introducción de nuevos microservicios sin duplicar lógica.

## Decisión

Se aplica API Gateway: punto único de entrada para los clientes. Implementación prevista: traefik.

## Justificación

Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones

## Consecuencias

Positivas:

- Centraliza la autenticación, evitando duplicar lógica en cada microservicio y reduciendo la superficie de ataque.
- Facilita la aplicación de límites de tasa y políticas de seguridad en un solo lugar, cumpliendo con RNF-06.
- Garantiza que todas las comunicaciones viajen cifradas y que los clientes accedan siempre a través de una única dirección, cumpliendo RNF-05.
- Simplifica la introducción de nuevos microservicios, ya que solo necesitan registrarse en el gateway sin modificar la lógica de autenticación.

Negativas:

- Conviértelo en un punto único de falla; si el gateway cae, todos los servicios quedan inaccesibles.
- Añade latencia adicional al enrutar cada solicitud a través del gateway, lo que puede afectar el rendimiento bajo carga.
- Requiere una configuración y mantenimiento más complejos, especialmente al escalar horizontalmente el gateway.
- Si no se dimensiona correctamente, el gateway puede convertirse en un cuello de botella, limitando el número de peticiones concurrentes.

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
| RF-01 | El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe. |
| RF-02 | Para entrar a su cuenta, el cliente usa su correo y su contraseña; después de cinco intentos fallidos seguidos, la cuenta queda bloqueada durante quince minutos. |
| RF-04 | Cuando el cliente cierra la sesión, su acceso deja de servir de inmediato y debe volver a identificarse para seguir comprando. |
| RF-20 | Como cliente, quiero eliminar mi cuenta y mis datos personales, salvo los que la ley obligue a conservar de mis compras, para dejar de figurar como cliente de la tienda. |
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
