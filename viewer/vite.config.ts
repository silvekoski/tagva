import { defineConfig } from "vite";

declare const process: { env: Record<string, string | undefined> };

const api = process.env.VIEWER_API ?? "http://127.0.0.1:8000";
const proxy = { "/api": api, "/scan": api, "/documents": api, "/models": api };
const headers = { "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Embedder-Policy": "require-corp" };

export default defineConfig({
  server: { port: 5173, strictPort: true, proxy, headers },
  preview: { port: 5173, strictPort: true, proxy, headers },
  optimizeDeps: { exclude: ["onnxruntime-web"] },
  build: { chunkSizeWarningLimit: 1000 },
});
