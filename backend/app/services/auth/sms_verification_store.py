"""短信验证码 Redis 存储"""

from app.core.redis import get_redis
from app.schemas.auth import SmsVerificationEntry


class SmsVerificationStore:
    """将短信验证码保存到 Redis，供多 worker 共享。"""

    KEY_PREFIX = "sms:verify:"
    TTL_SECONDS = 300

    def _key(self, verification_id: str) -> str:
        return f"{self.KEY_PREFIX}{verification_id}"

    async def save(self, verification_id: str, *, code: str, phone: str) -> None:
        entry = SmsVerificationEntry(code=code, phone=phone)
        await get_redis().set(
            self._key(verification_id),
            entry.model_dump_json(),
            ex=self.TTL_SECONDS,
        )

    async def get(self, verification_id: str) -> SmsVerificationEntry | None:
        raw = await get_redis().get(self._key(verification_id))
        if raw is None:
            return None
        return SmsVerificationEntry.model_validate_json(raw)

    async def delete(self, verification_id: str) -> None:
        await get_redis().delete(self._key(verification_id))
