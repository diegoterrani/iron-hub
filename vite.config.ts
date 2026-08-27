import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: '/console/',
  plugins: [react()],
  server: {
    port: 3900,
    proxy: {
      '/hub': 'http://127.0.0.1:3901',
      '/api': 'http://127.0.0.1:3901',
      '/t': 'http://127.0.0.1:3901',
    },
  },
});

