<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Seguridad y calidad de servicio transversal

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-05 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere garantizar la confidencialidad y autenticidad de las comunicaciones, limitar el abuso de recursos, proteger la información sensible y ofrecer una experiencia de usuario segura. Para ello se decide emplear Keycloak para la autenticación y autorización, TLS para todas las comunicaciones, un límite de 100 rps por cliente/IP y mensajes de error genéricos. Estas medidas satisfacen los requisitos RNF-05, RNF-06, RNF-07, RNF-04 y RNF-01.

## Decisión

Se usa Keycloak para autenticación y autorización, TLS para todas las comunicaciones, límite de 100 rps por cliente/IP y mensajes de error genéricos.

## Justificación

Cumple con RNF-05 (cifrado), RNF-06 (rate limiting), RNF-07 (errores claros), RNF-04 (solo personal admin) y RNF-01 (hash de contraseñas).

## Consecuencias

Positivas:

- Se garantiza la confidencialidad de los datos en tránsito y la integridad de las comunicaciones, reduciendo el riesgo de ataques de interceptación.
- El rate limiting protege la infraestructura contra ataques de denegación de servicio y evita la sobrecarga de los microservicios.
- Los mensajes de error genéricos impiden la divulgación de información sensible que podría ser explotada por atacantes.
- La centralización de la autenticación en Keycloak simplifica la gestión de usuarios y roles, reduciendo la complejidad de la implementación.

Negativas:

- La operación y mantenimiento de Keycloak añade una capa adicional de complejidad y requiere recursos de infraestructura dedicados.
- El uso de TLS en todas las comunicaciones aumenta el consumo de CPU y memoria, lo que puede afectar el rendimiento de los microservicios.
- La limitación de 100 rps por cliente/IP puede generar frustración en usuarios legítimos con cargas altas, afectando la experiencia de usuario.
- La necesidad de configurar y mantener reglas de rate limiting y mensajes de error uniformes implica trabajo adicional de desarrollo y pruebas.

## Trazabilidad

Servicios afectados: `usuarios`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
| RNF-07 | Cuando algo falla, el cliente ve un mensaje claro y sin detalles técnicos internos. |
| RNF-04 | Solo el personal de la empresa puede ser administrador, y ninguna función de administración está disponible para los clientes. |
| RNF-01 | Las contraseñas nunca se guardan tal como las escribe el cliente ni aparecen en ningún registro del sistema. |
