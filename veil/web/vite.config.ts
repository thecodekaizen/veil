import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // GitHub Pages serves the site under /veil/; local dev and preview use /
  base: process.env.VEIL_BASE || '/',
  plugins: [react()],
  server: {
    port: 3000,
    host: '127.0.0.1',
    proxy: {
      '/v1': {
        target: process.env.VEIL_API_URL || 'http://127.0.0.1:8020',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: process.env.VEIL_API_URL || 'http://127.0.0.1:8020',
        changeOrigin: true,
      },
    },
  },
});
