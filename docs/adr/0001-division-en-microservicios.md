<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0001: División en microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-01 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema debe soportar distintas funcionalidades (usuarios, catálogo, inventario, pedidos, pagos, avisos y reportes) que evolucionan de forma independiente y requieren aislamiento de datos. Dividir en microservicios permite escalar, desplegar y mantener cada dominio sin afectar a los demás, cumpliendo los requisitos de independencia de datos y disponibilidad.

## Decisión

Crear 7 microservicios: usuarios, catalogo, inventario, pedidos, pagos, avisos y reportes.

## Justificación

Los requisitos están agrupados por dominios (gestión de usuarios, catálogo, stock, pedidos, pagos, notificaciones y reportes). Mantener entre 3 y 7 servicios evita microservicios diminutos y permite independencia de datos.

## Consecuencias

Positivas:

- Aislamiento de datos y lógica de negocio por dominio, facilitando cambios y despliegues independientes.
- Escalabilidad horizontal: cada servicio puede escalar según su carga específica (p. ej., catálogo bajo alta demanda de búsqueda).
- Resiliencia: fallos en un servicio no interrumpen los demás, cumpliendo el requisito de independencia de datos.
- Mejor mantenibilidad y claridad de responsabilidades, reduciendo la complejidad de código y facilitando pruebas unitarias.

Negativas:

- Mayor complejidad operativa: gestión de múltiples contenedores, redes y orquestación de servicios.
- Incremento de latencia inter-servicios por llamadas HTTP/RabbitMQ, afectando la experiencia de usuario en operaciones críticas.
- Desafíos de consistencia eventual: actualizaciones de stock y pedidos requieren coordinación para evitar sobreventas.
- Coste de monitoreo y trazabilidad: se necesita un sistema de logging y tracing distribuido para diagnosticar fallos.

## Trazabilidad

Servicios afectados: `usuarios`, `catalogo`, `inventario`, `pedidos`, `pagos`, `avisos`, `reportes`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-01 | El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe. |
| RF-02 | Para entrar a su cuenta, el cliente usa su correo y su contraseña; después de cinco intentos fallidos seguidos, la cuenta queda bloqueada durante quince minutos. |
| RF-03 | El cliente puede consultar y cambiar su nombre, su teléfono y sus direcciones de envío, pero no puede cambiar por su cuenta el tipo de usuario que tiene. |
| RF-04 | Cuando el cliente cierra la sesión, su acceso deja de servir de inmediato y debe volver a identificarse para seguir comprando. |
| RF-05 | Cualquier visitante puede buscar productos por nombre o por categoría, y los resultados se muestran por páginas de como máximo 50 productos. |
| RF-06 | Cada producto muestra su nombre, su descripción, su precio, sus fotos y si quedan unidades disponibles. |
| RF-07 | El administrador crea, modifica y retira productos del catálogo, y puede subir hasta cinco fotos por producto en formato JPG o PNG de no más de 2 MB cada una. |
| RF-08 | Un producto retirado deja de aparecer en el catálogo, pero se conserva en los pedidos que ya lo incluían. |
| RF-09 | El cliente agrega productos a su carrito y elige la cantidad de cada uno, entre 1 y 10 unidades por producto. |
| RF-10 | Al confirmar el pedido, el precio de cada producto y el total se calculan con los precios del catálogo, sin aceptar los importes que envíe el navegador. |
| RF-11 | Si mientras el cliente confirma su pedido otro cliente compra las últimas unidades de un producto, el pedido no se acepta y se le indica qué productos ya no están disponibles. |
| RF-12 | Al aceptarse un pedido, sus unidades se descuentan del stock disponible. |
| RF-13 | El cliente ve la lista de sus pedidos con el estado y el detalle de cada uno, y nunca puede ver los pedidos de otro cliente. |
| RF-14 | La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado». |
| RF-15 | Un pedido que no se paga en 30 minutos se cancela solo y sus unidades vuelven al stock disponible. |
| RF-16 | El cliente recibe un correo cuando su pedido se acepta, cuando se paga y cada vez que cambia de estado. |
| RF-17 | El administrador cambia el estado de los pedidos pagados siguiendo siempre el mismo orden: en preparación, enviado y entregado. |
| RF-18 | El administrador obtiene un reporte de las ventas entre dos fechas, con un rango máximo de un año. |
| RF-19 | Como cliente, quiero cancelar un pedido mientras todavía no se haya enviado, para no pagar algo que ya no necesito. |
| RF-20 | Como cliente, quiero eliminar mi cuenta y mis datos personales, salvo los que la ley obligue a conservar de mis compras, para dejar de figurar como cliente de la tienda. |
| RNF-01 | Las contraseñas nunca se guardan tal como las escribe el cliente ni aparecen en ningún registro del sistema. |
| RNF-02 | El pago con tarjeta se hace en una pasarela de pagos externa, y la tienda nunca recibe ni guarda el número de la tarjeta ni su código de seguridad. |
| RNF-03 | Queda constancia de cada acción de un administrador sobre productos y pedidos, con quién la hizo, qué cambió y cuándo; esa constancia no se puede modificar y solo la consultan los administradores. |
| RNF-04 | Solo el personal de la empresa puede ser administrador, y ninguna función de administración está disponible para los clientes. |
| RNF-05 | Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
| RNF-07 | Cuando algo falla, el cliente ve un mensaje claro y sin detalles técnicos internos. |
| RNF-08 | La búsqueda en el catálogo debe responder en menos de un segundo con 200 clientes conectados a la vez. |
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
| RNF-10 | Las claves de la pasarela de pagos y de las bases de datos no pueden estar escritas en el código. |
