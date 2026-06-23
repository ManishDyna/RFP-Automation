import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        host: '0.0.0.0',
        port: 3000,
        allowedHosts:["be-aramco-01.bahra-cables.com"],
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/dashboard': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                bypass: function (req) {
                    var _a;
                    // Only proxy API calls (fetch/XHR), not browser page navigations
                    if ((_a = req.headers.accept) === null || _a === void 0 ? void 0 : _a.includes('text/html')) {
                        return req.url;
                    }
                },
            },
            '/upload': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
});
