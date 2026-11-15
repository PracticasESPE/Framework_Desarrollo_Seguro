<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Arquitectura: Tienda en línea

Generada el 2026-11-14 por el framework a partir de `arquitectura.json`, validada por OPA, para el documento requisitos.docx (SHA-256 `0515668b00b8`). Los diagramas siguen el modelo C4 y GitHub los dibuja a partir del texto Mermaid.

Para regenerarla:

```bash
framework arquitectura diagrama <arquitectura.json> --requisitos <modelo_requisitos.json> --nombre "<nombre del sistema>"
```

## 1. Contexto

Quién usa el sistema. Los actores salen de los requisitos del documento.

```mermaid
C4Context
    title Contexto: Tienda en línea
    Person(p_cliente, "Cliente", "Aparece en 15 requisito(s)")
    Person(p_administrador, "Administrador", "Aparece en 4 requisito(s)")
    Person(p_visitante, "Visitante", "Aparece en 1 requisito(s)")
    System(sistema, "Tienda en línea", "5 microservicios: usuarios, catalogo, pedidos, pagos, ventas")
    Rel(p_cliente, sistema, "Usa", "HTTPS")
    Rel(p_administrador, sistema, "Usa", "HTTPS")
    Rel(p_visitante, sistema, "Usa", "HTTPS")
```

## 2. Contenedores

Las piezas que forman el sistema y cómo se comunican. Las flechas «HTTP» entre servicios son llamadas síncronas (el que llama espera la respuesta); las «AMQP» pasan por el bus de eventos (el que publica no espera a nadie).

```mermaid
flowchart TB
    usuarios["<b>Usuarios</b><br/>[Persona]<br/>Actores de los requisitos"]
    subgraph sistema["Tienda en línea"]
        gateway["<b>API Gateway</b><br/>[Traefik]<br/>Entrada única: TLS, tokens y límite"]
        identidad["<b>Identidad</b><br/>[Keycloak]<br/>Inicio de sesión y JWT"]
        s_usuarios["<b>usuarios</b><br/>[NestJS]<br/>Registro, activación por email, login con bloqueo por inten…"]
        s_catalogo["<b>catalogo</b><br/>[NestJS]<br/>Búsqueda y visualización de productos, gestión de creación,…"]
        s_pedidos["<b>pedidos</b><br/>[NestJS]<br/>Manejo del carrito, creación y validación de pedidos, cálcu…"]
        s_pagos["<b>pagos</b><br/>[NestJS]<br/>Iniciar pagos mediante pasarela externa, validar notificaci…"]
        s_ventas["<b>ventas</b><br/>[NestJS]<br/>Generar reportes de ventas por rango de fechas y proporcion…"]
        db_usuarios_db[("<b>usuarios_db</b><br/>[PostgreSQL]")]
        db_catalogo_db[("<b>catalogo_db</b><br/>[PostgreSQL]")]
        db_pedidos_db[("<b>pedidos_db</b><br/>[PostgreSQL]")]
        db_pagos_db[("<b>pagos_db</b><br/>[PostgreSQL]")]
        db_ventas_db[("<b>ventas_db</b><br/>[PostgreSQL]")]
        eventos[["<b>Bus de eventos</b><br/>[RabbitMQ]"]]
    end
    usuarios -->|"HTTPS"| gateway
    gateway -->|"valida tokens (OIDC)"| identidad
    gateway -->|"HTTP"| s_usuarios
    gateway -->|"HTTP"| s_catalogo
    gateway -->|"HTTP"| s_pedidos
    gateway -->|"HTTP"| s_pagos
    gateway -->|"HTTP"| s_ventas
    s_usuarios -->|"SQL"| db_usuarios_db
    s_catalogo -->|"SQL"| db_catalogo_db
    s_pedidos -->|"SQL"| db_pedidos_db
    s_pagos -->|"SQL"| db_pagos_db
    s_ventas -->|"SQL"| db_ventas_db
    s_pedidos -->|"HTTP: validar identidad del cliente y obtener…"| s_usuarios
    s_pedidos -->|"HTTP: obtener precios y disponibilidad al cre…"| s_catalogo
    eventos -.->|"recibir notificación de pago y actualiz…"| s_pedidos
    eventos -.->|"recibir solicitud de pago para el pedido"| s_pagos
    s_ventas -->|"HTTP: consultar pedidos para calcular métrica…"| s_pedidos
    s_pagos -.->|"publica eventos"| eventos
    s_pedidos -.->|"publica eventos"| eventos
    classDef persona fill:#08427b,stroke:#052e56,color:#fff
    classDef contenedor fill:#438dd5,stroke:#2e6295,color:#fff
    classDef plataforma fill:#85bbf0,stroke:#5d82a8,color:#000
    classDef datos fill:#438dd5,stroke:#2e6295,color:#fff
    class usuarios persona
    class gateway,identidad,eventos plataforma
    class s_usuarios,s_catalogo,s_pedidos,s_pagos,s_ventas contenedor
    class db_usuarios_db,db_catalogo_db,db_pedidos_db,db_pagos_db,db_ventas_db datos
    style sistema fill:none,stroke:#666,stroke-dasharray:5 5
```

## 3. Servicios

| Servicio | Contexto | Responsabilidad | Base de datos | Requisitos | Etiquetas de seguridad |
|---|---|---|---|---|---|
| `usuarios` | Gestión de Usuarios y Autenticación | Registro, activación por email, login con bloqueo por intentos fallidos, gestión de perfil, logout, eliminación de cuenta y manejo seguro de credenciales. | `usuarios_db` | RF-02, RF-03, RF-04, RF-05, RNF-01, RF-21 | autenticacion, limite\_peticiones, control\_acceso\_recursos, hash\_password, autorizacion, auditoria |
| `catalogo` | Catálogo de Productos | Búsqueda y visualización de productos, gestión de creación, modificación y retiro de productos por administradores, manejo de fotos y disponibilidad. | `catalogo_db` | RF-06, RF-07, RF-08, RF-09, RNF-08 | validacion\_entrada |
| `pedidos` | Gestión de Pedidos y Carrito | Manejo del carrito, creación y validación de pedidos, cálculo de precios, control de stock, flujo de estados del pedido, cancelación, generación de eventos de pago y auditoría. | `pedidos_db` | RF-01, RF-10, RF-11, RF-12, RF-13, RF-14, RF-16, RF-17, RF-18, RF-20 | validacion\_entrada, control\_acceso\_recursos, autorizacion |
| `pagos` | Procesamiento de Pagos | Iniciar pagos mediante pasarela externa, validar notificaciones firmadas, registrar resultados y emitir eventos de pago aceptado o rechazado. | `pagos_db` | RNF-02, RF-15 | validacion\_entrada |
| `ventas` | Reportes y Analítica de Ventas | Generar reportes de ventas por rango de fechas y proporcionar datos a los administradores. | `ventas_db` | RF-19 | ninguna |

Requisitos transversales, que aplican a todo el sistema: RNF-03, RNF-04, RNF-05, RNF-06, RNF-07, RNF-09, RNF-10 (etiquetas: auditoria, autorizacion, cifrado\_transito, punto\_unico\_acceso, limite\_peticiones).

## 4. Dependencias entre servicios

| Servicio | Depende de | Tipo | Para qué |
|---|---|---|---|
| `pedidos` | `usuarios` | síncrona (HTTP) | validar identidad del cliente y obtener datos de cuenta |
| `pedidos` | `catalogo` | síncrona (HTTP) | obtener precios y disponibilidad al crear el pedido |
| `pedidos` | `pagos` | asíncrona (eventos) | recibir notificación de pago y actualizar estado del pedido |
| `pagos` | `pedidos` | asíncrona (eventos) | recibir solicitud de pago para el pedido |
| `ventas` | `pedidos` | síncrona (HTTP) | consultar pedidos para calcular métricas de venta |

## 5. Patrones aplicados

| Patrón | Implementación | Por qué lo infiere OPA | ADR |
|---|---|---|---|
| Database per Service | prisma\_postgresql | Cada servicio tiene su propia base de datos | [ver ADR](adr/0006-aplicar-el-patron-database-per-service.md) |
| Event-Driven | rabbitmq | Dependencias por eventos: pagos -&gt; pedidos, pedidos -&gt; pagos | [ver ADR](adr/0007-aplicar-el-patron-event-driven.md) |
| API Gateway | traefik | Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada; Hay requisitos de punto único de entrada o de límite de peticiones | [ver ADR](adr/0008-aplicar-el-patron-api-gateway.md) |
| Circuit Breaker | nestjs\_interceptor\_con\_reintentos\_y\_timeout | Llamadas síncronas entre servicios: pedidos -&gt; catalogo, pedidos -&gt; usuarios, ventas -&gt; pedidos | [ver ADR](adr/0009-aplicar-el-patron-circuit-breaker.md) |
| Saga | rabbitmq | pedidos coordina operaciones que involucran a otros servicios | [ver ADR](adr/0010-aplicar-el-patron-saga.md) |

## 6. Validación de OPA

Arquitectura aprobada: cumple los 4 criterios; patrones inferidos: api\_gateway, circuit\_breaker, database\_per\_service, event\_driven, saga

| Regla | Cumple | Detalle |
|---|---|---|
| `arquitectura.base_datos_propia` | sí | Cada servicio tiene su propia base de datos (Database per Service) |
| `arquitectura.sin_ciclos` | sí | Las llamadas síncronas entre servicios no forman ciclos |
| `arquitectura.dependencias_conocidas` | sí | Cada dependencia apunta a otro servicio de la arquitectura |
| `arquitectura.servicios_unicos` | sí | Hay al menos un servicio y no hay nombres repetidos |

Advertencias:

- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas ventas -&gt; pedidos -&gt; catalogo: si catalogo falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas ventas -&gt; pedidos -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.ciclo_de_eventos`: pagos, pedidos dependen unos de otros en círculo (pagos -&gt; pedidos (asincrona), pedidos -&gt; pagos (asincrona)): es una saga coreografiada; documenta sus eventos y la compensación si un paso falla
