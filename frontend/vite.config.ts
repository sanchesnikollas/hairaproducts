import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    // Bundle estava em 648KB single-chunk (~193KB gzip), bem acima do
    // orçamento de 300KB JS por app page. Split em chunks nomeados puxa
    // cada lib pesada em paralelo + permite cache eficiente entre deploys.
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — sempre carregado primeiro, raramente muda
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],

          // Recharts é gigante (~150kb gzipped). Só Dashboard e MetricsTab usam.
          // Em chunk separado, páginas que não usam não pagam o custo.
          'charts': ['recharts'],

          // Motion (framer-motion successor) — usado em várias páginas,
          // mas separar permite cache mesmo quando código de app muda
          'motion': ['motion'],

          // UI primitives (radix-like base-ui + utilities)
          // tw-animate-css e tailwindcss-animate são CSS-only (sem JS export),
          // ficam fora do chunk JS.
          'ui-vendor': [
            '@base-ui/react',
            'class-variance-authority',
            'clsx',
            'cmdk',
            'tailwind-merge',
          ],

          // Icons — lucide-react tree-shakes mas mesmo assim é grande
          'icons': ['lucide-react'],

          // Toast/notification + outras
          'misc-vendor': ['sonner'],
        },
      },
    },
    // Aceitamos 600KB por chunk individual no warning (vendor-react pode chegar)
    // mas o esperado é cada um < 250KB gzipped.
    chunkSizeWarningLimit: 600,
  },
})
