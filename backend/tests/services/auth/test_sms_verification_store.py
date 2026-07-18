"""短信验证码 Redis 存储与登录校验单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.auth import SmsLoginRequest, SmsVerificationEntry
from app.services.auth.sms_service import SmsService
from app.services.auth.sms_verification_store import SmsVerificationStore

_VERIFICATION_ID = "11111111-2222-4333-8444-555555555555"
_PHONE = "13800138000"
_CODE = "123456"
_ENTRY = SmsVerificationEntry(code=_CODE, phone=_PHONE)


@pytest.fixture
def redis_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def store(redis_mock: AsyncMock) -> SmsVerificationStore:
    with patch(
        "app.services.auth.sms_verification_store.get_redis",
        return_value=redis_mock,
    ):
        yield SmsVerificationStore()


@pytest.mark.asyncio
async def test_save_writes_key_with_ttl(store: SmsVerificationStore, redis_mock: AsyncMock) -> None:
    await store.save(_VERIFICATION_ID, code=_CODE, phone=_PHONE)

    redis_mock.set.assert_awaited_once_with(
        f"sms:verify:{_VERIFICATION_ID}",
        _ENTRY.model_dump_json(),
        ex=SmsVerificationStore.TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_get_returns_entry_when_present(
    store: SmsVerificationStore, redis_mock: AsyncMock
) -> None:
    redis_mock.get.return_value = _ENTRY.model_dump_json()

    entry = await store.get(_VERIFICATION_ID)

    assert entry == _ENTRY
    redis_mock.get.assert_awaited_once_with(f"sms:verify:{_VERIFICATION_ID}")


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(
    store: SmsVerificationStore, redis_mock: AsyncMock
) -> None:
    redis_mock.get.return_value = None

    assert await store.get(_VERIFICATION_ID) is None


@pytest.mark.asyncio
async def test_delete_removes_key(store: SmsVerificationStore, redis_mock: AsyncMock) -> None:
    await store.delete(_VERIFICATION_ID)

    redis_mock.delete.assert_awaited_once_with(f"sms:verify:{_VERIFICATION_ID}")


def _login_request(*, code: str = _CODE, phone: str = _PHONE) -> SmsLoginRequest:
    return SmsLoginRequest(
        verification_id=_VERIFICATION_ID,
        verification_code=code,
        phone_number=phone,
    )


@pytest.mark.asyncio
async def test_sms_login_wrong_code_does_not_delete() -> None:
    store_mock = AsyncMock()
    store_mock.get.return_value = _ENTRY

    with patch("app.services.auth.sms_service._store", store_mock):
        with pytest.raises(HTTPException) as exc_info:
            await SmsService.sms_login(_login_request(code="000000"), MagicMock())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "验证码错误"
    store_mock.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_sms_login_success_deletes_verification() -> None:
    store_mock = AsyncMock()
    store_mock.get.return_value = _ENTRY
    user_mock = MagicMock()
    user_service_mock = MagicMock()
    user_service_mock.get_or_create_user_by_phone.return_value = user_mock

    with patch("app.services.auth.sms_service._store", store_mock):
        with patch(
            "app.services.auth.sms_service.UserDbService",
            return_value=user_service_mock,
        ):
            user = await SmsService.sms_login(_login_request(), MagicMock())

    assert user is user_mock
    store_mock.delete.assert_awaited_once_with(_VERIFICATION_ID)
    user_service_mock.get_or_create_user_by_phone.assert_called_once_with(_PHONE)


@pytest.mark.asyncio
async def test_sms_login_missing_verification_returns_400() -> None:
    store_mock = AsyncMock()
    store_mock.get.return_value = None

    with patch("app.services.auth.sms_service._store", store_mock):
        with pytest.raises(HTTPException) as exc_info:
            await SmsService.sms_login(_login_request(), MagicMock())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "验证码已过期或无效"
    store_mock.delete.assert_not_awaited()
