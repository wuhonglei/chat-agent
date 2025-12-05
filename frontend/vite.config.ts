import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig, loadEnv } from "vite";
import svgr from "vite-plugin-svgr";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), "");
  console.info("VITE_PROXY_TARGET:", env.VITE_PROXY_TARGET);

  return {
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
          target: env.VITE_PROXY_TARGET || "http://localhost:8000",
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
            components: [
              "@ant-design/x",
              "@ant-design/x-markdown",
              "@ant-design/icons",
              "antd",
            ],
          },
        },
      },
    },
  };
});
