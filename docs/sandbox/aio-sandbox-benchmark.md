# AIO Sandbox 10 实例基准测试

> 测试日期: 2026-07-31
> 镜像: `ghcr.io/agent-infra/sandbox:1.11.0`（国内镜像 `enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.11.0`）
> 主机: macOS, 7.75 GiB Docker 内存限制

## 测试方法

- 使用 `docker run -d` 依次启动 10 个 sandbox 容器（端口 8081-8090）
- 启动后等待 30s 采集首次内存数据，再等 60s 复测确认稳定性
- 使用 `docker stats --no-stream` 采集内存/CPU，`docker system df` 采集磁盘

## 内存占用

| 容器 | 30s 内存 | 90s 内存 | CPU |
|------|---------|---------|-----|
| sandbox-bench-1 | 598.3 MiB | 597.2 MiB | 3.36% |
| sandbox-bench-2 | 593.8 MiB | 591.4 MiB | 1.44% |
| sandbox-bench-3 | 616.9 MiB | 617.8 MiB | 5.69% |
| sandbox-bench-4 | 628.0 MiB | 624.0 MiB | 2.85% |
| sandbox-bench-5 | 588.1 MiB | 585.9 MiB | 3.75% |
| sandbox-bench-6 | 589.1 MiB | 585.9 MiB | 6.85% |
| sandbox-bench-7 | 585.4 MiB | 580.9 MiB | 3.08% |
| sandbox-bench-8 | 580.8 MiB | 580.1 MiB | 3.21% |
| sandbox-bench-9 | 573.3 MiB | 569.5 MiB | 2.56% |
| sandbox-bench-10 | 586.1 MiB | 591.3 MiB | 4.31% |
| **合计** | **~5.95 GiB** | **~5.93 GiB** | - |

- 单实例均值: ~595 MiB
- 内存范围: 569 - 628 MiB
- 初始化后内存稳定，无增长趋势

## 磁盘占用

| 项目 | 大小 |
|------|------|
| 镜像（10 容器共享） | 12.2 GB |
| 单容器可写层 (RW) | 14 - 31 MB |
| 10 容器可写层合计 | ~209 MB |
| 增量磁盘开销（不含镜像） | ~209 MB |

## 启动性能

| 指标 | 数值 |
|------|------|
| 10 容器 `docker run` 完成 | 2 秒 |
| 全部 healthy | ~30 秒 |

## 关键结论

1. **内存**: 每个 sandbox 实例运行时占用 ~590-630 MiB，10 个实例共占 ~6 GiB。这是主要的资源瓶颈。
2. **磁盘**: 镜像层完全共享，每个容器仅 14-31 MB 可写层，磁盘增量开销极小。
3. **启动速度**: 10 个容器 2 秒内全部拉起，30 秒内全部 healthy，启动非常快。
4. **稳定性**: 内存在初始化后完全稳定（30s vs 90s 差异 < 5 MiB），无泄漏迹象。
5. **镜像体积**: 12.2 GB 镜像较大，但只拉取一次；运行时增量成本主要在内存。

## 清理命令

```bash
docker rm -f $(docker ps -q --filter name=sandbox-bench)
```
