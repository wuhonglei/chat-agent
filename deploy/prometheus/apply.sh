#!/usr/bin/env bash
# 把 deploy/prometheus/ 下的规则文件同步到线上 Prometheus 并触发重载。
#
# 为什么需要这个脚本（Prometheus 不会自动应用规则）：
#   1) Prometheus **没有** 配置文件/规则文件的自动监视（不像 promtail 自带 watchConfig）；
#      它只在「进程启动」或「收到重载信号」时读取 rule_files。
#   2) 仓库里的规则只是源码；Prometheus 跑在监控机（默认 1.12.53.9）上，读的是
#      宿主 /root/prometheus/rules/（容器内 /etc/prometheus/rules/，只读挂载）。
#   3) 所以生效 = 两步：文件放进 rule_files 的 glob 目录 + 触发重载。
#
# 重载方式（按可用性回退）：
#   POST /-/reload        —— 需要容器带 --web.enable-lifecycle（线上已加）
#   kill -s HUP <pid>     —— 不需要任何开关，直接给进程发 SIGHUP
#   docker restart        —— 兜底
# 重载失败（配置语法错）时 Prometheus 会**保留旧配置继续运行**，不会挂；但仍应先校验再重载。
#
# 用法（在仓库里执行）：
#   PROM_SSH=ubuntu@1.12.53.9 bash deploy/prometheus/apply.sh
#   需要免密 ssh（或导出 SSHPASS 走 sshpass -e）；目标机需有 `sudo -n` 权限。
#
# 安全闸门：第 0 步会比对本地 HEAD 与 origin HEAD，本地落后就中止——在落后的 checkout 里
# 同步会把已被修掉的旧规则推回线上（比「没生效」更糟）。确实要强推用 FORCE_SYNC=1。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RULE_SRC="$REPO_DIR/deploy/prometheus"
PROM_SSH="${PROM_SSH:-ubuntu@1.12.53.9}"
PROM_API="${PROM_API:-http://127.0.0.1:9090}" # 从监控机本机访问
RULES_DEST="${RULES_DEST:-/root/prometheus/rules}"
FILES=(alerting_rules.yml recording_rules.yml container_alerting_rules.yml)

if [ -n "${SSHPASS:-}" ]; then
  SSH=(sshpass -e ssh -o StrictHostKeyChecking=no -o PreferredAuthentications=password \
    -o PubkeyAuthentication=no -o NumberOfPasswordPrompts=1 -o ConnectTimeout=10)
else
  SSH=(ssh -o ConnectTimeout=10)
fi

echo "==> 0/4 确认规则源版本不落后于 origin（防止把旧规则推回线上）"
if [ "${FORCE_SYNC:-}" = "1" ]; then
  echo "    FORCE_SYNC=1，跳过版本比对"
elif git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
  branch="$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [ -z "$branch" ] || [ "$branch" = "HEAD" ]; then
    ref="HEAD"
  else
    ref="refs/heads/$branch"
  fi
  local_head="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
  if command -v timeout >/dev/null 2>&1; then
    remote_head="$(GIT_TERMINAL_PROMPT=0 timeout 20 git -C "$REPO_DIR" ls-remote origin "$ref" 2>/dev/null | awk '{print $1}' || true)"
  else
    remote_head="$(GIT_TERMINAL_PROMPT=0 git -C "$REPO_DIR" ls-remote origin "$ref" 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [ -z "$local_head" ] || [ -z "$remote_head" ]; then
    echo "    ⏭️  跳过比对：拿不到本地 HEAD 或 origin/$branch 的 HEAD（离线 / 无权限 / 该分支还没推到 origin）"
  elif [ "$local_head" = "$remote_head" ]; then
    echo "    ✅ 本地 ${local_head:0:7} 与 origin/$branch 一致"
  elif git -C "$REPO_DIR" merge-base --is-ancestor "$local_head" "$remote_head" 2>/dev/null; then
    echo "    ❌ 本地 ${local_head:0:7} 落后于 origin/$branch ${remote_head:0:7}：先 git pull 再同步，"
    echo "       否则会把已被修掉的旧规则推回线上（确实要强推：FORCE_SYNC=1）"
    exit 1
  else
    echo "    ⚠️  本地 ${local_head:0:7} 不在 origin/$branch 历史里（有未推送的本地提交），照常同步"
  fi
else
  echo "    ⏭️  跳过比对：$REPO_DIR 不是 git 仓库（沙箱 / 打包产物环境）"
fi

echo "==> 1/4 传输规则文件 → $PROM_SSH:/tmp"
for f in "${FILES[@]}"; do
  "${SSH[@]}" "$PROM_SSH" "cat > /tmp/$f" < "$RULE_SRC/$f"
  echo "    $f"
done

echo "==> 2/4 安装到 $RULES_DEST 并用 promtool 校验（失败就中止，不动线上运行中的配置）"
"${SSH[@]}" "$PROM_SSH" 'bash -s' <<EOF
set -e
for f in ${FILES[*]}; do sudo -n install -m 644 /tmp/\$f $RULES_DEST/\$f; done
sudo -n docker run --rm -v /root/prometheus:/p:ro --entrypoint /bin/promtool \
  prom/prometheus:latest check rules $(for f in "${FILES[@]}"; do printf '/p/rules/%s ' "$f"; done)
EOF

echo "==> 3/4 触发重载"
code="$("${SSH[@]}" "$PROM_SSH" "curl -s -X POST -o /dev/null -w '%{http_code}' $PROM_API/-/reload" || true)"
if [ "$code" = "200" ]; then
  echo "    POST /-/reload -> 200"
else
  echo "    POST /-/reload -> ${code:-失败}（可能没开 --web.enable-lifecycle），改用 SIGHUP"
  "${SSH[@]}" "$PROM_SSH" 'sudo -n docker kill -s HUP prometheus'
fi

echo "==> 4/4 校验线上运行态"
"${SSH[@]}" "$PROM_SSH" 'python3 -' <<'PY'
import json
import urllib.request

PROM = "http://127.0.0.1:9090"


def get(path):
    with urllib.request.urlopen(PROM + path, timeout=10) as resp:
        return json.load(resp)


groups = get("/api/v1/rules")["data"]["groups"]
rules = [r for g in groups for r in g["rules"]]
bad = [r["name"] for r in rules if r.get("lastError")]
note = "" if all(r.get("health") for r in rules) else "（刚重载完可能还有规则未评估，health 为空是暂时的）"
print(f"    规则 {len(rules)} 条，lastError {len(bad)} {bad or ''} {note}")
targets = get("/api/v1/targets")["data"]["activeTargets"]
print(f"    targets up {sum(1 for t in targets if t['health'] == 'up')}/{len(targets)}")
ams = get("/api/v1/alertmanagers")["data"]["activeAlertmanagers"]
print(f"    Alertmanager {[a['url'] for a in ams] or '未配置'}")
PY

echo "==> 完成"
