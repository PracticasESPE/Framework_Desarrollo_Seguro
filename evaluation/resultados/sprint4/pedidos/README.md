# Servicio `pedidos` generado con la lógica de negocio del LLM (sprint 4, #62 y #64)

Servicio `pedidos` de la tienda en línea (documento 1 del dataset), a partir de la arquitectura
aprobada por OPA en `evaluation/resultados/sprint3/01_tienda_en_linea/`. Proveedor: Groq,
`openai/gpt-oss-120b` (nivel razonamiento), con el contexto de GraphRAG (11 controles ASVS y
12 CWE recuperados de Neo4j).

| Paso | Comando | Resultado |
|---|---|---|
| Especificación | `servicio prompt … --servicio pedidos --enviar` | `especificacion.yml`: 7 entidades; pasó el esquema a la primera |
| Esqueleto | `servicio generar especificacion.yml` | Copier generó el servicio sin errores; tsc sin errores |
| Lógica de negocio | `servicio logica <carpeta>` | Las 7 entidades aceptadas; el servicio completo compila con tsc |

`src/` tiene los `service.ts` de cada entidad con su punto de extensión ya relleno (el resto del
servicio es el de la plantilla) y `logica/` el registro de cada entidad: intentos, problemas del
análisis, errores de tsc, huella del prompt y respuesta del LLM.

## Lo que muestra

- **El ciclo con tsc funciona.** En `pedido`, el primer intento buscaba el carrito con
  `findUnique` por `clienteId`, que no es un campo único: tsc lo rechazó (TS2322), el error volvió
  al LLM y el segundo intento (`findFirst`) compiló. Las otras 6 entidades compilaron a la primera.
- **El LLM declara lo que no puede hacer.** Los métodos no reciben el usuario autenticado ni
  pueden enviar correos o programar tareas: la cancelación a los 30 minutos (RF-16), los correos
  (RF-17) y la comprobación de que el pedido es del cliente (RF-14) quedan como `Pendiente` en el
  bloque generado, en lugar de inventarse.
- **Reglas que se ven en `pedido.service.ts`:** el total se recalcula con los precios del catálogo
  y no se acepta el que envía el cliente (RF-11), se rechaza un pedido sin stock suficiente (RF-12),
  se descuenta el stock (RF-13) y no se puede cancelar un pedido ya enviado (RF-20).

## Para revisar

- **Requisitos citados de más.** En `carrito`, el LLM cita 10 requisitos pero deja casi todos en
  pendientes: la lista de requisitos de un bloque no garantiza que estén implementados.
- **Concurrencia.** El descuento del stock en `pedido` lee y actualiza sin transacción: dos pedidos
  simultáneos podrían vender la misma unidad. tsc no lo detecta; es tarea de las pruebas y de la
  revisión.
- **Producto duplicado.** La arquitectura asignó la entidad Producto también a `pedidos` (es de
  `catalogo`), así que el servicio la repite. Viene de la fase 2, no de este paso.
