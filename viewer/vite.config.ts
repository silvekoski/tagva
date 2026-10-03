import { defineConfig } from "vite";

declare const process: { env: Record<string, string | undefined> };

const api = process.env.VIEWER_API ?? "http://127.0.0.1:8000";
const proxy = { "/api": api, "/scan": api, "/documents": api };

export default defineConfig({
  server: { port: 5173, strictPort: true, proxy },
  preview: { port: 5173, strictPort: true, proxy },
  build: { chunkSizeWarningLimit: 1000 },
});
