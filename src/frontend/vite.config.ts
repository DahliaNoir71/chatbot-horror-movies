import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

/**
 * Injects a Content-Security-Policy meta tag into HTML files at build time.
 * Skipped in dev mode (Vite HMR requires inline scripts).
 * Note: frame-ancestors cannot be set via meta tag (CSP spec) — use HTTP headers on the production server.
 */
function cspPlugin(): Plugin {
  return {
    name: 'html-csp',
    transformIndexHtml(html, ctx) {
      if (ctx.server) return html
      const csp = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https://image.tmdb.org",
        "connect-src 'self'",
        "frame-src 'self' http://localhost:3000",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        'upgrade-insecure-requests',
      ].join('; ')
      return html.replace(
        '<head>',
        `<head>\n    <meta http-equiv="Content-Security-Policy" content="${csp}" />`,
      )
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  plugins: [vue(), tailwindcss() as any, cspPlugin()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        landing: resolve(__dirname, 'index.html'),
        chatbot: resolve(__dirname, 'chatbot.html'),
        admin: resolve(__dirname, 'admin.html'),
      },
    },
  },
})
