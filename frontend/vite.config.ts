import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    svgr({
      svgrOptions: {
        icon: true, // 让 SVG 自适应 (width/height = 1em)
      },
    }),
  ],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: [
            "react",
            "react-dom",
            "antd",
            "axios",
            "lodash-es",
            "dayjs",
            "uuid",
            "mitt",
            "simplebar-react",
          ],
          markdown: [
            "react-markdown",
            "react-syntax-highlighter",
            "rehype-external-links",
            "rehype-highlight",
            "rehype-katex",
            "rehype-raw",
            "remark-gfm",
            "remark-math",
          ],
        },
      },
    },
  },
});
