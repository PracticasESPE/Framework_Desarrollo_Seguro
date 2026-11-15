<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0004: Gestión de secretos

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-04 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita evitar que las claves de la pasarela de pagos y las credenciales de las bases de datos queden expuestas en el código fuente. Para cumplir con RNF-10, se decide centralizar los secretos en Vault y exponerlos a los microservicios mediante variables de entorno seguras. Esta medida garantiza la separación de la configuración sensible del código y facilita la rotación de credenciales.

## Decisión

Almacenar claves de pasarela y credenciales de bases de datos en Vault y acceder mediante variables de entorno seguras.

## Justificación

Cumple RNF-10 que prohíbe hardcode de claves.

## Consecuencias

Positivas:

- Reducción del riesgo de exposición accidental de credenciales, cumpliendo con RNF-10 y mejorando la postura de seguridad.
- Facilita la rotación y revocación de secretos sin necesidad de redeployar los servicios, lo que mejora la operatividad.
- Centraliza la gestión de secretos, permitiendo auditorías y trazabilidad de accesos a través de Vault.

Negativas:

- Incrementa la complejidad operativa al requerir la configuración y mantenimiento de Vault, así como la gestión de certificados TLS.
- Introduce una dependencia de red adicional; la disponibilidad de Vault es crítica y su caída puede bloquear el despliegue de microservicios.
- Requiere que los contenedores tengan acceso a Vault, lo que implica la configuración de políticas de acceso y la gestión de tokens de autenticación.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-10 | Las claves de la pasarela de pagos y de las bases de datos no pueden estar escritas en el código. |
