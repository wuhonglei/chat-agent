"""短信相关纯函数与同步发送封装"""

from app.schemas.config import SmsConfig


def format_phone_e164(phone: str) -> str:
    """将手机号格式化为 E.164（+86xxx）"""
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return phone
    if digits.startswith("86") and len(digits) == 11:
        return "+" + digits
    if len(digits) == 11:
        return "+86" + digits
    return "+" + digits if not phone.strip().startswith("+") else phone


def send_sms_sync(phone_e164: str, code: str, sms_config: SmsConfig) -> None:
    """同步调用腾讯云短信 SDK 发送短信。"""
    from tencentcloud.common import credential
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
        TencentCloudSDKException,
    )
    from tencentcloud.sms.v20210111 import models, sms_client

    cred = credential.Credential(
        sms_config.tencentcloud_secret_id,
        sms_config.tencentcloud_secret_key,
    )
    client = sms_client.SmsClient(cred, sms_config.region)
    req = models.SendSmsRequest()
    req.SmsSdkAppId = sms_config.sms_sdk_app_id
    req.SignName = sms_config.sign_name
    req.TemplateId = sms_config.template_id
    req.TemplateParamSet = [code]  # 模板变量仅为验证码
    req.PhoneNumberSet = [phone_e164]
    resp = client.SendSms(req)
    if not resp.SendStatusSet:
        raise TencentCloudSDKException("SendSms", "No SendStatusSet in response", "")
    status = resp.SendStatusSet[0]
    if status.Code != "Ok":
        raise TencentCloudSDKException(
            "SendSms", status.Code or "Unknown", status.Message or ""
        )
