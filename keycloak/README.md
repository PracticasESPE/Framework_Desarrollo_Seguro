# Realm de Keycloak del framework

`realm-framework.json` define el realm `framework` que usa el servicio de referencia `usuarios`.
`docker-compose.dev.yml` lo importa al arrancar Keycloak (`start-dev --import-realm`).

| Elemento | Valor | Para qué |
|---|---|---|
| Realm | `framework` | Emisor de los tokens: `http://localhost:<KEYCLOAK_PORT>/realms/framework` |
| Roles | `usuarios-lectura`, `usuarios-escritura` | Autorización por rol (llegará con los guards por rol) |
| Cliente | `usuarios-cli` (público, *direct access grants*) | Solo para pedir tokens en desarrollo y en `scripts/probar-jwt.mjs` |
| Mapper de audiencia | añade `usuarios-api` al claim `aud` | El guard del servicio exige esa audiencia |
| Usuario | `ana`, con los dos roles | Usuario de prueba |

Seguridad del realm: `sslRequired: external`, registro desactivado, protección contra fuerza
bruta y tokens de acceso de 5 minutos. La contraseña de `ana` no está en el archivo: Keycloak
sustituye `${KEYCLOAK_PRUEBA_PASSWORD}` con la variable de entorno al importar.

El cliente con *direct access grants* (usuario y contraseña) es solo para pruebas. Un cliente
real usaría el flujo de código con PKCE.

## Importar o reimportar

Keycloak solo importa un realm si todavía no existe:

```powershell
docker compose -f docker-compose.dev.yml up -d --force-recreate keycloak
docker compose -f docker-compose.dev.yml logs keycloak | Select-String "Realm 'framework' imported"
```

Si el realm ya existía con otra configuración, bórralo desde la consola de administración
(`http://localhost:<KEYCLOAK_PORT>/admin`) y vuelve a recrear el contenedor.
