<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0004: Gestión de secretos

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Decisión D-04 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere evitar que las claves de pasarela y credenciales de bases de datos queden en el código fuente, por lo que se decide usar Vault para su almacenamiento y acceso seguro.

## Decisión

Almacenar claves de pasarela y credenciales de bases de datos en Vault y acceder mediante variables de entorno seguras.

## Justificación

Cumple RNF-10 que prohíbe hardcode de claves.

## Consecuencias

Positivas:

- Mejora la seguridad al eliminar la exposición de secretos en repositorios y despliegues.
- Facilita la rotación y revocación de credenciales sin modificar el código.
- Cumple con el requisito RNF-10 y reduce riesgos de cumplimiento.

Negativas:

- Incrementa la complejidad operativa al requerir la gestión y mantenimiento de Vault.
- Introduce latencia adicional en la inicialización de servicios al recuperar secretos en tiempo de arranque.
- Puede convertirse en un punto único de falla si Vault no está disponible, afectando la disponibilidad de todos los microservicios.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-10 | Las claves de la pasarela de pagos y de las bases de datos no pueden estar escritas en el código. |
