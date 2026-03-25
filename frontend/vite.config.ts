import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import svgr from "vite-plugin-svgr";
import { defineConfig } from "vite-plus";
import { generateComponentSchemas } from "./vite-plugins/generate-component-schemas.ts";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const oxfmtrc = JSON.parse(readFileSync(path.join(__dirname, ".oxfmtrc.json"), "utf8")) as { ignorePatterns: string[] };

// https://vitejs.dev/config/
export default defineConfig({
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
    ignorePatterns: [".agents/**"],
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
    ignorePatterns: oxfmtrc.ignorePatterns,
  },
  staged: {
    "*.{ts,tsx,js,jsx}": "vp check --fix",
    "*.{json,css,md}": "vp fmt",
  },
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
      outputDirs: ["src/componentTools/component-schemas", "public/component-schemas"],
    }), // 在构建时自动生成组件 JSON Schema
  ],
  server: {
    host: true,
    port: 3000,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8000",
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
