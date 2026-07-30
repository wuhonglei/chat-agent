# AIO Sandbox 性能测试报告

> 项目地址：https://github.com/agent-infra/sandbox
>
> 测试时间：2026-07-28
>
> 测试环境：macOS Docker Desktop 29.6.2 (aarch64), 无 CPU/内存限制, shm_size=2GB
>
> 镜像版本：enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest (v1.0.0.156)

---

## 一、冷启动时间

从 `docker run` 发起至 API `/v1/sandbox` 返回 HTTP 200 的端到端耗时：

| 阶段 | 时间点 | 耗时 |
|------|--------|------|
| `docker run` 发起 | T+0s | — |
| entrypoint 初始化（用户创建、目录、Nginx 配置） | T+0~0.02s | 20ms |
| supervisord 启动 | T+0.11s | — |
| 全部 10 个子进程 spawned | T+1.13s | 1.02s |
| 全部子进程进入 RUNNING 状态 | T+2.17s | 1.04s |
| **API `/v1/sandbox` 返回 200** | **T+3.32s** | — |

**冷启动总时间：~3.3 秒**

容器内通过 supervisord 启动的 10 个服务：

1. python-server（Sandbox API 后端）
2. gem-server（WebSocket 代理）
3. browser（Chromium 浏览器）
4. nginx（反向代理）
5. websocat（WebSocket 桥接）
6. code-server（VSCode Server）
7. mcp-server-browser（MCP 浏览器服务）
8. jupyter（Jupyter Lab）
9. openbox（窗口管理器）
10. tigervnc（VNC 远程桌面）

---

## 二、内存占用

| 状态 | 内存 | 占主机比 | 进程数 |
|------|------|---------|--------|
| **空闲（刚启动）** | **503 MiB** | 6.3% | 177 |
| **Jupyter CPU 计算后** | **579 MiB** | 7.3% | 198 |
| **稳定后** | **578 MiB** | 7.3% | 198 |

### 各服务内存分布（空闲时 RSS Top）

| 服务 | RSS | 说明 |
|------|-----|------|
| **Chromium 浏览器**（主进程 + renderer + GPU + network） | **~400 MiB** | 占总内存约 70% |
| gem-server (Python) | 105 MiB | WebSocket 代理 + CDP |
| Jupyter Lab (Python 3.12) | 104 MiB | 交互式 Python 环境 |
| mcp-server-browser (Node.js) | 83 MiB | MCP 浏览器自动化 |
| Xvnc | 79 MiB | 虚拟帧缓冲 |
| python-server | 78 MiB | Sandbox REST API |
| code-server (VSCode) | 62 MiB + 61 MiB | Web IDE |

---

## 三、CPU 占用

| 状态 | CPU |
|------|-----|
| 空闲 | ~2% |
| Jupyter 重计算（200 轮循环求和）后瞬间 | ~1.7% |
| 5 秒后稳定 | ~2.1% |

CPU 在有计算任务时短暂升高后迅速回落，空闲时接近零。

---

## 四、关键结论与部署建议

### 资源画像

- **基础内存开销 ~500 MiB**，稳定运行 ~580 MiB
- **Chromium 浏览器是最大内存消耗源**，占 70%
- 空闲 CPU 开销可忽略（~2%）
- 进程数：空闲 177，工作后 ~200

### 生产配置建议

| 场景 | 最低 CPU | 最低内存 | 备注 |
|------|---------|---------|------|
| 单实例（含浏览器） | 1 vCPU | 1 GB | 完整能力 |
| 单实例（仅代码执行，无浏览器） | 0.5 vCPU | 512 MB | 需自定义镜像裁剪浏览器 |
| 10 并发 | 4 vCPU | 6 GB | 每实例 ~580 MiB |
| 50 并发 | 16 vCPU | 30 GB | 需监控容器调度 |

### 优劣势总结

| 优势 | 劣势 |
|------|------|
| 3.3s 冷启动，Docker 原生部署 | 镜像体积 2.35GB（压缩后），首次 pull 耗时 |
| 浏览器 + 终端 + Jupyter + VSCode 一体化 | 每实例 ~580 MiB，浏览器占大头 |
| 无需 KVM，普通云服务器即可运行 | 无内置多租户资源隔离（依赖 Docker/k8s 层） |
| REST API + MCP 协议，Agent 集成友好 | 浏览器组件不可单独裁剪（镜像内置） |
| 支持 Python/JS/Go SDK | — |

### 与当前 chat-agent execute_code 方案对比

| 维度 | execute_code（现有） | AIO Sandbox |
|------|---------------------|-------------|
| 隔离级别 | 进程内执行，无隔离 | Docker 容器级隔离 |
| 冷启动 | 无（进程常驻） | ~3.3s |
| 内存开销/实例 | 0（共享主进程） | ~580 MiB |
| 浏览器能力 | 无 | 完整 Chromium + VNC |
| 文件系统隔离 | 无 | 容器内独立文件系统 |
| 适合场景 | 内部可信代码执行 | 多租户 / 用户提交代码 / 需要浏览器 |

---

## 五、相关链接

- 项目仓库：https://github.com/agent-infra/sandbox
- 官方文档：https://sandbox.agent-infra.com
- Docker 镜像：ghcr.io/agent-infra/sandbox:latest
- 国内镜像：enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:latest
