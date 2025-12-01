from github_webhook import Webhook
from flask import Flask
import subprocess
import os
import threading
from dotenv import load_dotenv
from loguru import logger

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
        logger.info(f"执行命令：{cmd}\n工作目录：{cwd}")

        # 使用 Popen 实时读取输出
        process = subprocess.Popen(
            cmd, cwd=cwd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 将 stderr 合并到 stdout
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )

        # 实时读取并打印输出
        for line in process.stdout:
            logger.info(line.rstrip())

        # 等待进程完成
        process.wait()

        if process.returncode == 0:
            logger.info(f"执行成功：{cmd}")
            return True
        else:
            logger.error(f"执行失败：{cmd}")
            logger.error(f"退出代码：{process.returncode}")
            return False

    except FileNotFoundError as e:
        logger.error(f"执行失败：{cmd}")
        logger.error(f"文件未找到：{e}")
        return False
    except Exception as e:
        logger.error(f"执行失败：{cmd}")
        logger.error(f"未知错误：{e}")
        return False


def async_deploy(commit_sha=None, commit_message=None):
    """异步执行部署任务"""
    logger.info("开始异步部署任务...")

    try:
        # 确保在 main 分支上
        if not run_command("git checkout main", REPO_PATH):
            logger.error("异步部署失败：git checkout 出错")
            return

        # 拉取代码
        if not run_command("git pull origin main", REPO_PATH):
            logger.error("异步部署失败：git pull 出错")
            return

        # 打印最新 commit 信息
        if not run_command("git log --oneline -1", REPO_PATH):
            logger.error("异步部署失败：git log 出错")
            return

        # 执行 deploy.sh
        if not run_command(f"bash {DEPLOY_SCRIPT}", REPO_PATH):
            logger.error(f"异步部署失败：deploy.sh 执行出错 ({DEPLOY_SCRIPT})")
            return

        logger.info("异步部署成功完成！")

    except Exception as e:
        logger.error(f"异步部署出现异常：{e}")


@webhook.hook(event_type='push')
def on_push(payload):
    # 仅监听 main 分支的 push 事件
    ref = payload.get('ref', '')
    if ref != 'refs/heads/main':
        logger.info(f"非 main 分支推送，忽略：{ref}")
        return "忽略"

    logger.info("收到 main 分支推送，启动异步部署...")

    # 提取 commit 信息（可选）
    commit_sha = None
    commit_message = None
    if 'head_commit' in payload:
        commit_sha = payload['head_commit'].get('id', 'unknown')
        commit_message = payload['head_commit'].get('message', 'unknown')

    # 启动异步部署任务
    deploy_thread = threading.Thread(
        target=async_deploy,
        args=(commit_sha, commit_message),
        daemon=True
    )
    deploy_thread.start()

    # 立即返回，避免 webhook 超时
    return "部署任务已启动", 202


if __name__ == '__main__':
    # 仅用于开发环境，生产环境请使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=9000, debug=DEBUG)
