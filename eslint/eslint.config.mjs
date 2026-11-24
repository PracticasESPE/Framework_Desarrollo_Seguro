// @ts-check
// ESLint del Gate 1 para los servicios generados con la plantilla (fase 4, #71).
//
// Vive en el framework y no en cada servicio: el código generado (y el LLM que completa su lógica
// de negocio) no puede desactivar ni relajar estas reglas. Son las del servicio de referencia
// (services/usuarios), sin Prettier: eslint-plugin-security y las reglas de typescript-eslint que
// usan los tipos.
//
// Se ejecuta desde la carpeta del servicio, con este archivo como --config (ver
// scripts/gate1-servicios.sh): esa carpeta es la base de las rutas y la raíz de su tsconfig.json,
// y los tipos de sus dependencias salen de su propio node_modules.
import eslint from '@eslint/js';
import pluginSecurity from 'eslint-plugin-security';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // Solo el código que se ejecuta en producción: las pruebas las valida Jest.
    ignores: ['src/generated/**', 'dist/**', 'node_modules/**', 'coverage/**', '**/*.spec.ts'],
  },
  eslint.configs.recommended,
  pluginSecurity.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      globals: { ...globals.node },
      sourceType: 'commonjs',
      parserOptions: {
        projectService: true,
        tsconfigRootDir: process.cwd(),
      },
    },
  },
  {
    rules: {
      // Las mismas excepciones que el servicio de referencia.
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-floating-promises': 'warn',
      '@typescript-eslint/no-unsafe-argument': 'warn',
      // Lo que prohíbe el generador de lógica en el código del LLM, como error y no como aviso:
      // un eval con datos externos solo era un aviso que no bloqueaba el Gate 1 (#73).
      'no-eval': 'error',
      'no-new-func': 'error',
      'security/detect-eval-with-expression': 'error',
      'security/detect-child-process': 'error',
      'security/detect-non-literal-require': 'error',
    },
  },
);
