<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0004: Base de datos por microservicio

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-04 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere que cada dominio de negocio (catálogo, pedidos, pagos) pueda crecer y actualizarse de forma independiente, sin que la caída de uno afecte a los demás. Para cumplir con RNF-09 y RNF-10, se decide que cada microservicio mantenga su propia base de datos PostgreSQL aislada. Esta arquitectura facilita la gestión de secretos y la escalabilidad de cada servicio sin compartir datos sensibles.

## Decisión

Cada microservicio posee su propia base PostgreSQL aislada.

## Justificación

Garantiza la independencia de datos y la capacidad de escalar o actualizar cada dominio sin afectar a los demás, cumpliendo RNF-09 y facilitando la gestión de secretos (RNF-10).

## Consecuencias

Positivas:

- Permite actualizar, escalar y desplegar cada microservicio sin interrumpir a los demás, reduciendo el riesgo de downtime global.
- Al aislar las bases de datos, cada servicio puede gestionar sus credenciales de forma independiente, cumpliendo RNF-10 y reduciendo la superficie de ataque.
- Cada base puede escalar horizontalmente según la carga específica del dominio, optimizando recursos y costos.

Negativas:

- Requiere administrar múltiples bases de datos PostgreSQL, aumentando la carga de mantenimiento y la necesidad de herramientas de orquestación.
- La separación de datos puede dificultar la coordinación de transacciones entre dominios, requiriendo patrones de eventual consistency.
- Cada base de datos consume memoria y CPU adicionales, elevando el consumo total de recursos en el clúster.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
| RNF-10 | Las claves de la pasarela de pagos y de las bases de datos no pueden estar escritas en el código. |
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
