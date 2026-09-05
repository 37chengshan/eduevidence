import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  build: {
    outDir: "../web/studio",
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
  },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
