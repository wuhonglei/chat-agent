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
    """执行命令并打印日志"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8'
        )
        print(f"执行成功：{cmd}\n输出：{result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"执行失败：{cmd}\n错误：{e.stderr}")
        return False


def is_tag_on_main_branch(tag_name, repo_path):
    """检查标签是否在 main 分支上"""
    try:
        # 先获取标签指向的 commit
        result = subprocess.run(
            f"git rev-parse {tag_name}",
            cwd=repo_path, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8'
        )
        tag_commit = result.stdout.strip()

        # 检查该 commit 是否在 main 分支上（包括本地和远程分支）
        result = subprocess.run(
            f"git branch -a --contains {tag_commit}",
            cwd=repo_path, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8'
        )
        branches = result.stdout.strip()

        # 检查是否包含 main 分支（可能是 main、origin/main 或 remotes/origin/main）
        return ('main' in branches or 'origin/main' in branches or
                'remotes/origin/main' in branches)
    except subprocess.CalledProcessError as e:
        print(f"检查标签分支失败：{e.stderr}")
        return False


@webhook.hook(event_type='create')
def on_tag_create(payload):
    # 仅监听「标签创建」事件（GitHub 事件类型为 create，且 ref_type=tag）
    if payload.get('ref_type') != 'tag':
        print("非标签事件，忽略")
        return "忽略"

    tag_name = payload.get('ref')
    print(f"收到标签推送：{tag_name}，检查是否在 main 分支...")

    # 先拉取最新的标签和分支信息
    if not run_command("git fetch origin --tags --prune", REPO_PATH):
        return "部署失败：git fetch 出错", 500

    if not run_command("git fetch origin main", REPO_PATH):
        return "部署失败：git fetch main 出错", 500

    # 检查标签是否在 main 分支上
    if not is_tag_on_main_branch(tag_name, REPO_PATH):
        print(f"标签 {tag_name} 不在 main 分支上，忽略")
        return f"忽略：标签 {tag_name} 不在 main 分支上", 200

    print(f"标签 {tag_name} 在 main 分支上，开始部署...")

    # 拉取代码
    if not run_command("git pull origin main --depth=1", REPO_PATH):
        return "部署失败：git pull 出错", 500

    # 执行 deploy.sh
    if not run_command(f"bash {DEPLOY_SCRIPT}", REPO_PATH):
        return "部署失败：deploy.sh 出错", 500

    return f"部署成功：{tag_name}", 200


if __name__ == '__main__':
    # 仅用于开发环境，生产环境请使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=9000, debug=DEBUG)
