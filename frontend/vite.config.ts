import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import svgr from "vite-plugin-svgr";
import { defineConfig, loadEnv } from "vite-plus";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// .env 不会自动进入 process.env；代理目标需 loadEnv。使用与 NODE_ENV 对应的 mode（.env 在任意 mode 下都会加载）
const env = loadEnv(
  process.env.NODE_ENV === "production" ? "production" : "development",
  __dirname,
  "VITE_",
);
const apiProxyTarget = env.VITE_PROXY_TARGET || "http://localhost:8000";
const webTitle = env.VITE_WEB_TITLE || "然宝";
const webTabTitle = env.VITE_WEB_TAB_TITLE || "然宝 - 免费中文 AI 智能助手";

// https://vitejs.dev/config/
export default defineConfig({
  define: {
    __WEB_TITLE__: JSON.stringify(webTitle),
    __WEB_TAB_TITLE__: JSON.stringify(webTabTitle),
  },
  lint: {
    plugins: ["oxc", "typescript", "unicorn", "react"],
    categories: {
      // 交给 Oxlint 的分类规则统一管理，避免手写大段 core rules 列表
      correctness: "error",
    },
    env: {
      builtin: true,
      node: true,
    },
    globals: {
      aegis: "readonly",
    },
    ignorePatterns: [".agents/**", ".cursor/skills/**"],
    overrides: [
      {
        files: ["**/*.ts", "**/*.tsx"],
        rules: {
          // 核心 correctness/suspicious 交给 categories；这里只保留项目偏好与少量 TS/React 规则
          "no-shadow": "off",
          "no-unused-vars": "warn",
          "@typescript-eslint/no-explicit-any": "warn",
          "@typescript-eslint/ban-ts-comment": "error",
          "@typescript-eslint/no-require-imports": "error",
          "react-hooks/rules-of-hooks": "error",
          "react-hooks/exhaustive-deps": "warn",
          "react/react-in-jsx-scope": "off",
          "react/no-children-prop": "off",
          "react/only-export-components": "warn",
        },
        env: {
          es2026: true,
          browser: true,
        },
      },
    ],
    options: {
      typeAware: false,
      typeCheck: false,
    },
  },
  fmt: {
    semi: true,
    trailingComma: "es5",
    singleQuote: false,
    printWidth: 120,
    tabWidth: 2,
    useTabs: false,
    bracketSpacing: true,
    bracketSameLine: false,
    arrowParens: "avoid",
    endOfLine: "lf",
    quoteProps: "as-needed",
    jsxSingleQuote: false,
    proseWrap: "preserve",
    sortPackageJson: false,
    ignorePatterns: [
      "node_modules/",
      "dist/",
      "build/",
      "*.min.js",
      "*.min.css",
      "*.bundle.js",
      "package-lock.json",
      "yarn.lock",
      ".agents/**",
      ".cursor/skills/**",
      "backend/skills/**",
      ".env",
      ".env.local",
      ".env.*.local",
      ".vscode/",
      ".idea/",
      ".DS_Store",
      "Thumbs.db",
      "*.log",
      "npm-debug.log*",
      "yarn-debug.log*",
      "yarn-error.log*",
      "coverage/",
      "*.tmp",
      "*.temp",
    ],
  },
  staged: {
    "*.{ts,tsx,js,jsx}": "bash ./scripts/vp-check-staged.sh",
    // 经脚本过滤后再 fmt/check，避免仅暂存 skills 目录下文件时 vp 无目标而失败
    "*.{json,css,md}": "bash ./scripts/vp-fmt-staged.sh",
  },
  plugins: [
    react(),
    tailwindcss(),
    svgr({
      svgrOptions: {
        icon: true, // 让 SVG 自适应 (width/height = 1em)
      },
    }),
    {
      name: "inject-web-tab-title",
      transformIndexHtml(html) {
        return html.replace(/<title>[\s\S]*?<\/title>/, `<title>${webTabTitle}</title>`);
      },
    },
  ],
  server: {
    host: true,
    port: 3000,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        headers: {
          "X-Real-IP": "14.154.22.216", // 模拟真实环境访问时，会自动带上这个头，表示用户 IP
        },
      },
    },
  },
  resolve: {
    alias: {
      "@rc-component/util/lib": "@rc-component/util/es",
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
});
