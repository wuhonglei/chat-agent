from github_webhook import Webhook
from flask import Flask
import subprocess
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

DEBUG = os.getenv('DEBUG', 'False') == 'True'
app = Flask(__name__)

# 从环境变量读取配置，如果不存在则使用默认值（生产环境必须设置）
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
if not WEBHOOK_SECRET:
    raise ValueError(
        "WEBHOOK_SECRET 环境变量未设置。请在 .env 文件中设置或通过环境变量传入。"
    )

webhook = Webhook(app, endpoint="/webhook", secret=WEBHOOK_SECRET)

# 配置项（从环境变量读取）
REPO_PATH = os.getenv('REPO_PATH', '/home/ubuntu/ai-doc')
DEPLOY_SCRIPT = os.getenv('DEPLOY_SCRIPT', '/home/ubuntu/ai-doc/deploy.sh')


def run_command(cmd, cwd):
    """执行命令并实时打印日志"""
    try:
        print(f"执行命令：{cmd}\n工作目录：{cwd}")
        result = subprocess.run(
            cmd, cwd=cwd, shell=True, check=True,
            text=True, capture_output=False, timeout=None
        )
        print(f"执行成功：{cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"执行失败：{cmd}\n退出代码：{e.returncode}")
        return False


@webhook.hook(event_type='push')
def on_push(payload):
    # 仅监听 main 分支的 push 事件
    ref = payload.get('ref', '')
    if ref != 'refs/heads/main':
        print(f"非 main 分支推送，忽略：{ref}")
        return "忽略"

    print("收到 main 分支推送，开始部署...")

    # 确保在 main 分支上
    if not run_command("git checkout main", REPO_PATH):
        return "部署失败：git checkout 出错", 500

    # 拉取代码
    if not run_command("git pull origin main", REPO_PATH):
        return "部署失败：git pull 出错", 500

    # 打印最新 commit 信息
    if not run_command("git log --oneline -1", REPO_PATH):
        return "部署失败：git log 出错", 500

    # 执行 deploy.sh
    if not run_command(f"bash {DEPLOY_SCRIPT}", REPO_PATH):
        return "部署失败：deploy.sh 出错", 500

    return "部署成功", 200


if __name__ == '__main__':
    # 仅用于开发环境，生产环境请使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=9000, debug=DEBUG)
