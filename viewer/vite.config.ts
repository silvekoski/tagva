import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

declare const process: { env: Record<string, string | undefined> };

const api = process.env.VIEWER_API ?? "http://127.0.0.1:8000";
const proxy = { "/api": api, "/scan": api, "/documents": api, "/models": api };
const isolation = (coep: string) => ({ "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Embedder-Policy": coep });

const tweakcnPreview = (): Plugin => ({
  name: "tweakcn-live-preview",
  apply: "serve",
  transformIndexHtml: () => [
    { tag: "script", attrs: { src: "https://tweakcn.com/live-preview.min.js", crossorigin: "anonymous" }, injectTo: "head" },
  ],
});

export default defineConfig({
  plugins: [react(), tailwindcss(), tweakcnPreview()],
  resolve: { alias: { "@": decodeURIComponent(new URL("./src", import.meta.url).pathname) } },
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy, headers: isolation("credentialless") },
  preview: { host: "127.0.0.1", port: 5173, strictPort: true, proxy, headers: isolation("require-corp") },
  optimizeDeps: { exclude: ["onnxruntime-web"] },
  build: {
    chunkSizeWarningLimit: 1000,
    rolldownOptions: { output: { codeSplitting: { groups: [{ name: "three", test: /node_modules[\\/]three[\\/]/ }] } } },
  },
});
