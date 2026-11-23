import { ConfiguracionInvalida, leerEntorno } from './entorno';

const CLAVE = 'clave-de-prueba';

const valido = {
  NODE_ENV: 'development',
  PORT: '3000',
  DATABASE_URL: `postgresql://servicio:${CLAVE}@localhost:5432/servicio_db`,
  KEYCLOAK_ISSUER: 'http://localhost:8081/realms/framework',
  KEYCLOAK_AUDIENCE: 'servicio-api',
};

function problemas(env: NodeJS.ProcessEnv): string[] {
  try {
    leerEntorno(env, 3000);
  } catch (error) {
    if (error instanceof ConfiguracionInvalida) return error.problemas;
    throw error;
  }
  return [];
}

describe('leerEntorno', () => {
  it('en desarrollo publica /docs y registra todo', () => {
    const entorno = leerEntorno(valido, 3000);

    expect(entorno).toMatchObject({
      nombre: 'development',
      puerto: 3000,
      documentacion: true,
    });
    expect(entorno.registro).toContain('debug');
  });

  it('sin NODE_ENV asume producción: sin /docs y sin depuración en el registro', () => {
    const entorno = leerEntorno({ ...valido, NODE_ENV: undefined }, 3000);

    expect(entorno.nombre).toBe('production');
    expect(entorno.documentacion).toBe(false);
    expect(entorno.registro).not.toContain('debug');
  });

  it('en pruebas solo registra advertencias y errores', () => {
    expect(leerEntorno({ ...valido, NODE_ENV: 'test' }, 3000).registro).toEqual(
      ['fatal', 'error', 'warn'],
    );
  });

  it('sin PORT usa el puerto de la plantilla', () => {
    expect(leerEntorno({ ...valido, PORT: undefined }, 3002).puerto).toBe(3002);
  });

  it('rechaza un NODE_ENV desconocido', () => {
    expect(problemas({ ...valido, NODE_ENV: 'staging' })).toEqual([
      'NODE_ENV debe ser development, test, production',
    ]);
  });

  it.each(['80', '70000', 'abc', '3000; rm'])(
    'rechaza el puerto %s',
    (puerto) => {
      expect(problemas({ ...valido, PORT: puerto })).toEqual([
        'PORT debe ser un número entre 1024 y 65535',
      ]);
    },
  );

  it('reúne todas las variables que faltan en un solo error', () => {
    expect(problemas({ NODE_ENV: 'development' })).toEqual([
      'Falta DATABASE_URL',
      'Falta KEYCLOAK_ISSUER',
      'Falta KEYCLOAK_AUDIENCE',
    ]);
  });

  it('rechaza URL que no son de PostgreSQL ni de Keycloak', () => {
    expect(
      problemas({
        ...valido,
        DATABASE_URL: 'mysql://usuario:clave@localhost/base',
        KEYCLOAK_ISSUER: 'javascript:alert(1)',
        KEYCLOAK_AUDIENCE: 'dos palabras',
        KEYCLOAK_JWKS_URI: 'file:///etc/passwd',
      }),
    ).toEqual([
      'DATABASE_URL debe ser una URL postgresql://',
      'KEYCLOAK_ISSUER debe ser la URL http(s) del realm',
      'KEYCLOAK_AUDIENCE solo admite letras, números, «.», «_» y «-»',
      'KEYCLOAK_JWKS_URI debe ser una URL http(s)',
    ]);
  });

  it.each([
    [
      'la contraseña de .env.example',
      'postgresql://servicio:CAMBIAR@db:5432/servicio_db',
    ],
    ['ninguna contraseña', 'postgresql://servicio@db:5432/servicio_db'],
  ])('en producción rechaza %s', (_caso, url) => {
    expect(
      problemas({ ...valido, NODE_ENV: 'production', DATABASE_URL: url }),
    ).toHaveLength(1);
  });

  it('en desarrollo admite la contraseña de .env.example', () => {
    const url = 'postgresql://servicio:CAMBIAR@localhost:5432/servicio_db';

    expect(problemas({ ...valido, DATABASE_URL: url })).toEqual([]);
  });

  it('el error nunca incluye el valor de una variable', () => {
    let mensaje = '';
    try {
      leerEntorno(
        {
          ...valido,
          NODE_ENV: 'production',
          DATABASE_URL: `mysql://u:${CLAVE}@db/x`,
        },
        3000,
      );
    } catch (error) {
      mensaje = (error as Error).message;
    }

    expect(mensaje).toContain('DATABASE_URL');
    expect(mensaje).not.toContain(CLAVE);
  });
});
