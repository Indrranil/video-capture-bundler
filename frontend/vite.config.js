import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// VITE_API_PORT (frontend/.env) controls where `npm run dev`'s proxy sends /api requests.
// Only matters for local dev — the production build is served same-origin by the FastAPI
// backend itself, so this has no effect there.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiPort = env.VITE_API_PORT || "5000";

  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": `http://localhost:${apiPort}`,
      },
    },
  };
});
