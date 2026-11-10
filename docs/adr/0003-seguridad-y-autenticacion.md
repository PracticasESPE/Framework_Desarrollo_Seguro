<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Seguridad y autenticación

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere cifrado TLS en todas las comunicaciones, autenticación y autorización centralizadas, y protección contra abuso mediante límites de peticiones. Además, la gestión de cuentas debe incluir registro, confirmación por correo, bloqueo tras intentos fallidos, cierre de sesión inmediato y eliminación de datos personales. Estas necesidades se derivan de los requisitos RNF-05, RNF-06, RNF-04, RF-01, RF-02, RF-04 y RF-20.

## Decisión

Integrar Keycloak como IdP y usar JWT en el gateway Traefik. Aplicar TLS en todas las comunicaciones y límite de peticiones.

## Justificación

Requisitos RNF-05, RNF-06, RNF-04, RF-01, RF-02, RF-04 y RF-20 requieren autenticación, autorización y protección contra abuso.

## Consecuencias

Positivas:

- Implementar Keycloak como IdP garantiza un control centralizado de usuarios y roles, reduciendo la duplicación de lógica de autenticación en cada microservicio.
- El uso de JWT en Traefik permite la autorización sin estado, lo que simplifica la escalabilidad y la gestión de sesiones en un entorno de contenedores.
- Aplicar TLS en todas las comunicaciones asegura la confidencialidad e integridad de los datos, cumpliendo con RNF-05 y protegiendo contra ataques de intermediarios.
- El límite de 100 peticiones por minuto impide el abuso y protege la disponibilidad del servicio, cumpliendo con RNF-06 y reduciendo la carga en los microservicios.

Negativas:

- La incorporación de Keycloak añade complejidad operativa y requiere mantenimiento de su infraestructura, incluyendo actualizaciones y respaldo.
- La gestión de certificados TLS y su renovación automática implica tareas adicionales de DevOps y posibles interrupciones si no se automatiza correctamente.
- El manejo de expiración y revocación de JWT necesita lógica adicional para invalidar tokens, lo que puede aumentar la latencia y el consumo de recursos.
- El límite de peticiones puede bloquear usuarios legítimos si los parámetros no se ajustan adecuadamente, afectando la experiencia de usuario.

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
