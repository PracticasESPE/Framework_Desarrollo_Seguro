<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Base de datos por microservicio

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere que cada microservicio maneje datos sensibles de forma aislada para cumplir con requisitos de confidencialidad y retención. Al asignar una base de datos PostgreSQL propia a cada servicio, se evita la exposición de datos entre dominios y se facilita la aplicación de políticas de cifrado y retención específicas. Esta arquitectura también simplifica la gestión de secretos y la auditoría de accesos.

## Decisión

Cada microservicio posee su propia base de datos PostgreSQL aislada.

## Justificación

Garantiza aislamiento de datos sensibles (RNF-02, RNF-07) y permite aplicar políticas de retención y cifrado por dominio, evitando dependencias de esquema entre servicios.

## Consecuencias

Positivas:

- Aislamiento de datos reduce riesgo de filtraciones entre servicios y facilita cumplimiento de requisitos de confidencialidad.
- Permite aplicar políticas de retención y cifrado por dominio sin afectar a los demás servicios, cumpliendo con RNF-02 y RNF-07.
- Simplifica la gestión de secretos y auditoría, ya que cada servicio controla sus propias credenciales.
- Mejora la escalabilidad y disponibilidad, ya que fallos en una base de datos no afectan a los demás servicios.

Negativas:

- Incrementa la complejidad operativa y el coste de mantenimiento de múltiples bases de datos PostgreSQL.
- Aumenta el consumo de recursos (memoria, CPU, almacenamiento) y la sobrecarga de gestión de contenedores.
- Dificulta la realización de consultas transversales entre dominios, requiriendo patrones de integración adicionales.
- Requiere más esfuerzo en la configuración de backups y recuperación, ya que cada base debe ser respaldada individualmente.

## Trazabilidad

Servicios afectados: `historia`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-02 | Las historias clínicas se guardan cifradas y se conservan al menos 15 años, aunque el paciente cierre su cuenta. |
| RNF-07 | Las claves del laboratorio, de la pasarela, del envío de mensajes y de las bases de datos se guardan en un almacén de secretos y nunca en el código. |
