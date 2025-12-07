from github_webhook import Webhook
from flask import Flask
import subprocess
import os
import multiprocessing
import time
import signal
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

# 全局变量用于跟踪当前的部署状态
current_deploy_info = {
    'process': None,
    'start_time': None,
    'commit_sha': None,
    'log_file_path': None
}
deploy_lock = multiprocessing.Lock()


def run_command(cmd, cwd):
    """执行命令并实时打印日志

    Args:
        cmd: 要执行的命令
        cwd: 工作目录
    """
    try:
        log_msg = f"执行命令：{cmd}\n工作目录：{cwd}"
        logger.info(log_msg)

        # 使用 Popen 实时读取输出，创建新进程组以便后续管理
        process = subprocess.Popen(
            cmd, cwd=cwd, shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 将 stderr 合并到 stdout
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True,
            preexec_fn=os.setsid  # 创建新进程组
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


def terminate_previous_deploy():
    """终止之前的部署进程"""
    global current_deploy_info

    with deploy_lock:
        if current_deploy_info['process'] and current_deploy_info['process'].is_alive():
            logger.info("检测到正在进行的部署，正在强制终止...")

            try:
                # 获取进程组ID并终止整个进程组（包括子进程）
                try:
                    pgid = os.getpgid(current_deploy_info['process'].pid)
                    logger.info(f"终止进程组 {pgid}（包括子进程）")
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    # 如果进程已经不存在，直接返回
                    logger.info("进程已经不存在，无需终止")
                    return
                except Exception as e:
                    logger.warning(f"使用进程组终止失败，尝试直接终止进程：{e}")
                    # 回退到直接终止进程
                    current_deploy_info['process'].terminate()

                # 等待进程结束，最多等待5秒
                current_deploy_info['process'].join(timeout=5)

                # 如果进程还没结束，使用 SIGKILL 强制终止进程组
                if current_deploy_info['process'].is_alive():
                    try:
                        pgid = os.getpgid(current_deploy_info['process'].pid)
                        logger.warning(f"进程组 {pgid} 未在预期时间内结束，强制杀死")
                        os.killpg(pgid, signal.SIGKILL)
                        current_deploy_info['process'].join(timeout=2)
                    except Exception as e:
                        logger.warning(f"强制杀死进程组失败：{e}")
                        # 最后的回退方案：直接杀死进程
                        current_deploy_info['process'].kill()
                        current_deploy_info['process'].join(timeout=2)

            except Exception as e:
                logger.warning(f"终止部署进程时出错：{e}")

            # 记录终止信息
            if current_deploy_info['start_time']:
                duration = round(
                    time.time() - current_deploy_info['start_time'], 2)
                logger.info(f"之前的部署已被强制终止（运行时长：{duration}秒）")

            # 清理全局状态
            current_deploy_info['process'] = None
            current_deploy_info['start_time'] = None
            current_deploy_info['commit_sha'] = None
            current_deploy_info['log_file_path'] = None


def async_deploy(commit_sha=None, commit_message=None, log_file_path=None):
    """异步执行部署任务

    Args:
        commit_sha: commit SHA
        commit_message: commit 消息
        log_file_path: 日志文件路径
    """
    # 获取当前进程
    current_process = multiprocessing.current_process()

    # 记录部署开始时间
    deploy_start_time = time.time()

    # 更新全局状态
    global current_deploy_info
    with deploy_lock:
        current_deploy_info['process'] = current_process
        current_deploy_info['start_time'] = deploy_start_time
        current_deploy_info['commit_sha'] = commit_sha
        current_deploy_info['log_file_path'] = log_file_path

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
            raise Exception("异步部署失败：git checkout 出错")

        # 拉取代码
        if not run_command("git pull origin main", REPO_PATH):
            logger.error("异步部署失败：git pull 出错")
            raise Exception("异步部署失败：git pull 出错")

        # 打印最新 commit 信息
        if not run_command("git log --oneline -1", REPO_PATH):
            logger.error("异步部署失败：git log 出错")
            raise Exception("异步部署失败：git log 出错")

        # 执行 deploy.sh
        if not run_command(f"bash {DEPLOY_SCRIPT}", REPO_PATH):
            error_msg = (
                f"异步部署失败：deploy.sh 执行出错 ({DEPLOY_SCRIPT})"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

        # 计算部署时长
        deploy_end_time = time.time()
        deploy_duration = round(deploy_end_time - deploy_start_time, 2)
        duration_formatted = f"{deploy_duration} 秒"

        logger.info("异步部署成功完成！")
        logger.info(f"部署总时长: {duration_formatted}")
        logger.info("=== 部署任务结束 ===")

        # 发送成功通知邮件（附带日志文件）
        email_notifier.send_deploy_success_notification(
            repo_path=REPO_PATH,
            deploy_script=DEPLOY_SCRIPT,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deploy_duration=duration_formatted,
            log_file_path=log_file_path
        )

    except Exception as e:
        # 计算部署时长（即使失败也要计算）
        deploy_end_time = time.time()
        deploy_duration = round(deploy_end_time - deploy_start_time, 2)
        duration_formatted = f"{deploy_duration} 秒"

        error_msg = f"异步部署出现异常：{e}"
        logger.error(error_msg)
        logger.error(f"部署总时长: {duration_formatted}")
        logger.error("=== 部署任务异常结束 ===")

        # 发送失败通知邮件（附带日志文件）
        email_notifier.send_deploy_failed_notification(
            repo_path=REPO_PATH,
            deploy_script=DEPLOY_SCRIPT,
            commit_sha=commit_sha,
            commit_message=commit_message,
            error_message=str(e),
            deploy_duration=duration_formatted,
            log_file_path=log_file_path
        )
    finally:
        # 移除本次部署的日志文件 sink
        if sink_id is not None:
            try:
                logger.remove(sink_id)
            except Exception as e:
                logger.warning(f"移除日志 sink 失败：{e}")

        # 清理全局状态（如果当前进程是活跃部署进程）
        with deploy_lock:
            if current_deploy_info['process'] == current_process:
                current_deploy_info['process'] = None
                current_deploy_info['start_time'] = None
                current_deploy_info['commit_sha'] = None
                current_deploy_info['log_file_path'] = None


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

    # 终止之前的部署进程（如果存在）
    terminate_previous_deploy()

    # 启动异步部署任务
    deploy_process = multiprocessing.Process(
        target=async_deploy,
        args=(commit_sha, commit_message, log_file_path)
    )
    deploy_process.start()

    # 实际返回是 github_webhook 内部处理(返回内容是 return "", 204)
    return "", 204


if __name__ == '__main__':
    # 仅用于开发环境，生产环境请使用 Gunicorn 或 uWSGI
    app.run(host='0.0.0.0', port=9000, debug=DEBUG)
