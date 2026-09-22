#!/usr/bin/env python3
"""把 Docker 容器状态写成 Prometheus textfile collector 指标。

为什么不用 cadvisor（2026-09-22 实测，应用机 Ubuntu + kernel 6.8 + cgroup v2）：
cadvisor v0.45（Docker Hub 上唯一可拉的版本，gcr.io 在境内不可达）只能枚举 cgroup，
无法把 `/system.slice/docker-<id>.scope` 映射回容器，日志持续刷
`failed getting container info for ...: unknown container`，导出的 `container_*`
系列**没有 `name` 标签**（0 条），拿不到任何按容器的指标。
所以这里用 docker CLI 直接采集，由 node-exporter 的 textfile collector 暴露。

用法（每分钟跑一次，写文件是原子的，node-exporter 直接读）：

    * * * * * /home/ubuntu/monitoring/collect_container_metrics.py

输出：/home/ubuntu/monitoring/textfile/chat_agent_containers.prom
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

TEXTFILE_DIR = Path(os.getenv("TEXTFILE_DIR", "/home/ubuntu/monitoring/textfile"))
OUT_FILE = TEXTFILE_DIR / "chat_agent_containers.prom"

# 这些容器即使不存在也要输出一条 up=0 —— 否则「容器被删了」只会表现为指标静默消失，
# 而 Prometheus 无法对「某条将来可能存在的序列」做 absent 告警。
EXPECTED_PREFIX = os.getenv("EXPECTED_PREFIX", "chat-agent-")
EXPECTED_CONTAINERS = [
    n.strip()
    for n in os.getenv(
        "EXPECTED_CONTAINERS",
        "chat-agent-backend,chat-agent-frontend,chat-agent-postgres,chat-agent-evaluator,"
        "chat-agent-memory-governance,chat-agent-sites,chat-agent-promtail",
    ).split(",")
    if n.strip()
]

_UNITS = {
    "b": 1,
    "kb": 10**3,
    "mb": 10**6,
    "gb": 10**9,
    "tb": 10**12,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
}


def docker(*args: str) -> str:
    """以非交互 sudo 调 docker；失败返回空串（指标缺一条好过整脚本崩掉）。"""
    try:
        res = subprocess.run(
            ["sudo", "-n", "docker", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""
    return res.stdout if res.returncode == 0 else ""


def parse_size(text: str) -> float:
    """'16.25MiB' / '512MiB' / '1.5GiB' -> bytes。"""
    text = text.strip().replace(" ", "")
    if not text:
        return 0.0
    idx = 0
    while idx < len(text) and (text[idx].isdigit() or text[idx] in ".,"):
        idx += 1
    try:
        value = float(text[:idx].replace(",", ""))
    except ValueError:
        return 0.0
    unit = text[idx:].lower()
    return value * _UNITS.get(unit, 1)


def escaped(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def collect() -> list[str]:
    names = [n for n in docker("ps", "-a", "--format", "{{.Names}}").splitlines() if n]
    stats = {}
    for line in docker(
        "stats", "--no-stream", "--format", "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}"
    ).splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            stats[parts[0]] = (parts[1], parts[2])

    lines = [
        "# HELP docker_container_up 1 = 容器存在且在运行，0 = 不存在或已停止",
        "# TYPE docker_container_up gauge",
        "# HELP docker_container_restart_count 容器累计重启次数（docker RestartCount）",
        "# TYPE docker_container_restart_count counter",
        "# HELP docker_container_start_time_seconds 容器最近一次启动时间（Unix 秒）",
        "# TYPE docker_container_start_time_seconds gauge",
        "# HELP docker_container_memory_working_set_bytes 容器内存占用（docker stats）",
        "# TYPE docker_container_memory_working_set_bytes gauge",
        "# HELP docker_container_memory_limit_bytes 容器内存上限（0 = 未限制）",
        "# TYPE docker_container_memory_limit_bytes gauge",
        "# HELP docker_container_cpu_percent 容器 CPU 使用率百分比（docker stats 瞬时值）",
        "# TYPE docker_container_cpu_percent gauge",
    ]

    seen: set[str] = set()
    for name in sorted(set(names)):
        if not name.startswith(EXPECTED_PREFIX):
            continue
        seen.add(name)
        raw = docker("inspect", name, "--format", "{{json .}}")
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        state = obj.get("State") or {}
        label = f'name="{escaped(name)}"'
        lines.append(f"docker_container_up{{{label}}} {1 if state.get('Running') else 0}")
        lines.append(
            f"docker_container_restart_count{{{label}}} {int(obj.get('RestartCount') or 0)}"
        )
        started = (state.get("StartedAt") or "")[:19]
        if started:
            try:
                import datetime

                ts = datetime.datetime.fromisoformat(started).replace(
                    tzinfo=datetime.timezone.utc
                )
                lines.append(
                    f"docker_container_start_time_seconds{{{label}}} {ts.timestamp():.0f}"
                )
            except ValueError:
                pass
        limit = int((obj.get("HostConfig") or {}).get("Memory") or 0)
        lines.append(f"docker_container_memory_limit_bytes{{{label}}} {limit}")
        if name in stats:
            mem_usage, cpu_percent = stats[name]
            mem_bytes = parse_size(mem_usage.split("/")[0])
            lines.append(
                f"docker_container_memory_working_set_bytes{{{label}}} {mem_bytes:.0f}"
            )
            try:
                lines.append(
                    f"docker_container_cpu_percent{{{label}}} "
                    f"{float(cpu_percent.rstrip('%') or 0):.2f}"
                )
            except ValueError:
                pass

    # 期望存在但已经不见了的容器：显式写 up=0，让告警能判「容器消失」。
    # 只覆盖 EXPECTED_CONTAINERS（脚本无从得知「本该有哪些容器」），
    # chat-agent-* 前缀的容器即使不在期望列表里也一并补 0。
    missing = {n for n in EXPECTED_CONTAINERS if n not in seen}
    missing |= {n for n in names if n.startswith(EXPECTED_PREFIX) and n not in seen}
    for name in sorted(missing):
        lines.append(f'docker_container_up{{name="{escaped(name)}"}} 0')

    return lines


def main() -> None:
    TEXTFILE_DIR.mkdir(parents=True, exist_ok=True)
    content = "\n".join(collect()) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(TEXTFILE_DIR), prefix=".tmp-")
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    # node-exporter 容器以非 root 身份运行，textfile 必须 world-readable
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT_FILE)


if __name__ == "__main__":
    main()
