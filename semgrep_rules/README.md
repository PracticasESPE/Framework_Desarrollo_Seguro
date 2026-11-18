# Reglas Semgrep propias (v1)

Reglas SAST para código TypeScript/NestJS/Prisma. Forman parte de la base de
conocimiento: cada una declara el CWE y la categoría OWASP que detecta.

| Regla | Severidad | CWE |
|---|---|---|
| nestjs-validationpipe-sin-whitelist | WARNING | 915 |
| prisma-sql-crudo-inseguro | ERROR | 89 |
| nestjs-cors-abierto | WARNING | 942 |
| jwt-secreto-en-codigo | ERROR | 798 |
| jwt-ignora-expiracion | ERROR | 613 |
| tls-verificacion-desactivada | ERROR | 295 |
| hash-criptografico-debil | WARNING | 327 |
| prisma-findmany-sin-limite | WARNING | 770 |

## Probar las reglas

    docker run --rm -v "${PWD}:/src" semgrep/semgrep:1.172.0 semgrep --test semgrep_rules/

Los casos de prueba están en `nestjs-seguridad.ts` y contienen código inseguro
a propósito. No es código del servicio.

## Cambios

Todo cambio en esta carpeta entra por pull request revisado por el otro integrante
(control de manipulación del conocimiento, capítulo 10 del plan).
