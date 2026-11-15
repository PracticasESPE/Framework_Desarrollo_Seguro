<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Seguridad y gestión de secretos

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere autenticación segura y gestión de secretos sin exponer credenciales en el código. Se necesita un único punto de acceso, cifrado de tráfico y soporte para MFA y expiración de sesión. Además, los mensajes de error deben ser genéricos y los secretos deben almacenarse de forma segura.

## Decisión

Se integra Keycloak como IdP para autenticación y autorización, se usan JWT firmados, TLS en todo el tráfico y los secretos (contraseñas DB, claves API) se almacenan en Vault, nunca en código.

## Justificación

Cumple RNF-03 (cifrado en tránsito y punto único de acceso), RNF-06 (no exponer detalles internos en errores) y RNF-07 (no hardcodear claves). Además soporta los requisitos de autenticación multifactor (RF-05) y expiración de sesión (RF-06).

## Consecuencias

Positivas:

- Centralización de la autenticación y autorización mediante Keycloak reduce la duplicación de lógica y facilita la gestión de usuarios y roles.
- El uso de JWT firmados permite una verificación rápida de identidad sin requerir llamadas a la base de datos en cada petición.
- La integración con Vault garantiza que las contraseñas y claves API nunca se expongan en el código, reduciendo el riesgo de filtraciones internas.
- La aplicación de TLS en todo el tráfico asegura la confidencialidad e integridad de los datos en tránsito, cumpliendo con RNF-03.

Negativas:

- La operación de Keycloak y Vault añade complejidad operativa y requiere monitoreo continuo, aumentando el coste de mantenimiento.
- La gestión de certificados TLS y su renovación automática implica procesos adicionales y posibles puntos de fallo si no se automatiza correctamente.
- La dependencia de servicios externos (Keycloak, Vault) introduce latencia adicional en la autenticación y la recuperación de secretos, lo que puede afectar el rendimiento.
- La configuración y el mantenimiento de MFA y expiración de sesión requieren ajustes en la lógica de negocio y pruebas exhaustivas para evitar bloqueos de usuarios legítimos.

## Trazabilidad

Servicios afectados: `usuarios`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-05 | Los docentes, la secretaría y la coordinación entran con su contraseña y además con un código de un solo uso que les da una aplicación de autenticación en el móvil. |
| RF-06 | Si una sesión pasa 15 minutos sin actividad, se cierra sola, porque muchos equipos del instituto son compartidos. |
| RNF-03 | Todo el acceso al sistema debe viajar cifrado y pasar por una única dirección, tanto desde el campus como desde fuera. |
| RNF-06 | Los mensajes de error no muestran detalles internos del sistema. |
| RNF-07 | Las claves de las bases de datos y la que usa la biblioteca no pueden estar escritas en el código. |
