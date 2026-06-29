import { defineConfig, loadEnv, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { jsonSuccessBody } from './src/lib/api/response';
import { getHealthData } from './src/lib/api/health';
import { getManifest } from './src/lib/api/manifest';

/** Serves OpenClaw standard routes during Vite dev (production uses Netlify Functions). */
function openclawApiDevPlugin(): Plugin {
  return {
    name: 'openclaw-api-dev',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = req.url?.split('?')[0] ?? '';
        if (path === '/api/v1/health') {
          const body = jsonSuccessBody(getHealthData());
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.setHeader(
            'Access-Control-Allow-Headers',
            'Content-Type, Authorization, X-API-Key'
          );
          res.end(JSON.stringify(body));
          return;
        }
        if (path === '/api/v1/manifest') {
          const body = jsonSuccessBody(getManifest());
          res.statusCode = 200;
          res.setHeader('Content-Type', 'application/json; charset=utf-8');
          res.setHeader(
            'Access-Control-Allow-Headers',
            'Content-Type, Authorization, X-API-Key'
          );
          res.end(JSON.stringify(body));
          return;
        }
        next();
      });
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  if (env.VITE_APP_NAME) process.env.VITE_APP_NAME = env.VITE_APP_NAME;
  if (env.NEXT_PUBLIC_APP_NAME) process.env.NEXT_PUBLIC_APP_NAME = env.NEXT_PUBLIC_APP_NAME;
  if (env.OPENCLAW_API_KEY) process.env.OPENCLAW_API_KEY = env.OPENCLAW_API_KEY;

  return {
    plugins: [react(), openclawApiDevPlugin()],
    server: {
      port: 3010,
    },
    optimizeDeps: {
      exclude: ['lucide-react'],
    },
  };
});
