import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev-only /api/assistant middleware is added in Milestone 7 (assistant bridge).
export default defineConfig({
  plugins: [react(), tailwindcss()],
})
