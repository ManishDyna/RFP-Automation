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
        port: 3000,
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
        },
    },
});
