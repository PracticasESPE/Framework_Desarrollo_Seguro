<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Seguridad y autenticación

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere un acceso seguro y centralizado para pacientes y personal, con comunicación cifrada y gestión de secretos. Se opta por Keycloak como IdP único y Vault para almacenar credenciales. Todos los microservicios, basados en NestJS, validan tokens JWT y usan roles para autorización.

## Decisión

Keycloak será el IdP único; todos los microservicios validan tokens JWT y usan autorización basada en roles. Las comunicaciones internas se cifran TLS y los secretos se almacenan en Vault.

## Justificación

Cumple RNF‑09 (cifrado en tránsito y punto único de acceso) y RNF‑13 (almacén de secretos).

## Consecuencias

Positivas:

- Centralización de la autenticación reduce la duplicación de lógica y facilita la auditoría de accesos.
- El uso de tokens JWT permite una validación rápida y sin estado en cada microservicio.
- Almacenar secretos en Vault evita la exposición de credenciales en el código y cumple con RNF‑13.

Negativas:

- La operación de Keycloak y Vault añade complejidad y requiere monitoreo constante para evitar caídas.
- La configuración de TLS en todas las comunicaciones internas aumenta la carga de mantenimiento y la posibilidad de errores de certificado.
- Dependencia de un único IdP puede convertirse en un punto de falla si no se replica adecuadamente.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-09 | Toda la comunicación con el sistema debe viajar cifrada, y pacientes y personal deben entrar siempre por una única dirección. |
| RNF-13 | Las claves del laboratorio, de la pasarela, del envío de mensajes y de las bases de datos se guardan en un almacén de secretos y nunca en el código. |
