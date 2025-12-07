import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from loguru import logger
from .template import success_template, failed_template


class EmailNotifier:
    """邮件通知类"""

    def __init__(self):
        """初始化邮件配置"""
        self.smtp_host = os.getenv('SMTP_HOST', '')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_to = os.getenv('EMAIL_TO', '')  # 多个收件人用逗号分隔
        self.email_enabled = os.getenv('EMAIL_ENABLED', 'False') == 'True'

    def _add_attachment(self, msg, attachment_path):
        """添加邮件附件

        Args:
            msg: MIMEMultipart 消息对象
            attachment_path: 附件文件路径
        """
        try:
            with open(attachment_path, 'rb') as f:
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(f.read())
            encoders.encode_base64(attachment)

            # 处理文件名：将 .log 后缀改为 .txt
            filename = os.path.basename(attachment_path)
            if filename.endswith('.log'):
                filename = filename[:-4] + '.txt'

            # 编码附件文件名（支持非 ASCII 字符）
            try:
                filename.encode('ascii')
                # 纯 ASCII 文件名，直接使用
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
            except UnicodeEncodeError:
                # 包含非 ASCII 字符，使用 RFC 2231 编码
                from urllib.parse import quote
                encoded_filename = quote(filename, safe='')
                attachment.add_header(
                    'Content-Disposition',
                    f'attachment; filename*=utf-8\'\'{encoded_filename}'
                )

            msg.attach(attachment)
            logger.info(f"已添加附件：{attachment_path}")
        except Exception as e:
            logger.warning(f"添加附件失败：{e}")

    def _close_server(self, server):
        """安全关闭 SMTP 服务器连接

        Args:
            server: SMTP 服务器对象
        """
        if not server:
            return
        try:
            server.quit()
        except Exception:
            try:
                server.close()
            except Exception:
                pass

    def send_email(self, subject, body, is_html=False,
                   attachment_path=None):
        """发送邮件通知

        Args:
            subject: 邮件主题
            body: 邮件正文
            is_html: 是否为 HTML 格式
            attachment_path: 附件文件路径（可选）
        """
        if not self.email_enabled:
            logger.info("邮件功能未启用，跳过发送")
            return False

        required_config = [
            self.smtp_host, self.smtp_user, self.smtp_password,
            self.email_from, self.email_to
        ]
        if not all(required_config):
            logger.warning("邮件配置不完整，跳过发送")
            return False

        try:
            # 创建邮件消息（统一使用 'mixed' 类型，支持正文和附件）
            msg = MIMEMultipart('mixed')
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = Header(subject, 'utf-8')

            # 添加正文
            msg.attach(MIMEText(body, 'html' if is_html else 'plain', 'utf-8'))

            # 添加附件（如果提供）
            if attachment_path and os.path.exists(attachment_path):
                self._add_attachment(msg, attachment_path)

            # 发送邮件，添加超时设置
            server = None
            try:
                server = smtplib.SMTP(
                    self.smtp_host, self.smtp_port, timeout=30
                )
                server.starttls()  # 启用 TLS
                server.login(self.smtp_user, self.smtp_password)
                # 支持多个收件人
                recipients = [email.strip()
                              for email in self.email_to.split(',')]
                message_str = msg.as_string()
                # sendmail 返回失败的收件人字典，空字典表示全部成功
                failed_recipients = server.sendmail(
                    self.email_from, recipients, message_str
                )
                if failed_recipients:
                    logger.warning(
                        f"部分收件人发送失败：{failed_recipients}"
                    )
            except smtplib.SMTPResponseException as e:
                # 检查是否为空响应异常（错误码 -1 且响应为空）
                # 可能是服务器响应异常，但邮件可能已经发送成功
                error_bytes = e.args[1] if len(e.args) > 1 else b''
                is_empty_response = (
                    e.smtp_code == -1 and
                    (not error_bytes or error_bytes.strip(b'\x00') == b'')
                )
                if is_empty_response:
                    logger.warning(
                        "SMTP 服务器响应异常（空响应），"
                        "但邮件可能已发送成功。请检查邮箱确认。"
                        f"错误：{e}"
                    )
                    return True
                raise
            finally:
                self._close_server(server)

            logger.info(f"邮件发送成功，收件人：{self.email_to}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败：{e}")
            return False

    def send_deploy_success_notification(
        self, repo_path, deploy_script, commit_sha=None,
        commit_message=None, deploy_duration=None, log_file_path=None
    ):
        """发送部署成功通知邮件"""
        subject = "部署成功通知"
        deploy_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = success_template.render(
            repo_path=repo_path,
            deploy_script=deploy_script,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deploy_time=deploy_time,
            deploy_duration=deploy_duration
        )

        return self.send_email(
            subject, body, is_html=True, attachment_path=log_file_path
        )

    def send_deploy_failed_notification(
        self, repo_path, deploy_script, commit_sha=None,
        commit_message=None, error_message=None, deploy_duration=None, log_file_path=None
    ):
        """发送部署失败通知邮件"""
        subject = "部署失败通知"
        deploy_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = failed_template.render(
            repo_path=repo_path,
            deploy_script=deploy_script,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deploy_time=deploy_time,
            error_message=error_message or '未知错误',
            deploy_duration=deploy_duration
        )

        return self.send_email(
            subject, body, is_html=True, attachment_path=log_file_path
        )


# 创建全局实例
email_notifier = EmailNotifier()
