<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0001: División en 5 microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-01 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para cumplir con los requisitos de disponibilidad continua, actualización automática de stock y pagos instantáneos, se decide dividir la aplicación en cinco microservicios: usuarios, catálogo, pedidos, pagos y ventas. Cada microservicio se implementa con la plantilla NestJS, su propia base de datos PostgreSQL y se comunica mediante RabbitMQ. El gateway Traefik y la identidad Keycloak garantizan la entrada y autenticación centralizadas.

## Decisión

Se crean los microservicios usuarios, catalogo, pedidos, pagos y ventas.

## Justificación

Los requisitos se agrupan naturalmente en contextos delimitados (autenticación, catálogo, flujo de pedido, pago y reportes). Esta separación evita servicios diminutos y permite escalar cada dominio de forma independiente.

## Consecuencias

Positivas:

- Escalado independiente de cada dominio permite asignar recursos según la carga específica, optimizando el rendimiento y reduciendo costos en momentos de baja demanda.
- Separación clara de responsabilidades facilita el desarrollo y la prueba de cada servicio, reduciendo el riesgo de introducir errores en dominios no relacionados.
- La arquitectura de microservicios mejora la tolerancia a fallos; un fallo en el servicio de pagos no afecta directamente al catálogo o a la gestión de usuarios.
- El uso de la misma plantilla NestJS y PostgreSQL simplifica la estandarización del código y la gestión de dependencias, acelerando la incorporación de nuevos desarrolladores.

Negativas:

- Mayor complejidad operativa: cada microservicio requiere su propio contenedor, base de datos y configuración de RabbitMQ, aumentando el esfuerzo de despliegue y monitoreo.
- Incremento en la latencia de las transacciones, ya que las peticiones deben pasar por múltiples servicios y colas de mensajes, lo que puede afectar la experiencia del usuario.
- Consumo de recursos más alto: cinco bases de datos PostgreSQL y cinco instancias de NestJS aumentan el uso de CPU, memoria y almacenamiento en el clúster.
- Mayor superficie de ataque: cada servicio expone endpoints y conexiones a la red, lo que requiere una configuración de seguridad más rigurosa y un mantenimiento continuo de las políticas de acceso.

## Trazabilidad

Servicios afectados: `usuarios`, `catalogo`, `pedidos`, `pagos`, `ventas`

| Requisito | Texto del documento |
|---|---|
| RF-01 | La empresa quiere que sus clientes compren a cualquier hora, que el stock se actualice solo y que el cobro con tarjeta sea inmediato. Trabajan en ella cuatro personas: dos atienden los pedidos y dos gestionan el catálogo. Ninguna tiene conocimientos técnicos. |
| RF-02 | El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe. |
| RF-06 | Cualquier visitante puede buscar productos por nombre o por categoría, y los resultados se muestran por páginas de como máximo 50 productos. |
| RF-10 | El cliente agrega productos a su carrito y elige la cantidad de cada uno, entre 1 y 10 unidades por producto. |
| RF-15 | La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado». |
| RF-19 | El administrador obtiene un reporte de las ventas entre dos fechas, con un rango máximo de un año. |
