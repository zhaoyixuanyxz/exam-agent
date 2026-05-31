import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const shared = process.env.EXAM_AGENT_SHARED === "1";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Plan A: allow Tailscale IP / Cloudflare tunnel Host headers
    ...(shared ? { host: true, allowedHosts: true } : {}),
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/export-files": "http://127.0.0.1:8000",
    },
  },
});
