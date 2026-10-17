import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { configDefaults, defineConfig } from 'vitest/config'
import { settingsEnv } from './app-settings'

const root = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': root } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
    // Same values next.config.ts passes to the browser, read from config.yaml.
    env: settingsEnv(root),
    // Playwright's end-to-end specs run with `npm run test:e2e`, not Vitest.
    exclude: [...configDefaults.exclude, 'e2e/**'],
  },
})
