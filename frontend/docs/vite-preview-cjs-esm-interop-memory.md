# Vite Preview CJS/ESM 互操作排障记忆

## 背景

在 `vp preview`（生产构建预览）场景下，页面加载后控制台报错：

- `Uncaught TypeError: (0 , _F.default) is not a function`
- `Uncaught TypeError: (0 , Tue.default) is not a function`

开发模式（`vp dev`）不一定复现，问题主要出现在生产产物的模块互操作阶段。

## 根因模式

`@ant-design/x` 的部分 ESM 文件会从 `@rc-component/util/lib/*` 引用工具函数。`lib` 是 CJS 产物，在生产打包后，某些 default interop 场景会出现运行时不兼容，最终触发 `xxx.default is not a function`。

典型触发点（通过 sourcemap 反查得到）：

- `@ant-design/x/es/conversations/index.js` -> `@rc-component/util/lib/pickAttrs`
- `@ant-design/x/es/sender/components/TextArea.js` -> `@rc-component/util/lib/utils/get`

## 已验证修复

在 `vite.config.ts` 中添加统一 alias，把 `@rc-component/util/lib` 全量重定向到 `@rc-component/util/es`：

```ts
resolve: {
  alias: {
    "@rc-component/util/lib": "@rc-component/util/es",
    "@": path.resolve(__dirname, "./src"),
  },
},
```

## 定位与验证流程（可复用）

1. 先构建带 sourcemap 的生产包：
   - `vp build -- --sourcemap`
2. 用 `@jridgewell/trace-mapping` 将 `components-*.js:line:column` 反查到源码文件。
3. 查看映射源码是否命中 `@rc-component/util/lib/*` 一类 CJS 路径。
4. 添加 alias 后重新构建并验证：
   - 产物 sourcemap 中不再出现 `@rc-component/util/lib/*`
   - `vp preview` 页面可正常运行

## 适用条件与边界

- 适用：`@ant-design/x` + Vite 生产预览出现 `*.default is not a function`，且 sourcemap 映射到 `@rc-component/util/lib/*`
- 不适用：与业务代码逻辑异常、浏览器权限策略提示（如 `Permissions policy violation`）等无关报错

## 结论

这是一个稳定可复用的构建互操作修复方案，优先级高于临时业务层 workaround。后续遇到同类症状，优先走 sourcemap 反查 + `lib -> es` alias 校正。
