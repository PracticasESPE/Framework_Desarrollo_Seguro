# Políticas de integración (Conftest)

Revisan los archivos Docker Compose antes de levantar nada. Las ejecuta `scripts/gate2.sh`
(fase 8 del workflow, Security Gate 2) sobre `docker-compose.dev.yml` y publican
`conftest.sarif` en la pestaña Security. Paquete Rego: `integracion.compose`.

Cubren lo que Trivy config no analiza en el Gate 1: Trivy solo revisa el Dockerfile.

| Tipo | Regla | Riesgo que evita |
|---|---|---|
| deny | `privileged: true` | acceso casi total al host |
| deny | `network_mode: host` | sin aislamiento de red |
| deny | montajes del host (`/`, `/etc`, `docker.sock`...) | escape del contenedor |
| deny | puertos que no escuchan solo en 127.0.0.1 | servicios internos expuestos a la red |
| deny | imágenes sin versión o `:latest` | despliegues no reproducibles |
| deny | secretos escritos en el archivo (deben venir de `${VAR}`) | credenciales en Git |
| deny | `cap_add` peligrosas y `seccomp/apparmor:unconfined` | privilegios del kernel |
| deny | un servicio apunta a la base de otro (`*-db`) | patrón Database per Service |
| warn | sin healthcheck, sin `no-new-privileges`, imagen sin digest, Keycloak en `start-dev` | endurecimiento pendiente |

`deny` bloquea el pipeline; `warn` solo avisa.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `compose.rego` | Las políticas |
| `compose_test.rego` | 28 pruebas: cada regla con un caso que la activa y otro que no |
| `ejemplos/compose-inseguro.yml` | Compose inseguro a propósito, para demostrar que las políticas bloquean |

## Probar en local (con Docker abierto, desde la raíz del repositorio)

```powershell
# Pruebas de las políticas (28 tests, 28 passed)
docker run --rm -v "${PWD}:/project" -w /project openpolicyagent/conftest:v0.70.1 verify --policy policies/integracion

# Compose de desarrollo: 0 failures y avisos de endurecimiento pendiente
docker run --rm -v "${PWD}:/project" -w /project openpolicyagent/conftest:v0.70.1 test docker-compose.dev.yml --policy policies/integracion --namespace integracion.compose

# Compose inseguro de ejemplo: varias reglas deny en FAIL
docker run --rm -v "${PWD}:/project" -w /project openpolicyagent/conftest:v0.70.1 test policies/integracion/ejemplos/compose-inseguro.yml --policy policies/integracion --namespace integracion.compose
```

## Avisos pendientes en docker-compose.dev.yml

Los 10 avisos actuales son endurecimiento que no rompe el entorno local y se resolverá al generar
el Compose del sistema (fase 7, sprint 5): `no-new-privileges` en los cuatro servicios, imágenes
fijadas por digest, healthcheck en Keycloak y Keycloak en modo producción.
