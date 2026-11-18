# Tienda en línea: documento de requisitos

Versión 1.0, noviembre de 2026.

## 1. Contexto

Una pequeña empresa que vende artesanías y productos de diseño local quiere dejar de vender solo por redes sociales y abrir su propia tienda en línea. Hoy recibe los pedidos por mensajes, anota el stock en una hoja de cálculo y cobra por transferencia bancaria, lo que provoca ventas de productos agotados y pagos que tardan días en confirmarse.

La empresa quiere que sus clientes compren a cualquier hora, que el stock se actualice solo y que el cobro con tarjeta sea inmediato. Trabajan en ella cuatro personas: dos atienden los pedidos y dos gestionan el catálogo. Ninguna tiene conocimientos técnicos.

## 2. Usuarios

| Usuario | Quién es | Qué hace en la tienda |
|---|---|---|
| Visitante | Cualquier persona sin cuenta | Navega por el catálogo y busca productos |
| Cliente | Persona registrada en la tienda | Compra, paga y sigue sus pedidos |
| Administrador | Personal de la empresa | Gestiona el catálogo, los pedidos y los reportes |

## 3. Cuenta del cliente

1. El cliente debe poder registrarse con su correo electrónico y una contraseña, y la cuenta solo se activa cuando confirma el correo desde el enlace que recibe.
2. Para entrar a su cuenta, el cliente usa su correo y su contraseña; después de cinco intentos fallidos seguidos, la cuenta queda bloqueada durante quince minutos.
3. El cliente puede consultar y cambiar su nombre, su teléfono y sus direcciones de envío, pero no puede cambiar por su cuenta el tipo de usuario que tiene.
4. Cuando el cliente cierra la sesión, su acceso deja de servir de inmediato y debe volver a identificarse para seguir comprando.
5. Las contraseñas nunca se guardan tal como las escribe el cliente ni aparecen en ningún registro del sistema.

## 4. Catálogo

1. Cualquier visitante puede buscar productos por nombre o por categoría, y los resultados se muestran por páginas de como máximo 50 productos.
2. Cada producto muestra su nombre, su descripción, su precio, sus fotos y si quedan unidades disponibles.
3. El administrador crea, modifica y retira productos del catálogo, y puede subir hasta cinco fotos por producto en formato JPG o PNG de no más de 2 MB cada una.
4. Un producto retirado deja de aparecer en el catálogo, pero se conserva en los pedidos que ya lo incluían.

## 5. Carrito y pedidos

1. El cliente agrega productos a su carrito y elige la cantidad de cada uno, entre 1 y 10 unidades por producto.
2. Al confirmar el pedido, el precio de cada producto y el total se calculan con los precios del catálogo, sin aceptar los importes que envíe el navegador.
3. Si mientras el cliente confirma su pedido otro cliente compra las últimas unidades de un producto, el pedido no se acepta y se le indica qué productos ya no están disponibles.
4. Al aceptarse un pedido, sus unidades se descuentan del stock disponible.
5. El cliente ve la lista de sus pedidos con el estado y el detalle de cada uno, y nunca puede ver los pedidos de otro cliente.

## 6. Pago

1. El pago con tarjeta se hace en una pasarela de pagos externa, y la tienda nunca recibe ni guarda el número de la tarjeta ni su código de seguridad.
2. La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado».
3. Un pedido que no se paga en 30 minutos se cancela solo y sus unidades vuelven al stock disponible.

## 7. Avisos al cliente

1. El cliente recibe un correo cuando su pedido se acepta, cuando se paga y cada vez que cambia de estado.

## 8. Administración

1. El administrador cambia el estado de los pedidos pagados siguiendo siempre el mismo orden: en preparación, enviado y entregado.
2. El administrador obtiene un reporte de las ventas entre dos fechas, con un rango máximo de un año.
3. Queda constancia de cada acción de un administrador sobre productos y pedidos, con quién la hizo, qué cambió y cuándo; esa constancia no se puede modificar y solo la consultan los administradores.
4. Solo el personal de la empresa puede ser administrador, y ninguna función de administración está disponible para los clientes.

## 9. Historias de usuario

Durante las reuniones con la empresa surgieron dos peticiones más, que se recogen tal como las contaron:

- Como cliente, quiero cancelar un pedido mientras todavía no se haya enviado, para no pagar algo que ya no necesito.
- Como cliente, quiero eliminar mi cuenta y mis datos personales, salvo los que la ley obligue a conservar de mis compras, para dejar de figurar como cliente de la tienda.

## 10. Condiciones generales

1. Toda la comunicación con la tienda debe viajar cifrada, y los clientes deben entrar siempre por una única dirección.
2. Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere.
3. Cuando algo falla, el cliente ve un mensaje claro y sin detalles técnicos internos.
4. La búsqueda en el catálogo debe responder en menos de un segundo con 200 clientes conectados a la vez.
5. El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás.
6. Las claves de la pasarela de pagos y de las bases de datos no pueden estar escritas en el código.

## 11. Fuera del alcance

En esta primera versión la empresa no necesita lo siguiente:

- Una aplicación móvil propia.
- Vender productos de otros vendedores.
- Envíos internacionales ni cobros en monedas distintas del dólar.
- Recomendaciones de productos personalizadas para cada cliente.
