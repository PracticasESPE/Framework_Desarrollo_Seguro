import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// En producción la API del motor sirve el dashboard compilado (dist/), así que comparten origen
// y no hace falta CORS. En desarrollo, Vite reenvía a la API las rutas que no son del dashboard.
const API = 'http://127.0.0.1:8000'
const RUTAS_API = ['/salud', '/fases', '/configuracion', '/documentos', '/ejecuciones']

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: Object.fromEntries(RUTAS_API.map((ruta) => [ruta, API])),
  },
  preview: { host: '127.0.0.1' },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/pruebas/preparar.ts'],
    restoreMocks: true,
  },
})
