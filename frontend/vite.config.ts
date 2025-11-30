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
          // 进一步拆分大块依赖，避免单 chunk 内存占用过高
          vendor: ["react", "react-dom"],
          utils: ["axios", "lodash-es", "dayjs", "uuid", "mitt"],
          ui: ["simplebar-react"],
          components: ["@ant-design/x", "@ant-design/icons", "antd"],
          markdown: [
            "react-markdown",
            "react-syntax-highlighter",
            "rehype-external-links",
            "rehype-raw",
            "remark-gfm",
          ],
          // 数学公式依赖最耗内存，单独拆分（若非必需可直接删除）
          math: ["rehype-katex", "remark-math"],
        },
      },
    },
  },
});
