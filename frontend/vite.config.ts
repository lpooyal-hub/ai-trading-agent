import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function allowedHosts() {
  return (process.env.VITE_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim())
    .filter(Boolean);
}

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: allowedHosts(),
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
