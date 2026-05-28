import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Split Vue core
          "vue-core": ["vue"],
          // Split Element Plus
          "element-plus": ["element-plus"],
        },
      },
    },
    // Enable CSS code splitting
    cssCodeSplit: true,
    // Generate sourcemaps for production debugging
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8080",
    },
  },
});
