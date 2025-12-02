import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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
            # 创建邮件消息
            msg = MIMEMultipart('alternative')
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = subject

            # 添加邮件正文
            if is_html:
                msg.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 添加附件（如果提供）
            if attachment_path and os.path.exists(attachment_path):
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment = MIMEBase('application', 'octet-stream')
                        attachment.set_payload(f.read())
                    encoders.encode_base64(attachment)
                    filename = os.path.basename(attachment_path)
                    attachment.add_header(
                        'Content-Disposition',
                        f'attachment; filename={filename}'
                    )
                    msg.attach(attachment)
                    logger.info(f"已添加附件：{attachment_path}")
                except Exception as e:
                    logger.warning(f"添加附件失败：{e}")

            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # 启用 TLS
                server.login(self.smtp_user, self.smtp_password)
                # 支持多个收件人
                recipients = [email.strip()
                              for email in self.email_to.split(',')]
                server.sendmail(self.email_from, recipients, msg.as_string())

            logger.info(f"邮件发送成功，收件人：{self.email_to}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败：{e}")
            return False

    def send_deploy_success_notification(
        self, repo_path, deploy_script, commit_sha=None,
        commit_message=None, log_file_path=None
    ):
        """发送部署成功通知邮件"""
        subject = "部署成功通知"
        deploy_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = success_template.render(
            repo_path=repo_path,
            deploy_script=deploy_script,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deploy_time=deploy_time
        )

        return self.send_email(
            subject, body, is_html=True, attachment_path=log_file_path
        )

    def send_deploy_failed_notification(
        self, repo_path, deploy_script, commit_sha=None,
        commit_message=None, error_message=None, log_file_path=None
    ):
        """发送部署失败通知邮件"""
        subject = "部署失败通知"
        deploy_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = failed_template.render(
            repo_path=repo_path,
            deploy_script=deploy_script,
            commit_sha=commit_sha,
            commit_message=commit_message,
            deploy_time=deploy_time
        )

        return self.send_email(
            subject, body, is_html=True, attachment_path=log_file_path
        )


# 创建全局实例
email_notifier = EmailNotifier()
