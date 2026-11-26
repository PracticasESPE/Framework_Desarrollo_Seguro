<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Seguridad y gestión de secretos

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Decisión D-05 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere cifrado de todas las comunicaciones y un manejo seguro de los secretos para proteger datos sensibles y cumplir con los requisitos de seguridad. Se decide usar TLS, Keycloak como IdP y un vault externo para almacenar claves.

## Decisión

Todas las comunicaciones usan TLS (HTTPS), Keycloak actúa como IdP y los secretos (claves de laboratorio, pasarela, DB) se almacenan en un vault externo.

## Justificación

Cumple RNF-03 (cifrado en tránsito y punto único de acceso), RNF-07 (almacenamiento seguro de claves) y refuerza los requisitos de autenticación y autorización (RF-03, RF-04, RF-06).

## Consecuencias

Positivas:

- Garantiza cifrado en tránsito y autenticación centralizada, reduciendo riesgo de interceptación.
- Centraliza el almacenamiento de secretos, facilitando rotación y auditoría sin exponer claves en código.
- Cumple con los requisitos RNF-03 y RNF-07, alineándose con políticas de seguridad y evitando sanciones.

Negativas:

- Dependencia de un servicio externo (vault) que puede convertirse en punto único de falla y requiere alta disponibilidad.
- Incrementa la complejidad operativa: configuración, mantenimiento y monitoreo de TLS, Keycloak y el vault.
- Posible aumento de latencia en la obtención de secretos y en la autenticación, afectando el rendimiento de los microservicios.

## Trazabilidad

Servicios afectados: `auth`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-03 | Toda la comunicación con el sistema debe viajar cifrada, y pacientes y personal deben entrar siempre por una única dirección. |
| RNF-07 | Las claves del laboratorio, de la pasarela, del envío de mensajes y de las bases de datos se guardan en un almacén de secretos y nunca en el código. |
| RF-03 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RF-04 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RF-06 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
