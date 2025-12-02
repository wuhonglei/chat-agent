from github_webhook import Webhook
from flask import Flask
import subprocess
import os
import threading
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from email_notifier import email_notifier

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
LOG_DIR = os.getenv('LOG_DIR', './logs')  # 日志文件存储目录

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)


def run_command(cmd, cwd):
    """执行命令并实时打印日志

    Args:
        cmd: 要执行的命令
        cwd: 工作目录
    """
    try:
        log_msg = f"执行命令：{cmd}\n工作目录：{cwd}"
        logger.info(log_msg)

        # 使用 Popen 实时读取输出
        process = subprocess.Popen(
            cmd, cwd=cwd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 将 stderr 合并到 stdout
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )

        # 实时读取并打印输出（loguru 会自动写入已配置的文件）
        for line in process.stdout:
            stripped_line = line.rstrip()
            logger.info(stripped_line)

        # 等待进程完成
        process.wait()

        if process.returncode == 0:
            success_msg = f"执行成功：{cmd}"
            logger.info(success_msg)
            return True
        else:
            error_msg = f"执行失败：{cmd}\n退出代码：{process.returncode}"
            logger.error(error_msg)
            return False

    except FileNotFoundError as e:
        error_msg = f"执行失败：{cmd}\n文件未找到：{e}"
        logger.error(error_msg)
        return False
    except Exception as e:
        error_msg = f"执行失败：{cmd}\n未知错误：{e}"
        logger.error(error_msg)
        return False


def async_deploy(commit_sha=None, commit_message=None, log_file_path=None):
    """异步执行部署任务

    Args:
        commit_sha: commit SHA
        commit_message: commit 消息
        log_file_path: 日志文件路径
    """
    # 为本次部署添加独立的日志文件 sink
    sink_id = None
    if log_file_path:
        try:
            # 添加文件 sink，使用自定义格式
            sink_id = logger.add(
                log_file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                level="DEBUG",
                encoding="utf-8",
                enqueue=False,  # 单线程不需要队列
                rotation=None,  # 不自动轮转
                retention=None,  # 不自动删除
            )
            logger.info("=" * 50)
            logger.info("=== 部署任务开始 ===")
            logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Commit SHA: {commit_sha or 'N/A'}")
            logger.info(f"Commit Message: {commit_message or 'N/A'}")
            logger.info(f"仓库路径: {REPO_PATH}")
            logger.info(f"部署脚本: {DEPLOY_SCRIPT}")
            logger.info("=" * 50)
        except Exception as e:
            logger.warning(f"无法创建日志文件 {log_file_path}: {e}")

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
            error_msg = (
                f"异步部署失败：deploy.sh 执行出错 ({DEPLOY_SCRIPT})"
            )
            logger.error(error_msg)
            return

        logger.info("异步部署成功完成！")
        logger.info("=== 部署任务结束 ===")

        # 发送成功通知邮件（附带日志文件）
        email_notifier.send_deploy_success_notification(
            repo_path=REPO_PATH,
            deploy_script=DEPLOY_SCRIPT,
            commit_sha=commit_sha,
            commit_message=commit_message,
            log_file_path=log_file_path
        )

    except Exception as e:
        error_msg = f"异步部署出现异常：{e}"
        logger.error(error_msg)
        logger.error("=== 部署任务异常结束 ===")

        # 发送失败通知邮件（附带日志文件）
        email_notifier.send_deploy_failed_notification(
            repo_path=REPO_PATH,
            deploy_script=DEPLOY_SCRIPT,
            commit_sha=commit_sha,
            commit_message=commit_message,
            error_message=str(e),
            log_file_path=log_file_path
        )
    finally:
        # 移除本次部署的日志文件 sink
        if sink_id is not None:
            try:
                logger.remove(sink_id)
            except Exception as e:
                logger.warning(f"移除日志 sink 失败：{e}")


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

    # 为本次部署创建唯一的日志文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if commit_sha and commit_sha != 'unknown':
        commit_short = commit_sha[:7]
    else:
        commit_short = 'unknown'
    log_filename = f"deploy_{timestamp}_{commit_short}.log"
    log_file_path = os.path.join(LOG_DIR, log_filename)

    logger.info(f"本次部署日志文件：{log_file_path}")

    # 启动异步部署任务
    deploy_thread = threading.Thread(
        target=async_deploy,
        args=(commit_sha, commit_message, log_file_path),
        daemon=True
    )
    deploy_thread.start()

    # 实际返回是 github_webhook 内部处理(返回内容是 return "", 204)
    return "", 204


if __name__ == '__main__':
    # 仅用于开发环境，生产环境请使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=9000, debug=DEBUG)
