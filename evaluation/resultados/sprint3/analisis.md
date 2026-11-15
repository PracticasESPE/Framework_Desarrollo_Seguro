# Análisis de las fases 1 y 2 con los 3 documentos (sprint 3)

Resultados de `uv run python -m evaluation.fases_1_2` (DOCX, Groq: `gpt-oss-20b` para clasificar y
redactar los ADR, `gpt-oss-120b` para la arquitectura). Las tablas y el detalle por documento están
en [README.md](README.md); este documento resume qué funciona, qué falla y qué conviene mejorar.

## Fase 1: requisitos

| | Tienda en línea | Gestión académica | Citas médicas | Total |
|---|---|---|---|---|
| Requisitos encontrados | 30/30 | 38/38 | 43/43 | **111/111 (100 %)** |
| Falsos positivos | 1 | 1 | 1 | 3 |
| Tipo correcto | 90 % | 87 % | 86 % | 97/111 (87 %) |
| Etiquetas: precisión / exhaustividad | 91 % / 62 % | 95 % / 50 % | 91 % / 44 % | |

**Lo que funciona.** El framework no pierde ningún requisito en ninguno de los tres documentos y
no toma como requisito nada de lo que queda fuera del alcance. Cada requisito conserva su texto
literal y su ubicación.

**Lo que falla, y por qué:**

1. **El mismo falso positivo en los tres documentos.** Es siempre el segundo párrafo del contexto,
   el que dice lo que el cliente *quiere* («La empresa quiere que sus clientes compren a cualquier
   hora…»). El LLM lo lee como un requisito porque expresa un deseo del sistema, aunque es el
   objetivo general del proyecto.
2. **Confusión entre funcional y no funcional (13 %).** Ocurre con requisitos que mezclan una
   función con una restricción, como «el cliente se registra… y la cuenta solo se activa al
   confirmar el correo», o con restricciones de seguridad redactadas como acciones.
3. **Etiquetas de seguridad conservadoras.** Cuando el LLM pone una etiqueta casi siempre acierta
   (precisión del 91 al 95 %), pero se le escapan entre un tercio y la mitad
   (exhaustividad del 44 al 62 %), sobre todo cuando el requisito tiene varias.

**Mejoras propuestas:** indicar en el mensaje de sistema que el objetivo general del contexto no es
un requisito; añadir ejemplos breves de cada etiqueta (hoy solo hay definiciones); y pedir que se
revise cada etiqueta por separado en los requisitos con varias exigencias.

## Fase 2: arquitectura

| | Tienda en línea | Gestión académica | Citas médicas |
|---|---|---|---|
| Ciclo LLM ↔ OPA | aprobada en el intento 1 | aprobada en el intento 1 | aprobada en el intento 1 |
| Servicios (propuestos / referencia) | 5 / 5 | 7 / 6 | 6 / 6 |
| Nombres que coinciden | 4 | 4 | 4 |
| Agrupación de requisitos (F1) | 0,83 | 0,59 | 0,79 |
| Patrones de la referencia inferidos | 5/5 | 4/4 (+ saga) | 4/6 (faltan bff y saga) |
| ADR generados | 10 | 8 | 9 |

**Lo que funciona.** Las tres arquitecturas cumplen las cuatro reglas de OPA y cada una tiene sus
ADR, su diagrama C4 y sus decisiones en Neo4j enlazadas a los requisitos y a las reglas. OPA infiere
13 de los 15 patrones de la referencia, cada uno con su justificación, sus controles ASVS y sus
CWE.

**Lo que falla, y por qué:**

1. **Notificaciones dentro de otro servicio.** En la tienda y en las citas, el LLM puso los correos
   dentro de pedidos o de citas, mientras que la referencia los separa en un servicio que reacciona
   a eventos. No incumple ninguna regla, pero acopla dos responsabilidades.
2. **Gestión académica, la agrupación más baja (F1 0,59).** El LLM separa notas y asistencia (la
   referencia las junta en calificaciones) y llama a la «oferta» académica «catálogo». Además usa
   muchas llamadas síncronas: OPA avisa de 10 cadenas de tres servicios encadenados.
3. **Citas médicas: faltan bff y saga.**
   - **bff** no se puede inferir hoy: sus condiciones («varios tipos de cliente») no salen de
     `arquitectura.json` (limitación ya documentada en `policies/arquitectura/README.md`).
   - **saga** no se infiere porque el LLM dejó a citas solo escuchando eventos de pagos. La
     referencia pide que «reserva y pago se confirmen juntos y se compensen si el pago no llega».
     La regla de OPA reconoce un coordinador cuando un servicio llama a otro y depende además de un
     tercero, y aquí no hay ninguno.
4. **Variabilidad del LLM.** En la primera ejecución de citas médicas, el LLM asignó un mismo
   requisito a dos servicios en sus tres propuestas y el motor las rechazó todas: la fase 2 terminó
   sin arquitectura. Al repetirla, cometió el mismo error dos veces y lo corrigió en la tercera.

**Mejoras propuestas:**

- Pedir en el mensaje de sistema un servicio de notificaciones que reaccione a eventos cuando haya
  avisos por correo.
- Preferir eventos a llamadas síncronas salvo que se necesite la respuesta en el momento (hoy el
  aviso de OPA llega tarde, cuando la propuesta ya está hecha).
- Ampliar la regla de saga a un flujo que se compensa por eventos (p. ej. cita y pago que se
  confirman o se anulan juntos), no solo a un servicio que llama a otros.
- Que un rechazo del motor por requisitos repetidos cuente como un intento más del ciclo, con su
  motivo, en lugar de detenerlo.

## Tiempos

Clasificar es el paso más lento (de 3 a 9 minutos por documento), porque el plan gratuito de Groq
limita las peticiones por minuto y el motor espera lo que pide el proveedor. La propuesta
arquitectónica tarda menos de medio minuto; los ADR, de 45 segundos a 5 minutos por la misma razón.
