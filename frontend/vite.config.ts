import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // 用 127.0.0.1 而非 localhost：新版 Node 會把 localhost 先解析成 IPv6 (::1)，
        // 但後端 uvicorn 預設只綁 IPv4，會導致 proxy 連線失敗、整個 Dashboard 變空白。
        target: 'http://127.0.0.1:19000',
        changeOrigin: true,
      },
    },
  },
})
