import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// @ts-expect-error plain ESM module without type declarations
import { assistantMiddleware } from './server/assistant.mjs'

// assistant-bridge: dev-only POST /api/assistant (staff chat). The static build has no endpoint; the client
// falls back to its keyword-search summary.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'assistant-bridge',
      configureServer(server) {
        server.middlewares.use(assistantMiddleware())
      },
    },
  ],
})
