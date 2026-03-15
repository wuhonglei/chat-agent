import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";
import { generateComponentSchemas } from "./vite-plugins/generate-component-schemas";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), "");

  return {
    plugins: [
      react(),
      tailwindcss(),
      svgr({
        svgrOptions: {
          icon: true, // 让 SVG 自适应 (width/height = 1em)
        },
      }),
      generateComponentSchemas({
        inputPath: "src/componentTools/index.ts",
        outputDirs: [
          "src/componentTools/component-schemas",
          "public/component-schemas",
        ],
      }), // 在构建时自动生成组件 JSON Schema
    ],
    server: {
      host: true,
      port: 3000,
      proxy: {
        "/api": {
          target: env.VITE_PROXY_TARGET || "http://localhost:8000",
          changeOrigin: true,
          headers: {
            "X-Real-IP": "14.154.22.216", // 模拟真实环境访问时，会自动带上这个头，表示用户 IP
          },
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
      rolldownOptions: {
        output: {
          // 使用 Rolldown codeSplitting 替代已移除的 manualChunks，拆分大块依赖
          codeSplitting: {
            groups: [
              {
                name: "vendor",
                test: /node_modules[\\/](react|react-dom)/,
                priority: 40,
              },
              {
                name: "utils",
                test: /node_modules[\\/](axios|lodash-es|dayjs|uuid|mitt)/,
                priority: 30,
              },
              {
                name: "ui",
                test: /node_modules[\\/]simplebar-react/,
                priority: 20,
              },
              {
                name: "components",
                test: /node_modules[\\/](@ant-design[\\/]x|@ant-design[\\/]x-markdown|@ant-design[\\/]icons|antd)/,
                priority: 10,
              },
            ],
          },
        },
      },
    },
  };
});
