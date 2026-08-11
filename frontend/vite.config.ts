import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function allowedHosts() {
  return (process.env.VITE_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
}

// When served through a TLS reverse proxy (e.g. trade.42222.cloud -> this
// container on :3000/:5173), Vite's default HMR client tries to open a
// websocket back to the container's own host:port (ws://localhost:5173),
// which the browser can't reach. Set VITE_HMR_HOST/VITE_HMR_PROTOCOL/
// VITE_HMR_CLIENT_PORT to point the client at the public proxy address
// instead. Left unset, Vite falls back to its normal same-origin behavior
// (fine for direct local access on localhost:5173/localhost:3000).
function hmrConfig() {
  const host = process.env.VITE_HMR_HOST;
  if (!host) return undefined;
  return {
    host,
    protocol: process.env.VITE_HMR_PROTOCOL ?? "wss",
    clientPort: process.env.VITE_HMR_CLIENT_PORT ? Number(process.env.VITE_HMR_CLIENT_PORT) : 443,
  };
}

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: allowedHosts(),
    hmr: hmrConfig(),
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
